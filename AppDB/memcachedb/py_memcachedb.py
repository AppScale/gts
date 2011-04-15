#Programmer: Chris Bunch
#py_memcached.py: Implements the necessary API to allow Google App Engine apps to be run using the memcachedb database.
# interfaces largely lifted from Raj's py_hbase interface
# actual code largely lifted from Soo Hwan's py_voldemort interface

import base64
import memcachedb
import logging
import logging.handlers
import time
import sys
from dhash_datastore import *
import sqlalchemy.pool as pool
import appscale_logger
import hashlib

PROFILING = True
DB_LOCATION = "localhost"
DB_PORT = 30000
# Use md5 key instead of real key.
# Hashkey doesn't have key length restriction,
# but there is a possibility of key conflict.
USE_HASHKEY = False

class DatastoreProxy(DHashDatastore):
  def __init__(self, logger = appscale_logger.getLogger("datastore-memcachedb")):
    DHashDatastore.__init__(self, logger)
  #  self.pool = pool.SingletonThreadPool(self.__createConnection, echo=True)
#    self.localpool = pool.QueuePool(self.__createLocalConnection)
#    self.masterpool = pool.QueuePool(self.__createMasterConnection)
    self.masterclient = self.__createMasterConnection()
    self.localclient = self.__createLocalConnection()

  def logTiming(self, function, start_time, end_time):
    if PROFILING:
      self.logger.info("%s: %s s" % (function,str(end_time - start_time)))

  """

  basic memcachedb functions - initconnection, get, set, etc

  """

  def __createConnection(self, db_location):
    return memcachedb.Client(["%s:%d" % (db_location, DB_PORT)], debug=0)

  def __createLocalConnection(self):
    return self.__createConnection(self.get_local_ip())

  def __createMasterConnection(self):
    return self.__createConnection(self.get_master_ip())

  def __getLocalConnection(self):
    return self.localclient
#    return self.localpool.connect()

  def __getMasterConnection(self):
    return self.masterclient
#    return self.masterpool.connect()

  def __closeConnection(self, conn):
    pass
#    if conn:
#      conn.close()

  def __encodekey(self, key):
    if USE_HASHKEY:
      # create hash key from actual key.
      m = hashlib.md5()
      m.update(key)
      return m.hexdigest()
    else:
      return key.encode()

  def get(self, key):
    st = time.time()

    self.logger.debug("getting [%s]" % key)
    if key is None:
      value = None
    else:
      client = self.__getLocalConnection()
      key = self.__encodekey(key)
      value = client.get(key)
      self.__closeConnection(client)

    et = time.time()
    self.logTiming("get", st, et)

    return value

  def put(self, key, value):
    st = time.time()

    client = self.__getMasterConnection()
    key = self.__encodekey(key)
    value = value.encode()
    result = client.set(key, value)
    self.logger.debug("set [%s],[%s] returned %s" % (str(key), str(value), str(result)))
    self.__closeConnection(client)
 
    et = time.time()
    self.logTiming("put", st, et)

    return result

  def remove(self, key):
    st = time.time()

    client = self.__getMasterConnection()
    key = self.__encodekey(key)
    result = client.delete(key)
    self.logger.debug("remove key [%s] returned [%s]" % (str(key), str(result)))
    self.__closeConnection(client)

    et = time.time()
    self.logTiming("delete", st, et)
 
    return result

  def get_all(self, key_list):
    st = time.time()

    client = self.__getLocalConnection()
    key_list = [self.__encodekey(key) for key in key_list]
    key_vals = client.get_multi(key_list)
    result = [key_vals[key] for key in key_list]
    self.logger.debug("get multi [%s] returned [%s]" % (str(key_list), str(result)))
    self.__closeConnection(client)

    et = time.time()

    self.logTiming("query", st, et)

    return result
