import datetime
import logging
import os
import random
import re
import sys
import threading
import time

from kazoo.client import KazooClient, KazooRetry
from tornado import gen

from appscale.datastore.utils import tornado_synchronous

import appscale_datastore_batch
import dbconstants
import utils

from appscale.common import appscale_info
from appscale.common import constants
from appscale.common.constants import ZK_PERSISTENT_RECONNECTS
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.common.unpackaged import DASHBOARD_DIR
from . import helper_functions
from .cassandra_env import cassandra_interface
from .datastore_distributed import DatastoreDistributed
from .index_manager import IndexManager
from .utils import get_composite_indexes_rows
from .zkappscale import zktransaction as zk
from .zkappscale.entity_lock import EntityLock
from .zkappscale.transaction_manager import TransactionManager

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_distributed
from google.appengine.api.memcache import memcache_distributed
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import entity_pb
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext import db
from google.appengine.ext.db import stats
from google.appengine.ext.db import metadata
from google.appengine.api import datastore_errors

sys.path.append(os.path.join(DASHBOARD_DIR, 'lib'))
from dashboard_logs import RequestLogLine

logger = logging.getLogger(__name__)


class TaskName(db.Model):
  """ A datastore model for tracking task names in order to prevent
  tasks with the same name from being enqueued repeatedly.

  Attributes:
    timestamp: The time the task was enqueued.
  """
  STORED_KIND_NAME = "__task_name__"
  timestamp = db.DateTimeProperty(auto_now_add=True)
  queue = db.StringProperty(required=True)
  state = db.StringProperty(required=True)
  endtime = db.DateTimeProperty()
  app_id = db.StringProperty(required=True)

  @classmethod
  def kind(cls):
    """ Kind name override. """
    return cls.STORED_KIND_NAME


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

  # The path in ZooKeeper where the groomer state is stored.
  GROOMER_STATE_PATH = '/appscale/groomer_state'

  # The characters used to separate values when storing the groomer state.
  GROOMER_STATE_DELIMITER = '||'

  # The ID for the task to clean up entities.
  CLEAN_ENTITIES_TASK = 'entities'

  # The ID for the task to clean up ascending indices.
  CLEAN_ASC_INDICES_TASK = 'asc-indices'

  # The ID for the task to clean up descending indices.
  CLEAN_DSC_INDICES_TASK = 'dsc-indices'

  # The ID for the task to clean up kind indices.
  CLEAN_KIND_INDICES_TASK = 'kind-indices'

  # The ID for the task to clean up old logs.
  CLEAN_LOGS_TASK = 'logs'

  # The ID for the task to clean up old tasks.
  CLEAN_TASKS_TASK = 'tasks'

  # The task ID for populating indexes with the scatter property.
  POPULATE_SCATTER = 'populate-scatter'

  # Log progress every time this many seconds have passed.
  LOG_PROGRESS_FREQUENCY = 60 * 5

  def __init__(self, zoo_keeper, table_name, ds_path):
    """ Constructor.

    Args:
      zk: ZooKeeper client.
      table_name: The database used (ie, cassandra)
      ds_path: The connection path to the datastore_server.
    """
    logger.info("Logging started")

    threading.Thread.__init__(self)
    self.zoo_keeper = zoo_keeper
    self.table_name = table_name
    self.db_access = None
    self.ds_access = None
    self.datastore_path = ds_path
    self.stats = {}
    self.namespace_info = {}
    self.num_deletes = 0
    self.entities_checked = 0
    self.journal_entries_cleaned = 0
    self.index_entries_checked = 0
    self.index_entries_delete_failures = 0
    self.index_entries_cleaned = 0
    self.scatter_prop_vals_populated = 0
    self.last_logged = time.time()
    self.groomer_state = []

  def stop(self):
    """ Stops the groomer thread. """
    self.zoo_keeper.close()

  def run(self):
    """ Starts the main loop of the groomer thread. """
    while True:

      logger.debug("Trying to get groomer lock.")
      if self.get_groomer_lock():
        logger.info("Got the groomer lock.")
        self.run_groomer()
        try:
          self.zoo_keeper.release_lock_with_path(zk.DS_GROOM_LOCK_PATH)
        except zk.ZKTransactionException, zk_exception:
          logger.error("Unable to release zk lock {0}.".\
            format(str(zk_exception)))
        except zk.ZKInternalException, zk_exception:
          logger.error("Unable to release zk lock {0}.".\
            format(str(zk_exception)))
      else:
        logger.info("Did not get the groomer lock.")
      sleep_time = random.randint(1, self.LOCK_POLL_PERIOD)
      logger.info('Sleeping for {:.1f} minutes.'.format(sleep_time/60.0))
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
    return self.db_access.range_query_sync(
      dbconstants.APP_ENTITY_TABLE, dbconstants.APP_ENTITY_SCHEMA,
      last_key, "", self.BATCH_SIZE, start_inclusive=False)

  def reset_statistics(self):
    """ Reinitializes statistics. """
    self.stats = {}
    self.namespace_info = {}
    self.num_deletes = 0
    self.journal_entries_cleaned = 0

  def hard_delete_row(self, row_key):
    """ Does a hard delete on a given row key to the entity
        table.

    Args:
      row_key: A str representing the row key to delete.
    Returns:
      True on success, False otherwise.
    """
    try:
      self.db_access.batch_delete_sync(dbconstants.APP_ENTITY_TABLE, [row_key])
    except dbconstants.AppScaleDBConnectionError, db_error:
      logger.error("Error hard deleting key {0}-->{1}".format(
        row_key, db_error))
      return False
    except Exception, exception:
      logger.error("Caught unexcepted exception {0}".format(exception))
      return False

    return True

  def fetch_entity_dict_for_references(self, references):
    """ Fetches a dictionary of valid entities for a list of references.

    Args:
      references: A list of index references to entities.
    Returns:
      A dictionary of validated entities.
    """
    keys = []
    for item in references:
      keys.append(item.values()[0][self.ds_access.INDEX_REFERENCE_COLUMN])
    keys = list(set(keys))
    entities = self.db_access.batch_get_entity_sync(
      dbconstants.APP_ENTITY_TABLE, keys, dbconstants.APP_ENTITY_SCHEMA)

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
      for key in keys:
        if key not in app_entities:
          continue
        if dbconstants.APP_ENTITY_SCHEMA[0] not in app_entities[key]:
          continue
        entities[key] = app_entities[key][dbconstants.APP_ENTITY_SCHEMA[0]]
    return entities

  def guess_group_from_table_key(self, entity_key):
    """ Construct a group reference based on an entity key.

    Args:
      entity_key: A string specifying an entity table key.
    Returns:
      An entity_pb.Reference object specifying the entity group.
    """
    project_id, namespace, path = entity_key.split(dbconstants.KEY_DELIMITER)

    group = entity_pb.Reference()
    group.set_app(project_id)
    if namespace:
      group.set_name_space(namespace)

    mutable_path = group.mutable_path()
    first_element = mutable_path.add_element()
    encoded_first_element = path.split(dbconstants.KIND_SEPARATOR)[0]
    kind, id_ = encoded_first_element.split(dbconstants.ID_SEPARATOR, 1)
    first_element.set_type(kind)

    # At this point, there's no way to tell if the ID was originally a name,
    # so this is a guess.
    try:
      first_element.set_id(int(id_))
    except ValueError:
      first_element.set_name(id_)

    return group

  @tornado_synchronous
  @gen.coroutine
  def lock_and_delete_indexes(self, references, direction, entity_key):
    """ For a list of index entries that have the same entity, lock the entity
    and delete the indexes.

    Since another process can update an entity after we've determined that
    an index entry is invalid, we need to re-check the index entries after
    locking their entity key.

    Args:
      references: A list of references to an entity.
      direction: The direction of the index.
      entity_key: A string containing the entity key.
    """
    if direction == datastore_pb.Query_Order.ASCENDING:
      table_name = dbconstants.ASC_PROPERTY_TABLE
    else:
      table_name = dbconstants.DSC_PROPERTY_TABLE

    group_key = self.guess_group_from_table_key(entity_key)
    entity_lock = EntityLock(self.zoo_keeper.handle, [group_key])
    with entity_lock:
      entities = self.fetch_entity_dict_for_references(references)

      refs_to_delete = []
      for reference in references:
        index_elements = reference.keys()[0].split(self.ds_access._SEPARATOR)
        prop = index_elements[self.ds_access.PROP_NAME_IN_SINGLE_PROP_INDEX]
        if not self.ds_access._DatastoreDistributed__valid_index_entry(
          reference, entities, direction, prop):
          refs_to_delete.append(reference.keys()[0])

      logger.debug('Removing {} indexes starting with {}'.
        format(len(refs_to_delete), [refs_to_delete[0]]))
      try:
        self.db_access.batch_delete_sync(
          table_name, refs_to_delete, column_names=dbconstants.PROPERTY_SCHEMA)
        self.index_entries_cleaned += len(refs_to_delete)
      except Exception:
        logger.exception('Unable to delete indexes')
        self.index_entries_delete_failures += 1

  @tornado_synchronous
  @gen.coroutine
  def lock_and_delete_kind_index(self, reference):
    """ For a list of index entries that have the same entity, lock the entity
    and delete the indexes.

    Since another process can update an entity after we've determined that
    an index entry is invalid, we need to re-check the index entries after
    locking their entity key.

    Args:
      reference: A dictionary containing a kind reference.
    """
    table_name = dbconstants.APP_KIND_TABLE
    entity_key = reference.values()[0].values()[0]

    group_key = self.guess_group_from_table_key(entity_key)
    entity_lock = EntityLock(self.zoo_keeper.handle, [group_key])
    with entity_lock:
      entities = self.fetch_entity_dict_for_references([reference])
      if entity_key not in entities:
        index_to_delete = reference.keys()[0]
        logger.debug('Removing {}'.format([index_to_delete]))
        try:
          self.db_access.batch_delete_sync(
            table_name, [index_to_delete],
            column_names=dbconstants.APP_KIND_SCHEMA)
          self.index_entries_cleaned += 1
        except dbconstants.AppScaleDBConnectionError:
          logger.exception('Unable to delete index.')
          self.index_entries_delete_failures += 1

  def insert_scatter_indexes(self, entity_key, path, scatter_prop):
    """ Writes scatter property references to the index tables.

    Args:
      entity_key: A string specifying the entity key.
      path: A list of strings representing path elements.
      scatter_prop: An entity_pb.Property object.
    """
    app_id, namespace, encoded_path = entity_key.split(
      dbconstants.KEY_DELIMITER)
    kind = path[-1].split(dbconstants.ID_SEPARATOR)[0]
    asc_val = str(utils.encode_index_pb(scatter_prop.value()))
    dsc_val = helper_functions.reverse_lex(asc_val)
    prefix = dbconstants.KEY_DELIMITER.join([app_id, namespace])
    prop_name = '__scatter__'
    rows = [{'table': dbconstants.ASC_PROPERTY_TABLE, 'val': asc_val},
            {'table': dbconstants.DSC_PROPERTY_TABLE, 'val': dsc_val}]

    for row in rows:
      index_key = utils.get_index_key_from_params(
        [prefix, kind, prop_name, row['val'], encoded_path])
      # There's no need to insert with a particular timestamp because
      # datastore writes and deletes to this key should take precedence.
      statement = """
        INSERT INTO "{table}" ({key}, {column}, {value})
        VALUES (%s, %s, %s)
      """.format(table=row['table'],
                 key=cassandra_interface.ThriftColumn.KEY,
                 column=cassandra_interface.ThriftColumn.COLUMN_NAME,
                 value=cassandra_interface.ThriftColumn.VALUE)
      params = (bytearray(index_key), 'reference', bytearray(entity_key))
      self.db_access.session.execute(statement, params)

  def populate_scatter_prop(self):
    """ Populates the scatter property for existing entities. """
    task_id = self.POPULATE_SCATTER

    # If we have state information beyond what function to use, load the last
    # seen start key.
    start_key = ''
    if len(self.groomer_state) > 1 and self.groomer_state[0] == task_id:
      start_key = self.groomer_state[1]

    # Indicate that this job has started after the scatter property was added.
    if not start_key:
      index_state = self.db_access.get_metadata(
        cassandra_interface.SCATTER_PROP_KEY)
      if index_state is None:
        self.db_access.set_metadata(
          cassandra_interface.SCATTER_PROP_KEY,
          cassandra_interface.ScatterPropStates.POPULATION_IN_PROGRESS)

    while True:
      statement = """
        SELECT DISTINCT key FROM "{table}"
        WHERE token(key) > %s
        LIMIT {limit}
      """.format(table=dbconstants.APP_ENTITY_TABLE, limit=self.BATCH_SIZE)
      parameters = (bytearray(start_key),)
      keys = self.db_access.session.execute(statement, parameters)

      if not keys:
        break

      def create_path_element(encoded_element):
        element = entity_pb.Path_Element()
        # IDs are treated as names here. This avoids having to fetch the entity
        # to tell the difference.
        key_name = encoded_element.split(dbconstants.ID_SEPARATOR, 1)[-1]
        element.set_name(key_name)
        return element

      key = None
      for row in keys:
        key = row.key
        encoded_path = key.split(dbconstants.KEY_DELIMITER)[2]
        path = [element for element
                in encoded_path.split(dbconstants.KIND_SEPARATOR) if element]
        element_list = [create_path_element(element) for element in path]
        scatter_prop = utils.get_scatter_prop(element_list)

        if scatter_prop is not None:
          self.insert_scatter_indexes(key, path, scatter_prop)
          self.scatter_prop_vals_populated += 1

      start_key = key

      if time.time() > self.last_logged + self.LOG_PROGRESS_FREQUENCY:
        logger.info('Populated {} scatter property index entries'
          .format(self.scatter_prop_vals_populated))
        self.last_logged = time.time()

      self.update_groomer_state([task_id, start_key])

    self.db_access.set_metadata(
      cassandra_interface.SCATTER_PROP_KEY,
      cassandra_interface.ScatterPropStates.POPULATED)

  def clean_up_indexes(self, direction):
    """ Deletes invalid single property index entries.

    This is needed because we do not delete index entries when updating or
    deleting entities. With time, this results in queries taking an increasing
    amount of time.

    Args:
      direction: The direction of the index.
    """
    if direction == datastore_pb.Query_Order.ASCENDING:
      table_name = dbconstants.ASC_PROPERTY_TABLE
      task_id = self.CLEAN_ASC_INDICES_TASK
    else:
      table_name = dbconstants.DSC_PROPERTY_TABLE
      task_id = self.CLEAN_DSC_INDICES_TASK

    # If we have state information beyond what function to use,
    # load the last seen start key.
    if len(self.groomer_state) > 1 and self.groomer_state[0] == task_id:
      start_key = self.groomer_state[1]
    else:
      start_key = ''
    end_key = dbconstants.TERMINATING_STRING

    # Indicate that an index scrub has started.
    if direction == datastore_pb.Query_Order.ASCENDING and not start_key:
      self.db_access.set_metadata_sync(
        cassandra_interface.INDEX_STATE_KEY,
        cassandra_interface.IndexStates.SCRUB_IN_PROGRESS)

    while True:
      references = self.db_access.range_query_sync(
        table_name=table_name,
        column_names=dbconstants.PROPERTY_SCHEMA,
        start_key=start_key,
        end_key=end_key,
        limit=self.BATCH_SIZE,
        start_inclusive=False,
      )
      if len(references) == 0:
        break

      self.index_entries_checked += len(references)
      if time.time() > self.last_logged + self.LOG_PROGRESS_FREQUENCY:
        logger.info('Checked {} index entries'
          .format(self.index_entries_checked))
        self.last_logged = time.time()
      first_ref = references[0].keys()[0]
      logger.debug('Fetched {} total refs, starting with {}, direction: {}'
        .format(self.index_entries_checked, [first_ref], direction))

      last_start_key = start_key
      start_key = references[-1].keys()[0]
      if start_key == last_start_key:
        raise dbconstants.AppScaleDBError(
          'An infinite loop was detected while fetching references.')

      entities = self.fetch_entity_dict_for_references(references)

      # Group invalid references by entity key so we can minimize locks.
      invalid_refs = {}
      for reference in references:
        prop_name = reference.keys()[0].split(self.ds_access._SEPARATOR)[3]
        if not self.ds_access._DatastoreDistributed__valid_index_entry(
          reference, entities, direction, prop_name):
          entity_key = reference.values()[0][self.ds_access.INDEX_REFERENCE_COLUMN]
          if entity_key not in invalid_refs:
            invalid_refs[entity_key] = []
          invalid_refs[entity_key].append(reference)

      for entity_key in invalid_refs:
        self.lock_and_delete_indexes(invalid_refs[entity_key], direction, entity_key)
      self.update_groomer_state([task_id, start_key])

  def clean_up_kind_indices(self):
    """ Deletes invalid kind index entries.

    This is needed because the datastore does not delete kind index entries
    when deleting entities.
    """
    table_name = dbconstants.APP_KIND_TABLE
    task_id = self.CLEAN_KIND_INDICES_TASK

    start_key = ''
    end_key = dbconstants.TERMINATING_STRING
    if len(self.groomer_state) > 1:
      start_key = self.groomer_state[1]

    while True:
      references = self.db_access.range_query_sync(
        table_name=table_name,
        column_names=dbconstants.APP_KIND_SCHEMA,
        start_key=start_key,
        end_key=end_key,
        limit=self.BATCH_SIZE,
        start_inclusive=False,
      )
      if len(references) == 0:
        break

      self.index_entries_checked += len(references)
      if time.time() > self.last_logged + self.LOG_PROGRESS_FREQUENCY:
        logger.info('Checked {} index entries'.
          format(self.index_entries_checked))
        self.last_logged = time.time()
      first_ref = references[0].keys()[0]
      logger.debug('Fetched {} kind indices, starting with {}'.
        format(len(references), [first_ref]))

      last_start_key = start_key
      start_key = references[-1].keys()[0]
      if start_key == last_start_key:
        raise dbconstants.AppScaleDBError(
          'An infinite loop was detected while fetching references.')

      entities = self.fetch_entity_dict_for_references(references)

      for reference in references:
        entity_key = reference.values()[0].values()[0]
        if entity_key not in entities:
          self.lock_and_delete_kind_index(reference)

      self.update_groomer_state([task_id, start_key])

    # Indicate that the index has been scrubbed after the journal was removed.
    index_state = self.db_access.get_metadata_sync(
      cassandra_interface.INDEX_STATE_KEY)
    if index_state == cassandra_interface.IndexStates.SCRUB_IN_PROGRESS:
      self.db_access.set_metadata_sync(cassandra_interface.INDEX_STATE_KEY,
                                       cassandra_interface.IndexStates.CLEAN)

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

    try:
      project_index_manager = self.ds_access.index_manager.projects[app_id]
    except KeyError:
      return []

    return [index for index in project_index_manager.indexes_pb
            if index.definition().entity_type() == kind]

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
    row_keys = get_composite_indexes_rows([entity], composites)
    self.db_access.batch_delete_sync(
      dbconstants.COMPOSITE_TABLE, row_keys,
      column_names=dbconstants.COMPOSITE_SCHEMA)

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
    kind = utils.get_entity_kind(entity.key())
    namespace = entity.key().name_space()

    if not kind:
      logger.warning("Entity did not have a kind {0}"\
        .format(entity))
      return False

    if re.match(self.PROTECTED_KINDS, kind):
      return True

    if re.match(self.PRIVATE_KINDS, kind):
      return True

    app_id = entity.key().app()
    if not app_id:
      logger.warning("Entity of kind {0} did not have an app id"\
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

  def process_entity(self, entity):
    """ Processes an entity by updating statistics, indexes, and removes
        tombstones.

    Args:
      entity: The entity to operate on.
    Returns:
      True on success, False otherwise.
    """
    logger.debug("Process entity {0}".format(str(entity)))
    key = entity.keys()[0]
    one_entity = entity[key][dbconstants.APP_ENTITY_SCHEMA[0]]

    logger.debug("Entity value: {0}".format(entity))

    ent_proto = entity_pb.EntityProto()
    ent_proto.ParseFromString(one_entity)
    self.process_statistics(key, ent_proto, len(one_entity))

    return True

  def create_namespace_entry(self, namespace, size, number, timestamp):
    """ Puts a namespace into the datastore.

    Args:
      namespace: A string, the namespace.
      size: An int representing the number of bytes taken by a namespace.
      number: The total number of entities in a namespace.
      timestamp: A datetime.datetime object.
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

    db.put(entities_to_write)
    logger.debug("Done creating namespace stats")

  def create_kind_stat_entry(self, kind, size, number, timestamp):
    """ Puts a kind statistic into the datastore.

    Args:
      kind: The entity kind.
      size: An int representing the number of bytes taken by entity kind.
      number: The total number of entities.
      timestamp: A datetime.datetime object.
    """
    kind_stat = stats.KindStat(kind_name=kind,
                               bytes=size,
                               count=number,
                               timestamp=timestamp)
    kind_entry = metadata.Kind(key_name=kind)
    entities_to_write = [kind_stat, kind_entry]
    db.put(entities_to_write)
    logger.debug("Done creating kind stat")

  def create_global_stat_entry(self, app_id, size, number, timestamp):
    """ Puts a global statistic into the datastore.

    Args:
      app_id: The application identifier.
      size: The number of bytes of all entities.
      number: The total number of entities of an application.
      timestamp: A datetime.datetime object.
    """
    global_stat = stats.GlobalStat(key_name=app_id,
                                   bytes=size,
                                   count=number,
                                   timestamp=timestamp)
    db.put(global_stat)
    logger.debug("Done creating global stat")

  def remove_old_tasks_entities(self):
    """ Queries for old tasks and removes the entity which tells
    use whether a named task was enqueued.

    Returns:
      True on success.
    """
    # If we have state information beyond what function to use,
    # load the last seen cursor.
    if (len(self.groomer_state) > 1 and
      self.groomer_state[0] == self.CLEAN_TASKS_TASK):
      last_cursor = Cursor(self.groomer_state[1])
    else:
      last_cursor = None
    self.register_db_accessor(constants.DASHBOARD_APP_ID)
    timeout = datetime.datetime.utcnow() - \
      datetime.timedelta(seconds=self.TASK_NAME_TIMEOUT)

    counter = 0
    logger.debug("The current time is {0}".format(datetime.datetime.utcnow()))
    logger.debug("The timeout time is {0}".format(timeout))
    while True:
      query = TaskName.all()
      if last_cursor:
        query.with_cursor(last_cursor)
      query.filter("timestamp <", timeout)
      entities = query.fetch(self.BATCH_SIZE)
      if len(entities) == 0:
        break
      last_cursor = query.cursor()
      for entity in entities:
        logger.debug("Removing task name {0}".format(entity.timestamp))
        entity.delete()
        counter += 1
      if time.time() > self.last_logged + self.LOG_PROGRESS_FREQUENCY:
        logger.info('Removed {} task entities.'.format(counter))
        self.last_logged = self.LOG_PROGRESS_FREQUENCY
      self.update_groomer_state([self.CLEAN_TASKS_TASK, last_cursor])

    logger.info("Removed {0} task name entities".format(counter))
    return True

  def clean_up_entities(self):
    # If we have state information beyond what function to use,
    # load the last seen key.
    if (len(self.groomer_state) > 1 and
      self.groomer_state[0] == self.CLEAN_ENTITIES_TASK):
      last_key = self.groomer_state[1]
    else:
      last_key = ""
    while True:
      try:
        logger.debug('Fetching {} entities'.format(self.BATCH_SIZE))
        entities = self.get_entity_batch(last_key)

        if not entities:
          break

        for entity in entities:
          self.process_entity(entity)

        last_key = entities[-1].keys()[0]
        self.entities_checked += len(entities)
        if time.time() > self.last_logged + self.LOG_PROGRESS_FREQUENCY:
          logger.info('Checked {} entities'.format(self.entities_checked))
          self.last_logged = time.time()
        self.update_groomer_state([self.CLEAN_ENTITIES_TASK, last_key])
      except datastore_errors.Error, error:
        logger.error("Error getting a batch: {0}".format(error))
        time.sleep(self.DB_ERROR_PERIOD)
      except dbconstants.AppScaleDBConnectionError, connection_error:
        logger.error("Error getting a batch: {0}".format(connection_error))
        time.sleep(self.DB_ERROR_PERIOD)

  def register_db_accessor(self, app_id):
    """ Gets a distributed datastore object to interact with
        the datastore for a certain application.

    Args:
      app_id: The application ID.
    Returns:
      A distributed_datastore.DatastoreDistributed object.
    """
    ds_distributed = datastore_distributed.DatastoreDistributed(
      app_id, self.datastore_path)
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', ds_distributed)
    apiproxy_stub_map.apiproxy.RegisterStub('memcache',
      memcache_distributed.MemcacheService(app_id))
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
    # If we have state information beyond what function to use,
    # load the last seen cursor.
    if (len(self.groomer_state) > 1 and
      self.groomer_state[0] == self.CLEAN_LOGS_TASK):
      last_cursor = Cursor(self.groomer_state[1])
    else:
      last_cursor = None

    self.register_db_accessor(constants.DASHBOARD_APP_ID)
    if log_timeout:
      timeout = (datetime.datetime.utcnow() -
        datetime.timedelta(seconds=log_timeout))
      query = RequestLogLine.query(RequestLogLine.timestamp < timeout)
      logger.debug("The timeout time is {0}".format(timeout))
    else:
      query = RequestLogLine.query()
    counter = 0
    logger.debug("The current time is {0}".format(datetime.datetime.utcnow()))

    while True:
      entities, next_cursor, more = query.fetch_page(self.BATCH_SIZE,
        start_cursor=last_cursor)
      for entity in entities:
        logger.debug("Removing {0}".format(entity))
        entity.key.delete()
        counter += 1
      if time.time() > self.last_logged + self.LOG_PROGRESS_FREQUENCY:
        logger.info('Removed {} log entries.'.format(counter))
        self.last_logged = time.time()
      if more:
        last_cursor = next_cursor
        self.update_groomer_state([self.CLEAN_LOGS_TASK,
          last_cursor.urlsafe()])
      else:
        break
    logger.info("Removed {0} log entries.".format(counter))
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
      logger.debug("Result from kind stat query: {0}".format(str(entities)))
      for entity in entities:
        logger.debug("Removing kind {0}".format(entity))
        entity.delete()

      query = stats.GlobalStat.all()
      entities = query.run()
      logger.debug("Result from global stat query: {0}".format(str(entities)))
      for entity in entities:
        logger.debug("Removing global {0}".format(entity))
        entity.delete()
      logger.debug("Done removing old stats for app {0}".format(app_id))

  def update_namespaces(self, timestamp):
    """ Puts the namespace information into the datastore for applications to
        access.

    Args:
      timestamp: A datetime time stamp to know which stat items belong
        together.
    """
    for app_id in self.namespace_info.keys():
      ds_distributed = self.register_db_accessor(app_id)
      namespaces = self.namespace_info[app_id].keys()
      for namespace in namespaces:
        size = self.namespace_info[app_id][namespace]['size']
        number = self.namespace_info[app_id][namespace]['number']
        try:
          self.create_namespace_entry(namespace, size, number, timestamp)
        except (datastore_errors.BadRequestError,
                datastore_errors.InternalError) as error:
          logger.error('Unable to insert namespace info: {}'.format(error))

      logger.info("Namespace for {0} are {1}"\
        .format(app_id, self.namespace_info[app_id]))
      del ds_distributed

  def update_statistics(self, timestamp):
    """ Puts the statistics into the datastore for applications
        to access.

    Args:
      timestamp: A datetime time stamp to know which stat items belong
        together.
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
        try:
          self.create_kind_stat_entry(kind, size, number, timestamp)
        except (datastore_errors.BadRequestError,
                datastore_errors.InternalError) as error:
          logger.error('Unable to insert kind stat: {}'.format(error))

      try:
        self.create_global_stat_entry(app_id, total_size, total_number,
                                      timestamp)
      except (datastore_errors.BadRequestError,
              datastore_errors.InternalError) as error:
        logger.error('Unable to insert global stat: {}'.format(error))

      logger.info("Kind stats for {0} are {1}"\
        .format(app_id, self.stats[app_id]))
      logger.info("Global stats for {0} are total size of {1} with " \
        "{2} entities".format(app_id, total_size, total_number))
      logger.info("Number of hard deletes: {0}".format(self.num_deletes))
      del ds_distributed

  def update_groomer_state(self, state):
    """ Updates the groomer's internal state and persists the state to
    ZooKeeper.

    Args:
      state: A list of strings representing the ID of the task to resume along
        with any additional data about the task.
    """
    zk_data = self.GROOMER_STATE_DELIMITER.join(state)

    # We don't want to crash the groomer if we can't update the state.
    try:
      self.zoo_keeper.update_node(self.GROOMER_STATE_PATH, zk_data)
    except zk.ZKInternalException as zkie:
      logger.exception(zkie)
    self.groomer_state = state

  def run_groomer(self):
    """ Runs the grooming process. Loops on the entire dataset sequentially
        and updates stats, indexes, and transactions.
    """
    self.db_access = appscale_datastore_batch.DatastoreFactory.getDatastore(
      self.table_name)
    transaction_manager = TransactionManager(self.zoo_keeper.handle)
    self.ds_access = DatastoreDistributed(
      self.db_access, transaction_manager, zookeeper=self.zoo_keeper)
    index_manager = IndexManager(self.zoo_keeper.handle, self.ds_access)
    self.ds_access.index_manager = index_manager

    logger.info("Groomer started")
    start = time.time()

    self.reset_statistics()

    clean_indexes = [
      {
        'id': self.CLEAN_ASC_INDICES_TASK,
        'description': 'clean up ascending indices',
        'function': self.clean_up_indexes,
        'args': [datastore_pb.Query_Order.ASCENDING]
      },
      {
        'id': self.CLEAN_DSC_INDICES_TASK,
        'description': 'clean up descending indices',
        'function': self.clean_up_indexes,
        'args': [datastore_pb.Query_Order.DESCENDING]
      },
      {
        'id': self.CLEAN_KIND_INDICES_TASK,
        'description': 'clean up kind indices',
        'function': self.clean_up_kind_indices,
        'args': []
      }
    ]

    populate_scatter_prop = [
      {'id': self.POPULATE_SCATTER,
       'description': 'populate indexes with scatter property',
       'function': self.populate_scatter_prop,
       'args': []}
    ]

    tasks = [
      {
        'id': self.CLEAN_ENTITIES_TASK,
        'description': 'clean up entities',
        'function': self.clean_up_entities,
        'args': []
      },
      {
        'id': self.CLEAN_LOGS_TASK,
        'description': 'clean up old logs',
        'function': self.remove_old_logs,
        'args': [self.LOG_STORAGE_TIMEOUT]
      },
      {
        'id': self.CLEAN_TASKS_TASK,
        'description': 'clean up old tasks',
        'function': self.remove_old_tasks_entities,
        'args': []
      }
    ]

    index_state = self.db_access.get_metadata_sync(
      cassandra_interface.INDEX_STATE_KEY)
    if index_state != cassandra_interface.IndexStates.CLEAN:
      tasks.extend(clean_indexes)

    scatter_prop_state = self.db_access.get_metadata(
      cassandra_interface.SCATTER_PROP_KEY)
    if scatter_prop_state != cassandra_interface.ScatterPropStates.POPULATED:
      tasks.extend(populate_scatter_prop)

    groomer_state = self.zoo_keeper.get_node(self.GROOMER_STATE_PATH)
    logger.info('groomer_state: {}'.format(groomer_state))
    if groomer_state:
      self.update_groomer_state(
        groomer_state[0].split(self.GROOMER_STATE_DELIMITER))

    for task_number in range(len(tasks)):
      task = tasks[task_number]
      if (len(self.groomer_state) > 0 and self.groomer_state[0] != '' and
        self.groomer_state[0] != task['id']):
        continue
      logger.info('Starting to {}'.format(task['description']))
      try:
        task['function'](*task['args'])
        if task_number != len(tasks) - 1:
          next_task = tasks[task_number + 1]
          self.update_groomer_state([next_task['id']])
      except Exception as exception:
        logger.error('Exception encountered while trying to {}:'.
          format(task['description']))
        logger.exception(exception)

    self.update_groomer_state([])

    timestamp = datetime.datetime.utcnow().replace(microsecond=0)

    self.update_statistics(timestamp)
    self.update_namespaces(timestamp)

    del self.db_access
    del self.ds_access

    time_taken = time.time() - start
    logger.info("Groomer cleaned {0} journal entries".format(
      self.journal_entries_cleaned))
    logger.info("Groomer checked {0} index entries".format(
      self.index_entries_checked))
    logger.info("Groomer cleaned {0} index entries".format(
      self.index_entries_cleaned))
    logger.info('Groomer populated {} scatter property index entries'.format(
      self.scatter_prop_vals_populated))
    if self.index_entries_delete_failures > 0:
      logger.info("Groomer failed to remove {0} index entries".format(
        self.index_entries_delete_failures))
    logger.info("Groomer took {0} seconds".format(str(time_taken)))


def main():
  """ This main function allows you to run the groomer manually. """
  zk_connection_locations = appscale_info.get_zk_locations_string()
  retry_policy = KazooRetry(max_tries=5)
  zk_client = KazooClient(
    zk_connection_locations, connection_retry=ZK_PERSISTENT_RECONNECTS,
    command_retry=retry_policy)
  zk_client.start()
  zookeeper = zk.ZKTransaction(zk_client)
  db_info = appscale_info.get_db_info()
  table = db_info[':table']

  datastore_path = ':'.join([appscale_info.get_db_proxy(),
                             str(constants.DB_SERVER_PORT)])
  ds_groomer = DatastoreGroomer(zookeeper, table, datastore_path)

  logger.debug("Trying to get groomer lock.")
  if ds_groomer.get_groomer_lock():
    logger.info("Got the groomer lock.")
    try:
      ds_groomer.run_groomer()
    except Exception as exception:
      logger.exception('Encountered exception {} while running the groomer.'
        .format(str(exception)))
    try:
      ds_groomer.zoo_keeper.release_lock_with_path(zk.DS_GROOM_LOCK_PATH)
    except zk.ZKTransactionException, zk_exception:
      logger.error("Unable to release zk lock {0}.".\
        format(str(zk_exception)))
    except zk.ZKInternalException, zk_exception:
      logger.error("Unable to release zk lock {0}.".\
        format(str(zk_exception)))
    finally:
      zk_client.stop()
      zk_client.close()
  else:
    logger.info("Did not get the groomer lock.")
