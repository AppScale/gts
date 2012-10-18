# Hypertable Interface for AppScale
# author: Navraj Chohan

import cgi
import os
import string
import sys
import time
import threading
import xml

import appscale_logger
import helper_functions

import hyperthrift.gen.ttypes as ttypes

from dbinterface_batch import *
from dbconstants import *
from hypertable.thriftclient import *

from xml.sax import make_parser
from xml.sax import parseString
from xml.sax.handler import feature_namespaces
from xml.sax import ContentHandler
from xml.sax import saxutils
from xml.sax.handler import ContentHandler

THRIFT_PORT = 38080

NS = "/appscale"

ROOT_TAG_BEGIN="<Schema>"

ROOT_TAG_END="</Schema>"

ACCGRP_TAG_BEGIN='<AccessGroup name="default">'

ACCGRP_TAG_END="</AccessGroup>"

COLFMLY_TAG_BEGIN="<ColumnFamily>"

COLFMLY_TAG_END="</ColumnFamily>"

NAME_TAG_TEXT = "Name"

NAME_TAG_BEGIN="<"+NAME_TAG_TEXT+">"

NAME_TAG_END="</"+NAME_TAG_TEXT+">"

PROFILING = False

class XmlSchemaParser(ContentHandler):
  def __init__(self, tag_name):
    self.tag_name = tag_name
    self.isName = 0
    self.attributes = []

  def clear_attributes(self):
    self.attributes = []

  def startElement(self, name, attrs):
    if name == self.tag_name:
      self.isName = 1

  def endElement(self, name):
    if name == self.tag_name:
      self.isName = 0

  def characters(self, ch):
    if self.isName == 1:
      self.attributes.append(ch)

class DatastoreProxy(AppDBInterface):
  """ Note: Hypertable will truncate any bytes after the terminating char
      and hence requires encoding/decoding functions 
  """
  def __init__(self, logger = appscale_logger.getLogger("datastore-hypertable")):
    self.logger = logger
    self.conn = None
    self.lock = threading.Lock()
    self.host = None

    #self.lock.acquire()
    f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
    self.host = f.read()
    f.close()

    self.conn = ThriftClient(self.host, THRIFT_PORT)
    self.ns = self.conn.namespace_open(NS)

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

    row_keys = [self.__encode(row) for row in row_keys]

    results = {}
    ret = {}
    row_intervals = []
    cell_intervals = None
    include_deletes = False
    for row in row_keys:
      row_intervals.append(ttypes.RowInterval(row, True, row, True))

    scan_spec = ttypes.ScanSpec(row_intervals, 
                                cell_intervals, 
                                include_deletes, 
                                1, 0, 0, 
                                None,  
                                column_names)

    res = self.conn.get_cells(self.ns, table_name, scan_spec)
    for cell in res:
      if self.__decode(cell.key.row) in ret:
        # update the dictionary
        col_dict = ret[self.__decode(cell.key.row)]
      else:
        # first time seen
        col_dict = {}
      col_dict[cell.key.column_family] = cell.value
      ret[self.__decode(cell.key.row)] = col_dict
    
    # If nothing was returned for any cell, put in empty values      
    for row in row_keys:
      if self.__decode(row) not in ret:
        col_dict = {}
        ret[self.__decode(row)] = col_dict

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

    __INSERT = 255
    cell_list = []

    mutator = self.conn.mutator_open(self.ns, table_name, 0, 0)

    for key in row_keys:
      for col in column_names: 
        cell = ttypes.Cell()
        keyflag = ttypes.KeyFlag()
        ttypekey = ttypes.Key(row=self.__encode(key), 
                              column_family=col, 
                              flag=__INSERT)
        cell.key = ttypekey
        cell.value = cell_values[key][col]
        cell_list.append(cell)

    self.conn.mutator_set_cells(mutator, cell_list)
    self.conn.mutator_close(mutator)

  def batch_delete(self, table_name, row_keys, column_names=[]):
    """Remove a set of keys
     
    Args:
      table_name: Table to delete rows from
      row_keys: A list of keys to remove
      column_names: Not used
    Returns:
      Nothing
    Raises:
      AppScaleDBConnectionError when unable to execute deletes
    """ 

    assert isinstance(table_name, str)
    assert isinstance(row_keys, list)

    row_keys = [self.__encode(row) for row in row_keys]
    __DELETE_ROW = 0
    cell_list = []

    mutator = self.conn.mutator_open(self.ns, table_name, 0, 0)

    for key in row_keys:
      cell = ttypes.Cell()
      keyflag = ttypes.KeyFlag()
      ttypekey = ttypes.Key(row=key, flag=__DELETE_ROW)
      cell.key = ttypekey
      cell_list.append(cell)

    self.conn.mutator_set_cells(mutator, cell_list)
    self.conn.mutator_close(mutator)

  def delete_table(self, table_name):
    """ Drops a given column family
  
    Args:
      table_name: The column family name
    Returns:
      Nothing
    """
    assert isinstance(table_name, str)

    self.conn.drop_table(self.ns, table_name, 1)
    return 


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
    table_names = None
    table_schema_xml = self.__constructSchemaXml(column_names)
    self.conn.create_table(self.ns,table_name,table_schema_xml)
    table_names = self.conn.get_tables(self.ns)
    self.__closeConnection(self.conn)
    return 

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
   
    start_key = self.__encode(start_key) 
    end_key = self.__encode(end_key) 

    # We add extra rows in case we exclusde the start/end keys
    # This makes sure the limit is upheld correctly
    if start_inclusive == False or end_inclusive == False:
      rowcount = limit + 2
  
    row_intervals = []
    row_intervals.append(ttypes.RowInterval(start_key, 
                                            start_inclusive, 
                                            end_key, 
                                            end_inclusive))

    cell_intervals = None
    include_deletes = False

    scan_spec = ttypes.ScanSpec(row_intervals, 
                                cell_intervals, 
                                include_deletes, 
                                1, # max revisions
                                limit, 
                                0, 
                                None, 
                                column_names)
    res = self.conn.get_cells(self.ns, table_name, scan_spec)

    results = []
    last_row = None
    for cell in res:
      # the current list element needs to be updated
      if cell.key.row == last_row:
        if not keys_only:
          row_dict = results[-1]
          col_dict = row_dict[self.__decode(cell.key.row)]
          col_dict[cell.key.column_family] = cell.value
          results[-1] = {self.__decode(cell.key.row):col_dict}
      # add a new list element for this item
      else:
        last_row = cell.key.row
        if keys_only:
          results.append(self.__decode(cell.key.row))
        else:
          col_dict = {}
          col_dict[cell.key.column_family] = cell.value
          results.append({self.__decode(cell.key.row):col_dict})

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
  def __closeConnection(self, conn):
    pass
    #self.lock.release()

  def __constructSchemaXml(self, column_names):
    """ For the column names of a table, this method returns
        an xml string representing the columns, which can 
        then be used with hypertable's thrift api
    """
    assert isinstance(column_names, list)
    schema_xml = ''.join([ROOT_TAG_BEGIN, ACCGRP_TAG_BEGIN])

    for col_name in column_names:
      schema_xml += ''.join([COLFMLY_TAG_BEGIN, 
                             NAME_TAG_BEGIN, 
                             col_name,
                             NAME_TAG_END, 
                             COLFMLY_TAG_END])

    schema_xml += ''.join([ACCGRP_TAG_END, ROOT_TAG_END])
    return schema_xml

  def __setup_connection(self):
    """ Retrives a connection from the connection pool
    """
    return self.pool.get()

  def __close_connection(self, client):
    """ Closes a connection by returning it to the pool
    """
    if client:
      self.pool.return_conn(client)

  def __encode(self, bytes_in):
    """ Removes \x00 character with \x01
    """
    return bytes_in.replace('\x00','\x01')

  def __decode(self, bytes_out):
    """ Replaces \x01 character with \x00
    """
    return bytes_out.replace('\x01', '\x00')

