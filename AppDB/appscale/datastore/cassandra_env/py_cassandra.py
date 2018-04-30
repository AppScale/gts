"""
Cassandra Interface for AppScale
"""
import time

from appscale.common import appscale_info
import cassandra
from cassandra.cluster import BatchStatement
from cassandra.cluster import Cluster
from cassandra.cluster import SimpleStatement
from cassandra.query import ConsistencyLevel
from cassandra.query import ValueSequence
from tornado import gen

from appscale.datastore import dbconstants
from appscale.datastore.cassandra_env.constants import LB_POLICY
from appscale.datastore.cassandra_env.cassandra_interface import (
  INITIAL_CONNECT_RETRIES, KEYSPACE, ThriftColumn
)
from appscale.datastore.cassandra_env.retry_policies import BASIC_RETRIES
from appscale.datastore.cassandra_env.tornado_cassandra import TornadoCassandra
from appscale.datastore.dbconstants import (
  AppScaleDBConnectionError, SCHEMA_TABLE, SCHEMA_TABLE_SCHEMA
)
from appscale.datastore.dbinterface import AppDBInterface
from appscale.datastore.utils import tornado_synchronous

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
        cluster = Cluster(hosts, load_balancing_policy=LB_POLICY)
        self.session = cluster.connect(keyspace=KEYSPACE)
        self.tornado_cassandra = TornadoCassandra(self.session)
        break
      except cassandra.cluster.NoHostAvailable as connection_error:
        remaining_retries -= 1
        if remaining_retries < 0:
          raise connection_error
        time.sleep(3)

    self.session.default_consistency_level = ConsistencyLevel.QUORUM

    # Provide synchronous version of get_schema method
    self.get_schema_sync = tornado_synchronous(self.get_schema)

  @gen.coroutine
  def get_entity(self, table_name, row_key, column_names):
    error = [ERROR_DEFAULT]
    list_ = error
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
      results = yield self.tornado_cassandra.execute(query, parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      raise AppScaleDBConnectionError('Unable to fetch entity')

    results_dict = {}
    for (_, column, value) in results:
      results_dict[column] = value

    if not results_dict:
      list_[0] += 'Not found'
      raise gen.Return(list_)

    for column in column_names:
      list_.append(results_dict[column])
    raise gen.Return(list_)

  @gen.coroutine
  def put_entity(self, table_name, row_key, column_names, cell_values):
    error = [ERROR_DEFAULT]
    list_ = error

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
      yield self.tornado_cassandra.execute(batch)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      list_[0] += 'Unable to insert entity'
      raise gen.Return(list_)

    list_.append("0")
    raise gen.Return(list_)

  def put_entity_dict(self, table_name, row_key, value_dict):
    raise NotImplementedError("put_entity_dict is not implemented in %s." % self.__class__)

  @gen.coroutine
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
      results = yield self.tornado_cassandra.execute(query)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      response[0] += 'Unable to fetch table contents'
      raise gen.Return(response)

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
          raise gen.Return(response)

    raise gen.Return(response)

  @gen.coroutine
  def delete_row(self, table_name, row_key):
    response = [ERROR_DEFAULT]
    row_key = bytearray('/'.join([table_name, row_key]))

    statement = 'DELETE FROM "{table}" WHERE {key} = %s'.format(
      table=table_name, key=ThriftColumn.KEY)
    delete = SimpleStatement(statement, retry_policy=BASIC_RETRIES)

    try:
      yield self.tornado_cassandra.execute(delete, (row_key,))
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      response[0] += 'Unable to delete row'
      raise gen.Return(response)

    response.append('0')
    raise gen.Return(response)

  @gen.coroutine
  def get_schema(self, table_name):
    error = [ERROR_DEFAULT]
    result = error
    ret = yield self.get_entity(SCHEMA_TABLE, table_name, SCHEMA_TABLE_SCHEMA)
    if len(ret) > 1:
      schema = ret[1]
    else:
      error[0] = ret[0] + "--unable to get schema"
      raise gen.Return(error)
    schema = schema.split(':')
    result = result + schema
    raise gen.Return(result)
