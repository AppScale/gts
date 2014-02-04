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

from zkappscale import zktransaction as zk

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_distributed
from google.appengine.datastore import entity_pb
from google.appengine.ext import db
from google.appengine.ext.db import stats
from google.appengine.ext.db import metadata
from google.appengine.api import datastore_errors

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info
import constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppTaskQueue/"))
from distributed_tq import TaskName

class DatastoreGroomer(threading.Thread):
  """ Scans the entire database for each application. """
 
  # The amount of seconds between polling to get the groomer lock.
  LOCK_POLL_PERIOD = 24 * 60 * 60

  # The number of entities retrieved in a datastore request.
  BATCH_SIZE = 100 

  # Any kind that is of __*__ is private and should not have stats.
  PRIVATE_KINDS = '__(.*)__'

  # Any kind that is of _*_ is protected and should not have stats.
  PROTECTED_KINDS = '_(.*)_'
  
  # The amount of time in seconds before we want to clean up task name holders.
  TASK_NAME_TIMEOUT = 24 * 60 * 60

  # Do not generate stats for AppScale internal apps.
  APPSCALE_APPLICATIONS = ['apichecker', 'appscaledashboard']

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
    self.datastore_path = ds_path
    self.stats = {}
    self.namespace_info = {}
    self.num_deletes = 0

  def stop(self):
    """ Stops the groomer thread. """
    self.zoo_keeper.close()

  def run(self):
    """ Starts the main loop of the groomer thread. """
    while True:
      time.sleep(random.randint(1, self.LOCK_POLL_PERIOD))
      logging.info("Trying to get groomer lock.")
      if self.get_groomer_lock():
        logging.info("Got the groomer lock.")
        self.run_groomer()
        try:
          self.zoo_keeper.release_datastore_groomer_lock()
        except zk.ZKTransactionException, zk_exception:
          logging.error("Unable to release zk lock {0}.".\
            format(str(zk_exception)))
      else:
        logging.info("Did not get the groomer lock.")

  def get_groomer_lock(self):
    """ Tries to acquire the lock to the datastore groomer. 
  
    Returns:
      True on success, False otherwise.
    """
    return self.zoo_keeper.get_datastore_groomer_lock()

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
      logging.error("Error hard deleting key {0}".format(row_key))
      return False 
    except Exception, exception:
      logging.error("Caught unexcepted exception {0}".format(exception))
      return False
 
    return True

  @staticmethod
  def get_root_key_from_entity_key(key):
    """ Extract the root key from an entity key. We 
        remove any excess children from a string to get to
        the root key.
    
    Args:
      entity_key: A string representing a row key.
    Returns:
      The root key extracted from the row key.
    """
    tokens = key.split(dbconstants.KIND_SEPARATOR)
    return tokens[0] + dbconstants.KIND_SEPARATOR

  @staticmethod
  def get_prefix_from_entity_key(entity_key):
    """ Extracts the prefix from a key to the entity table.

    Args:
      entity_key: A str representing a row key to the entity table.
    Returns:
      A str representing the app prefix (app_id and namespace).
    """
    tokens = entity_key.split(dbconstants.KEY_DELIMITER)
    return tokens[0] + dbconstants.KEY_DELIMITER + tokens[1]

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
    app_prefix = DatastoreGroomer.get_prefix_from_entity_key(key)
    root_key = DatastoreGroomer.get_root_key_from_entity_key(key)
    
    if self.zoo_keeper.is_blacklisted(app_prefix, version):
      return False
 
    txn_id = self.zoo_keeper.get_transaction_id(app_prefix)
    try:
      if self.zoo_keeper.acquire_lock(app_prefix, txn_id, root_key):
        success = self.hard_delete_row(key)
      else:
        success = False
    except zk.ZKTransactionException, zk_exception:
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
        # the hard delete has already happened.
        pass

    if success:
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
      self.stats[app_id][namespace] = {'size': 0, 'number': 0}

  def process_statistics(self, key, entity, version):
    """ Processes an entity and adds to the global statistics.

    Args: 
      key: The key to the entity table.
      entity: The entity in string serialized form.
      version: The version of the entity in the datastore.
    Returns:
      True on success, False otherwise. 
    """
    ent_proto = entity_pb.EntityProto() 
    ent_proto.ParseFromString(entity)
    kind = datastore_server.DatastoreDistributed.\
      get_entity_kind(ent_proto.key())
    namespace = ent_proto.key().name_space()

    if not kind:
      logging.warning("Entity did not have a kind {0}"\
        .format(entity))
      return False

    if re.match(self.PROTECTED_KINDS, kind):
      return True

    if re.match(self.PRIVATE_KINDS, kind):
      return True

    app_id = ent_proto.key().app()
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
    self.namespace_info[app_id][namespace]['size'] += len(entity)
    self.namespace_info[app_id][namespace]['number'] += 1
    self.stats[app_id][kind]['size'] += len(entity)
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
    logging.debug("Process entity {0}".format(str(entity)))
    key = entity.keys()[0] 
    one_entity = entity[key][dbconstants.APP_ENTITY_SCHEMA[0]]
    version = entity[key][dbconstants.APP_ENTITY_SCHEMA[1]]

    logging.debug("Entity value: {0}".format(entity))
    if one_entity == datastore_server.TOMBSTONE:
      return self.process_tombstone(key, one_entity, version)
       
    self.process_statistics(key, one_entity, version)

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
    timeout = datetime.datetime.now() - \
      datetime.timedelta(seconds=self.TASK_NAME_TIMEOUT)
    query = TaskName.all()
    query.filter("timestamp <", timeout)
    entities = query.run()
    counter = 0
    logging.info("The current time is {0}".format(datetime.datetime.now()))
    logging.info("The timeout time is {0}".format(timeout))
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
    os.environ['APPLICATION_ID'] = app_id
    os.environ['AUTH_DOMAIN'] = "appscale.com"
    return ds_distributed

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
    logging.info("Groomer started")
    start = time.time()
    last_key = ""
    self.reset_statistics()

    self.db_access = appscale_datastore_batch.DatastoreFactory.getDatastore(
      self.table_name)

    while True:
      entities = self.get_entity_batch(last_key)

      if not entities:
        break

      for entity in entities:
        self.process_entity(entity)

      last_key = entities[-1].keys()[0]

    timestamp = datetime.datetime.now()

    if not self.update_statistics(timestamp):
      logging.error("There was an error updating the statistics")

    if not self.update_namespaces(timestamp):
      logging.error("There was an error updating the namespaces")

    self.remove_old_tasks_entities()

    del self.db_access

    time_taken = time.time() - start
    logging.info("Groomer stopped (Took {0} seconds)".format(str(time_taken)))

def main():
  """ This main function allows you to run the groomer manually. """
  zk_connection_locations = appscale_info.get_zk_locations_string()
  zookeeper = zk.ZKTransaction(host=zk_connection_locations)
  datastore_path = "localhost:8888"
  db_info = appscale_info.get_db_info()
  table = db_info[':table']
  ds_groomer = DatastoreGroomer(zookeeper, table, datastore_path)
  try:
    ds_groomer.run_groomer()
  finally:
    zookeeper.close()

if __name__ == "__main__":
  main()
