# Cassandra Interface for AppScale
# author: Navraj Chohan

import base64
import os
import string
import sys
import time

from thrift_cass.Cassandra import Client
from thrift_cass.ttypes import *
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

import appscale_logger
import helper_functions
import pycassa

from dbconstants import *
from dbinterface_batch import *
from pycassa.system_manager import *


CASS_DEFAULT_PORT = 9160

CONSISTENCY_ONE = pycassa.cassandra.ttypes.ConsistencyLevel.ONE

CONSISTENCY_QUORUM = pycassa.cassandra.ttypes.ConsistencyLevel.QUORUM

KEYSPACE = "Keyspace1"

STANDARD_COL_FAM = "Standard1"

class DatastoreProxy(AppDBInterface):
  """ A class interface to batch interfaces for Cassandra
  """
  def __init__(self, logger = appscale_logger.getLogger("datastore-cassandra")):
    f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
    self.host = f.read()
    f.close()
    self.port = CASS_DEFAULT_PORT
    self.pool = pycassa.ConnectionPool(keyspace=KEYSPACE,
                          server_list=[self.host+":"+str(self.port)], 
                          prefill=False)
    self.logger = logger

  def batch_get_entity(self, table_name, row_keys, column_names):
    """Allows access to multiple rows with a single call
    
    Args:
      table_name: The table to access
      row_keys: A list of keys to access
      column_names: A list of columns to access
    Returns:
      A dictionary of {key:{column_name:value,...}}
    """

    assert isinstance(table_name, str)
    assert isinstance(column_names, list)
    assert isinstance(row_keys, list)
 
    client = None
    results = {}
    ret = {}
    client = self.__setup_connection()
    path = ColumnPath(table_name)
    slice_predicate = SlicePredicate(column_names=column_names)
    results = client.multiget_slice(row_keys, 
                                   path, 
                                   slice_predicate, 
                                   CONSISTENCY_QUORUM)
    for row in row_keys:
      col_dic = {}
      for columns in results[row]:
        col_dic[columns.column.name] = columns.column.value
      ret[row] = col_dic
    self.__close_connection(client)
    return ret

  def batch_put_entity(self, table_name, row_keys, column_names, cell_values):
    """Allows callers to store multiple rows with a single call.
   
    Args: 
      table_name: The table to mutate
      row_keys: A list of keys to store on
      column_names: A list of columns to mutate
      cell_values: A dict of key/value pairs
    Returns:
      Nothing 
    """

    assert isinstance(table_name, str)
    assert isinstance(column_names, list)
    assert isinstance(row_keys, list)
    assert isinstance(cell_values, dict)

    cf = pycassa.ColumnFamily(self.pool,table_name)
    multi_map = {}
    for key in row_keys:
      cols = {}
      for cname in column_names:
        cols[cname] = cell_values[key][cname]
      multi_map[key] = cols
    cf.batch_insert(multi_map)
      
  def batch_delete(self, table_name, row_keys):
    """Remove a set of keys
     
    Args:
      table_name: Table to delete rows from
      row_keys: A list of keys to remove
    Returns:
      Nothing
    Raises:
      AppScaleDBConnectionError when unable to execute deletes
    """ 

    assert isinstance(table_name, str)
    assert isinstance(row_keys, list)

    path = ColumnPath(table_name)
    try:
      cf = pycassa.ColumnFamily(self.pool,table_name)
      b = cf.batch()
      for key in row_keys:
        b.remove(key)
      b.send()
    except Exception, ex:
      raise AppScaleDBConnectionError("Exception %s" % str(ex))

  def delete_table(self, table_name):
    """ Drops a given column family
  
    Args:
      table_name: The column family name
    Returns:
      Nothing
    """

    assert isinstance(table_name, str)

    f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
    host = f.read()
    f.close()
    sysman = SystemManager(host + ":" + str(CASS_DEFAULT_PORT))
    sysman.drop_column_family(KEYSPACE, table_name)

  def create_table(self, table_name, column_names):
    """ Creates a table as a column family
    
    Args:
      table_name: The column family name
      column_names: not used
    Returns:
      Nothing
    """

    assert isinstance(table_name, str)
    assert isinstance(column_names, list)

    f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
    host = f.read()
    f.close()
    sysman = SystemManager(host + ":" + str(CASS_DEFAULT_PORT))
    try:
      sysman.create_column_family(KEYSPACE,
                                table_name, 
                                comparator_type=UTF8_TYPE)
    except InvalidRequestException, e:
      print "Table %s exists"%table_name
    
  def range_query(self, 
                  table_name, 
                  column_names, 
                  start_key, 
                  end_key, 
                  limit, 
                  offset=0, 
                  start_inclusive=True, 
                  end_inclusive=True,
                  keys_only=False):
    """ Gets a dense range ordered by keys. Returns an ordered list of 
        dictionary of [key:{column1:value1, column2:value2},...]
        or a list of keys if keys only.
     
    Args:
      table_name: column family name (Cassandra's name for a table)
      column_names: columns which get returned within the key range
      start_key: starts query with this key
      end_key: ends query with this key
      limit: maximum number of results to return
      offset: cuts off these many from the results [offset:]
      start_inclusive: if results should include the start_key
      end_inclusive: if results should include the end_key
      keys_only: only returns keys and not values
    """
    assert isinstance(table_name, str)
    assert isinstance(column_names, list)
    assert isinstance(start_key, str)
    assert isinstance(end_key, str)
    assert isinstance(limit, int)
    assert isinstance(offset, int)
    
    # We add extra rows in case we exclusde the start/end keys
    # This makes sure the limit is upheld correctly
    if start_inclusive == False or end_inclusive == False:
      rowcount = limit + 2

    results = []
    keyslices = []

    cf = pycassa.ColumnFamily(self.pool,table_name)
    keyslices = cf.get_range(columns=column_names, 
                             start=start_key, 
                             finish=end_key,
                             row_count=limit,
                             read_consistency_level=CONSISTENCY_QUORUM)

    for key in keyslices:
      if keys_only:
        results.append(key[0]) 
      else:
        columns = key[1]
        col_mapping = {}
        for column in columns.items():
          col_mapping[str(column[0])] = column[1]
        results.append({key[0]:col_mapping})
   
    if start_inclusive == False and len(results) > 0:
      if start_key in results[0]:
        results = results[1:] 

    if end_inclusive == False and len(results) > 0:
      if end_key in results[-1]:
        results = results[:-1]

    if len(results) > limit:
      results = results[:limit]

    if offset != 0 and offset <= len(results):
      results = results[offset:]

    return results 
     

  ######################################################################
  # private methods 
  ######################################################################
  def __setup_connection(self):
    """ Retrives a connection from the connection pool
    """

    return self.pool.get()

  def __close_connection(self, client):
    """ Closes a connection by returning it to the pool
    """
    if client:
      self.pool.return_conn(client)

