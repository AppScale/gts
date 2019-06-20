"""
A datastore implementation that uses FoundationDB.

All datastore state is split between multiple FoundationDB directories. All of
the state for a given project is stored in (appscale, datastore, <project-id>).
Within each project directory, there is a directory for each of the following:

data: encoded entity data
indexes: entity key references by property values
transactions: transaction metadata

See each submodule for more implementation details.
"""
import logging
import sys

from tornado import gen
from tornado.ioloop import IOLoop

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.dbconstants import (
  BadRequest, ConcurrentModificationException, InternalError)
from appscale.datastore.fdb.cache import ProjectCache
from appscale.datastore.fdb.codecs import decode_str, encode_read_vs
from appscale.datastore.fdb.data import DataManager
from appscale.datastore.fdb.gc import GarbageCollector
from appscale.datastore.fdb.indexes import (
  get_order_info, IndexManager, KEY_PROP)
from appscale.datastore.fdb.transactions import TransactionManager
from appscale.datastore.fdb.utils import (
  fdb, next_entity_version, DS_ROOT, ScatteredAllocator, TornadoFDB)

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb

logger = logging.getLogger(__name__)


class FDBDatastore(object):
  """ A datastore implementation that uses FoundationDB. """

  def __init__(self):
    self.index_manager = None
    self._data_manager = None
    self._db = None
    self._scattered_allocator = ScatteredAllocator()
    self._tornado_fdb = None
    self._tx_manager = None
    self._gc = None

  def start(self):
    self._db = fdb.open()
    self._tornado_fdb = TornadoFDB(IOLoop.current())
    ds_dir = fdb.directory.create_or_open(self._db, DS_ROOT)

    project_cache = ProjectCache(self._tornado_fdb, ds_dir)
    tr = self._db.create_transaction()
    project_cache.ensure_metadata_key(tr)
    tr.commit().wait()

    self._data_manager = DataManager(self._tornado_fdb, project_cache)
    self.index_manager = IndexManager(
      self._db, self._tornado_fdb, self._data_manager, project_cache)
    self._tx_manager = TransactionManager(self._tornado_fdb, project_cache)
    self._gc = GarbageCollector(
      self._db, self._tornado_fdb, self._data_manager, self.index_manager,
      self._tx_manager, project_cache)
    self._gc.start()

  @gen.coroutine
  def dynamic_put(self, project_id, put_request, put_response):
    #logger.debug('put_request:\n{}'.format(put_request))
    project_id = decode_str(project_id)
    # TODO: Enforce max key length (100 elements).
    # Enforce max element size (1500 bytes).
    # Enforce max kind size (1500 bytes).
    # Enforce key name regex (reserved names match __.*__).

    if put_request.auto_id_policy() != put_request.CURRENT:
      raise BadRequest('Sequential allocator is not implemented')

    tr = self._db.create_transaction()

    if put_request.has_transaction():
      logger.debug('put in tx: {}'.format(put_request.transaction().handle()))
      yield self._tx_manager.log_puts(tr, project_id, put_request)
      writes = [(entity.key(), None, None, None)
                for entity in put_request.entity_list()]
    else:
      futures = []
      for entity in put_request.entity_list():
        futures.append(self._upsert(tr, entity))

      writes = yield futures

    old_entities = [(old_entity, old_vs) for _, old_entity, old_vs, _ in writes
                    if old_entity is not None]
    vs_future = None
    if old_entities:
      vs_future = tr.get_versionstamp()

    yield self._tornado_fdb.commit(tr)

    if old_entities:
      self._gc.clear_later(old_entities, vs_future.wait().value)

    for key, _, _, new_version in writes:
      put_response.add_key().CopyFrom(key)
      if new_version is not None:
        put_response.add_version(new_version)

    logger.debug('success')
    #logger.debug('put_response:\n{}'.format(put_response))

  @gen.coroutine
  def dynamic_get(self, project_id, get_request, get_response):
    logger.debug('get_request:\n{}'.format(get_request))
    project_id = decode_str(project_id)
    tr = self._db.create_transaction()

    read_vs = None
    if get_request.has_transaction():
      yield self._tx_manager.log_lookups(tr, project_id, get_request)

      # Ensure the GC hasn't cleaned up an entity written after the tx start.
      safe_read_stamps = yield [self._gc.safe_read_vs(tr, key)
                                for key in get_request.key_list()]
      safe_read_stamps = [vs for vs in safe_read_stamps if vs is not None]
      read_vs = encode_read_vs(get_request.transaction().handle())
      if any(safe_vs > read_vs for safe_vs in safe_read_stamps):
        raise BadRequest(u'The specified transaction has expired')

    futures = []
    for key in get_request.key_list():
      futures.append(self._data_manager.get_latest(tr, key, read_vs))

    version_entries = yield futures

    # If this read is in a transaction, logging the RPC is a mutation.
    yield self._tornado_fdb.commit(tr)

    for entry in version_entries:
      response_entity = get_response.add_entity()
      response_entity.mutable_key().MergeFrom(entry.key)
      response_entity.set_version(entry.version)
      if entry.complete:
        entity = entity_pb.EntityProto(entry.encoded)
        response_entity.mutable_entity().MergeFrom(entity)

    logger.debug('fetched paths: {}'.format(
      [entry.path for entry in version_entries if entry.present]))

  @gen.coroutine
  def dynamic_delete(self, project_id, delete_request):
    logger.debug('delete_request:\n{}'.format(delete_request))
    project_id = decode_str(project_id)
    tr = self._db.create_transaction()

    if delete_request.has_transaction():
      yield self._tx_manager.log_deletes(tr, project_id, delete_request)
      deletes = [(None, None, None) for _ in delete_request.key_list()]
    else:
      futures = []
      for key in delete_request.key_list():
        futures.append(self._delete(tr, key))

      deletes = yield futures

    old_entities = [(old_entity, old_vs) for old_entity, old_vs, _ in deletes
                    if old_entity is not None]
    vs_future = None
    if old_entities:
      vs_future = tr.get_versionstamp()

    yield self._tornado_fdb.commit(tr)

    if old_entities:
      self._gc.clear_later(old_entities, vs_future.wait().value)

    # TODO: Once the Cassandra backend is removed, populate a delete response.
    for old_entity, old_vs, new_version in deletes:
      logger.debug('new_version: {}'.format(new_version))

  @gen.coroutine
  def _dynamic_run_query(self, query, query_result):
    logger.debug('query: {}'.format(query))
    project_id = decode_str(query.app())
    tr = self._db.create_transaction()
    read_vs = None
    if query.has_transaction():
      yield self._tx_manager.log_query(tr, project_id, query)

      # Ensure the GC hasn't cleaned up an entity written after the tx start.
      safe_vs = yield self._gc.safe_read_vs(tr, query.ancestor())
      read_vs = encode_read_vs(query.transaction().handle())
      if safe_vs is not None and safe_vs > read_vs:
        raise BadRequest(u'The specified transaction has expired')

    fetch_data = self.index_manager.include_data(query)
    rpc_limit, check_more_results = self.index_manager.rpc_limit(query)

    iterator = yield self.index_manager.get_iterator(tr, query, read_vs)
    for prop_name in query.property_name_list():
      prop_name = decode_str(prop_name)
      if prop_name not in iterator.prop_names:
        raise BadRequest(
          u'Projections on {} are not supported'.format(prop_name))

    data_futures = [] if fetch_data else None
    unique_keys = set()
    results = []
    entries_fetched = 0
    skipped_results = 0
    cursor = None
    while True:
      remainder = rpc_limit - entries_fetched
      iter_offset = max(query.offset() - entries_fetched, 0)
      entries, more_iterator_results = yield iterator.next_page()
      entries_fetched += len(entries)
      if not entries and more_iterator_results:
        continue

      if not entries and not more_iterator_results:
        break

      skipped_results += min(len(entries), iter_offset)
      suitable_entries = entries[iter_offset:remainder]
      if entries[:remainder]:
        cursor = entries[:remainder][-1]

      if not fetch_data and not query.keys_only():
        results.extend([entry.prop_result() for entry in suitable_entries])
        continue

      for entry in suitable_entries:
        if entry.path in unique_keys:
          continue

        unique_keys.add(entry.path)
        if fetch_data:
          data_futures.append(
            self._data_manager.get_entry(tr, entry, snapshot=True))
        else:
          results.append(entry.key_result())

      if not more_iterator_results:
        break

    if fetch_data:
      entity_results = yield data_futures
      results = [entity.encoded for entity in entity_results]
    else:
      results = [result.Encode() for result in results]

    yield self._tornado_fdb.commit(tr)

    query_result.result_list().extend(results)
    # TODO: Figure out how ndb multi queries use compiled cursors.
    if query.compile():
      ordered_props = tuple(prop_name for prop_name, _ in get_order_info(query)
                            if prop_name != KEY_PROP)
      mutable_cursor = query_result.mutable_compiled_cursor()
      if cursor is not None:
        mutable_cursor.MergeFrom(cursor.cursor_result(ordered_props))

    more_results = check_more_results and entries_fetched > rpc_limit
    query_result.set_more_results(more_results)

    if skipped_results:
      query_result.set_skipped_results(skipped_results)

    if query.keys_only():
      query_result.set_keys_only(True)

    logger.debug(u'{} results'.format(len(query_result.result_list())))

  @gen.coroutine
  def setup_transaction(self, project_id, is_xg):
    project_id = decode_str(project_id)
    tr = self._db.create_transaction()
    txid = yield self._tx_manager.create(tr, project_id)
    logger.debug(u'Started new transaction: {}:{}'.format(project_id, txid))
    yield self._tornado_fdb.commit(tr)
    raise gen.Return(txid)

  @gen.coroutine
  def apply_txn_changes(self, project_id, txid):
    logger.debug(u'Applying {}:{}'.format(project_id, txid))
    project_id = decode_str(project_id)
    tr = self._db.create_transaction()
    read_vs = encode_read_vs(txid)
    lookups, queried_groups, mutations = yield self._tx_manager.get_metadata(
      tr, project_id, txid)

    try:
      old_entities = yield self._apply_mutations(
        tr, project_id, queried_groups, mutations, lookups, read_vs)
    finally:
      yield self._tx_manager.delete(tr, project_id, txid)

    vs_future = None
    if old_entities:
      vs_future = tr.get_versionstamp()

    yield self._tornado_fdb.commit(tr)

    if old_entities:
      old_decoded = [entity.decoded for entity in old_entities]
      self._gc.clear_later(old_decoded, vs_future.wait().value)

    logger.debug(u'Finished applying {}:{}'.format(project_id, txid))

  @gen.coroutine
  def rollback_transaction(self, project_id, txid):
    project_id = decode_str(project_id)
    logger.debug(u'Rolling back {}:{}'.format(project_id, txid))

    tr = self._db.create_transaction()
    yield self._tx_manager.delete(tr, project_id, txid)
    yield self._tornado_fdb.commit(tr)

  @gen.coroutine
  def update_composite_index(self, project_id, index):
    project_id = decode_str(project_id)
    yield self.index_manager.update_composite_index(project_id, index)

  @gen.coroutine
  def _upsert(self, tr, entity):
    last_element = entity.key().path().element(-1)
    auto_id = False
    if not last_element.has_name():
      auto_id = not (last_element.has_id() and last_element.id() != 0)

    if auto_id:
      last_element.set_id(self._scattered_allocator.get_id())

    old_entity = yield self._data_manager.get_latest(tr, entity.key())

    # If the datastore chose an ID, don't overwrite existing data.
    if auto_id and old_entity.present:
      self._scattered_allocator.invalidate()
      raise InternalError('The datastore chose an existing ID')

    new_version = next_entity_version(old_entity.version)
    yield self._data_manager.put(
      tr, entity.key(), new_version, entity.Encode())
    yield self.index_manager.put_entries(
      tr, old_entity.decoded, old_entity.commit_vs, entity)
    if old_entity.present:
      yield self._gc.index_deleted_version(tr, old_entity)

    raise gen.Return(
      (entity.key(), old_entity, old_entity.commit_vs, new_version))

  @gen.coroutine
  def _delete(self, tr, key):
    old_entity = yield self._data_manager.get_latest(tr, key)

    if not old_entity.present:
      raise gen.Return((None, None, None))

    new_version = next_entity_version(old_entity.version)
    yield self._data_manager.put(tr, key, new_version, b'')
    yield self.index_manager.put_entries(
      tr, old_entity.decoded, old_entity.commit_vs, new_entity=None)
    if old_entity.present:
      yield self._gc.index_deleted_version(tr, old_entity)

    raise gen.Return((old_entity.decoded, old_entity.commit_vs, new_version))

  @gen.coroutine
  def _apply_mutations(self, tr, project_id, queried_groups, mutations,
                       lookups, read_vs):
    # TODO: Check if transactional tasks count as a side effect.
    if not mutations:
      raise gen.Return([])

    group_update_futures = [
      self._data_manager.last_group_vs(tr, project_id, namespace, group_path)
      for namespace, group_path in queried_groups]

    # Index keys that require a full lookup rather than a versionstamp.
    require_data = set()
    for mutation in mutations:
      key = (mutation if isinstance(mutation, entity_pb.Reference)
             else mutation.key())
      require_data.add(key.Encode())

    # Start fetching versionstamps for lookups first to invalidate sooner.
    futures = {}
    for key in lookups:
      encoded_key = key.Encode()
      futures[encoded_key] = self._data_manager.get_latest(
        tr, key, include_data=encoded_key in require_data)

    # Fetch remaining entities that were mutated.
    for mutation in mutations:
      key = (mutation if isinstance(mutation, entity_pb.Reference)
             else mutation.key())
      encoded_key = key.Encode()
      if encoded_key not in futures:
        futures[encoded_key] = self._data_manager.get_latest(tr, key)

    group_updates = yield group_update_futures
    group_updates = [vs for vs in group_updates if vs is not None]
    if any(commit_vs > read_vs for commit_vs in group_updates):
      raise ConcurrentModificationException(
        u'A queried group was modified after this transaction was started.')

    version_entries = yield [futures[key.Encode()] for key in lookups]
    if any(entry.present and entry.commit_vs > read_vs
           for entry in version_entries):
      raise ConcurrentModificationException(
        u'An entity was modified after this transaction was started.')

    # Apply mutations.
    old_entities = []
    for mutation in mutations:
      op = 'delete' if isinstance(mutation, entity_pb.Reference) else 'put'
      key = mutation if op == 'delete' else mutation.key()
      old_entity = yield futures[key.Encode()]
      if old_entity.present:
        old_entities.append(old_entity)

      new_version = next_entity_version(old_entity.version)
      new_encoded = mutation.Encode() if op == 'put' else b''
      yield self._data_manager.put(tr, key, new_version, new_encoded)
      new_entity = mutation if op == 'put' else None
      yield self.index_manager.put_entries(
        tr, old_entity.decoded, old_entity.commit_vs, new_entity)
      if old_entity.present:
        yield self._gc.index_deleted_version(tr, old_entity)

    raise gen.Return(old_entities)
