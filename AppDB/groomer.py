""" This process grooms the datastore cleaning up old state and
calculates datastore statistics. Removes tombstoned items for garbage
collection.
"""
import datetime
import logging
import os
import random
import re
import sys
import threading
import time

import appscale_datastore_batch
import dbconstants
import datastore_server
import entity_utils

from zkappscale import zktransaction as zk

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_distributed
from google.appengine.api.memcache import memcache_distributed
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import entity_pb
from google.appengine.ext import db
from google.appengine.ext.db import stats
from google.appengine.ext.db import metadata
from google.appengine.api import datastore_errors

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info
import constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppDashboard/lib/"))
from app_dashboard_data import InstanceInfo
from app_dashboard_data import ServerStatus
from app_dashboard_data import RequestInfo
from dashboard_logs import RequestLogLine

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppTaskQueue/"))
from distributed_tq import TaskName


class DatastoreGroomer(threading.Thread):
  """ Scans the entire database for each application. """

  # The amount of seconds between polling to get the groomer lock.
  # Each datastore server does this poll, so it happens the number
  # of datastore servers within this lock period.
  LOCK_POLL_PERIOD = 4 * 60 * 60 # <- 4 hours

  # Retry sleep on datastore error in seconds.
  DB_ERROR_PERIOD = 30

  # The number of entities retrieved in a datastore request.
  BATCH_SIZE = 100

  # Any kind that is of __*__ is private and should not have stats.
  PRIVATE_KINDS = '__(.*)__'

  # Any kind that is of _*_ is protected and should not have stats.
  PROTECTED_KINDS = '_(.*)_'

  # The amount of time in seconds before we want to clean up task name holders.
  TASK_NAME_TIMEOUT = 24 * 60 * 60

  # The amount of time before logs are considered too old.
  LOG_STORAGE_TIMEOUT = 24 * 60 * 60 * 7

  # Do not generate stats for AppScale internal apps.
  APPSCALE_APPLICATIONS = ['apichecker', 'appscaledashboard']

  # A sentinel value to signify that this app does not have composite indexes.
  NO_COMPOSITES = "NO_COMPS_INDEXES_HERE"

  # The amount of time in seconds dashboard data should be kept around for.
  DASHBOARD_DATA_TIMEOUT = 60 * 60 

  # The dashboard types we want to clean up after.
  DASHBOARD_DATA_MODELS = [InstanceInfo, ServerStatus, RequestInfo]

  # The number of dashboard entities to grab at a time. Makes the cleanup
  # process have an upper limit on each run.
  DASHBOARD_BATCH = 1000

  def __init__(self, zoo_keeper, table_name, ds_path):
    """ Constructor.

    Args:
      zk: ZooKeeper client.
      table_name: The database used (ie, cassandra)
      ds_path: The connection path to the datastore_server.
    """
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
      '%(lineno)s %(message)s ', level=logging.INFO)
    logging.info("Logging started")

    threading.Thread.__init__(self)
    self.zoo_keeper = zoo_keeper
    self.table_name = table_name
    self.db_access = None
    self.ds_access = None
    self.datastore_path = ds_path
    self.stats = {}
    self.namespace_info = {}
    self.num_deletes = 0
    self.composite_index_cache = {}
    self.journal_entries_cleaned = 0
    self.index_entries_checked = 0
    self.index_entries_delete_failures = 0
    self.index_entries_cleaned = 0

  def stop(self):
    """ Stops the groomer thread. """
    self.zoo_keeper.close()

  def run(self):
    """ Starts the main loop of the groomer thread. """
    while True:

      logging.debug("Trying to get groomer lock.")
      if self.get_groomer_lock():
        logging.info("Got the groomer lock.")
        self.run_groomer()
        try:
          self.zoo_keeper.release_lock_with_path(zk.DS_GROOM_LOCK_PATH)
        except zk.ZKTransactionException, zk_exception:
          logging.error("Unable to release zk lock {0}.".\
            format(str(zk_exception)))
        except zk.ZKInternalException, zk_exception:
          logging.error("Unable to release zk lock {0}.".\
            format(str(zk_exception)))
      else:
        logging.info("Did not get the groomer lock.")
      sleep_time = random.randint(1, self.LOCK_POLL_PERIOD)
      logging.info('Sleeping for {} hours.'.format(sleep_time/60/60))
      time.sleep(sleep_time)

  def get_groomer_lock(self):
    """ Tries to acquire the lock to the datastore groomer.

    Returns:
      True on success, False otherwise.
    """
    return self.zoo_keeper.get_lock_with_path(zk.DS_GROOM_LOCK_PATH)

  def get_entity_batch(self, last_key):
    """ Gets a batch of entites to operate on.

    Args:
      last_key: The last key from a previous query.
    Returns:
      A list of entities.
    """
    return self.db_access.range_query(dbconstants.APP_ENTITY_TABLE,
      dbconstants.APP_ENTITY_SCHEMA, last_key, "", self.BATCH_SIZE,
      start_inclusive=False)

  def reset_statistics(self):
    """ Reinitializes statistics. """
    self.stats = {}
    self.namespace_info = {}
    self.num_deletes = 0
    self.journal_entries_cleaned = 0

  def remove_deprecated_dashboard_data(self, model_type):
    """ Remove entities that do not have timestamps in Dashboard data. 

    AppScale 2.3 and earlier lacked a timestamp attribute. 

    Args:
      model_type: A class type for a ndb model.
    """
    query = model_type.query()
    entities = query.fetch(self.DASHBOARD_BATCH)
    counter = 0
    for entity in entities:
      if not hasattr(entity, "timestamp"):
        entity.key.delete()
        counter += 1
    if counter > 0:
      logging.warning("Removed {0} deprecated {1} dashboard entities".format(
        counter, entity._get_kind()))

  def remove_old_dashboard_data(self):
    """ Removes old statistics from the AppScale dashboard application. """
    self.register_db_accessor(constants.DASHBOARD_APP_ID)
    timeout = datetime.datetime.utcnow() - \
      datetime.timedelta(seconds=self.DASHBOARD_DATA_TIMEOUT)
    for model_type in self.DASHBOARD_DATA_MODELS:
      query = model_type.query().filter(model_type.timestamp < timeout)
      entities = query.fetch(self.DASHBOARD_BATCH)
      counter = 0
      kind = ""
      for entity in entities:
        kind = entity.key.kind()
        entity.key.delete()
        counter += 1
      if counter > 0:
        logging.info("Removed {0} {1} dashboard entities".format(counter,
          kind))
     
      # Do a scan of all entities and remove any that
      # do not have timestamps for AppScale versions 2.3 and before. 
      # This may take some time on the initial run, but subsequent runs should
      # be quick given a low dashboard data timeout.
      self.remove_deprecated_dashboard_data(model_type)
    return 

  def clean_journal_entries(self, txn_id, key):
    """ Remove journal entries that are no longer needed. Assumes
    transaction numbers are only increasing.

    Args:
      txn_id: An int of the transaction number to delete up to.
      key: A str, the entity table key for which we are deleting.
    Returns:
      True on success, False otherwise.
    """
    if txn_id == 0:
      return True
    start_row = datastore_server.DatastoreDistributed.get_journal_key(key, 0)
    end_row = datastore_server.DatastoreDistributed.get_journal_key(key,
      int(txn_id) - 1)
    last_key = start_row

    keys_to_delete = []
    while True:
      try:
        results = self.db_access.range_query(dbconstants.JOURNAL_TABLE,
          dbconstants.JOURNAL_SCHEMA, last_key, end_row, self.BATCH_SIZE,
          start_inclusive=False, end_inclusive=True)
        if len(results) == 0:
          return True
        keys_to_delete = []
        for item in results:
          keys_to_delete.append(item.keys()[0])
        self.db_access.batch_delete(dbconstants.JOURNAL_TABLE,
            keys_to_delete)
        self.journal_entries_cleaned += len(keys_to_delete)
      except dbconstants.AppScaleDBConnectionError, db_error:
        logging.error("Error hard deleting keys {0} --> {1}".format(
          keys_to_delete, db_error))
        logging.error("Backing off!")
        time.sleep(self.DB_ERROR_PERIOD)
        return False
      except Exception, exception:
        logging.error("Caught unexcepted exception {0}".format(exception))
        logging.error("Backing off!")
        time.sleep(self.DB_ERROR_PERIOD)
        return False

  def hard_delete_row(self, row_key):
    """ Does a hard delete on a given row key to the entity
        table.

    Args:
      row_key: A str representing the row key to delete.
    Returns:
      True on success, False otherwise.
    """
    try:
      self.db_access.batch_delete(dbconstants.APP_ENTITY_TABLE,
        [row_key])
    except dbconstants.AppScaleDBConnectionError, db_error:
      logging.error("Error hard deleting key {0}-->{1}".format(
        row_key, db_error))
      return False
    except Exception, exception:
      logging.error("Caught unexcepted exception {0}".format(exception))
      return False

    return True

  def load_composite_cache(self, app_id):
    """ Load the composite index cache for an application ID.

    Args:
      app_id: A str, the application ID.
    Returns:
      True if the application has composites. False otherwise.
    """
    start_key = datastore_server.DatastoreDistributed.get_meta_data_key(
      app_id, "index", "")
    end_key = datastore_server.DatastoreDistributed.get_meta_data_key(
      app_id, "index", dbconstants.TERMINATING_STRING)

    results = self.db_access.range_query(dbconstants.METADATA_TABLE,
      dbconstants.METADATA_TABLE, start_key, end_key,
      dbconstants.MAX_NUMBER_OF_COMPOSITE_INDEXES)
    list_result = []
    for list_item in results:
      for _, value in list_item.iteritems():
        list_result.append(value['data'])

    self.composite_index_cache[app_id] = self.NO_COMPOSITES
    kind_index_dictionary = {}
    for index in list_result:
      new_index = entity_pb.CompositeIndex()
      new_index.ParseFromString(index)
      kind = new_index.definition().entity_type()
      if kind in kind_index_dictionary:
        kind_index_dictionary[kind].append(new_index)
      else:
        kind_index_dictionary[kind] = [new_index]
    if kind_index_dictionary:
      self.composite_index_cache[app_id] = kind_index_dictionary
      return True

    return False

  def acquire_lock_for_key(self, app_id, key, retries, retry_time):
    """ Acquires a lock for a given entity key.

    Args:
      app_id: The application ID.
      key: A string containing an entity key.
      retries: An integer specifying the number of times to retry.
      retry_time: How many seconds to wait before each retry.
    Returns:
      A transaction ID.
    Raises:
      ZKTransactionException if unable to acquire a lock from ZooKeeper.
    """
    root_key = key.split(dbconstants.KIND_SEPARATOR)[0]
    root_key += dbconstants.KIND_SEPARATOR

    txn_id = self.zoo_keeper.get_transaction_id(app_id, is_xg=False)
    try:
      self.zoo_keeper.acquire_lock(app_id, txn_id, root_key)
    except zk.ZKTransactionException as zkte:
      logging.warning('Concurrent transaction exception for app id {} with '
        'info {}'.format(app_id, str(zkte)))
      if retries > 0:
        logging.info('Trying again to acquire lock info {} with retry #{}'
          .format(str(zkte), retries))
        time.sleep(retry_time)
        return self.acquire_lock_for_key(
          app_id=app_id,
          key=key,
          retries=retries - 1,
          retry_time=retry_time
        )
      self.zoo_keeper.notify_failed_transaction(app_id, txn_id)
      raise zkte
    return txn_id

  def release_lock_for_key(self, app_id, key, txn_id):
    """ Releases a lock for a given entity key.

    Args:
      app_id: The application ID.
      key: A string containing an entity key.
      txn_id: A transaction ID.
    """
    root_key = key.split(dbconstants.KIND_SEPARATOR)[0]
    root_key += dbconstants.KIND_SEPARATOR

    self.zoo_keeper.release_lock(app_id, txn_id)

  def fetch_entity_dict_for_references(self, references):
    """ Fetches a dictionary of valid entities for a list of references.

    Args:
      references: A list of index references to entities.
    Returns:
      A dictionary of validated entities.
    """
    keys = list(set([item.values()[0]['reference'] for item in references]))
    entities = self.db_access.batch_get_entity(dbconstants.APP_ENTITY_TABLE,
      keys, dbconstants.APP_ENTITY_SCHEMA)

    # The datastore needs to know the app ID. The indices could be scattered
    # across apps.
    entities_by_app = {}
    for key in entities:
      app = key.split(self.ds_access._SEPARATOR)[0]
      if app not in entities_by_app:
        entities_by_app[app] = {}
      entities_by_app[app][key] = entities[key]

    entities = {}
    for app in entities_by_app:
      app_entities = entities_by_app[app]
      app_entities = self.ds_access.validated_result(app, app_entities)
      app_entities = self.ds_access.remove_tombstoned_entities(app_entities)
      for key in keys:
        if key not in app_entities:
          continue
        if dbconstants.APP_ENTITY_SCHEMA[0] not in app_entities[key]:
          continue
        entities[key] = app_entities[key][dbconstants.APP_ENTITY_SCHEMA[0]]
    return entities

  def lock_and_delete_index(self, reference, direction, prop_name):
    """ For a given index entry, lock its entity and delete it.

    Since another process can update an entity after we've determined that
    an index entry is invalid, we need to re-check the index entry after
    locking its entity key.

    Args:
      reference: A references to an entity.
      direction: The direction of the index.
      prop_name: A string containing the property name.
    """
    if direction == datastore_pb.Query_Order.ASCENDING:
      table_name = dbconstants.ASC_PROPERTY_TABLE
    else:
      table_name = dbconstants.DSC_PROPERTY_TABLE

    index_entry = reference.keys()[0]
    app = index_entry.split(self.ds_access._SEPARATOR)[0]
    key = reference.values()[0]['reference']
    try:
      txn_id = self.acquire_lock_for_key(
        app_id=app,
        key=key,
        retries=self.ds_access.NON_TRANS_LOCK_RETRY_COUNT,
        retry_time=self.ds_access.LOCK_RETRY_TIME
      )
    except zk.ZKTransactionException:
      self.index_entries_delete_failures += 1
      return

    entities = self.fetch_entity_dict_for_references([reference])

    if not self.ds_access._DatastoreDistributed__valid_index_entry(reference,
      entities, direction, prop_name):
      self.db_access.batch_delete(table_name, [index_entry],
        column_names=dbconstants.PROPERTY_SCHEMA)
      self.index_entries_cleaned += 1

    self.release_lock_for_key(app, key, txn_id)

  def clean_up_indexes(self, direction):
    """ Deletes invalid single property index entries.

    This is needed because we do not delete index entries when updating or
    deleting entities. With time, this results in queries taking an increasing
    amount of time.

    Args:
      direction: The direction of the index.
    """
    start_key = ''
    end_key = dbconstants.TERMINATING_STRING
    batch_size = 100
    if direction == datastore_pb.Query_Order.ASCENDING:
      table_name = dbconstants.ASC_PROPERTY_TABLE
    else:
      table_name = dbconstants.DSC_PROPERTY_TABLE

    while True:
      references = self.db_access.range_query(
        table_name=table_name,
        column_names=dbconstants.PROPERTY_SCHEMA,
        start_key=start_key,
        end_key=end_key,
        limit=batch_size,
        start_inclusive=False,
      )
      self.index_entries_checked += len(references)
      if len(references) == 0:
        break

      last_start_key = start_key
      start_key = references[-1].keys()[0]
      if start_key == last_start_key:
        raise dbconstants.AppScaleDBError(
          'An infinite loop was detected while fetching references.')

      entities = self.fetch_entity_dict_for_references(references)

      for reference in references:
        prop_name = reference.keys()[0].split(self.ds_access._SEPARATOR)[3]
        if self.ds_access._DatastoreDistributed__valid_index_entry(
          reference, entities, direction, prop_name):
          continue
        self.lock_and_delete_index(reference, direction, prop_name)

  def clean_up_composite_indexes(self):
    """ Deletes old composite indexes and bad references.

    Returns:
      True on success, False otherwise.
    """
    return True

  def get_composite_indexes(self, app_id, kind):
    """ Fetches the composite indexes for a kind.

    Args:
      app_id: The application ID.
      kind: A string, the kind for which we need composite indexes.
    Returns:
      A list of composite indexes.
    """
    if not kind:
      return []

    if app_id in self.composite_index_cache:
      if self.composite_index_cache[app_id] == self.NO_COMPOSITES:
        return []
      elif kind in self.composite_index_cache[app_id]:
        return self.composite_index_cache[app_id][kind]
      else:
        return []
    else:
      if self.load_composite_cache(app_id):
        if kind in self.composite_index_cache[app_id]:
          return self.composite_index_cache[kind]
      return []

  def delete_indexes(self, entity):
    """ Deletes indexes for a given entity.

    Args:
      entity: An EntityProto.
    """
    return

  def delete_composite_indexes(self, entity, composites):
    """ Deletes composite indexes for an entity.

    Args:
      entity: An EntityProto.
      composites: A list of datastore_pb.CompositeIndexes composite indexes.
    """
    row_keys = datastore_server.DatastoreDistributed.\
      get_composite_indexes_rows([entity], composites)
    self.db_access.batch_delete(dbconstants.COMPOSITE_TABLE,
      row_keys, column_names=dbconstants.COMPOSITE_SCHEMA)

  def fix_badlisted_entity(self, key, version):
    """ Places the correct entity given the current one is from a blacklisted
    transaction.

    Args:
      key: The key to the entity table.
      version: The bad version of the entity.
    Returns:
      True on success, False otherwise.
    """
    app_prefix = entity_utils.get_prefix_from_entity_key(key)
    root_key = entity_utils.get_root_key_from_entity_key(key)
    # TODO watch out for the race condition of doing a GET then a PUT.

    try:
      txn_id = self.zoo_keeper.get_transaction_id(app_prefix)
      if self.zoo_keeper.acquire_lock(app_prefix, txn_id, root_key):
        valid_id = self.zoo_keeper.get_valid_transaction_id(app_prefix,
          version, key)
        # Insert the entity along with regular indexes and composites.
        ds_distributed = self.register_db_accessor(app_prefix)
        bad_key = datastore_server.DatastoreDistributed.get_journal_key(key,
          version)
        good_key = datastore_server.DatastoreDistributed.get_journal_key(key,
          valid_id)

        # Fetch the journal and replace the bad entity.
        good_entry = entity_utils.fetch_journal_entry(self.db_access, good_key)
        bad_entry = entity_utils.fetch_journal_entry(self.db_access, bad_key)

        # Get the kind to lookup composite indexes.
        kind = None
        if good_entry:
          kind = datastore_server.DatastoreDistributed.get_entity_kind(
            good_entry.key())
        elif bad_entry:
          kind = datastore_server.DatastoreDistributed.get_entity_kind(
            bad_entry.key())

        # Fetch latest composites for this entity
        composites = self.get_composite_indexes(app_prefix, kind)

        # Remove previous regular indexes and composites if it's not a
        # TOMBSTONE.
        if bad_entry:
          self.delete_indexes(bad_entry)
          self.delete_composite_indexes(bad_entry, composites)

        # Overwrite the entity table with the correct version.
        # Insert into entity table, regular indexes, and composites.
        if good_entry:
          # TODO
          #self.db_access.batch_put_entities(...)
          #self.insert_indexes(good_entry)
          #self.insert_composite_indexes(good_entry, composites)
          pass
        else:
          # TODO
          #self.db_access.batch_delete_entities(...)
          pass
        del ds_distributed
      else:
        success = False
    except zk.ZKTransactionException, zk_exception:
      logging.error("Caught exception {0}".format(zk_exception))
      success = False
    except zk.ZKInternalException, zk_exception:
      logging.error("Caught exception {0}".format(zk_exception))
      success = False
    except dbconstants.AppScaleDBConnectionError, db_exception:
      logging.error("Caught exception {0}".format(db_exception))
      success = False
    finally:
      if not success:
        if not self.zoo_keeper.notify_failed_transaction(app_prefix, txn_id):
          logging.error("Unable to invalidate txn for {0} with txnid: {1}"\
            .format(app_prefix, txn_id))
      try:
        self.zoo_keeper.release_lock(app_prefix, txn_id)
      except zk.ZKTransactionException, zk_exception:
        # There was an exception releasing the lock, but
        # the replacement has already happened.
        pass
      except zk.ZKInternalException, zk_exception:
        pass

    return True

  def process_tombstone(self, key, entity, version):
    """ Processes any entities which have been soft deleted.
        Does an actual delete to reclaim disk space.

    Args:
      key: The key to the entity table.
      entity: The entity in string serialized form.
      version: The version of the entity in the datastore.
    Returns:
      True if a hard delete occurred, False otherwise.
    """
    success = False
    app_prefix = entity_utils.get_prefix_from_entity_key(key)
    root_key = entity_utils.get_root_key_from_entity_key(key)

    try:
      if self.zoo_keeper.is_blacklisted(app_prefix, version):
        logging.error("Found a blacklisted item for version {0} on key {1}".\
          format(version, key))
        return True
        #TODO actually fix the badlisted entity
        return self.fix_badlisted_entity(key, version)
    except zk.ZKTransactionException, zk_exception:
      logging.error("Caught exception {0}.\nBacking off!".format(zk_exception))
      time.sleep(self.DB_ERROR_PERIOD)
      return False
    except zk.ZKInternalException, zk_exception:
      logging.error("Caught exception {0}.\nBacking off!".format(zk_exception))
      time.sleep(self.DB_ERROR_PERIOD)
      return False

    txn_id = 0
    try:
      txn_id = self.zoo_keeper.get_transaction_id(app_prefix)
    except zk.ZKTransactionException, zk_exception:
      logging.error("Exception tossed: {0}".format(zk_exception))
      logging.error("Backing off!")
      time.sleep(self.DB_ERROR_PERIOD)
      return False
    except zk.ZKInternalException, zk_exception:
      logging.error("Exception tossed: {0}".format(zk_exception))
      logging.error("Backing off!")
      time.sleep(self.DB_ERROR_PERIOD)
      return False

    try:
      if self.zoo_keeper.acquire_lock(app_prefix, txn_id, root_key):
        success = self.hard_delete_row(key)
        if success:
          # Increment the txn ID by one because we want to delete this current
          # entry as well.
          success = self.clean_journal_entries(txn_id + 1, key)
      else:
        success = False
    except zk.ZKTransactionException, zk_exception:
      logging.error("Exception tossed: {0}".format(zk_exception))
      logging.error("Backing off!")
      time.sleep(self.DB_ERROR_PERIOD)
      success = False
    except zk.ZKInternalException, zk_exception:
      logging.error("Exception tossed: {0}".format(zk_exception))
      logging.error("Backing off!")
      time.sleep(self.DB_ERROR_PERIOD)
      success = False
    finally:
      if not success:
        try:
          if not self.zoo_keeper.notify_failed_transaction(app_prefix, txn_id):
            logging.error("Unable to invalidate txn for {0} with txnid: {1}"\
              .format(app_prefix, txn_id))
          self.zoo_keeper.release_lock(app_prefix, txn_id)
        except zk.ZKTransactionException, zk_exception:
          logging.error("Caught exception: {0}\nIgnoring...".format(
            zk_exception))
          # There was an exception releasing the lock, but
          # the hard delete has already happened.
        except zk.ZKInternalException, zk_exception:
          logging.error("Caught exception: {0}\nIgnoring...".format(
            zk_exception))
    if success:
      try:
        self.zoo_keeper.release_lock(app_prefix, txn_id)
      except Exception, exception:
        logging.error("Unable to release lock: {0}".format(exception))
      self.num_deletes += 1

    logging.debug("Deleting tombstone for key {0}: {1}".format(key, success))
    return success

  def initialize_kind(self, app_id, kind):
    """ Puts a kind into the statistics object if
        it does not already exist.
    Args:
      app_id: The application ID.
      kind: A string representing an entity kind.
    """
    if app_id not in self.stats:
      self.stats[app_id] = {kind: {'size': 0, 'number': 0}}
    if kind not in self.stats[app_id]:
      self.stats[app_id][kind] = {'size': 0, 'number': 0}

  def initialize_namespace(self, app_id, namespace):
    """ Puts a namespace into the namespace object if
        it does not already exist.
    Args:
      app_id: The application ID.
      namespace: A string representing a namespace.
    """
    if app_id not in self.namespace_info:
      self.namespace_info[app_id] = {namespace: {'size': 0, 'number': 0}}

    if namespace not in self.namespace_info[app_id]:
      self.namespace_info[app_id] = {namespace: {'size': 0, 'number': 0}}
    if namespace not in self.namespace_info[app_id]:
      self.stats[app_id][namespace] = {'size': 0, 'number': 0}

  def process_statistics(self, key, entity, size):
    """ Processes an entity and adds to the global statistics.

    Args:
      key: The key to the entity table.
      entity: EntityProto entity.
      size: A int of the size of the entity.
    Returns:
      True on success, False otherwise.
    """
    kind = datastore_server.DatastoreDistributed.get_entity_kind(entity.key())
    namespace = entity.key().name_space()

    if not kind:
      logging.warning("Entity did not have a kind {0}"\
        .format(entity))
      return False

    if re.match(self.PROTECTED_KINDS, kind):
      return True

    if re.match(self.PRIVATE_KINDS, kind):
      return True

    app_id = entity.key().app()
    if not app_id:
      logging.warning("Entity of kind {0} did not have an app id"\
        .format(kind))
      return False

    # Do not generate statistics for applications which are internal to
    # AppScale.
    if app_id in self.APPSCALE_APPLICATIONS:
      return True

    self.initialize_kind(app_id, kind)
    self.initialize_namespace(app_id, namespace)
    self.namespace_info[app_id][namespace]['size'] += size
    self.namespace_info[app_id][namespace]['number'] += 1
    self.stats[app_id][kind]['size'] += size
    self.stats[app_id][kind]['number'] += 1
    return True

  def txn_blacklist_cleanup(self):
    """ Clean up old transactions and removed unused references
        to reap storage.

    Returns:
      True on success, False otherwise.
    """
    #TODO implement
    return True

  def verify_entity(self, entity, key, txn_id):
    """ Verify that the entity is not blacklisted. Clean up old journal
    entries if it is valid.

    Args:
      entity: The entity to verify.
      key: The key to the entity table.
      txn_id: An int, a transaction ID.
    Returns:
      True on success, False otherwise.
    """
    app_prefix = entity_utils.get_prefix_from_entity_key(key)
    try:
      if not self.zoo_keeper.is_blacklisted(app_prefix, txn_id):
        self.clean_journal_entries(txn_id, key)
      else:
        logging.error("Found a blacklisted item for version {0} on key {1}".\
          format(txn_id, key))
        return True
        #TODO fix the badlisted entity.
        return self.fix_badlisted_entity(key, txn_id)
    except zk.ZKTransactionException, zk_exception:
      logging.error("Caught exception {0}, backing off!".format(zk_exception))
      time.sleep(self.DB_ERROR_PERIOD)
      return True
    except zk.ZKInternalException, zk_exception:
      logging.error("Caught exception: {0}, backing off!".format(
      zk_exception))
      time.sleep(self.DB_ERROR_PERIOD)
      return True

    return True

  def process_entity(self, entity):
    """ Processes an entity by updating statistics, indexes, and removes
        tombstones.

    Args:
      entity: The entity to operate on.
    Returns:
      True on success, False otherwise.
    """
    logging.debug("Process entity {0}".format(str(entity)))
    key = entity.keys()[0]
    one_entity = entity[key][dbconstants.APP_ENTITY_SCHEMA[0]]
    version = entity[key][dbconstants.APP_ENTITY_SCHEMA[1]]

    logging.debug("Entity value: {0}".format(entity))
    if one_entity == datastore_server.TOMBSTONE:
      return self.process_tombstone(key, one_entity, version)

    ent_proto = entity_pb.EntityProto()
    ent_proto.ParseFromString(one_entity)
    self.verify_entity(ent_proto, key, version)
    self.process_statistics(key, ent_proto, len(one_entity))

    return True

  def create_namespace_entry(self, namespace, size, number, timestamp):
    """ Puts a namespace into the datastore.

    Args:
      namespace: A string, the namespace.
      size: An int representing the number of bytes taken by a namespace.
      number: The total number of entities in a namespace.
      timestamp: A datetime.datetime object.
    Returns:
      True on success, False otherwise.
    """
    entities_to_write = []
    namespace_stat = stats.NamespaceStat(subject_namespace=namespace,
                               bytes=size,
                               count=number,
                               timestamp=timestamp)
    entities_to_write.append(namespace_stat)

    # All application are assumed to have the default namespace.
    if namespace != "":
      namespace_entry = metadata.Namespace(key_name=namespace)
      entities_to_write.append(namespace_entry)
    try:
      db.put(entities_to_write)
    except datastore_errors.InternalError, internal_error:
      logging.error("Error inserting namespace info: {0}.".\
        format(internal_error))
      return False
    logging.debug("Done creating namespace stats")
    return True


  def create_kind_stat_entry(self, kind, size, number, timestamp):
    """ Puts a kind statistic into the datastore.

    Args:
      kind: The entity kind.
      size: An int representing the number of bytes taken by entity kind.
      number: The total number of entities.
      timestamp: A datetime.datetime object.
    Returns:
      True on success, False otherwise.
    """
    kind_stat = stats.KindStat(kind_name=kind,
                               bytes=size,
                               count=number,
                               timestamp=timestamp)
    kind_entry = metadata.Kind(key_name=kind)
    entities_to_write = [kind_stat, kind_entry]
    try:
      db.put(entities_to_write)
    except datastore_errors.InternalError, internal_error:
      logging.error("Error inserting kind stat: {0}.".format(internal_error))
      return False
    logging.debug("Done creating kind stat")
    return True

  def create_global_stat_entry(self, app_id, size, number, timestamp):
    """ Puts a global statistic into the datastore.

    Args:
      app_id: The application identifier.
      size: The number of bytes of all entities.
      number: The total number of entities of an application.
      timestamp: A datetime.datetime object.
    Returns:
      True on success, False otherwise.
    """
    global_stat = stats.GlobalStat(key_name=app_id,
                                   bytes=size,
                                   count=number,
                                   timestamp=timestamp)
    try:
      db.put(global_stat)
    except datastore_errors.InternalError, internal_error:
      logging.error("Error inserting global stat: {0}.".format(internal_error))
      return False
    logging.debug("Done creating global stat")
    return True

  def remove_old_tasks_entities(self):
    """ Queries for old tasks and removes the entity which tells
    use whether a named task was enqueued.

    Returns:
      True on success.
    """
    self.register_db_accessor(constants.DASHBOARD_APP_ID)
    timeout = datetime.datetime.utcnow() - \
      datetime.timedelta(seconds=self.TASK_NAME_TIMEOUT)
    query = TaskName.all()
    query.filter("timestamp <", timeout)
    entities = query.run()
    counter = 0
    logging.debug("The current time is {0}".format(datetime.datetime.utcnow()))
    logging.debug("The timeout time is {0}".format(timeout))
    for entity in entities:
      logging.debug("Removing task name {0}".format(entity.timestamp))
      entity.delete()
      counter += 1
    logging.info("Removed {0} task name entities".format(counter))
    return True

  def register_db_accessor(self, app_id):
    """ Gets a distributed datastore object to interact with
        the datastore for a certain application.

    Args:
      app_id: The application ID.
    Returns:
      A distributed_datastore.DatastoreDistributed object.
    """
    ds_distributed = datastore_distributed.DatastoreDistributed(app_id,
      self.datastore_path, require_indexes=False)
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', ds_distributed)
    apiproxy_stub_map.apiproxy.RegisterStub('memcache',
      memcache_distributed.MemcacheService())
    os.environ['APPLICATION_ID'] = app_id
    os.environ['APPNAME'] = app_id
    os.environ['AUTH_DOMAIN'] = "appscale.com"
    return ds_distributed

  def remove_old_logs(self, log_timeout):
    """ Removes old logs.

    Args:
      log_timeout: The timeout value in seconds.

    Returns:
      True on success, False otherwise.
    """
    self.register_db_accessor(constants.DASHBOARD_APP_ID)
    if log_timeout:
      timeout = datetime.datetime.utcnow() - \
        datetime.timedelta(seconds=log_timeout)
      query = RequestLogLine.query(RequestLogLine.timestamp < timeout)
      logging.debug("The timeout time is {0}".format(timeout))
    else:
      query = RequestLogLine.query()
    counter = 0
    logging.debug("The current time is {0}".format(datetime.datetime.utcnow()))
    for entity in query.iter():
      logging.debug("Removing {0}".format(entity))
      entity.key.delete()
      counter += 1
    logging.info("Removed {0} log entries.".format(counter))
    return True

  def remove_old_statistics(self):
    """ Does a range query on the current batch of statistics and
        deletes them.
    """
    #TODO only remove statistics older than 30 days.
    for app_id in self.stats.keys():
      self.register_db_accessor(app_id)
      query = stats.KindStat.all()
      entities = query.run()
      logging.debug("Result from kind stat query: {0}".format(str(entities)))
      for entity in entities:
        logging.debug("Removing kind {0}".format(entity))
        entity.delete()

      query = stats.GlobalStat.all()
      entities = query.run()
      logging.debug("Result from global stat query: {0}".format(str(entities)))
      for entity in entities:
        logging.debug("Removing global {0}".format(entity))
        entity.delete()
      logging.debug("Done removing old stats for app {0}".format(app_id))

  def update_namespaces(self, timestamp):
    """ Puts the namespace information into the datastore for applications to
        access.

    Args:
      timestamp: A datetime time stamp to know which stat items belong
        together.
    Returns:
      True if there were no errors, False otherwise.
    """
    for app_id in self.namespace_info.keys():
      ds_distributed = self.register_db_accessor(app_id)
      namespaces = self.namespace_info[app_id].keys()
      for namespace in namespaces:
        size = self.namespace_info[app_id][namespace]['size']
        number = self.namespace_info[app_id][namespace]['number']
        if not self.create_namespace_entry(namespace, size, number, timestamp):
          return False

      logging.info("Namespace for {0} are {1}"\
        .format(app_id, self.namespace_info[app_id]))
      del ds_distributed

    return True


  def update_statistics(self, timestamp):
    """ Puts the statistics into the datastore for applications
        to access.

    Args:
      timestamp: A datetime time stamp to know which stat items belong
        together.
    Returns:
      True if there were no errors, False otherwise.
    """
    for app_id in self.stats.keys():
      ds_distributed = self.register_db_accessor(app_id)
      total_size = 0
      total_number = 0
      kinds = self.stats[app_id].keys()
      for kind in kinds:
        size = self.stats[app_id][kind]['size']
        number = self.stats[app_id][kind]['number']
        total_size += size
        total_number += number
        if not self.create_kind_stat_entry(kind, size, number, timestamp):
          return False

      if not self.create_global_stat_entry(app_id, total_size, total_number,
                                           timestamp):
        return False

      logging.info("Kind stats for {0} are {1}"\
        .format(app_id, self.stats[app_id]))
      logging.info("Global stats for {0} are total size of {1} with " \
        "{2} entities".format(app_id, total_size, total_number))
      logging.info("Number of hard deletes: {0}".format(self.num_deletes))
      del ds_distributed

    return True

  def run_groomer(self):
    """ Runs the grooming process. Loops on the entire dataset sequentially
        and updates stats, indexes, and transactions.
    """
    self.db_access = appscale_datastore_batch.DatastoreFactory.getDatastore(
      self.table_name)
    self.ds_access = datastore_server.DatastoreDistributed(
      datastore_batch=self.db_access, zookeeper=self.zoo_keeper)

    logging.info("Groomer started")
    start = time.time()
    last_key = ""
    self.reset_statistics()
    self.composite_index_cache = {}

    try:
      self.clean_up_indexes(datastore_pb.Query_Order.ASCENDING)
    except datastore_errors.Error, error:
      logging.error("Error while cleaning up ASC indexes: {0}".format(error))

    try:
      self.clean_up_indexes(datastore_pb.Query_Order.DESCENDING)
    except datastore_errors.Error, error:
      logging.error("Error while cleaning up DSC indexes: {0}".format(error))

    try:
      # We do this first to clean up soft deletes later.
      self.remove_old_logs(self.LOG_STORAGE_TIMEOUT)
    except datastore_errors.Error, error:
      logging.error("Error while cleaning up old tasks: {0}".format(error))

    try:
      # We do this first to clean up soft deletes later.
      self.remove_old_tasks_entities()
    except datastore_errors.Error, error:
      logging.error("Error while cleaning up old tasks: {0}".format(error))

    try:
      # We do this first to clean up soft deletes later.
      self.remove_old_dashboard_data()
    except datastore_errors.Error, error:
      logging.error("Error while cleaning up old dashboard items: {0}".format(
        error))

    while True:
      try:
        entities = self.get_entity_batch(last_key)

        if not entities:
          break

        for entity in entities:
          self.process_entity(entity)

        last_key = entities[-1].keys()[0]
      except datastore_errors.Error, error:
        logging.error("Error getting a batch: {0}".format(error))
        time.sleep(self.DB_ERROR_PERIOD)
      except dbconstants.AppScaleDBConnectionError, connection_error:
        logging.error("Error getting a batch: {0}".format(connection_error))
        time.sleep(self.DB_ERROR_PERIOD)

    timestamp = datetime.datetime.utcnow()

    if not self.update_statistics(timestamp):
      logging.error("There was an error updating the statistics")

    if not self.update_namespaces(timestamp):
      logging.error("There was an error updating the namespaces")

    del self.db_access

    time_taken = time.time() - start
    logging.info("Groomer checked {0} index entries".format(
      self.index_entries_checked))
    logging.info("Groomer cleaned {0} index entries".format(
      self.index_entries_cleaned))
    if self.index_entries_delete_failures > 0:
      logging.info("Groomer failed to remove {0} index entries".format(
        self.index_entries_delete_failures))
    logging.info("Groomer cleaned {0} journal entries".format(
      self.journal_entries_cleaned))
    logging.info("Groomer took {0} seconds".format(str(time_taken)))

def main():
  """ This main function allows you to run the groomer manually. """
  zk_connection_locations = appscale_info.get_zk_locations_string()
  zookeeper = zk.ZKTransaction(host=zk_connection_locations)
  db_info = appscale_info.get_db_info()
  table = db_info[':table']
  master = appscale_info.get_db_master_ip()
  datastore_path = "{0}:8888".format(master)
  ds_groomer = DatastoreGroomer(zookeeper, table, datastore_path)

  logging.debug("Trying to get groomer lock.")
  if ds_groomer.get_groomer_lock():
    logging.info("Got the groomer lock.")
    ds_groomer.run_groomer()
    try:
      ds_groomer.zoo_keeper.release_lock_with_path(zk.DS_GROOM_LOCK_PATH)
    except zk.ZKTransactionException, zk_exception:
      logging.error("Unable to release zk lock {0}.".\
        format(str(zk_exception)))
    except zk.ZKInternalException, zk_exception:
      logging.error("Unable to release zk lock {0}.".\
        format(str(zk_exception)))
    finally:
      zookeeper.close()
  else:
    logging.info("Did not get the groomer lock.")

if __name__ == "__main__":
  main()
