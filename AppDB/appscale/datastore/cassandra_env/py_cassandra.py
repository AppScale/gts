"""
Cassandra Interface for AppScale
"""
import cassandra
import sys
import time

from cassandra.cluster import BatchStatement
from cassandra.cluster import Cluster
from cassandra.cluster import SimpleStatement
from cassandra.query import ConsistencyLevel
from cassandra.query import ValueSequence
from .cassandra_interface import INITIAL_CONNECT_RETRIES
from .cassandra_interface import KEYSPACE
from .cassandra_interface import ThriftColumn
from .retry_policies import BASIC_RETRIES
from .. import dbconstants
from ..dbconstants import AppScaleDBConnectionError
from ..dbconstants import SCHEMA_TABLE
from ..dbconstants import SCHEMA_TABLE_SCHEMA
from ..dbinterface import AppDBInterface
from ..unpackaged import APPSCALE_LIB_DIR

sys.path.append(APPSCALE_LIB_DIR)
import appscale_info

ERROR_DEFAULT = "DB_ERROR:" # ERROR_CASSANDRA

PERSISTENT_CONNECTION = False
PROFILING = False

MAX_ROW_COUNT = 10000000


class DatastoreProxy(AppDBInterface):
  def __init__(self):
    hosts = appscale_info.get_db_ips()

    remaining_retries = INITIAL_CONNECT_RETRIES
    while True:
      try:
        cluster = Cluster(hosts)
        self.session = cluster.connect(keyspace=KEYSPACE)
        break
      except cassandra.cluster.NoHostAvailable as connection_error:
        remaining_retries -= 1
        if remaining_retries < 0:
          raise connection_error
        time.sleep(3)

    self.session.default_consistency_level = ConsistencyLevel.QUORUM

  def get_entity(self, table_name, row_key, column_names):
    error = [ERROR_DEFAULT]
    list = error
    row_key = bytearray('/'.join([table_name, row_key]))
    statement = """
      SELECT * FROM "{table}"
      WHERE {key} = %(key)s
      AND {column} IN %(columns)s
    """.format(table=table_name,
               key=ThriftColumn.KEY,
               column=ThriftColumn.COLUMN_NAME)
    query = SimpleStatement(statement, retry_policy=BASIC_RETRIES)
    parameters = {'key': row_key,
                  'columns': ValueSequence(column_names)}
    try:
      results = self.session.execute(query, parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      raise AppScaleDBConnectionError('Unable to fetch entity')

    results_dict = {}
    for (_, column, value) in results:
      results_dict[column] = value

    if not results_dict:
      list[0] += 'Not found'
      return list

    for column in column_names:
      list.append(results_dict[column])
    return list

  def put_entity(self, table_name, row_key, column_names, cell_values):
    error = [ERROR_DEFAULT]
    list = error

    row_key = bytearray('/'.join([table_name, row_key]))
    values = {}
    for index, column in enumerate(column_names):
      values[column] = cell_values[index]

    statement = """
      INSERT INTO "{table}" ({key}, {column}, {value})
      VALUES (%(key)s, %(column)s, %(value)s)
    """.format(table=table_name,
               key=ThriftColumn.KEY,
               column=ThriftColumn.COLUMN_NAME,
               value=ThriftColumn.VALUE)
    batch = BatchStatement(retry_policy=BASIC_RETRIES)
    for column in column_names:
      parameters = {'key': row_key,
                   'column': column,
                   'value': bytearray(values[column])}
      batch.add(statement, parameters)

    try:
      self.session.execute(batch)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      list[0] += 'Unable to insert entity'
      return list

    list.append("0")
    return list

  def put_entity_dict(self, table_name, row_key, value_dict):
    raise NotImplementedError("put_entity_dict is not implemented in %s." % self.__class__)


  def get_table(self, table_name, column_names):
    """ Fetch a list of values for the given columns in a table.

    Args:
      table_name: A string containing the name of the table.
      column_names: A list of column names to retrieve values for.
    Returns:
      A list containing a status marker followed by the values.
      Note: The response does not contain any row keys or column names.
    """
    response = [ERROR_DEFAULT]

    statement = 'SELECT * FROM "{table}"'.format(table=table_name)
    query = SimpleStatement(statement, retry_policy=BASIC_RETRIES)

    try:
      results = self.session.execute(query)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      response[0] += 'Unable to fetch table contents'
      return response

    results_list = []
    current_item = {}
    current_key = None
    for (key, column, value) in results:
      if key != current_key:
        if current_item:
          results_list.append({current_key: current_item})
        current_item = {}
        current_key = key

      current_item[column] = value
    if current_item:
      results_list.append({current_key: current_item})

    for result in results_list:
      result_columns = result.values()[0]
      for column in column_names:
        try:
          response.append(result_columns[column])
        except KeyError:
          response[0] += 'Table contents did not match schema'
          return response

    return response

  def delete_row(self, table_name, row_key):
    response = [ERROR_DEFAULT]
    row_key = bytearray('/'.join([table_name, row_key]))

    statement = 'DELETE FROM "{table}" WHERE {key} = %s'.format(
      table=table_name, key=ThriftColumn.KEY)
    delete = SimpleStatement(statement, retry_policy=BASIC_RETRIES)

    try:
      self.session.execute(delete, (row_key,))
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      response[0] += 'Unable to delete row'
      return response

    response.append('0')
    return response

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
