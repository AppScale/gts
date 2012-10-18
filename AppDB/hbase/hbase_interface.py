#Author: Navraj Chohan

import os

import Hbase
import ttypes
import time
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol
from dbinterface import *
#import sqlalchemy.pool as pool
import appscale_logger
import threading
from socket import gethostname; 
PROFILING = False
ERROR_HB = "DB_ERROR:"
DB_LOCATION = gethostname()
THRIFT_PORT = 9090

class DatastoreProxy(AppDBInterface):

  def __init__(self, logger = appscale_logger.getLogger("datastore-hbase")):
    self.logger = logger
    self.lock = threading.Lock()
    self.connection = self.__createConnection()
    #self.pool = pool.QueuePool(self.__createConnection)

  def logTiming(self, function, start_time, end_time):
    if PROFILING:
      self.logger.debug(function + ": " + str(end_time - start_time) + " s")

  def __createConnection(self):
    t = TSocket.TSocket(DB_LOCATION, THRIFT_PORT)
    #t = TSocket.TSocket(self.get_local_ip(), THRIFT_PORT)
    t = TTransport.TBufferedTransport(t)
    p = TBinaryProtocol.TBinaryProtocol(t)
    c = Hbase.Client(p)
    t.open()
    return c

  def __initConnection(self):
    self.lock.acquire()
    if self.connection:
      return self.connection
    else:
      self.connection = self.__createConnection()
      return self.connection
    #return self.pool.connect()

  def __closeConnection(self, conn):
    #conn.close()
    self.lock.release()

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

    client = self.__initConnection() 
    result = {}
    rows = None
    column_list = []

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
    self.__closeConnection(client)
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
    """

    assert isinstance(table_name, str)
    assert isinstance(column_names, list)
    assert isinstance(row_keys, list)
    assert isinstance(cell_values, dict)
    client = self.__initConnection()

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

    client.mutateRows(table_name, all_mutations)
    self.__closeConnection(client)
 
  def batch_delete(self, table_name, row_keys, column_names=[]):
    """Remove a set of keys
     
    Args:
      table_name: Table to delete rows from
      row_keys: A list of keys to remove
      column_names: A list of column names
    Returns:
      Nothing
    Raises:
      AppScaleDBConnectionError when unable to execute deletes
    """

    assert isinstance(table_name, str)
    assert isinstance(row_keys, list)
    client = self.__initConnection()

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
    client.mutateRows(table_name, all_mutations)
    self.__closeConnection(client)
 
  def delete_table(self, table_name):
    """ Drops a given column family
  
    Args:
      table_name: The column family name
    Returns:
      Nothing
    """
    assert isinstance(table_name, str)

    client = self.__initConnection() 
    try:
      client.disableTable(table_name)
      client.deleteTable(table_name)
    except ttypes.IOError, io: # table not found
      pass
    self.__closeConnection(client)

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

    client = self.__initConnection()
    columnlist = []
    for ii in column_names:
      col = ttypes.ColumnDescriptor()
      col.name = ii + ":"
      col.maxVersions = 1
      columnlist.append(col)
    client.createTable(table_name, columnlist)
    self.__closeConnection(client)

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
    assert isinstance(limit, int) or isinstance(limit, long)
    assert isinstance(offset, int)

    results = []

    # We add extra rows in case we exclusde the start/end keys
    # This makes sure the limit is upheld correctly
    rowcount = limit
    if not start_inclusive or not end_inclusive:
      rowcount = limit + 2
    client = self.__initConnection()
    col_names = []
    for col in column_names:
      col_names.append(col + ":")
    scanner = client.scannerOpenWithStop(table_name, start_key, end_key, col_names) 
    rowresult = client.scannerGetList(scanner, rowcount)
    while rowresult:
      rowcount -= len(rowresult) 
      for row in rowresult:
        item = {}
        col_dict = {}
        for c in column_names:
          col_dict[c] = row.columns[c+":"].value
        item[row.row] = col_dict
        results.append(item)   
      if rowcount <= 0:
        break
      rowresult = client.scannerGetList(scanner, rowcount)
    client.scannerClose(scanner) 
    self.__closeConnection(client)

    # The end key is not included in the scanner. Get the last key if 
    # needed
    if rowcount != 0 and end_inclusive:
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

