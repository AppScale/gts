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
from appscale.datastore.fdb.cache import DirectoryCache
from appscale.datastore.fdb.codecs import decode_str, TransactionID
from appscale.datastore.fdb.data import DataManager, VersionEntry
from appscale.datastore.fdb.gc import GarbageCollector
from appscale.datastore.fdb.indexes import (
  get_order_info, IndexManager, KEY_PROP)
from appscale.datastore.fdb.transactions import TransactionManager
from appscale.datastore.fdb.utils import (
  ABSENT_VERSION, fdb, FDBErrorCodes, next_entity_version, DS_ROOT,
  ScatteredAllocator, TornadoFDB)

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
    directory_cache = DirectoryCache(self._db, self._tornado_fdb, ds_dir)
    directory_cache.initialize()

    self._data_manager = DataManager(self._tornado_fdb, directory_cache)
    self.index_manager = IndexManager(
      self._db, self._tornado_fdb, self._data_manager, directory_cache)
    self._tx_manager = TransactionManager(
      self._db, self._tornado_fdb, directory_cache)
    self._gc = GarbageCollector(
      self._db, self._tornado_fdb, self._data_manager, self.index_manager,
      self._tx_manager, directory_cache)
    self._gc.start()

  @gen.coroutine
  def dynamic_put(self, project_id, put_request, put_response, retries=5):
    # logger.debug(u'put_request:\n{}'.format(put_request))
    project_id = decode_str(project_id)
    # TODO: Enforce max key length (100 elements).
    # Enforce max element size (1500 bytes).
    # Enforce max kind size (1500 bytes).
    # Enforce key name regex (reserved names match __.*__).

    if put_request.auto_id_policy() != put_request.CURRENT:
      raise BadRequest(u'Sequential allocator is not implemented')

    tr = self._db.create_transaction()

    if put_request.has_transaction():
      yield self._tx_manager.log_puts(tr, project_id, put_request)
      writes = [(VersionEntry.from_key(entity.key()),
                 VersionEntry.from_key(entity.key()))
                for entity in put_request.entity_list()]
    else:
      futures = []
      for entity in put_request.entity_list():
        futures.append(self._upsert(tr, entity))

      writes = yield futures

    old_entries = [old_entry for old_entry, _ in writes if old_entry.present]
    versionstamp_future = None
    if old_entries:
      versionstamp_future = tr.get_versionstamp()

    try:
      yield self._tornado_fdb.commit(tr, convert_exceptions=False)
    except fdb.FDBError as fdb_error:
      if fdb_error.code != FDBErrorCodes.NOT_COMMITTED:
        raise InternalError(fdb_error.description)

      retries -= 1
      if retries < 0:
        raise InternalError(fdb_error.description)

      yield self.dynamic_put(project_id, put_request, put_response, retries)
      return

    if old_entries:
      self._gc.clear_later(old_entries, versionstamp_future.wait().value)

    for _, new_entry in writes:
      put_response.add_key().CopyFrom(new_entry.key)
      if new_entry.version != ABSENT_VERSION:
        put_response.add_version(new_entry.version)

    #logger.debug('put_response:\n{}'.format(put_response))

  @gen.coroutine
  def dynamic_get(self, project_id, get_request, get_response):
    logger.debug(u'get_request:\n{}'.format(get_request))
    project_id = decode_str(project_id)
    tr = self._db.create_transaction()

    read_versionstamp = None
    if get_request.has_transaction():
      yield self._tx_manager.log_lookups(tr, project_id, get_request)

      # Ensure the GC hasn't cleaned up an entity written after the tx start.
      safe_read_stamps = yield [self._gc.safe_read_versionstamp(tr, key)
                                for key in get_request.key_list()]
      safe_read_stamps = [vs for vs in safe_read_stamps if vs is not None]
      read_versionstamp = TransactionID.decode(
        get_request.transaction().handle())[1]
      if any(safe_versionstamp > read_versionstamp
             for safe_versionstamp in safe_read_stamps):
        raise BadRequest(u'The specified transaction has expired')

    futures = []
    for key in get_request.key_list():
      futures.append(self._data_manager.get_latest(tr, key, read_versionstamp,
                                                   snapshot=True))

    version_entries = yield futures

    # If this read is in a transaction, logging the RPC is a mutation.
    yield self._tornado_fdb.commit(tr)

    for entry in version_entries:
      response_entity = get_response.add_entity()
      response_entity.set_version(entry.version)
      if entry.has_entity:
        response_entity.mutable_entity().MergeFrom(entry.decoded)
      else:
        response_entity.mutable_key().MergeFrom(entry.key)

    logger.debug(u'fetched paths: {}'.format(
      [entry.path for entry in version_entries if entry.has_entity]))

  @gen.coroutine
  def dynamic_delete(self, project_id, delete_request, retries=5):
    logger.debug(u'delete_request:\n{}'.format(delete_request))
    project_id = decode_str(project_id)
    tr = self._db.create_transaction()

    if delete_request.has_transaction():
      yield self._tx_manager.log_deletes(tr, project_id, delete_request)
      deletes = [(VersionEntry.from_key(key), None)
                 for key in delete_request.key_list()]
    else:
      futures = []
      for key in delete_request.key_list():
        futures.append(self._delete(tr, key))

      deletes = yield futures

    old_entries = [old_entry for old_entry, _ in deletes if old_entry.present]
    versionstamp_future = None
    if old_entries:
      versionstamp_future = tr.get_versionstamp()

    try:
      yield self._tornado_fdb.commit(tr, convert_exceptions=False)
    except fdb.FDBError as fdb_error:
      if fdb_error.code != FDBErrorCodes.NOT_COMMITTED:
        raise InternalError(fdb_error.description)

      retries -= 1
      if retries < 0:
        raise InternalError(fdb_error.description)

      yield self.dynamic_delete(project_id, delete_request, retries)
      return

    if old_entries:
      self._gc.clear_later(old_entries, versionstamp_future.wait().value)

    # TODO: Once the Cassandra backend is removed, populate a delete response.
    for old_entry, new_version in deletes:
      logger.debug(u'new_version: {}'.format(new_version))

  @gen.coroutine
  def _dynamic_run_query(self, query, query_result):
    logger.debug(u'query: {}'.format(query))
    project_id = decode_str(query.app())
    tr = self._db.create_transaction()
    read_versionstamp = None
    if query.has_transaction():
      yield self._tx_manager.log_query(tr, project_id, query)

      # Ensure the GC hasn't cleaned up an entity written after the tx start.
      safe_versionstamp = yield self._gc.safe_read_versionstamp(
        tr, query.ancestor())
      read_versionstamp = TransactionID.decode(query.transaction().handle())[1]
      if (safe_versionstamp is not None and
          safe_versionstamp > read_versionstamp):
        raise BadRequest(u'The specified transaction has expired')

    fetch_data = self.index_manager.include_data(query)
    rpc_limit, check_more_results = self.index_manager.rpc_limit(query)

    iterator = yield self.index_manager.get_iterator(
      tr, query, read_versionstamp)
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
    txid = yield self._tx_manager.create(project_id)
    logger.debug(u'Started new transaction: {}:{}'.format(project_id, txid))
    raise gen.Return(txid)

  @gen.coroutine
  def apply_txn_changes(self, project_id, txid, retries=5):
    logger.debug(u'Applying {}:{}'.format(project_id, txid))
    project_id = decode_str(project_id)
    tr = self._db.create_transaction()
    read_versionstamp = TransactionID.decode(txid)[1]
    lookups, queried_groups, mutations = yield self._tx_manager.get_metadata(
      tr, project_id, txid)

    try:
      old_entries = yield self._apply_mutations(
        tr, project_id, queried_groups, mutations, lookups, read_versionstamp)
    finally:
      yield self._tx_manager.delete(tr, project_id, txid)

    versionstamp_future = None
    if old_entries:
      versionstamp_future = tr.get_versionstamp()

    try:
      yield self._tornado_fdb.commit(tr)
    except fdb.FDBError as fdb_error:
      if fdb_error.code != FDBErrorCodes.NOT_COMMITTED:
        raise InternalError(fdb_error.description)

      retries -= 1
      if retries < 0:
        raise InternalError(fdb_error.description)

      yield self.apply_txn_changes(project_id, txid, retries)
      return

    if old_entries:
      self._gc.clear_later(old_entries, versionstamp_future.wait().value)

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
      # Avoid mutating the object given.
      new_entity = entity_pb.EntityProto()
      new_entity.CopyFrom(entity)
      entity = new_entity
      last_element = entity.key().path().element(-1)
      last_element.set_id(self._scattered_allocator.get_id())

    old_entry = yield self._data_manager.get_latest(tr, entity.key())

    # If the datastore chose an ID, don't overwrite existing data.
    if auto_id and old_entry.present:
      self._scattered_allocator.invalidate()
      raise InternalError(u'The datastore chose an existing ID')

    new_version = next_entity_version(old_entry.version)
    yield self._data_manager.put(
      tr, entity.key(), new_version, entity.Encode())
    yield self.index_manager.put_entries(tr, old_entry, entity)
    if old_entry.present:
      yield self._gc.index_deleted_version(tr, old_entry)

    new_entry = VersionEntry.from_key(entity.key())
    new_entry.version = new_version
    raise gen.Return((old_entry, new_entry))

  @gen.coroutine
  def _delete(self, tr, key):
    old_entry = yield self._data_manager.get_latest(tr, key)

    if not old_entry.present:
      raise gen.Return((old_entry, None))

    new_version = next_entity_version(old_entry.version)
    yield self._data_manager.put(tr, key, new_version, b'')
    yield self.index_manager.put_entries(tr, old_entry, new_entity=None)
    if old_entry.present:
      yield self._gc.index_deleted_version(tr, old_entry)

    raise gen.Return((old_entry, new_version))

  @gen.coroutine
  def _apply_mutations(self, tr, project_id, queried_groups, mutations,
                       lookups, read_versionstamp):
    # TODO: Check if transactional tasks count as a side effect.
    if not mutations:
      raise gen.Return([])

    group_update_futures = [
      self._data_manager.last_group_versionstamp(
        tr, project_id, namespace, group_path)
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
    if any(commit_vs > read_versionstamp for commit_vs in group_updates):
      raise ConcurrentModificationException(
        u'A queried group was modified after this transaction was started.')

    version_entries = yield [futures[key.Encode()] for key in lookups]
    if any(entry.present and entry.commit_versionstamp > read_versionstamp
           for entry in version_entries):
      raise ConcurrentModificationException(
        u'An entity was modified after this transaction was started.')

    mutated_groups = set()
    # Apply mutations.
    old_entries = []
    for mutation in mutations:
      op = 'delete' if isinstance(mutation, entity_pb.Reference) else 'put'
      key = mutation if op == 'delete' else mutation.key()
      encoded_key = key.Encode()
      mutated_groups.add(encoded_key)
      # TODO: Check if this constraint is still needed.
      if len(mutated_groups) > 25:
        raise BadRequest(u'Too many entity groups modified in transaction')

      old_entry = yield futures[encoded_key]
      new_version = next_entity_version(old_entry.version)
      new_encoded = mutation.Encode() if op == 'put' else b''
      yield self._data_manager.put(tr, key, new_version, new_encoded)
      new_entity = mutation if op == 'put' else None
      yield self.index_manager.put_entries(tr, old_entry, new_entity)
      if old_entry.present:
        yield self._gc.index_deleted_version(tr, old_entry)
        old_entries.append(old_entry)

    raise gen.Return(old_entries)
