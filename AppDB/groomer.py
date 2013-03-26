""" This process grooms the datastore cleaning up old state and 
calculates datastore statistics. Removed tombstoned items for garbage 
collection.
"""

import dbconstants
import threading
import time
#from google.appengine.ext import db
#from google.appengine.ext.db import stats
import appscale_datastore_batch

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
    threading.Thread.__init__(self)
    self.zoo_keeper = zoo_keeper
    self.table_name = table_name
    self.stats = {}

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
      dbconstants.APP_ENTITY_SCHEMA, last_key, "", self.BATCH_SIZE)

  def reset_statistics(self):
    """ Reinitializes statistics. """
    self.stats = {}

  def process_entity(self, entity):
    """ Processes an entity by updating statistics, indexes, and removes 
        tombstones.

    Args:
      entity: The entity to operate on. 
    Returns:
      True on success, False otherwise.
    """
    return True
 
  def run_groomer(self):
    """ Runs the grooming process. Loops on the entire dataset sequentially
        and updates stats, indexes, and transactions.
    Returns:
      True on success, False otherwise.
    """
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
    return True

