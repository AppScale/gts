# Programmer: Navraj Chohan <nlake44@gmail.com>

"""
 Cassandra Interface for AppScale
"""
import logging
import os
import sys

from dbconstants import AppScaleDBConnectionError
from dbinterface import AppDBInterface
from cassandra.cluster import Cluster
from cassandra.query import BatchStatement
from cassandra.query import ConsistencyLevel
from cassandra.query import SimpleStatement
from cassandra.query import ValueSequence

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import file_io

# The directory Cassandra is installed to.
CASSANDRA_INSTALL_DIR = '/opt/cassandra'

# Full path for the nodetool binary.
NODE_TOOL = '{}/cassandra/bin/nodetool'.format(CASSANDRA_INSTALL_DIR)

# This is the default cassandra connection port
CASS_DEFAULT_PORT = 9160

# The keyspace used for all tables
KEYSPACE = "Keyspace1"

# The standard column family used for tables
STANDARD_COL_FAM = "Standard1"

# Cassandra watch name.
CASSANDRA_MONIT_WATCH_NAME = "cassandra-9999"


class ThriftColumn(object):
  """ Columns created by default with thrift interface. """
  KEY = 'key'
  COLUMN_NAME = 'column1'
  VALUE = 'value'


class DatastoreProxy(AppDBInterface):
  """ 
    Cassandra implementation of the AppDBInterface
  """
  def __init__(self):
    """
    Constructor.
    """

    # Allow the client to choose any database node to connect to.
    database_master = file_io.read('/etc/appscale/masters').split()
    database_slaves = file_io.read('/etc/appscale/slaves').split()

    # In a one node deployment, the master is also written in the slaves file,
    # so we have to take out any duplicates.
    self.hosts = list(set(database_master + database_slaves))
    self.cluster = Cluster(self.hosts)
    self.session = self.cluster.connect(KEYSPACE)

  def batch_get_entity(self, table_name, row_keys, column_names):
    """
    Takes in batches of keys and retrieves their corresponding rows.
    
    Args:
      table_name: The table to access
      row_keys: A list of keys to access
      column_names: A list of columns to access
    Returns:
      A dictionary of rows and columns/values of those rows. The format 
      looks like such: {key:{column_name:value,...}}
    Raises:
      TypeError: If an argument passed in was not of the expected type.
      AppScaleDBConnectionError: If the batch_get could not be performed due to
        an error with Cassandra.
    """
    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(column_names, list): raise TypeError("Expected a list")
    if not isinstance(row_keys, list): raise TypeError("Expected a list")

    row_keys_bytes = [bytearray(row_key) for row_key in row_keys]

    statement = 'SELECT * FROM "{table}" '\
                'WHERE {key} IN %s and {column} IN %s'.format(
                  table=table_name,
                  key=ThriftColumn.KEY,
                  column=ThriftColumn.COLUMN_NAME,
                )
    query = SimpleStatement(statement,
                            consistency_level=ConsistencyLevel.QUORUM)
    parameters = (ValueSequence(row_keys_bytes), ValueSequence(column_names))

    try:
      results = self.session.execute(query, parameters=parameters)

      results_dict = {}
      for (key, column, value) in results:
        if key not in results_dict:
          results_dict[key] = {}
        results_dict[key][column] = value

      return results_dict
    except Exception:
      message = 'Exception during batch_put_entity'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

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
      TypeError: If an argument passed in was not of the expected type.
      AppScaleDBConnectionError: If the batch_put could not be performed due to
        an error with Cassandra.
    """
    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(column_names, list): raise TypeError("Expected a list")
    if not isinstance(row_keys, list): raise TypeError("Expected a list")
    if not isinstance(cell_values, dict): raise TypeError("Expected a dic")

    statement = self.session.prepare(
      'INSERT INTO "{table}" ({key}, {column}, {value}) '\
      'VALUES (?, ?, ?)'.format(
        table=table_name,
        key=ThriftColumn.KEY,
        column=ThriftColumn.COLUMN_NAME,
        value=ThriftColumn.VALUE
      ))
    batch_insert = BatchStatement(consistency_level=ConsistencyLevel.QUORUM)

    for row_key in row_keys:
      for column in column_names:
        batch_insert.add(
          statement,
          (bytearray(row_key), column, bytearray(cell_values[row_key][column]))
        )

    try:
      self.session.execute(batch_insert)
    except Exception:
      message = 'Exception during batch_put_entity'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)
      
  def batch_delete(self, table_name, row_keys, column_names=()):
    """
    Remove a set of rows corresponding to a set of keys.
     
    Args:
      table_name: Table to delete rows from
      row_keys: A list of keys to remove
      column_names: Not used
    Raises:
      TypeError: If an argument passed in was not of the expected type.
      AppScaleDBConnectionError: If the batch_delete could not be performed due
        to an error with Cassandra.
    """ 
    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(row_keys, list): raise TypeError("Expected a list")

    row_keys_bytes = [bytearray(row_key) for row_key in row_keys]

    statement = 'DELETE FROM "{table}" WHERE {key} IN %s'.\
      format(
        table=table_name,
        key=ThriftColumn.KEY
      )
    query = SimpleStatement(statement,
                            consistency_level=ConsistencyLevel.QUORUM)
    parameters = (ValueSequence(row_keys_bytes),)

    try:
      self.session.execute(query, parameters=parameters)
    except Exception:
      message = 'Exception during batch_delete'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

  def delete_table(self, table_name):
    """ 
    Drops a given table (aka column family in Cassandra)
  
    Args:
      table_name: A string name of the table to drop
    Raises:
      TypeError: If an argument passed in was not of the expected type.
      AppScaleDBConnectionError: If the delete_table could not be performed due
        to an error with Cassandra.
    """
    if not isinstance(table_name, str): raise TypeError("Expected a str")

    statement = 'DROP TABLE "{table}"'.format(table=table_name)
    query = SimpleStatement(statement,
                            consistency_level=ConsistencyLevel.QUORUM)

    try:
      self.session.execute(query)
    except Exception:
      message = 'Exception during delete_table'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

  def create_table(self, table_name, column_names):
    """ 
    Creates a table as a column family
    
    Args:
      table_name: The column family name
      column_names: Not used but here to match the interface
    Raises:
      TypeError: If an argument passed in was not of the expected type.
      AppScaleDBConnectionError: If the create_table could not be performed due
        to an error with Cassandra.
    """
    if not isinstance(table_name, str): raise TypeError("Expected a str")
    if not isinstance(column_names, list): raise TypeError("Expected a list")

    statement = 'CREATE TABLE {table} ('\
        '{key} blob,'\
        '{column} text,'\
        '{value} blob,'\
        'PRIMARY KEY ({key}, {column})'\
      ') WITH COMPACT STORAGE'.format(
        table=table_name,
        key=ThriftColumn.KEY,
        column=ThriftColumn.COLUMN_NAME,
        value=ThriftColumn.VALUE
      )
    query = SimpleStatement(statement,
                            consistency_level=ConsistencyLevel.QUORUM)

    try:
      self.session.execute(query)
    except Exception:
      message = 'Exception during create_table'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

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
      TypeError: If an argument passed in was not of the expected type.
      AppScaleDBConnectionError: If the range_query could not be performed due
        to an error with Cassandra.
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

    if start_inclusive:
      gt_compare = '>='
    else:
      gt_compare = '>'

    if end_inclusive:
      lt_compare = '<='
    else:
      lt_compare = '<'

    statement = 'SELECT * FROM "{table}" WHERE '\
                'token({key}) {gt_compare} %s AND '\
                'token({key}) {lt_compare} %s AND '\
                '{column} IN %s '\
                'LIMIT {limit} '\
                'ALLOW FILTERING'.format(
                  table=table_name,
                  key=ThriftColumn.KEY,
                  gt_compare=gt_compare,
                  lt_compare=lt_compare,
                  column=ThriftColumn.COLUMN_NAME,
                  limit=len(column_names) * limit
                )
    query = SimpleStatement(statement,
                            consistency_level=ConsistencyLevel.QUORUM)
    parameters = (bytearray(start_key), bytearray(end_key),
                  ValueSequence(column_names))

    try:
      results = self.session.execute(query, parameters=parameters)

      results_list = []
      current_item = {}
      current_key = None
      for (key, column, value) in results:
        if keys_only:
          results_list.append(key)
          continue

        if key != current_key:
          if current_item:
            results_list.append({current_key: current_item})
          current_item = {}
          current_key = key

        current_item[column] = value
      if current_item:
        results_list.append({current_key: current_item})
      return results_list[offset:]
    except Exception:
      message = 'Exception during range_query'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)
