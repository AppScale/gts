# Modified by Navraj Chohan to use rget and the dbinterface super class
#Programmer: Chris Bunch
#py_memcached.py: Implements the necessary API to allow Google App Engine apps to be run using the memcachedb database.
# interfaces largely lifted from Raj's py_hbase interface
# actual code largely lifted from Soo Hwan's py_voldemort interface

import base64
import memcachedb
import appscale_logger
from dbinterface import *
PROFILING = False
ENCODED = ["Encoded_Entity", "tar_ball"]

ERROR_DEFAULT = "DB_ERROR:" 
# Store all schema information in a special table
# If a table does not show up in this table, try a range query 
# to discover it's schema
SCHEMA_TABLE = "__key__"
SCHEMA_TABLE_SCHEMA = ['schema']

PERSISTENT_CONNECTION = False
PROFILING = True

DEFAULT_HOST = "localhost"
DB_PORT = 30000

MAX_ROW_COUNT = 10000000
table_cache = {}
class DatastoreProxy(AppDBInterface):
  def __init__(self, logger = appscale_logger.getLogger("datastore-memcachedb")):
    # TODO: is this correct?
    self.logger = logger

  def logTiming(self, function, start_time, end_time):
    if PROFILING:
      self.logger.debug(function + ": " + str(end_time - start_time) + " s")
  
  def get_entity(self, table_name, row_key, column_names):
    error = [ERROR_DEFAULT]
    elist = error
    row_key = table_name + '/' + row_key
    try: 
      result = self.get(row_key) 
      if result == None:
        elist[0]+= "Not Found"
        return elist
      c_dict = eval(result)
      for column in column_names:
        for r in c_dict:
          if column == r:
            value = c_dict[r]
            if r in ENCODED:
              value = base64.b64decode(value)
            elist.append(value)
    except Exception, ex:
      #self.logger.debug("Exception %s" % ex)
      elist[0]+=("Exception: %s"%ex)
      return elist
    if len(elist) == 1:
      elist[0] += "Not found"
    return elist


  def put_entity(self, table_name, row_key, column_names, cell_values):
    error = [ERROR_DEFAULT]
    elist = error
    dict_row = {}
    # The first time a table is seen
    if table_name not in table_cache:
      self.create_table(table_name, column_names)

    row_key = table_name + '/' + row_key
    # Get previous columns not in this put
    prev = self.get(row_key)
    if prev:
      prev = eval(prev)
      
    for ii in range(len(column_names)):
      column_name, value = column_names[ii], cell_values[ii]
      if column_name in ENCODED:
        value = base64.b64encode(value)
      dict_row[column_name] = value
    # fill in old values not being updated
    # This could be a race condition where all columns are
    # not updated
    if prev:
      for ii in prev:
        if ii not in column_names:
          dict_row[ii] = prev[ii]

    value = str(dict_row)
    try: 
      self.put(row_key, value)
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      elist[0]+=("Exception: %s"%ex)
      elist.append("0")
      return elist
    elist.append("0")
    return elist

  def put_entity_dict(self, table_name, row_key, value_dict):
    raise NotImplementedError("put_entity_dict is not implemented in %s." % self.__class__)


  def get_table(self, table_name, column_names):
    error = [ERROR_DEFAULT]  
    result = error
    start_key = table_name
    end_key = table_name + '~'
    try: 
      values = self.rget(start_key, end_key)
      print "RGET return:",
      print values
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      result[0] += "Exception: " + str(ex)
      return result
    # Convert to just values
    for ii in values:
      # take from a string dic to a value, decode tar's and entities
      # TODO verify
      value = values[ii]
      value = eval(value)
      for column in column_names:
        for c in values:
          # for ordering according to column_names
          if c == column:
            v = value[column]
            if c in ENCODED:
              v = base64.b64decode(v)
            result.append(v)
    return result

  def delete_row(self, table_name, row_key):
    error = [ERROR_DEFAULT]
    ret = error
    row_key = table_name + '/' + row_key
    try: 
      # Result is a column type which has name, value, timestamp
      self.remove(row_key)
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      ret[0]+=("Exception: %s"%ex)
      return ret 
    ret.append("0")
    return ret

  def get_schema(self, table_name):
    error = [ERROR_DEFAULT]
    result = error  
    ret = self.get_entity(SCHEMA_TABLE, 
                          table_name, 
                          SCHEMA_TABLE_SCHEMA)
    if len(ret) > 1:
      schema = ret[1]
    else:
      error[0] = ret[0] + "--unable to get schema"
      return error
    schema = schema.split(':')
    result = result + schema
    return result


  def delete_table(self, table_name):
    error = [ERROR_DEFAULT]  
    result = error
    keyslices = []
    start_key = table_name
    end_key = table_name + '~'
    try: 
      keyslices = self.rget(start_key, 
                              end_key)
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      result[0]+=("Exception: %s"%ex)
      return result
    keys_removed = False
    for row_key in keyslices:
      self.remove(row_key)
      keys_removed = True
    if table_name not in table_cache and not keys_removed:
      result[0] += "Table does not exist"
      return  result
    if table_name in table_cache:
      del table_cache[table_name]
 
    return result

  # Only stores the schema
  def create_table(self, table_name, column_names):
    table_cache[table_name] = 1
    columns = ':'.join(column_names)
    row_key = table_name
    # Get and make sure we are not overwriting previous schemas
    ret = self.get_entity(SCHEMA_TABLE, row_key, SCHEMA_TABLE_SCHEMA)
    print "Getting schema first:",ret
    print ret
    if ret[0] != ERROR_DEFAULT:
      print "making table..."
      print self.put_entity(SCHEMA_TABLE, row_key, SCHEMA_TABLE_SCHEMA, [columns])
     

  def __createConnection(self, db_location):
    return memcachedb.Client(["%s:%d" % (db_location, DB_PORT)], debug=0)

  def __createLocalConnection(self):
    return self.__createConnection(self.get_local_ip())

  def __createMasterConnection(self):
    return self.__createConnection(self.get_master_ip())


  def __closeConnection(self, conn):
    if conn:
      conn.disconnect_all()

  def get(self, key):
    self.logger.debug("getting [%s]" % key)
    if key is None:
      return None
    client = self.__createLocalConnection()
    key = key.encode()
    value = client.get(key)
    self.__closeConnection(client)
    return value

  def put(self, key, value):
    client = self.__createMasterConnection()
    key = key.encode()
    value = value.encode()
    result = client.set(key, value)
    self.logger.debug("set [%s],[%s] returned %s" % (str(key), str(value), str(result)))
    self.__closeConnection(client)
    return result

  def remove(self, key):
    client = self.__createMasterConnection()
    key = key.encode()
    result = client.delete(key)
    self.logger.debug("remove key [%s] returned [%s]" % (str(key), str(result)))
    self.__closeConnection(client)
    return result

  def rget(self, start, end):
    if start is None:
      return None
    if end is None:
      return None
    ret_dict = {}
    client = self.__createLocalConnection()
    start = start.encode()
    end = end.encode()
    print start, end
    values = client.rget(start, end, 0, 0, MAX_ROW_COUNT)
    print "client returned for rget:",values
    for ii in values:
      ret_dict[ii[0]] = ii[1] 
    self.__closeConnection(client)
    # VALUES NEED TO BE IN A key/value format
    return ret_dict

