# Cassandra Interface for AppScale
# author: Navraj Chohan

import os,sys
import time
import collections

from thrift_cass.Cassandra import Client
from thrift_cass.ttypes import *
import helper_functions
import string
import base64
from dbconstants import *
from dbinterface_batch import *
import appscale_logger
import pycassa
from pycassa.system_manager import *
from thrift import Thrift
from thrift.transport import TSocket
from thrift.transport import TTransport
from thrift.protocol import TBinaryProtocol

CASS_DEFAULT_PORT = 9160

CONSISTENCY_ONE = pycassa.cassandra.ttypes.ConsistencyLevel.ONE

CONSISTENCY_QUORUM = pycassa.cassandra.ttypes.ConsistencyLevel.QUORUM

KEYSPACE = "Keyspace1"

class DatastoreProxy(AppDBInterface):
  def __init__(self, logger = appscale_logger.getLogger("datastore-cassandra")):
    f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
    self.host = f.read()
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
    for ii in row_keys:
      col_dic = {}
      for kk in results[ii]:
        col_dic[kk.column.name] = kk.column.value
      ret[ii] = col_dic
    self.__close_connection(client)
    return ret

  def batch_put_entity(self, table_name, row_keys, column_names, cell_values):
    """Allows storage to multiple rows with a single call
   
    Args: 
      table_name: The table to mutate
      row_keys: A list of keys to store on
      column_names: A list of columns to mutate
      cell_values: A dict of key/value pairs
    Returns:
      Nothing 
    """
    cf = pycassa.ColumnFamily(self.pool,table_name)
    curtime = self.timestamp()
    multi_map = {}
    for key in row_keys:
      cols = {}
      for ii in column_names:
        cols[ii] = cell_values[key][ii]
      multi_map[key] = cols
    cf.batch_insert(multi_map)
      
  def batch_delete(self, table_name, row_keys):
    """Remove a set of keys
     
    Args:
      table_name: Table to mutate
      row_keys: A list of keys to remove
    Returns:
      Nothing
    """ 

    path = ColumnPath(table_name)
    try:
      cf = pycassa.ColumnFamily(self.pool,table_name)
      b = cf.batch()
      curtime = self.timestamp()
      for key in row_keys:
        b.remove(key)
      b.send()
    except Exception, ex:
      raise AppScaleDBConnectionError("Exception %s" % str(ex))

  def get_schema(self, table_name):
    """ Returns the schema of a column family
    Args:
      table_name: The column family name
    Returns:
      Nothing
    """

    #cf = pycassa.ColumnFamily(self.pool,table_name)
    #return cf.load_schema()
    raise NotImplementedError("No get_schema available") 

  def delete_table(self, table_name):
    """ Drops a given column family
  
    Args:
      table_name: The column family name
    Returns:
      Nothing
    """

    f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
    host = f.read()
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

    f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
    host = f.read()
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
      table_name: column family name
      column_names: columns which get returned
      start_key: starts query with this key
      end_key: ends query with this key
      limit: max number of results to return
      offset: cuts off these many from the results [offset:]
      start_inclusive: if results should include the start_key
      end_inclusive: if results should include the end_key
      keys_only: only returns keys and not values
    """

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

    for ii in keyslices:
      if keys_only:
        results.append(ii[0]) 
      else:
        columns = ii[1]
        col_mapping = {}
        for hh in columns.items():
          col_mapping[str(hh[0])] = hh[1]
        results.append({ii[0]:col_mapping})
   
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
    return self.pool.get()

  def __close_connection(self, client):
    if client:
      self.pool.return_conn(client)

  def timestamp(self):
    return int(time.time() * 1000)
