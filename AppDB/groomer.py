""" This process grooms the datastore cleaning up old state and 
calculates datastore statistics. Removes tombstoned items for garbage 
collection.
"""
import logging
import os
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

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

class DatastoreGroomer(threading.Thread):
  """ Scans the entire database for each application. """
 
  # The amount of seconds between polling to get the groomer lock.
  LOCK_POLL_PERIOD = 3600

  # The number of entities retrieved in a datastore request.
  BATCH_SIZE = 100 

  # Any kind that is of __*__ is protected and should not have 
  # stats.
  PROTECTED_KINDS = '__(.*)__'

  def __init__(self, zoo_keeper, table_name, ds_path):
    """ Constructor. 

    Args:
      zk: ZooKeeper client.
      table_name: The table used (cassandra, hypertable, etc).
      ds_path: The connection string to the datastore.
    """
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
      '%(lineno)s %(message)s ', level=logging.DEBUG)
    logging.info("Logging started")

    threading.Thread.__init__(self)
    self.zoo_keeper = zoo_keeper
    self.table_name = table_name
    self.datastore_path = ds_path
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
    if not kind:
      logging.warning("Entity did not have a kind {0}"\
        .format(entity))
      return False

    if re.match(self.PROTECTED_KINDS, kind):
      return True

    app_id = ent_proto.key().app()
    if not app_id:
      logging.warning("Entity of kind {0} did not have an app id"\
        .format(kind))
      return False

    self.initialize_kind(app_id, kind) 

    all_kinds = self.stats[app_id] 
    self.stats[app_id][kind]['size'] += len(entity)
    self.stats[app_id][kind]['number'] += 1
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
    one_entity = entity[key][dbconstants.APP_ENTITY_SCHEMA[0]]
    version = entity[key][dbconstants.APP_ENTITY_SCHEMA[1]]

    if one_entity == datastore_server.TOMBSTONE:
      return self.process_tombstone(key, one_entity, version)
       
    self.process_statistics(key, one_entity, version)

    return True

  def create_kind_stat_entry(self, app_id, kind, size, number):
    """ Puts a kind statistic into the datastore.
 
    Args:
      app_id: The application ID.
      kind: The entity kind.
      size: An int on the number of bytes taken by the given kind.
      number: The total number of entities.
    """
    kind_stat = KindStat(kind_name=kind, 
                         bytes=size,
                         count=number,
                         timestamp=datetime.datetime.now())
    kind_stat.put()

  # TODO
  #def create_global_stat_entry(self, app_id, size)

  def get_db_accessor(self, app_id):
    """ Gets a distributed datastore object to interact with
        the datastore for a certain application.

    Args:
      app_id: The application ID.
    Returns:
      A distributed_datastore.DatastoreDistributed object.
    """
    db = datastore_distributed.DatastoreDistributed(app_id, 
      self.datastore_path, False, False)
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', db)
    os.environ['APPLICATION_ID'] = app_id
    return db

  def remove_old_statistics(self):
    """ Does a range query on the current batch of statistics and 
        deletes them.
    """
    for app_id in self.stats.keys():
      db = self.get_db_accessor(app_id) 
      query = db.stats.KindStat.all()
      entities = query.run()
      for entity in entities:
        logging.debug("Removing kind {0}".format(entity))
        entity.delete()

  def update_statistics(self):
    """ Puts the statistics into the datastore for applications
        to access.
    """
    self.remove_old_statistics()
    for app_id in self.stats.keys():
      kinds = app_id.keys()
      for kind in kinds:
        size = kinds[kind]['size']
        number = kinds[kind]['number']
        create_kind_stat_entry(app_id, kind, size, number)

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
  
    try: 
      self.update_statistics()
    except Exception, exception:
      #TODO do not do a catch all
      logging.info("Error updating statistics {0}".format(str(exception)))

    logging.debug("Groomer stopped")
    return True

def main():
  """ This main function allows you to run the groomer manually. """
  zookeeper = zk.ZKTransaction(host="localhost:2181")
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
