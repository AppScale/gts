# Programmer: Navraj Chohan <nlake44@gmail.com>

"""
 Cassandra Interface for AppScale
"""
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

import helper_functions
import pycassa

from dbconstants import *
from dbinterface_batch import *
from pycassa.system_manager import *

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import constants

# This is the default cassandra connection port
CASS_DEFAULT_PORT = 9160

# Data consistency models available with cassandra
CONSISTENCY_ONE = pycassa.cassandra.ttypes.ConsistencyLevel.ONE
CONSISTENCY_QUORUM = pycassa.cassandra.ttypes.ConsistencyLevel.QUORUM
CONSISTENCY_ALL = pycassa.cassandra.ttypes.ConsistencyLevel.ALL

# The keyspace used for all tables
KEYSPACE = "Keyspace1"

# The standard column family used for tables
STANDARD_COL_FAM = "Standard1"

class DatastoreProxy(AppDBInterface):
  """ 
    Cassandra implementation of the AppDBInterface
  """
  def __init__(self):
    """
    Constructor.
    """

    self.host = helper_functions.read_file(constants.APPSCALE_HOME + \
                '/.appscale/my_private_ip')
    self.port = CASS_DEFAULT_PORT
    self.pool = pycassa.ConnectionPool(keyspace=KEYSPACE,
                          server_list=[self.host+":"+str(self.port)], 
                          prefill=False)

  def batch_get_entity(self, table_name, row_keys, column_names):
    """
    Takes in batches of keys and retrieves their cooresponding rows.
    
    Args:
      table_name: The table to access
      row_keys: A list of keys to access
      column_names: A list of columns to access
    Returns:
      A dictionary of rows and columns/values of those rows. The format 
      looks like such: {key:{column_name:value,...}}
    """

    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(column_names, list): raise TypeError("Expected a list")
    if not isinstance(row_keys, list): raise TypeError("Expected a list")

    ret_val = {}
    client = self.pool.get()
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
      ret_val[row] = col_dic

    if client:
      self.pool.return_conn(client)
    return ret_val

  def batch_put_entity(self, table_name, row_keys, column_names, cell_values):
    """
    Allows callers to store multiple rows with a single call. A row can 
    have multiple columns and values with them. We refer to each row as 
    an entity.
   
    Args: 
      table_name: The table to mutate
      row_keys: A list of keys to store on
      column_names: A list of columns to mutate
      cell_values: A dict of key/value pairs
    Raises:
      TypeError: when bad arguments are given
    """

    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(column_names, list): raise TypeError("Expected a list")
    if not isinstance(row_keys, list): raise TypeError("Expected a list")
    if not isinstance(cell_values, dict): raise TypeError("Expected a dic")

    cf = pycassa.ColumnFamily(self.pool,table_name)
    multi_map = {}
    for key in row_keys:
      cols = {}
      for cname in column_names:
        cols[cname] = cell_values[key][cname]
      multi_map[key] = cols
    cf.batch_insert(multi_map)
      
  def batch_delete(self, table_name, row_keys, column_names=[]):
    """
    Remove a set of rows cooresponding to a set of keys.
     
    Args:
      table_name: Table to delete rows from
      row_keys: A list of keys to remove
      column_names: Not used
    Raises:
      AppScaleDBConnectionError: when unable to execute deletes
      TypeError: when given bad argument types 
    """ 

    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(row_keys, list): raise TypeError("Expected a list")

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
    """ 
    Drops a given table (aka column family in Cassandra)
  
    Args:
      table_name: A string name of the table to drop
    Rasies:
      TypeError: when given bad argument types 
    """

    if not isinstance(table_name, str): raise TypeError("Expected a str")

    sysman = pycassa.system_manager.SystemManager(self.host + ":" + str(CASS_DEFAULT_PORT))
    sysman.drop_column_family(KEYSPACE, table_name)

  def create_table(self, table_name, column_names):
    """ 
    Creates a table as a column family
    
    Args:
      table_name: The column family name
      column_names: Not used but here to match the interface
    Raises:
      TypeError: when given bad argument types 
    """

    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(column_names, list): raise TypeError("Expected a list")

    sysman = pycassa.system_manager.SystemManager(self.host + ":" + str(CASS_DEFAULT_PORT))
    try:
      sysman.create_column_family(KEYSPACE,
                                table_name, 
                                comparator_type=UTF8_TYPE)
    except InvalidRequestException, e:
      pass
    
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
    """ 
    Gets a dense range ordered by keys. Returns an ordered list of 
    a dictionary of [key:{column1:value1, column2:value2},...]
    or a list of keys if keys only.
     
    Args:
      table_name: Name of table to access
      column_names: Columns which get returned within the key range
      start_key: String for which the query starts at
      end_key: String for which the query ends at
      limit: Maximum number of results to return
      offset: Cuts off these many from the results [offset:]
      start_inclusive: Boolean if results should include the start_key
      end_inclusive: Boolean if results should include the end_key
      keys_only: Boolean if to only keys and not values
    Raises:
      TypeError: when bad arguments are given
    Returns:
      An ordered list of dictionaries of key=>columns/values
    """

    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(column_names, list): raise TypeError("Expected a list")
    if not isinstance(start_key, str): raise TypeError("Expected a str")
    if not isinstance(end_key, str): raise TypeError("Expected a str")
    if not isinstance(limit, int) and not isinstance(limit, long): 
      raise TypeError("Expected an int or long")
    if not isinstance(offset, int) and not isinstance(offset, long): 
      raise TypeError("Expected an int or long")
    
    # We add extra rows in case we exclude the start/end keys
    # This makes sure the limit is upheld correctly
    row_count = limit
    if not start_inclusive:
      row_count += 1
    if not end_inclusive:
      row_count += 1

    results = []

    cf = pycassa.ColumnFamily(self.pool,table_name)
    keyslices = cf.get_range(columns=column_names, 
                             start=start_key, 
                             finish=end_key,
                             row_count=row_count,
                             read_consistency_level=CONSISTENCY_QUORUM)

    for key in keyslices:
      if keys_only:
        results.append(key[0]) 
      else:
        columns = key[1]
        col_mapping = {}
        for column in columns.items():
          col_name = str(column[0]) 
          col_val = column[1]
          col_mapping[col_name] = col_val

        k = key[0]
        v = col_mapping
        item = {k:v}
        results.append(item)

   
    if not start_inclusive and len(results) > 0:
      if start_key in results[0]:
        results = results[1:] 

    if not end_inclusive and len(results) > 0:
      if end_key in results[-1]:
        results = results[:-1]

    if len(results) > limit:
      results = results[:limit]

    if offset != 0 and offset <= len(results):
      results = results[offset:]
    
    return results 
     
