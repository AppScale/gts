# Abstract class for Distributed hash key type storage
# by NOMURA Yoshihide <nomura@pobox.com>

import os,sys
import base64
import time
from dbinterface import *
from dbconstants import *
import appscale_logger
import threading
import memcache
import memcache_mutex
import weakref
import cPickle as pickle

MAX_KEYS = 10000
KEY_REPOSITORY="__keys_" # special key for storing keys information. 
TABLE_PREFIX="__table_" # special keys for storing a table information. 
CREATE_LOCK_PREFIX="__create__"
GLOBAL_TABLES_KEY="__global_tables__"
SCHEMA_COLUMN="schema"
DEFAULT_VALUE="value"
ERROR_DEFAULT = "DB_ERROR:"
USE_MEMCACHED = True
# split key list into this number to improve multithread request throughput.
DEFAULT_KEYSIZE = 16

class DHashDatastore(AppDBInterface):

  # Override these methods in sub class.
  def __init__(self, logger = appscale_logger.getLogger("dhash")):
    self.logger = logger
    if USE_MEMCACHED:
      self.memcache_locations = self.__getMemcachedLocations()
      self.memcache = memcache.Client(self.memcache_locations, debug=0)
    else:
      self.lockhash = weakref.WeakValueDictionary()
    self.hashkey_size = DEFAULT_KEYSIZE

  def get(self, key):
    raise NotImplementedError("get is not implemented in %s." % self.__class__)
  def put(self, key, value):
    raise NotImplementedError("put is not implemented in %s." % self.__class__)
  def remove(self, key):
    raise NotImplementedError("remove is not implemented in %s." % self.__class__)

  # override this method if there is get all function.
  def get_all(self, keys):
    values = [self.get(key) for key in keys]
    return values

  def lock(self, table):
    # TODO: timeout should be needed.
    lock = None
#    print "lock %s" % table
    if USE_MEMCACHED:
      # Distributed version
      lock = memcache_mutex.MemcacheMutex(table, self.memcache)
      lock.acquire()
      return lock

    # Local lock version
    try:
      lock = self.lockhash[table]
      lock.acquire()
    except KeyError:
      lock = threading.Condition()
      self.lockhash[table] = lock
      lock.acquire()
    return lock

  def unlock(self, table, lock):
#    print "unlock %s" % table
    lock.release()
    # the lockhash will be cleared by gc

  def __getMemcachedLocations(self):
    """ This method returns list of memcached server.
    """
    locations = []
    try:
      f = open(APPSCALE_HOME + "/.appscale/all_ips", "r")
      for line in f.readlines():
        server = line.strip()
        if len(server) > 0:
          locations.append(server + ":11211")
      f.close()
    except IOError as e:
      # there is no all_ips file.
      self.logger.warn("Fail to read all_ips. Use localhost to connect memcached. %s" % str(e))
      locations.append("localhost:11211")
    return locations

  def get_entity(self, table_name, row_key, column_names):
    self.logger.debug("get_entity table:%s key:%s columns:%s" % (table_name, row_key, column_names)) 
    elist = [ERROR_DEFAULT]
    
    if None in [table_name, row_key, column_names]:
      self.logger.debug("get_entity error - there is None in parameters")
      return [ERROR_DEFAULT + "Not found"]

    internal_key = self.__make_internal_key(table_name, row_key)
    value = self.get(internal_key)

    try: 
      if not value:
        elist[0] += "Not found"
      else:
        row = pickle.loads(value) # change string to dict 
        for column in column_names:
          if column == "Encoded_Entity":
            elist.append(base64.b64decode(row[column]))
          else:
            elist.append(row[column])
    except Exception as e:
      self.logger.error("Exception: %s" % e)
      elist[0] += "Not found"

    return elist

  def put_entity(self, table_name, row_key, column_names, cell_values):
    self.logger.debug("put_entity table:%s key:%s" % (table_name, row_key))
    elist = [ERROR_DEFAULT] 
    if None in [table_name, row_key, column_names, cell_values]: 
      self.logger.debug("there is None in parameters")
      return [ERROR_DEFAULT + "Not found"]
      
    internal_key = self.__make_internal_key(table_name, row_key)
    
    if len(column_names) != len(cell_values):
      self.logger.debug( "Number of values does not match the number of columns")
      elist[0] += "Number of values does not match the number of columns" 
      return elist

    if not self.table_exist(table_name):
      lock = self.lock(CREATE_LOCK_PREFIX + table_name)
      if not self.table_exist(table_name):
#        print "creating table %s." % table_name
        self.create_table(table_name, column_names)
      self.unlock(CREATE_LOCK_PREFIX + table_name, lock)
    
    dict_row = {}
    # check if the key already has a record (for AppScale1.1)
    try:
      value = self.get(internal_key)
      if value:
        dict_row = pickle.loads(value)

      for i in range(len(column_names)):
        column_name, value = column_names[i], cell_values[i]
        if column_name == "Encoded_Entity":
          value = base64.b64encode(value)
        dict_row[column_name] = value

      self.put(internal_key, pickle.dumps(dict_row))
      self.add_key(row_key, table_name) 
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)

    elist.append("0")
    return elist

  def get_table(self, table_name, column_names):
    self.logger.debug("get_table table:%s columns:%s" % (table_name, column_names))
    elist = [ERROR_DEFAULT]
    if None in [table_name, column_names]: 
      self.logger.debug("None in parameters")
      return [ERROR_DEFAULT + "Not found"]

    keys_in_table = self.get_keys(table_name)
    if SCHEMA_COLUMN in keys_in_table:
      keys_in_table.remove(SCHEMA_COLUMN)
    values = self.get_entities(table_name, keys_in_table, column_names)
    if values[0] == ERROR_DEFAULT:
      elist.extend(values[1:])
    else:
      elist[0] = values[0]
#    for key in keys_in_table: 
#      values = self.get_entity(table_name, key, column_names)[1:]
      self.logger.debug("values: %s" % values)
      elist.extend(values)
    return elist

  def get_entities(self, table_name, row_keys, column_names):
#    st = time.time()
    elist = [ERROR_DEFAULT]

    if None in [table_name, row_keys, column_names]:
      self.logger.debug("get_entities error - there is None in parameters")
      elist[0] += "Not found"
      return elist

    internal_keys = [self.__make_internal_key(table_name, key) for key in row_keys]
    values = self.get_all(internal_keys)
    try:
      for value in values:
        if value is None:
          elist[0] += "Not found"
        else:
          row = pickle.loads(value) # change string to dict 
          for column in column_names:
            if column == "Encoded_Entity":
              elist.append(base64.b64decode(row[column]))
            else:
              elist.append(row[column])
    except TypeError as type:
      self.logger.debug("TypeError %s" % str(type))
      elist[0] += "Not found"
    except Exception as e:
      self.logger.debug("Exception %s" % str(e))
      elist[0] += "Not found"
    return elist

  def delete_row(self, table_name, row_id):
    self.logger.debug("delete_row table: %s row:%s" % (table_name, row_id))
    elist = [ERROR_DEFAULT]
    if None in [table_name, row_id]: 
      self.logger.debug("None in parameters")
      return [ERROR_DEFAULT + "Not found"]

    internal_key = self.__make_internal_key(table_name, row_id)
    if self.remove_key(row_id, table_name):
      self.remove(internal_key)
      return elist
    #else:
    elist.append("0")
    return elist

  def get_schema(self, table_name):
    self.logger.debug("get_schema: %s" % table_name) 
    elist = [ERROR_DEFAULT]
    try: 
      key = self.__make_internal_key(table_name, "schema")
      value = self.get(key)
      if value: 
        elist.extend(pickle.loads(value))
      else:
        elist[0] += "get_schema failed"
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      return [ERROR_DEFAULT + "Not found"]
    return elist

  def delete_table(self, table_name):
    self.logger.debug("delete table %s" % table_name)    
    elist = [ERROR_DEFAULT]
    lock = self.lock(CREATE_LOCK_PREFIX + table_name)
    if not self.table_exist(table_name):
      elist[0] += "table doesn't exist"
      self.unlock(CREATE_LOCK_PREFIX + table_name, lock)
      return elist
    keys_in_table = self.get_keys(table_name)
    for key in keys_in_table:
      self.delete_row(table_name, key)
    self.remove(self.__make_internal_key(table_name, "schema"))
    self.remove_key(table_name)
    self.unlock(CREATE_LOCK_PREFIX + table_name, lock)
    return elist

  ######################################################################
  # other methods 
  ######################################################################

  def get_row_count(self, table_name): 
    self.logger.debug("get_row_count table: %s" % (table_name))
    elist = [ERROR_DEFAULT]
    key_list = self.get_keys(table_name)
    elist.append(len(key_list) - 1) # list of keys in table and schema 
    return elist

  def get_row(self, table_name, key):
    self.logger.debug("get_row table: %s, key: %s" % (table_name, key))
    elist = [ERROR_DEFAULT]
    try: 
      schema = self.get_schema(table_name)[1:]
      internal_key = self.__make_internal_key(table_name, key)
      value = self.get(internal_key)
      if not value:
        elist[0] += "Not exist"
      else:
        row = pickle.loads(value) # change string to dict 
        for column in schema:
          elist.append(row[column])
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      return [ERROR_DEFAULT + "Not exist"]
    return elist

  def get_keys(self, tablename = GLOBAL_TABLES_KEY):
    ret = []
    for i in range(0, self.hashkey_size):
      key_list = self.get_keys_list(tablename + str(i))
      if key_list:
        ret.extend(key_list)
    return ret

  def get_keys_list(self, tablename = GLOBAL_TABLES_KEY):
    key_name = KEY_REPOSITORY + tablename
    value = self.get(key_name)
    if value:
      try:
        key_list = pickle.loads(value)
        if isinstance(key_list, list):
          return key_list
      except TypeError, detail:
        self.logger.error("get_keys exception: %s" % detail)
    return []

  def put_keys_list(self, key_list, tablename = GLOBAL_TABLES_KEY):
    try:
      key_name = KEY_REPOSITORY + tablename
      self.put(key_name, pickle.dumps(key_list))
    except:
      self.logger.error("fail to put keys")
      return False
    return True

  def add_key(self, key, orgtablename = GLOBAL_TABLES_KEY):
    tablename = orgtablename + str(hash(key) % self.hashkey_size)
#    print "add_key: %s for %s" % (key, orgtablename)
    lock = self.lock(tablename)
    if not lock:
      return False
    key_list = self.get_keys_list(tablename)
    if key in key_list:
      ret = False
    else:
      key_list.append(key)
      ret = self.put_keys_list(key_list, tablename)
    self.unlock(tablename, lock)
    return ret

  def remove_key(self, key, orgtablename = GLOBAL_TABLES_KEY):
    tablename = orgtablename + str(hash(key) % self.hashkey_size)
#    print "remove_key: %s for %s" % (key, orgtablename)
    lock = self.lock(tablename)
    if not lock:
      return False
    key_list = self.get_keys_list(tablename)
    if key in key_list:
      key_list.remove(key)
      ret = self.put_keys_list(key_list, tablename)
    else:
      ret = False
    self.unlock(tablename, lock)
    return ret

  def __make_internal_key(self, table_name, key): 
    if None in [table_name, key]:
      self.logger.debug("make_internal_key: None in parameters")
      return TABLE_PREFIX + "garbage_key"
    return TABLE_PREFIX + table_name + "_" + key 

  def create_table(self, table_name, schema):
    elist = [ERROR_DEFAULT]
    key = self.__make_internal_key(table_name, "schema")
    self.put(key, pickle.dumps(schema))
    self.add_key(table_name) 
    self.add_key("schema", table_name) 
    return elist

  def table_exist(self, table_name): 
    key = self.__make_internal_key(table_name, "schema")
    if self.get(key):
      return True
    else:
      return False
