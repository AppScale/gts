#
# Voldemort Interface for AppScale
#
# Modified by Chris Bunch to use new non-Thrift interface
# for 0.80 RC1 on 2/17/10

__author__="Soo Hwan Park (suwanny@gmail.com)"
__date__="$2009.6.9 19:44:00$"

import os,sys
import string
import base64   # base64    2009.04.16
import logging
import time

#from voldemort import StoreConfig
from voldemort_client.voldemort import StoreClient
from dbinterface import *
from dhash_datastore import *
import sqlalchemy.pool as pool
import appscale_logger

ERROR_DEFAULT = "DB_ERROR:" # ERROR_VOLDEMORT

# use 1 Table and 1 ColumnFamily in Cassandra
STORE = "appscale"
MAX_RETRIES = 3

DB_HOST = "localhost"
DB_PORT = 6666
RETRY_TIMEOUT = 100

class DatastoreProxy(DHashDatastore):

  def __init__(self, logger_ = appscale_logger.getLogger("datastore-voldemort")):
#    self.__host = 'localhost'
#    self.__port = 9090
    DHashDatastore.__init__(self, logger_)
    self.__store = STORE
    #self.logger.debug("AppVoldemort is created")
    self.pool = pool.QueuePool(self.__create_connection)

  ######################################################################
  # voldemort specific methods 
  ######################################################################    

  def get(self, key):
    done = False
    timeout = RETRY_TIMEOUT
    while (done != True and timeout > 0):
      try:
        value = self.real_get(key)
        done = True
      except:
        timeout -= 1
    if timeout <= 0:
      raise
    return value

  def real_get(self, key):
    if key == None:
      #self.logger.debug("key is None")
      return None

    client = None
    try: 
      client = self.__setup_connection()
      value = client.get(key)
    except Exception as e:
      #print "real_get: Exception occurred", e
      self.__close_connection(client)
      raise

    if value == []:
      value = None
    else:
      value = value[0][0]
    #self.logger.debug("get key returned [%s]" % (str(value)))
    self.__close_connection(client)
    return value

  # this seems not working right now.

  def get_all_org(self, key_list):
    done = False
    timeout = RETRY_TIMEOUT
    while (done != True and timeout > 0):
      try:
        values = self.real_get_all(key_list)
        done = True
      except:
        timeout -= 1
    if timeout <= 0:
      raise
    return values

  def real_get_all(self, key_list):
    if key_list == None:
      #self.logger.debug("key is None")
      return []

    client = None
    try: 
      client = self.__setup_connection()
      key_vals = client.get_all(key_list)
    except Exception as e:
      #print "real_get_all: Exception occurred", e
      self.__close_connection(client)
      raise

    values = [key_vals[key] for key in key_list]
    #values = key_vals[0][0]
    #self.logger.debug("get all key returned [%s]" % (str(values)))
    self.__close_connection(client)
    return values

  def put(self, key, value):
    done = False
    timeout = RETRY_TIMEOUT
    #print "Voldemort Put, key and value:",key,value
    while (done != True):
      try:
        self.real_put(key, value)
        done = True
      except:
        timeout -= 1
      if timeout <= 0:
        raise 

  def real_put(self, key, value):
    #self.logger.debug("put key(%s)" % (key)) 
    #self.logger.debug("put value(%s)" % (value)) 
    if key == None or value == None: 
      #self.logger.debug("key or value is None")
      return 

    client = None
    try: 
      client = self.__setup_connection()
      client.put(key, value)
    except Exception as e:
      #print "real_put: Exception occurred", e
      self.__close_connection(client)
      raise
    self.__close_connection(client)

  def remove(self, key):
    done = False
    timeout = 100
    while (done != True):
      try:
        self.real_remove(key)
        done = True
      except Exception as e:
        timeout -= 1

  def real_remove(self, key):
    #self.logger.debug("remove key(%s)" % (key)) 
    client = None
    try:
      client = self.__setup_connection()
      client.delete(key)
    except Exception as e:
      #print "Exception occurred", e
      self.__close_connection(client)
      raise
    self.__close_connection(client)

  ######################################################################
  # private methods 
  ######################################################################

  def __create_connection(self):
    return StoreClient(STORE, [(DB_HOST, DB_PORT)])

  def __setup_connection(self):
    return self.pool.connect()

  def __close_connection(self, conn):
    if conn:
      conn.close()
