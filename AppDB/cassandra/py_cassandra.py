#
# Cassandra Interface for AppScale
# Rewritten by Navraj Chohan for using range queries
# Modified by Chris Bunch for upgrade to Cassandra 0.50.0
# on 2/17/10
# Original author: suwanny@gmail.com

import os,sys
import time

from thrift_cass.Cassandra import Client
from thrift_cass.ttypes import *

import string
import base64   # base64    2009.04.16
from dbconstants import *
from dbinterface import *
import sqlalchemy.pool as pool
import appscale_logger

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
ERROR_DEFAULT = "DB_ERROR:" # ERROR_CASSANDRA
# Store all schema information in a special table
# If a table does not show up in this table, try a range query 
# to discover it's schema
SCHEMA_TABLE = "__key__"
SCHEMA_TABLE_SCHEMA = ['schema']
# use 1 Table and 1 ColumnFamily in Cassandra
MAIN_TABLE = "Keyspace1"
COLUMN_FAMILY = "Standard1"

PERSISTENT_CONNECTION = False
PROFILING = False

DEFAULT_HOST = "localhost"
DEFAULT_PORT = 9160

CONSISTENCY_ZERO = 0 # don't use this for reads
CONSISTENCY_ONE = 1
CONSISTENCY_QUORUM = 2
CONSISTENCY_ALL = 5 # don't use this for reads (next version may fix this)

MAX_ROW_COUNT = 10000000
table_cache = {}
class DatastoreProxy(AppDBInterface):
  def __init__(self, logger = appscale_logger.getLogger("datastore-cassandra")):
    f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
    self.host = f.read()
    self.port = DEFAULT_PORT
    self.pool = pool.QueuePool(self.__create_connection, reset_on_return=False)
    self.logger = logger

  def logTiming(self, function, start_time, end_time):
    if PROFILING:
      self.logger.debug(function + ": " + str(end_time - start_time) + " s")
  
  def get_entity(self, table_name, row_key, column_names):
    error = [ERROR_DEFAULT]
    list = error
    client = None
    row_key = table_name + '/' + row_key
    try: 
      slice_predicate = SlicePredicate(column_names=column_names)
      path = ColumnPath(COLUMN_FAMILY)
      client = self.__setup_connection()
      # Result is a column type which has name, value, timestamp
      result = client.get_slice(MAIN_TABLE, row_key, path, slice_predicate,
                                 CONSISTENCY_QUORUM) 
      for column in column_names:
        for r in result:
          c = r.column
          if column == c.name:
            list.append(c.value)
    except NotFoundException: # occurs normally if the item isn't in the db 
      list[0] += "Not found"
      self.__close_connection(client)
      return list
    except Exception, ex:
      #self.logger.debug("Exception %s" % ex)
      list[0]+=("Exception: %s"%ex)
      self.__close_connection(client)
      return list
    self.__close_connection(client)
    if len(list) == 1:
      list[0] += "Not found"
    return list


  def put_entity(self, table_name, row_key, column_names, cell_values):
    error = [ERROR_DEFAULT]
    list = error
    client = None

    # The first time a table is seen
    if table_name not in table_cache:
      self.create_table(table_name, column_names)

    row_key = table_name + '/' + row_key
    try: 
      client = self.__setup_connection()
      curtime = self.timestamp()
      # Result is a column type which has name, value, timestamp
      mutations = []
      for index, ii in enumerate(column_names):
        column = Column(name = ii, value=cell_values[index],
                      timestamp=curtime)
        c_or_sc = ColumnOrSuperColumn(column=column)
        mutation = Mutation(column_or_supercolumn=c_or_sc)
        mutations.append(mutation)
      mutation_map = {row_key : { COLUMN_FAMILY : mutations } }
      client.batch_mutate(MAIN_TABLE, mutation_map,
                               CONSISTENCY_QUORUM) 
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      list[0]+=("Exception: %s"%ex)
      self.__close_connection(client)
      list.append("0")
      return list
    self.__close_connection(client)
    list.append("0")
    return list

  def put_entity_dict(self, table_name, row_key, value_dict):
    raise NotImplementedError("put_entity_dict is not implemented in %s." % self.__class__)


  def get_table(self, table_name, column_names):
    error = [ERROR_DEFAULT]  
    client = None
    result = error
    keyslices = []
    column_parent = ColumnParent(column_family="Standard1")
    predicate = SlicePredicate(column_names=column_names)
    start_key = table_name + "/"
    end_key = table_name + '/~'
    try: 
      client = self.__setup_connection()
      keyslices = client.get_range_slice(MAIN_TABLE, 
                              column_parent, 
                              predicate, 
                              start_key, 
                              end_key, 
                              MAX_ROW_COUNT, 
                              CONSISTENCY_QUORUM)
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      result[0] += "Exception: " + str(ex)
      self.__close_connection(client)
      return result
    for keyslice in keyslices:
      ordering_dict = {}
      for c in keyslice.columns:
        column = c.column
        value = column.value
        ordering_dict[column.name] = value
      if len(ordering_dict) == 0:
        continue
      for column in column_names:
        try:
          result.append(ordering_dict[column])
        except:
          result[0] += "Key error, get_table did not return the correct schema"
    self.__close_connection(client)
    return result

  def delete_row(self, table_name, row_key):
    error = [ERROR_DEFAULT]
    ret = error
    client = None
    row_key = table_name + '/' + row_key
    path = ColumnPath(COLUMN_FAMILY)
    try: 
      client = self.__setup_connection()
      curtime = self.timestamp()
      # Result is a column type which has name, value, timestamp
      client.remove(MAIN_TABLE, row_key, path, curtime,
                               CONSISTENCY_QUORUM) 
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      ret[0]+=("Exception: %s"%ex)
      self.__close_connection(client)
      return ret 
    self.__close_connection(client)
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
    column_parent = ColumnParent(column_family="Standard1")
    predicate = SlicePredicate(column_names=[])
    curtime = self.timestamp()
    path = ColumnPath(COLUMN_FAMILY)
    start_key = table_name + "/"
    end_key = table_name + '/~'
    try: 
      client = self.__setup_connection()
      keyslices = client.get_range_slice(MAIN_TABLE, 
                              column_parent, 
                              predicate, 
                              start_key, 
                              end_key, 
                              MAX_ROW_COUNT, 
                              CONSISTENCY_QUORUM)
    except Exception, ex:
      self.logger.debug("Exception %s" % ex)
      result[0]+=("Exception: %s"%ex)
      self.__close_connection(client)
      return result
    keys_removed = False
    for keyslice in keyslices:
      row_key = keyslice.key
      client.remove(MAIN_TABLE, 
                    row_key, 
                    path, 
                    curtime,
                    CONSISTENCY_QUORUM) 
      keys_removed = True
    if table_name not in table_cache and keys_removed:
      result[0] += "Table does not exist"
      return  result
    if table_name in table_cache:
      del table_cache[table_name]
 
    self.__close_connection(client)
    return result

  # Only stores the schema
  def create_table(self, table_name, column_names):
    table_cache[table_name] = 1
    columns = ':'.join(column_names)
    row_key = table_name
    # Get and make sure we are not overwriting previous schemas
    ret = self.get_entity(SCHEMA_TABLE, row_key, SCHEMA_TABLE_SCHEMA)
    if ret[0] != ERROR_DEFAULT:
      self.put_entity(SCHEMA_TABLE, row_key, SCHEMA_TABLE_SCHEMA, [columns])

  ######################################################################
  # private methods 
  ######################################################################
  def __create_connection(self):
    transport = TSocket.TSocket(self.host, self.port)
    transport = TTransport.TBufferedTransport(transport)
    protocol = TBinaryProtocol.TBinaryProtocol(transport)
    client = Client(protocol)
    transport.open()
    return client

  def __setup_connection(self):
    return self.pool.connect()

  def __close_connection(self, client):
    if client:
      client.close()

  def timestamp(self):
    return int(time.time() * 1000)
