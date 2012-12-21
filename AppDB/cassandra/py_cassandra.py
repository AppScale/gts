"""
Cassandra Interface for AppScale
"""

import base64   
import os
import pycassa
import sys
import time
import string

from dbconstants import *
from dbinterface import *
from pycassa.system_manager import *
from pycassa.cassandra.ttypes import NotFoundException

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import constants
import file_io

ERROR_DEFAULT = "DB_ERROR:" # ERROR_CASSANDRA
# Store all schema information in a special table
# If a table does not show up in this table, try a range query 
# to discover it's schema
SCHEMA_TABLE = "__key__"
SCHEMA_TABLE_SCHEMA = ['schema']
MAIN_TABLE = "Keyspace1"

PERSISTENT_CONNECTION = False
PROFILING = False

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9160

#CONSISTENCY_ZERO = 0 # don't use this for reads
CONSISTENCY_ONE = pycassa.cassandra.ttypes.ConsistencyLevel.ONE
CONSISTENCY_QUORUM = pycassa.cassandra.ttypes.ConsistencyLevel.QUORUM
#CONSISTENCY_ALL = 5 # don't use this for reads (next version may fix this)

MAX_ROW_COUNT = 10000000
table_cache = {}
class DatastoreProxy(AppDBInterface):
  def __init__(self):
    self.host = file_io.read_file(constants.APPSCALE_HOME + '/.appscale/my_private_ip')
    self.port = DEFAULT_PORT
    self.pool = pycassa.ConnectionPool(keyspace='Keyspace1', 
                           server_list=[self.host+":"+str(self.port)], 
                           prefill=False)
    sys = SystemManager(self.host + ":" + str(DEFAULT_PORT))
    try: 
      sys.create_column_family('Keyspace1', 
                               SCHEMA_TABLE, 
                               comparator_type=UTF8_TYPE)
    except Exception, e:
      print "Exception creating column family: %s"%str(e)
      pass


  def get_entity(self, table_name, row_key, column_names):
    error = [ERROR_DEFAULT]
    list = error
    row_key = table_name + '/' + row_key
    try:
      cf = pycassa.ColumnFamily(self.pool, 
                                string.replace(table_name, '-','a'))
      result = cf.get(row_key, columns=column_names)
      # Order entities by column_names 
      for column in column_names:
        list.append(result[column])
    except NotFoundException: 
      list[0] += "Not found"
      return list
    except Exception, ex:
      list[0]+=("Exception: %s"%ex)
      return list

    if len(list) == 1:
      list[0] += "Not found"
    return list

  def put_entity(self, table_name, row_key, column_names, cell_values):
    error = [ERROR_DEFAULT]
    list = error

    # The first time a table is seen
    if table_name not in table_cache:
      self.create_table(table_name, column_names)

    row_key = table_name + '/' + row_key
    cell_dict = {}
    for index, ii in enumerate(column_names):
      cell_dict[ii] = cell_values[index]

    try:
      # cannot have "-" in the column name
      cf = pycassa.ColumnFamily(self.pool, string.replace(table_name, '-','a'))
    except NotFoundException:
      print "Unable to find column family for table %s"%table_name
      list[0]+=("Exception: Column family not found for table %s"%table_name)
      return list

    cf.insert(row_key, cell_dict)
    list.append("0")
    return list

  def put_entity_dict(self, table_name, row_key, value_dict):
    raise NotImplementedError("put_entity_dict is not implemented in %s." % self.__class__)


  def get_table(self, table_name, column_names):
    error = [ERROR_DEFAULT]  
    result = error
    keyslices = []
    start_key = table_name + "/"
    end_key = table_name + '/~'
    try: 
      cf = pycassa.ColumnFamily(self.pool, string.replace(table_name, '-','a'))
      keyslices = cf.get_range(columns=column_names, 
                              start=start_key, 
                              finish=end_key)
      keyslices = list(keyslices)
    except pycassa.NotFoundException, ex:
      return result
    except Exception, ex:
      result[0] += "Exception: " + str(ex)
      return result
    # keyslices format is [key:(column1:val,col2:val2), key2...]
    for ii, entry in enumerate(keyslices):
      orddic = entry[1]
      ordering_dict = {}
      for col in orddic:
        val = orddic[col]
        ordering_dict[col] = val
        
      if len(ordering_dict) == 0:
        continue
      for column in column_names:
        try:
          result.append(ordering_dict[column])
        except:
          result[0] += "Key error, get_table did not return the correct schema"
    return result

  def delete_row(self, table_name, row_key):
    error = [ERROR_DEFAULT]
    ret = error
    row_key = table_name + '/' + row_key
    try: 
      cf = pycassa.ColumnFamily(self.pool, string.replace(table_name, '-','a'))
      # Result is a column type which has name, value, timestamp
      cf.remove(row_key)
    except Exception, ex:
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
    curtime = self.timestamp()
    start_key = table_name + "/"
    end_key = table_name + '/~'
    try: 
      cf = pycassa.ColumnFamily(self.pool, string.replace(table_name, '-','a'))
      cf.truncate()
      self.delete_row(SCHEMA_TABLE, row_key)
    except Exception, ex:
      result[0]+=("Exception: %s"%ex)
      return result
    if table_name not in table_cache:
      result[0] += "Table does not exist"
      return  result
    if table_name in table_cache:
      del table_cache[table_name]
    return result

  # Only stores the schema
  def create_table(self, table_name, column_names):
    if table_name == SCHEMA_TABLE:
      return  

    columns = ':'.join(column_names)
    row_key = table_name
    # Get and make sure we are not overwriting previous schemas
    ret = self.get_entity(SCHEMA_TABLE, row_key, SCHEMA_TABLE_SCHEMA)
    if ret[0] != ERROR_DEFAULT:
      sysman = SystemManager(self.host + ":" + str(DEFAULT_PORT))
      print "Creating column family %s"%table_name
      try:
        sysman.create_column_family('Keyspace1', string.replace(table_name, '-','a'), comparator_type=UTF8_TYPE)
        print "Done creating column family"
        self.put_entity(SCHEMA_TABLE, row_key, SCHEMA_TABLE_SCHEMA, [columns])
      except Exception, e:
        print "Unable to create column family %s"%str(e)
        return

    table_cache[table_name] = 1

  ######################################################################
  # private methods 
  ######################################################################
  def __setup_connection(self):
    return self.pool.get()

  def __close_connection(self, client):
    if client:
      self.pool.return_conn(client)

  def timestamp(self):
    return int(time.time() * 1000)
