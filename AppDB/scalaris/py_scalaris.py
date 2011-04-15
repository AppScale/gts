#
# Scalaris Interface for AppScale
#
__author__="Yoshihide Nomura <nomura@pobox.com>"
__date__="$2009.6.9 19:44:00$"

import os,sys
import time
import string
import base64

from jsonrpc.proxy import ServiceProxy
import sqlalchemy.pool as pool
from dbinterface import *
from dhash_datastore import *
import appscale_logger

DETAILED_DEBUG = False
ERROR_DEFAULT = "DB_ERROR:"
TIMEOUT_RETRY = 20
DB_HOST = "localhost"
DB_PORT = 9001

class DatastoreProxy(DHashDatastore):

  def __init__(self, logger_ = appscale_logger.getLogger("datastore-scalaris")):
    DHashDatastore.__init__(self, logger_)
    self.host = DB_HOST
    self.port = DB_PORT
    #self.logger.debug("AppScalaris is created Host:%s:%d" % (self.host, self.port))
    self.pool = pool.QueuePool(self.__create_connection)

  def __create_connection(self):
    client = ServiceProxy("http://%s:%d/jsonrpc.yaws" % (self.host, self.port))
    return client

  def get_connection(self):
    return self.pool.connect()

  def close_connection(self, conn):
    if conn:
      conn.close()

  ######################################################################
  # Scalaris specific methods 
  ######################################################################    

  def get(self, key):
    if key == None:
      #self.logger.error("key is None")
      return None

    #self.logger.debug("get key: %s" % (key)) 
    req = [{"read":key}]

    timeoutcount = 0
    client = None
    ret = None
    try:
      client = self.get_connection()
      retry = True
      while retry and timeoutcount < TIMEOUT_RETRY:
        response = client.req_list(req)
        if DETAILED_DEBUG:
          self.logger.debug("raw response: %s" % response)

        for d in response['results']:
          if 'fail' in d and d['fail'] == 'not_found':
            retry = False
            break
          elif 'key' in d and d['key'] == key and not 'fail' in d:
            ret = d['value']
            retry = False
            break
        if not retry:
          break
        #self.logger.debug("retrying get %s" % key)
        time.sleep(0.1)
        timeoutcount += 1
    except Exception as e: 
      #self.logger.error("Exception occured in get: %s" % e)
      pass
    self.close_connection(client)
    return ret

  def put(self, key, value):
    if DETAILED_DEBUG:
      self.logger.debug("put key: %s" % (key)) 
      self.logger.debug("put value(%s)" % (value)) 
    if key == None or value == None: 
      self.logger.error("key or value is None")
      return 

    req = [{"write":{key:value}},{"commit":"commit"}]

    client = None
    try: 
      client = self.get_connection()
      retry = True
      timeoutcount = 0
      while retry and timeoutcount < TIMEOUT_RETRY:
        response = client.req_list(req)
        if DETAILED_DEBUG:
          self.logger.debug("raw response: %s" % response)
        
        for d in response['results']:
          if 'op' in d and d['op'] == 'commit' and 'key' in d and d['key'] == 'ok':
            retry = False
            break
        if not retry:
          break
        #self.logger.debug("retrying put %s" % key)
        time.sleep(0.1)
        timeoutcount += 1
    except Exception as e:
      #self.logger.error("Exception occurred in put: %s" % e);
      pass
    self.close_connection(client)

  def remove(self, key):
    #self.logger.debug("remove key: %s" % (key))
    req = [{"key":key}]
    client = None
    try:
      client = self.get_connection()
      retry = True
      timeoutcount = 0
      while retry and timeoutcount < TIMEOUT_RETRY:
        response = client.delete(key)
        if DETAILED_DEBUG:
          self.logger.debug("raw response: %s" % response)
        if 'ok' in response:
          retry = False
          break
        #self.logger.debug("retrying remove %s" % key)
        time.sleep(0.1)
        timeoutcount += 1
    except Exception as e:
      #self.logger.error("Exception occurred in remove: %s" % e)
      pass
    self.close_connection(client)
