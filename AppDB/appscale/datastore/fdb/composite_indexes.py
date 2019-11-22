import logging
import random
import sys
import uuid
from collections import namedtuple

import monotonic
from tornado import gen
from tornado.ioloop import IOLoop

from appscale.common.datastore_index import DatastoreIndex
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.dbconstants import InternalError
from appscale.datastore.fdb.cache import (
  current_metadata_version, ensure_metadata_key)
from appscale.datastore.fdb.codecs import decode_str
from appscale.datastore.fdb.index_directories import CompositeIndex, KindIndex
from appscale.datastore.fdb.polling_lock import PollingLock
from appscale.datastore.fdb.utils import fdb, MAX_FDB_TX_DURATION, ResultIterator

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb

logger = logging.getLogger(__name__)

# Though there is only one metadata version at any given time, it can be
# expensive to fetch definitions for all projects when a request only needs
# definitions for a single project. Therefore, the metadata version is cached
# alongside the index definitions for each project.
ProjectDefinitions = namedtuple('ProjectDefinitions',
                                ['version', 'definitions'])


class IndexMetadataDirectory(object):
  DIR_NAME = u'index-definitions'

  __slots__ = ['directory']

  def __init__(self, directory):
    self.directory = directory

  @classmethod
  def directory_path(cls, project_id):
    return project_id, cls.DIR_NAME

  def encode_key(self, index_id):
    if index_id is None:
      raise InternalError(u'Index definition must have an assigned ID')

    return self.directory.pack((index_id,))

  def encode(self, definition):
    return self.encode_key(definition.id), definition.to_pb().Encode()

  def decode(self, kvs):
    return tuple(DatastoreIndex.from_pb(entity_pb.CompositeIndex(kv.value))
                 for kv in kvs)

  def get_slice(self):
    return self.directory.range()


class CompositeIndexManager(object):
  _LOCK_KEY = u'composite-index-manager-lock'

  _REBUILD_TRIGGER_KEY = u'rebuild-trigger'

  def __init__(self, db, tornado_fdb, data_manager, directory_cache):
    self._db = db
    self._tornado_fdb = tornado_fdb
    self._data_manager = data_manager
    self._directory_cache = directory_cache
    self._trigger_key = None

    # By project ID
    self._cache = {}

    lock_key = self._directory_cache.root_dir.pack((self._LOCK_KEY,))
    self._lock = PollingLock(self._db, self._tornado_fdb, lock_key)

  def start(self):
    """ Starts the garbage collection work. """
    ensure_metadata_key(self._db)
    self._trigger_key = self._directory_cache.root_dir.pack(
      (self._REBUILD_TRIGGER_KEY,))
    self._lock.start()
    IOLoop.current().spawn_callback(self._build_indexes)

  @gen.coroutine
  def get_definitions(self, tr, project_id):
    """ Fetches index definitions for a given project. """
    current_version = yield current_metadata_version(tr, self._tornado_fdb)
    cached_definitions = self._cache.get(
      project_id, ProjectDefinitions(None, ()))
    if current_version != cached_definitions.version:
      directory = yield self._get_directory(tr, project_id)
      results = yield ResultIterator(tr, self._tornado_fdb,
                                     directory.get_slice()).list()
      self._cache[project_id] = ProjectDefinitions(
        current_version, directory.decode(results))

    raise gen.Return(self._cache[project_id].definitions)

  @gen.coroutine
  def merge(self, tr, project_id, new_indexes):
    """
    Adds new indexes to a project. Existing indexes that match are ignored.
    """
    existing_indexes = yield self.get_definitions(tr, project_id)

    # Disregard index entries that already exist.
    existing_index_defs = {index.encoded_def for index in existing_indexes}
    new_indexes = [index for index in new_indexes
                   if index.encoded_def not in existing_index_defs]

    if not new_indexes:
      return

    # Assign each new index an ID and store it.
    directory = yield self._get_directory(tr, project_id)
    for new_index in new_indexes:
      if new_index.id is None:
        # The ID must be a positive number that fits in a signed 64-bit int.
        new_index.id = uuid.uuid1().int >> 65

      key, value = directory.encode(new_index)
      tr[key] = value

    self._mark_schema_change(tr)

  @gen.coroutine
  def update_composite_index(self, project_id, index_pb, cursor=(None, None)):
    start_ns, start_key = cursor
    project_id = decode_str(project_id)
    kind = decode_str(index_pb.definition().entity_type())
    tr = self._db.create_transaction()
    deadline = monotonic.monotonic() + MAX_FDB_TX_DURATION - 1
    kind_indexes = yield self._indexes_for_kind(tr, project_id, kind)
    for kind_index in kind_indexes:
      if start_ns is not None and kind_index.namespace < start_ns:
        continue

      composite_path = CompositeIndex.directory_path(
        project_id, index_pb.id(), kind_index.namespace)
      composite_dir = yield self._directory_cache.get(tr, composite_path)
      order_info = tuple(
        (decode_str(prop.name()), prop.direction())
        for prop in index_pb.definition().property_list())
      composite_index = CompositeIndex(
        composite_dir, kind, index_pb.definition().ancestor(), order_info)

      logger.info(u'Backfilling {}'.format(composite_index))
      remaining_range = kind_index.directory.range()
      if start_key is not None:
        remaining_range = slice(
          fdb.KeySelector.first_greater_than(start_key), remaining_range.stop)
        start_key = None

      result_iterator = ResultIterator(tr, self._tornado_fdb, remaining_range)
      while True:
        results, more_results = yield result_iterator.next_page()
        index_entries = [kind_index.decode(result) for result in results]
        version_entries = yield [self._data_manager.get_entry(tr, entry)
                                 for entry in index_entries]
        for index_entry, version_entry in zip(index_entries, version_entries):
          new_keys = composite_index.encode_keys(
            version_entry.decoded.property_list(), version_entry.path,
            version_entry.commit_versionstamp)
          for new_key in new_keys:
            tr[new_key] = index_entry.deleted_versionstamp or b''

        if not more_results:
          logger.info(u'Finished backfilling {}'.format(composite_index))
          break

        if monotonic.monotonic() > deadline:
          try:
            yield self._tornado_fdb.commit(tr)
            cursor = (kind_index.namespace, results[-1].key)
          except fdb.FDBError as fdb_error:
            logger.warning(u'Error while updating index: {}'.format(fdb_error))
            tr.on_error(fdb_error).wait()

          yield self.update_composite_index(project_id, index_pb, cursor)
          return

    yield self._tornado_fdb.commit(tr)

    tr = self._db.create_transaction()
    metadata_dir = yield self._get_directory(tr, project_id)
    current_definition = yield self._tornado_fdb.get(
      tr, metadata_dir.encode_key(index_pb.id()))
    if not current_definition.present():
      return

    index = DatastoreIndex.from_pb(
      entity_pb.CompositeIndex(current_definition.value))
    index.ready = True
    key, value = metadata_dir.encode(index)
    tr[key] = value
    self._mark_schema_change(tr)

    yield self._tornado_fdb.commit(tr)
    logger.info(u'{} is ready'.format(index))

  @gen.coroutine
  def _build_indexes(self):
    while True:
      try:
        yield self._lock.acquire()
        tr = self._db.create_transaction()

        # TODO: This can be made async.
        project_ids = self._directory_cache.root_dir.list(tr)
        project_definitions = yield [self.get_definitions(tr, project_id)
                                     for project_id in project_ids]
        to_rebuild = None
        for project_id, definitions in zip(project_ids, project_definitions):
          to_rebuild = next((definition for definition in definitions
                             if not definition.ready), None)
          if to_rebuild is not None:
            break

        if to_rebuild is None:
          watch_future = self._tornado_fdb.watch(tr, self._trigger_key)
          yield self._tornado_fdb.commit(tr)
          yield watch_future
          continue

        yield self.update_composite_index(to_rebuild.project_id,
                                          to_rebuild.to_pb())
      except Exception:
        logger.exception(u'Unexpected error while rebuilding indexes')
        yield gen.sleep(random.random() * 20)

  @gen.coroutine
  def _indexes_for_kind(self, tr, project_id, kind):
    section_path = KindIndex.section_path(project_id)
    section_dir = yield self._directory_cache.get(tr, section_path)
    # TODO: This can be made async.
    try:
      namespaces = section_dir.list(tr)
    except ValueError:
      # There are no kind indexes that this transaction can see.
      raise gen.Return([])

    indexes = []
    for namespace in namespaces:
      ns_dir = section_dir.open(tr, (namespace,))
      try:
        kind_dir = ns_dir.open(tr, (kind,))
      except ValueError:
        continue

      indexes.append(KindIndex(kind_dir))

    raise gen.Return(indexes)

  def _mark_schema_change(self, tr):
    # Notify leader that at least one index needs to be rebuilt.
    tr.set_versionstamped_value(self._trigger_key, b'\x00' * 14)
    self._directory_cache.invalidate(tr)

  @gen.coroutine
  def _get_directory(self, tr, project_id):
    path = IndexMetadataDirectory.directory_path(project_id)
    directory = yield self._directory_cache.get(tr, path)
    raise gen.Return(IndexMetadataDirectory(directory))
