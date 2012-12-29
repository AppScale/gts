# Author: Navraj Chohan <nlake44@gmail.com>

import os

import appscale_logger
import Hbase
import helper_functions
import threading
import ttypes

from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from dbinterface import *

# Thrift port to connect to HBase
THRIFT_PORT = 9090

class DatastoreProxy(AppDBInterface):
  """ 
    The AppScale DB API class implementation for HBase
  """
  def __init__(self, logger = appscale_logger.getLogger("datastore-hbase")):
    """
    Constructor
    Args:
      logger: Used for logging
    """
    self.lock = threading.Lock()
    self.logger = logger
    self.connection = self.create_connection()

  def batch_get_entity(self, table_name, row_keys, column_names):
    """Allows access to multiple rows with a single call
    
    Args:
      table_name: The table to access
      row_keys: A list of keys to access
      column_names: A list of columns to access
    Returns:
      A dictionary of {key:{column_name:value,...}}
    Raise: 
      TypeError: Raised when given bad types for args.
    """

    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(column_names, list): raise TypeError("Expected list")
    if not isinstance(row_keys, list): raise TypeError("Expected list")

    result = {}
    rows = []
    column_list = []
    client = self.__init_connection() 

    for ii in column_names:
      column_list.append(ii + ":") 
      rows = client.getRowsWithColumns(table_name, row_keys, column_list)

    for row in rows:
      result[row.row] = {}
      for col in column_names:
        if (col+":") in row.columns:
          result[row.row][col] = row.columns[col + ":"].value

    for row in row_keys:
      if row not in result:
        result[row] = {}
    self.__release_lock()
    return result  

  def batch_put_entity(self, table_name, row_keys, column_names, cell_values):
    """Allows callers to store multiple rows with a single call.
   
    Args: 
      table_name: The table to mutate
      row_keys: A list of keys to store on
      column_names: A list of columns to mutate
      cell_values: A dict of key/value pairs
    Returns:
      Nothing 
    Raises:
      TypeError: Raised when given bad types of for args.
    """

    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(column_names, list): raise TypeError("Expected list")
    if not isinstance(row_keys, list): raise TypeError("Expected list")
    if not isinstance(cell_values, dict): raise TypeError("Expected dict")


    all_mutations = []
    for row in row_keys:
      batch_mutation = ttypes.BatchMutation()
      mutations = []
      for col in column_names:
        m = ttypes.Mutation()
        m.column = col + ":"
        m.value = cell_values[row][col]
        mutations.append(m)
      batch_mutation.mutations = mutations
      batch_mutation.row = row
      all_mutations.append(batch_mutation) 

    client = self.__init_connection()
    client.mutateRows(table_name, all_mutations)
    self.__release_lock()
 
  def batch_delete(self, table_name, row_keys, column_names=[]):
    """ Remove a batch of rows.
     
    Args:
      table_name: Table to delete rows from
      row_keys: A list of keys to remove
      column_names: A list of column names
    Returns:
      Nothing
    Raises: 
      TypeError: Raised when given bad types of for args.
    """

    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(row_keys, list): raise TypeError("Expected list")


    all_mutations = []
    for row in row_keys:
      batch_mutation = ttypes.BatchMutation()
      mutations = []
      for col in column_names:
        m = ttypes.Mutation(isDelete=True)
        m.column = col + ":"
        mutations.append(m)
      batch_mutation.mutations = mutations
      batch_mutation.row = row
      all_mutations.append(batch_mutation) 
    client = self.__init_connection()
    client.mutateRows(table_name, all_mutations)
    self.__release_lock()
 
  def delete_table(self, table_name):
    """ Drops a given table
  
    Args:
      table_name: The table to drop
    Returns:
      Nothing
    Raises:
      TypeError: Raised when given bad types of for args.
    """
    if not isinstance(table_name, str): raise TypeError("Excepted str")

    client = self.__init_connection() 
    try:
      client.disableTable(table_name)
      client.deleteTable(table_name)
    except ttypes.IOError, io: # table not found
      pass
    self.__release_lock()

  def create_table(self, table_name, column_names):
    """ Creates a table as a column family.
    
    Args:
      table_name: The column family name
      column_names: not used
    Returns:
      Nothing
    Raises:
      TypeError: Raised when given bad types of for args.
    """

    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(column_names, list): raise TypeError("Expected list")

    columnlist = []
    for ii in column_names:
      col = ttypes.ColumnDescriptor()
      col.name = ii + ":"
      col.maxVersions = 1
      columnlist.append(col)
    client = self.__init_connection()
    client.createTable(table_name, columnlist)
    self.__release_lock()

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
      table_name: Table to access
      column_names: Columns which get returned within the key range
      start_key: String key starting the range query
      end_key: String key ending the range query
      limit: Maximum number of results to return
      offset: Number to cut off from the results [offset:]
      start_inclusive: Boolean if results should include the start_key
      end_inclusive: Boolean if results should include the end_key
      keys_only: Boolean if only returns keys and not values
    Raises: 
      TypeError: Raised when given bad types of for args.
    Returns:
      Dictionary of the results
    """
    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(column_names, list): raise TypeError("Expected list")
    if not isinstance(start_key, str): raise TypeError("Expected str")
    if not isinstance(end_key, str): raise TypeError("Expected str")
    if not isinstance(limit, int) and not isinstance(limit, long): 
      raise TypeError("Expected int or long")
    if not isinstance(offset, int) and not isinstance(offset, long): 
      raise TypeError("Expected an int or long")

    results = []

    # We add extra rows in case we exclude the start/end keys
    # This makes sure the limit is upheld correctly
    row_count = limit
    if not start_inclusive:
      row_count += 1
    if not end_inclusive:
      row_count += 1

    col_names = []
    for col in column_names:
      col_names.append(col + ":")

    client = self.__init_connection()
    scanner = client.scannerOpenWithStop(
                  table_name, start_key, end_key, col_names) 

    rowresult = client.scannerGetList(scanner, row_count)
    while rowresult:
      row_count -= len(rowresult) 
      for row in rowresult:
        item = {}
        col_dict = {}
        for c in column_names:
          col_dict[c] = row.columns[c+":"].value
        item[row.row] = col_dict
        results.append(item)   
      if row_count <= 0:
        break
      rowresult = client.scannerGetList(scanner, row_count)
    client.scannerClose(scanner) 
    self.__release_lock()

    # The end key is not included in the scanner. Get the last key if 
    # needed
    if row_count != 0 and end_inclusive:
      item = self.batch_get_entity(table_name, [end_key], column_names)
      if item[end_key]:
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

  ########################
  # Private methods
  ########################
  def create_connection(self):
    """ Creates a connection to HBase's Thrift to the local node.

    Returns: 
      An HBase client object
    """
    host = helper_functions.read_file('/etc/appscale/my_private_ip')
    t = TSocket.TSocket(host, THRIFT_PORT)
    t = TTransport.TBufferedTransport(t)
    p = TBinaryProtocol.TBinaryProtocol(t)
    c = Hbase.Client(p)
    t.open()
    return c

  def __init_connection(self):
    """
    Provides a locking wrapper around a connection to make it threadsafe. 
    Blocks until the lock is available.
    Returns:
      An HBase connection
    """
    self.lock.acquire()
    if self.connection:
      return self.connection
    else:
      self.connection = self.create_connection()
      return self.connection

  def __release_lock(self):
    """
    Releases the connection lock.
    """ 
    self.lock.release()

