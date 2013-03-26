""" This process grooms the datastore cleaning up old state and 
calculates datastore statistics. Removed tombstoned items for garbage 
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
      '%(lineno)s %(message)s ', level=logging.INFO)
    logging.info("Logging started")

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
    #ent = datastore_pb.EntityProto().ParseFromString(entity)
    #self.stats[ent.app
    print entity
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
        print entity
        self.process_entity(entity)
    logging.debug("Groomer stopped")
    return True


def main():
  """ This main function allows you to run the groomer manually. """
  zookeeper = zk.ZKTransaction(host="localhost:2181")
  db_info = appscale_info.get_db_info()
  table = db_info[':table']
  ds_groomer = DatastoreGroomer(zookeeper, table)
  ds_groomer.run_groomer()

if __name__ == "__main__":
  main()

