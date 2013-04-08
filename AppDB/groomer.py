""" This process grooms the datastore cleaning up old state and 
calculates datastore statistics. Removes tombstoned items for garbage 
collection.
"""
import logging
import os
import sys
import threading
import time

#from google.appengine.ext import db
#from google.appengine.ext.db import stats
import appscale_datastore_batch
import dbconstants

from zkappscale import zktransaction as zk

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

class DatastoreGroomer(threading.Thread):
  """ Scans the entire database for each application. """
 
  # The amount of seconds between polling to get the groomer lock.
  LOCK_POLL_PERIOD = 3600

  # The number of entities retrieved in a datastore request.
  BATCH_SIZE = 100 

  def __init__(self, zoo_keeper, table_name):
    """ Constructor. 

    Args:
      zk: ZooKeeper client.
      table_name: The table used (cassandra, hypertable, etc).
    """
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
      '%(lineno)s %(message)s ', level=logging.DEBUG)
    logging.info("Logging started")

    threading.Thread.__init__(self)
    self.zoo_keeper = zoo_keeper
    self.table_name = table_name
    self.stats = {}

  def stop(self):
    """ Stops the groomer thread. """
    self.zoo_keeper.close()

  def run(self):
    """ Starts the main loop of the groomer thread. """
    while True:
      time.sleep(self.LOCK_POLL_PERIOD)
      if self.get_groomer_lock():
        self.run_groomer()

  def get_groomer_lock(self):
    """ Tries to acquire the lock to the datastore groomer. 
  
    Returns:
      True on success, False otherwise.
    """
    return self.zoo_keeper.get_datastore_groomer_lock()

  def get_entity_batch(self, db_access, last_key=""):
    """ Gets a batch of entites to operate on.

    Args:
      db_access: A DatastoreFactory object.
      last_key: The last key to continue from.
    Returns:
      A list of entities.
    """ 
    return db_access.range_query(dbconstants.APP_ENTITY_TABLE, 
      dbconstants.APP_ENTITY_SCHEMA, last_key, "", self.BATCH_SIZE,
      start_inclusive=False)

  def reset_statistics(self):
    """ Reinitializes statistics. """
    self.stats = {}

  def process_tombstone(self, key, entity, version):
    """ Processes any entities which have been soft deleted. 
        Does an actual delete to reclaim disk space.
    Args: 
      key: The key to the entity table.
      entity: The entity in string serialized form.
      version: The version of the entity in the datastore.
    Returns:
      True if a hard delete occurred, false otherwise.
    """
    return False

  def process_statistics(self, key, entity, version):
    """ Processes an entity and adds to the global statistics.
    Args: 
      key: The key to the entity table.
      entity: The entity in string serialized form.
      version: The version of the entity in the datastore.
    Returns:
      True on success, False otherwise. 
    """
    return True

  def txn_blacklist_cleanup():
    """ Clean up old transactions and removed unused references
        to reap storage.

    Returns:
      True on success, False otherwise.
    """
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
    entitiy = entity[key][dbconstants.APP_ENTITY_SCHEMA[0]]
    version = entity[key][dbconstants.APP_ENTITY_SCHEMA[1]]

    if entity == datastore_server.TOMBSTONE:
      return process_tombstone(key, entity, version)
       
    process_statistics(key, entity, version)

    return True

  def run_groomer(self):
    """ Runs the grooming process. Loops on the entire dataset sequentially
        and updates stats, indexes, and transactions.
    Returns:
      True on success, False otherwise.
    """
    logging.debug("Groomer started")
    last_key = ""
    self.reset_statistics()
    while True:
      db_access = appscale_datastore_batch.DatastoreFactory.getDatastore(
        self.table_name)
      entities = self.get_entity_batch(db_access, last_key=last_key)

      if not entities:
        break

      for entity in entities:
        self.process_entity(entity)

      last_key = entities[-1].keys()[0]

    logging.debug("Groomer stopped")
    return True


def main():
  """ This main function allows you to run the groomer manually. """
  zookeeper = zk.ZKTransaction(host="localhost:2181")
  db_info = appscale_info.get_db_info()
  table = db_info[':table']
  ds_groomer = DatastoreGroomer(zookeeper, table)
  try:
    ds_groomer.run_groomer()
  finally:
    zookeeper.close()

if __name__ == "__main__":
  main()
