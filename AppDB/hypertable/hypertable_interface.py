# Programmer: Navraj Chohan <nlake44@gmail.com>

"""
 Hypertable Interface for AppScale
"""
import os
import time

import helper_functions

import hyperthrift.gen.ttypes as ttypes

from dbinterface_batch import *
from dbconstants import *
from hypertable import thriftclient


from xml.sax import make_parser
from xml.sax import parseString
from xml.sax.handler import feature_namespaces
from xml.sax import ContentHandler
from xml.sax import saxutils
from xml.sax.handler import ContentHandler

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import constants

# The port hypertable's thrift uses on the local machine
THRIFT_PORT = 38080

# AppScale default namespace for Hypertable
NS = "/appscale"

# XML tags used for parsing Hypertable results
ROOT_TAG_BEGIN="<Schema>"
ROOT_TAG_END="</Schema>"
ACCGRP_TAG_BEGIN='<AccessGroup name="default">'
ACCGRP_TAG_END="</AccessGroup>"
COLFMLY_TAG_BEGIN="<ColumnFamily>"
COLFMLY_TAG_END="</ColumnFamily>"
NAME_TAG_TEXT = "Name"
NAME_TAG_BEGIN="<"+NAME_TAG_TEXT+">"
NAME_TAG_END="</"+NAME_TAG_TEXT+">"


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
      and hence requires encoding/decoding functions. Yet, the encoding and 
      decoding functions must keep lexigraphical ordering for range queries 
      to work properly.
  """
  def __init__(self):
    """
      Constructor.
    """
    self.host = helper_functions.read_file(
                   constants.APPSCALE_HOME + '/.appscale/my_private_ip')
    self.conn = thriftclient.ThriftClient(self.host, THRIFT_PORT)
    self.ns = self.conn.namespace_open(NS)

  def batch_get_entity(self, table_name, row_keys, column_names):
    """Allows access to multiple rows with a single call
    
    Args:
      table_name: The table to access
      row_keys: A list of keys to access
      column_names: A list of columns to access
    Raises:
      TypeError: Bad argument types
    Returns:
      A dictionary of {key:{column_name:value,...}}
    """

    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(column_names, list): raise TypeError("Expected list")
    if not isinstance(row_keys, list): raise TypeError("Expected list")

 
    row_keys = [self.__encode(row) for row in row_keys]

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
    Raises:
      TypeError: Bad argument types
    Returns:
      Nothing 
    """

    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(column_names, list): raise TypeError("Expected list")
    if not isinstance(row_keys, list): raise TypeError("Expected list")
    if not isinstance(cell_values, dict): raise TypeError("Expected dict")

    __INSERT = 255
    cell_list = []

    mutator = self.conn.mutator_open(self.ns, table_name, 0, 0)

    for key in row_keys:
      for col in column_names: 
        cell = ttypes.Cell()
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
    Raises:
      AppScaleDBConnectionError when unable to execute deletes
      TypeError: Bad argument types
    Returns:
      Nothing
    """ 

    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(row_keys, list): raise TypeError("Expected list")

    row_keys = [self.__encode(row) for row in row_keys]
    __DELETE_ROW = 0
    cell_list = []

    mutator = self.conn.mutator_open(self.ns, table_name, 0, 0)

    for key in row_keys:
      cell = ttypes.Cell()
      ttypekey = ttypes.Key(row=key, flag=__DELETE_ROW)
      cell.key = ttypekey
      cell_list.append(cell)

    self.conn.mutator_set_cells(mutator, cell_list)
    self.conn.mutator_close(mutator)


  def delete_table(self, table_name):
    """ Drops a given column family
  
    Args:
      table_name: The column family name
    Raises: 
      TypeError: Bad argument types
    Returns:
      Nothing
    """
    if not isinstance(table_name, str): raise TypeError("Expected str")

    self.conn.drop_table(self.ns, table_name, 1)
    return 


  def create_table(self, table_name, column_names):
    """ Creates a table as a column family
    
    Args:
      table_name: The column family name
      column_names: Not used
    Raises: 
      TypeError: Bad argument types
    Returns:
      Nothing
    """

    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(column_names, list): raise TypeError("Expected list")

    table_schema_xml = self.__construct_schema_xml(column_names)
    self.conn.create_table(self.ns,table_name,table_schema_xml)
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
        a dictionary of [key:{column1:value1, column2:value2},...]
        or a list of keys if keys only.
     
    Args:
      table_name: Name of table to access
      column_names: Columns which get returned within the key range
      start_key: String for which the query starts at
      end_key: String for which the query ends at
      limit: Maximum number of results to return
      offset: Number to cut off from the results [offset:]
      start_inclusive: Boolean if results should include the start_key
      end_inclusive: Boolean if results should include the end_key
      keys_only: Boolean if to only keys and not values
    Raises:
      TypeError: Bad argument types
    Return:
      List of ordered results.
    """
    if not isinstance(table_name, str): raise TypeError("Expected str")
    if not isinstance(column_names, list): raise TypeError("Expected list")
    if not isinstance(start_key, str): raise TypeError("Expected str")
    if not isinstance(end_key, str): raise TypeError("Expected str")
    if not isinstance(limit, int) and not isinstance(limit, long): 
      raise TypeError("Expected int or long")
    if not isinstance(offset, int) and not isinstance(offset, long): 
      raise TypeError("Expected an int or long")
   
    start_key = self.__encode(start_key) 
    end_key = self.__encode(end_key) 

    # We add two extra rows in case we exclude the start/end keys
    # This makes sure the limit is upheld correctly, where we have
    # to remove the first and last key
    row_count = limit
    if not start_inclusive:
      row_count += 1
    if not end_inclusive:
      row_count += 1
  
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
                                row_count, 
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

  ######################################################################
  # private methods 
  ######################################################################

  def __construct_schema_xml(self, column_names):
    """ For the column names of a table, this method returns
        an xml string representing the columns, which can 
        then be used with hypertable's thrift api
    Args:
      column_names: A list of column names to construct xml
    """

    if not isinstance(column_names, list): raise TypeError("Expected list")

    schema_xml = ''.join([ROOT_TAG_BEGIN, ACCGRP_TAG_BEGIN])

    for col_name in column_names:
      schema_xml += ''.join([COLFMLY_TAG_BEGIN, 
                             NAME_TAG_BEGIN, 
                             col_name,
                             NAME_TAG_END, 
                             COLFMLY_TAG_END])

    schema_xml += ''.join([ACCGRP_TAG_END, ROOT_TAG_END])
    return schema_xml


  def __encode(self, bytes_in):
    """ Removes \x00 character with \x01 because hypertable truncates strings
        with null chars.
   
    Args:
      bytes_in: The string which will be encoded
    Returns:
      modified string with replaced chars
    """
    return bytes_in.replace('\x00','\x01')

  def __decode(self, bytes_out):
    """ Replaces \x01 character with \x00 because we swap out strings to 
        prevent truncating keys.
   
    Args:
      bytes_out: The string which will be decoded 
    Returns:
      Modified string with replaced chars
    """
    return bytes_out.replace('\x01', '\x00')

