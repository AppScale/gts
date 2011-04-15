# Programmer: Chris Bunch
# uses the amazing boto library to provide an interface to
# simpledb for google app engine apps

import base64
import boto
import logging
import logging.handlers
import time
import sys
from dhash_datastore import *
import sqlalchemy.pool as pool
import appscale_logger

PROFILING = True
APPSCALE_DOMAIN = "appscale"

ACCESS_KEY = os.environ.get("SIMPLEDB_ACCESS_KEY")
if ACCESS_KEY:
  pass
else:
  print "SIMPLEDB_ACCESS_KEY env var not set"
  exit(1)

SECRET_KEY = os.environ.get("SIMPLEDB_SECRET_KEY")
if SECRET_KEY:
  pass
else:
  print "SIMPLEDB_SECRET_KEY env var not set"
  exit(1)

class DatastoreProxy(DHashDatastore):
  def __init__(self, logger = appscale_logger.getLogger("datastore-simpledb")):
    DHashDatastore.__init__(self, logger)
    self.conn = boto.connect_sdb(ACCESS_KEY, SECRET_KEY)
    self.domain = self.conn.get_domain(APPSCALE_DOMAIN)

  def logTiming(self, function, start_time, end_time):
    if PROFILING:
      self.logger.info("%s: %s s" % (function,str(end_time - start_time)))

  """

  basic simple functions - initconnection, get, set, etc

  """

  def get(self, key):
    st = time.time()
    #self.logger.debug("getting [%s]" % key)
    if key is None:
      return None
    #key = key.encode()

    item = self.conn.get_attributes(APPSCALE_DOMAIN, key, 'value')

    #item = self.domain.get_item(key)

    if item:
      value = str(item['value'])
    else:
      value = None

    et = time.time()
    self.logTiming("get", st, et)

    #value = str(item['value'])
    #value = str(item[key))

    return value

  def put(self, key, value):
    st = time.time()
    #key = key.encode()
    #value = value.encode()

    """
    row = self.domain.new_item(key)
    row[key] = value
    result = row.save()"""

    attrs = {'value':value}
    result = self.conn.put_attributes(APPSCALE_DOMAIN, key, attrs)

    #self.logger.debug("set [%s],[%s] returned [%s]" % (str(key), str(value), str(result)))

    et = time.time()
    self.logTiming("put", st, et)
    return result

  def remove(self, key):
    st = time.time()
    #key = key.encode()

    """
    item = self.domain.get_item(key)
    result = self.domain.delete_item(item)

    """

    result = self.conn.delete_attributes(APPSCALE_DOMAIN, key)

    #self.logger.debug("remove key [%s] returned [%s]" % (str(key), str(result)))
    et = time.time()
    self.logTiming("delete", st, et)
    return result

  def get_all(self, key_list):
    # TODO: consider making one connection here and reusing it
    # or just get the connection pooling working
    #key_list = [key.encode() for key in key_list]

    st = time.time()
    vals = []
    for key in key_list:
      vals.append(self.get(key))

    #self.logger.debug("get multi [%s] returned [%s]" % (str(key_list), str(vals)))
    et = time.time()
    self.logTiming("query", st, et)
    return vals

