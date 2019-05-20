# Programmer: Navraj Chohan <nlake44@gmail.com>

"""
 Cassandra Interface for AppScale
"""
import datetime
import logging
import struct
import sys
import time
import uuid

from appscale.common import appscale_info
from appscale.common.async_retrying import retry_raw_coroutine
from appscale.common.constants import SCHEMA_CHANGE_TIMEOUT
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
import cassandra
from cassandra.cluster import Cluster
from cassandra.query import BatchStatement
from cassandra.query import ConsistencyLevel
from cassandra.query import SimpleStatement
from cassandra.query import ValueSequence
from tornado import gen

from appscale.datastore import dbconstants
from appscale.datastore.cassandra_env.constants import (
  CURRENT_VERSION, LB_POLICY
)
from appscale.datastore.cassandra_env.large_batch import (
  BatchNotApplied, FailedBatch, LargeBatch
)
from appscale.datastore.cassandra_env.retry_policies import (
  BASIC_RETRIES, NO_RETRIES
)
from appscale.datastore.cassandra_env.tornado_cassandra import TornadoCassandra
from appscale.datastore.dbconstants import (
  AppScaleDBConnectionError, Operations, TxnActions
)
from appscale.datastore.dbinterface import AppDBInterface
from appscale.datastore.utils import create_key, get_write_time, tx_partition, \
  tornado_synchronous

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.datastore import entity_pb


# The directory Cassandra is installed to.
CASSANDRA_INSTALL_DIR = '/opt/cassandra'

# The maximum amount of entities to fetch concurrently.
ENTITY_FETCH_THRESHOLD = 100

# Full path for the nodetool binary.
NODE_TOOL = '{}/cassandra/bin/nodetool'.format(CASSANDRA_INSTALL_DIR)

# The keyspace used for all tables
KEYSPACE = "Keyspace1"

# Cassandra watch name.
CASSANDRA_MONIT_WATCH_NAME = "cassandra"

# The number of times to retry connecting to Cassandra.
INITIAL_CONNECT_RETRIES = 20

# The metadata key for the data layout version.
VERSION_INFO_KEY = 'version'

# The metadata key used to indicate the state of the indexes.
INDEX_STATE_KEY = 'index_state'

# The metadata key used to indicate whether or not some entities are missing
# the scatter property.
SCATTER_PROP_KEY = 'scatter_prop'

# The metadata key indicating that the database has been primed.
PRIMED_KEY = 'primed'

# The size in bytes that a batch must be to use the batches table.
LARGE_BATCH_THRESHOLD = 5 << 10

logger = logging.getLogger(__name__)


def batch_size(batch):
  """ Calculates the size of a batch.

  Args:
    batch: A list of dictionaries representing mutations.
  Returns:
    An integer specifying the size in bytes of the batch.
  """
  size = 0
  for mutation in batch:
    size += len(mutation['key'])
    if 'values' in mutation:
      for value in mutation['values'].values():
        size += len(value)
  return size


class ThriftColumn(object):
  """ Columns created by default with thrift interface. """
  KEY = 'key'
  COLUMN_NAME = 'column1'
  VALUE = 'value'


class IndexStates(object):
  """ Possible states for datastore indexes. """
  CLEAN = 'clean'
  DIRTY = 'dirty'
  SCRUB_IN_PROGRESS = 'scrub_in_progress'


class ScatterPropStates(object):
  """ Possible states for indexing the scatter property. """
  POPULATED = 'populated'
  POPULATION_IN_PROGRESS = 'population_in_progress'


class DatastoreProxy(AppDBInterface):
  """
    Cassandra implementation of the AppDBInterface
  """
  def __init__(self, log_level=logging.INFO, hosts=None):
    """
    Constructor.
    """
    class_name = self.__class__.__name__
    self.logger = logging.getLogger(class_name)
    self.logger.setLevel(log_level)
    self.logger.info('Starting {}'.format(class_name))

    if hosts is not None:
      self.hosts = hosts
    else:
      self.hosts = appscale_info.get_db_ips()

    remaining_retries = INITIAL_CONNECT_RETRIES
    while True:
      try:
        self.cluster = Cluster(self.hosts, default_retry_policy=BASIC_RETRIES,
                               load_balancing_policy=LB_POLICY)
        self.session = self.cluster.connect(KEYSPACE)
        self.tornado_cassandra = TornadoCassandra(self.session)
        break
      except cassandra.cluster.NoHostAvailable as connection_error:
        remaining_retries -= 1
        if remaining_retries < 0:
          raise connection_error
        time.sleep(3)

    self.session.default_consistency_level = ConsistencyLevel.QUORUM
    self.prepared_statements = {}

    # Provide synchronous version of some async methods
    self.batch_get_entity_sync = tornado_synchronous(self.batch_get_entity)
    self.batch_put_entity_sync = tornado_synchronous(self.batch_put_entity)
    self.batch_delete_sync = tornado_synchronous(self.batch_delete)
    self.valid_data_version_sync = tornado_synchronous(self.valid_data_version)
    self.range_query_sync = tornado_synchronous(self.range_query)
    self.get_metadata_sync = tornado_synchronous(self.get_metadata)
    self.set_metadata_sync = tornado_synchronous(self.set_metadata)
    self.delete_table_sync = tornado_synchronous(self.delete_table)

  def close(self):
    """ Close all sessions and connections to Cassandra. """
    self.cluster.shutdown()

  @gen.coroutine
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
    query = SimpleStatement(statement, retry_policy=BASIC_RETRIES)

    results = []
    # Split the rows up into chunks to reduce the likelihood of timeouts.
    chunk_indexes = [
      (n, n + ENTITY_FETCH_THRESHOLD)
      for n in xrange(0, len(row_keys_bytes), ENTITY_FETCH_THRESHOLD)]

    # TODO: This can be made more efficient by maintaining a constant number
    # of concurrent requests rather than waiting for each batch to complete.
    for start, end in chunk_indexes:
      parameters = (ValueSequence(row_keys_bytes[start:end]),
                    ValueSequence(column_names))
      try:
        batch_results = yield self.tornado_cassandra.execute(
          query, parameters=parameters)
      except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
        message = 'Exception during batch_get_entity'
        logger.exception(message)
        raise AppScaleDBConnectionError(message)

      results.extend(list(batch_results))

    results_dict = {row_key: {} for row_key in row_keys}
    for (key, column, value) in results:
      if key not in results_dict:
        results_dict[key] = {}

      results_dict[key][column] = value

    raise gen.Return(results_dict)

  @gen.coroutine
  def batch_put_entity(self, table_name, row_keys, column_names, cell_values,
                       ttl=None):
    """
    Allows callers to store multiple rows with a single call. A row can
    have multiple columns and values with them. We refer to each row as
    an entity.

    Args:
      table_name: The table to mutate
      row_keys: A list of keys to store on
      column_names: A list of columns to mutate
      cell_values: A dict of key/value pairs
      ttl: The number of seconds to keep the row.
    Raises:
      TypeError: If an argument passed in was not of the expected type.
      AppScaleDBConnectionError: If the batch_put could not be performed due to
        an error with Cassandra.
    """
    if not isinstance(table_name, str):
      raise TypeError("Expected a str")
    if not isinstance(column_names, list):
      raise TypeError("Expected a list")
    if not isinstance(row_keys, list):
      raise TypeError("Expected a list")
    if not isinstance(cell_values, dict):
      raise TypeError("Expected a dict")

    insert_str = (
      'INSERT INTO "{table}" ({key}, {column}, {value}) '
      'VALUES (?, ?, ?)'
    ).format(table=table_name,
               key=ThriftColumn.KEY,
               column=ThriftColumn.COLUMN_NAME,
               value=ThriftColumn.VALUE)

    if ttl is not None:
      insert_str += 'USING TTL {}'.format(ttl)

    statement = self.session.prepare(insert_str)

    statements_and_params = []
    for row_key in row_keys:
      for column in column_names:
        params = (bytearray(row_key), column,
                  bytearray(cell_values[row_key][column]))
        statements_and_params.append((statement, params))

    try:
      yield [
        self.tornado_cassandra.execute(statement, parameters=params)
        for statement, params in statements_and_params
      ]
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during batch_put_entity'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  def prepare_insert(self, table):
    """ Prepare an insert statement.

    Args:
      table: A string containing the table name.
    Returns:
      A PreparedStatement object.
    """
    statement = (
      'INSERT INTO "{table}" ({key}, {column}, {value}) '
      'VALUES (?, ?, ?) '
      'USING TIMESTAMP ?'
    ).format(table=table,
               key=ThriftColumn.KEY,
               column=ThriftColumn.COLUMN_NAME,
               value=ThriftColumn.VALUE)

    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = self.session.prepare(statement)

    return self.prepared_statements[statement]

  def prepare_delete(self, table):
    """ Prepare a delete statement.

    Args:
      table: A string containing the table name.
    Returns:
      A PreparedStatement object.
    """
    statement = (
      'DELETE FROM "{table}" '
      'USING TIMESTAMP ? '
      'WHERE {key} = ?'
    ).format(table=table, key=ThriftColumn.KEY)

    if statement not in self.prepared_statements:
      self.prepared_statements[statement] = self.session.prepare(statement)

    return self.prepared_statements[statement]

  @gen.coroutine
  def normal_batch(self, mutations, txid):
    """ Use Cassandra's native batch statement to apply mutations atomically.

    Args:
      mutations: A list of dictionaries representing mutations.
      txid: An integer specifying a transaction ID.
    """
    self.logger.debug('Normal batch: {} mutations'.format(len(mutations)))
    batch = BatchStatement(consistency_level=ConsistencyLevel.QUORUM,
                           retry_policy=BASIC_RETRIES)
    prepared_statements = {'insert': {}, 'delete': {}}
    for mutation in mutations:
      table = mutation['table']

      if table == 'group_updates':
        key = mutation['key']
        insert = (
          'INSERT INTO group_updates (group, last_update) '
          'VALUES (%(group)s, %(last_update)s) '
          'USING TIMESTAMP %(timestamp)s'
        )
        parameters = {'group': key, 'last_update': mutation['last_update'],
                      'timestamp': get_write_time(txid)}
        batch.add(insert, parameters)
        continue

      if mutation['operation'] == Operations.PUT:
        if table not in prepared_statements['insert']:
          prepared_statements['insert'][table] = self.prepare_insert(table)
        values = mutation['values']
        for column in values:
          batch.add(
            prepared_statements['insert'][table],
            (bytearray(mutation['key']), column, bytearray(values[column]),
             get_write_time(txid))
          )
      elif mutation['operation'] == Operations.DELETE:
        if table not in prepared_statements['delete']:
          prepared_statements['delete'][table] = self.prepare_delete(table)
        batch.add(
          prepared_statements['delete'][table],
          (get_write_time(txid), bytearray(mutation['key']))
        )

    try:
      yield self.tornado_cassandra.execute(batch)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Unable to apply batch'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  def statements_for_mutations(self, mutations, txid):
    """ Generates Cassandra statements for a list of mutations.

    Args:
      mutations: A list of dictionaries representing mutations.
      txid: An integer specifying a transaction ID.
    Returns:
      A list of tuples containing Cassandra statements and parameters.
    """
    prepared_statements = {'insert': {}, 'delete': {}}
    statements_and_params = []
    for mutation in mutations:
      table = mutation['table']

      if table == 'group_updates':
        key = mutation['key']
        insert = (
          'INSERT INTO group_updates (group, last_update) '
          'VALUES (%(group)s, %(last_update)s) '
          'USING TIMESTAMP %(timestamp)s'
        )
        parameters = {'group': key, 'last_update': mutation['last_update'],
                      'timestamp': get_write_time(txid)}
        statements_and_params.append((SimpleStatement(insert), parameters))
        continue

      if mutation['operation'] == Operations.PUT:
        if table not in prepared_statements['insert']:
          prepared_statements['insert'][table] = self.prepare_insert(table)
        values = mutation['values']
        for column in values:
          params = (bytearray(mutation['key']), column,
                    bytearray(values[column]), get_write_time(txid))
          statements_and_params.append(
            (prepared_statements['insert'][table], params))
      elif mutation['operation'] == Operations.DELETE:
        if table not in prepared_statements['delete']:
          prepared_statements['delete'][table] = self.prepare_delete(table)
        params = (get_write_time(txid), bytearray(mutation['key']))
        statements_and_params.append(
          (prepared_statements['delete'][table], params))

    return statements_and_params

  @gen.coroutine
  def apply_mutations(self, mutations, txid):
    """ Apply mutations across tables.

    Args:
      mutations: A list of dictionaries representing mutations.
      txid: An integer specifying a transaction ID.
    """
    statements_and_params = self.statements_for_mutations(mutations, txid)
    yield [
      self.tornado_cassandra.execute(statement, parameters=params)
      for statement, params in statements_and_params
    ]

  @gen.coroutine
  def large_batch(self, app, mutations, entity_changes, txn):
    """ Insert or delete multiple rows across tables in an atomic statement.

    Args:
      app: A string containing the application ID.
      mutations: A list of dictionaries representing mutations.
      entity_changes: A list of changes at the entity level.
      txn: A transaction ID handler.
    Raises:
      FailedBatch if a concurrent process modifies the batch status.
      AppScaleDBConnectionError if a database connection error was encountered.
    """
    self.logger.debug('Large batch: transaction {}, {} mutations'.
                      format(txn, len(mutations)))
    large_batch = LargeBatch(self.session, app, txn)
    try:
      yield large_batch.start()
    except FailedBatch as batch_error:
      raise BatchNotApplied(str(batch_error))

    insert_item = (
      'INSERT INTO batches (app, transaction, namespace, '
      '                     path, old_value, new_value) '
      'VALUES (?, ?, ?, ?, ?, ?)'
    )
    insert_statement = self.session.prepare(insert_item)

    statements_and_params = []
    for entity_change in entity_changes:
      old_value = None
      if entity_change['old'] is not None:
        old_value = bytearray(entity_change['old'].Encode())
      new_value = None
      if entity_change['new'] is not None:
        new_value = bytearray(entity_change['new'].Encode())

      parameters = (app, txn, entity_change['key'].name_space(),
                    bytearray(entity_change['key'].path().Encode()), old_value,
                    new_value)
      statements_and_params.append((insert_statement, parameters))

    try:
      yield [
        self.tornado_cassandra.execute(statement, parameters=params)
        for statement, params in statements_and_params
      ]
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Unable to write large batch log'
      logger.exception(message)
      raise BatchNotApplied(message)

    # Since failing after this point is expensive and time consuming, retry
    # operations to make a failure less likely.
    custom_retry_coroutine = retry_raw_coroutine(
      backoff_threshold=5, retrying_timeout=10,
      retry_on_exception=dbconstants.TRANSIENT_CASSANDRA_ERRORS)

    persistent_apply_batch = custom_retry_coroutine(large_batch.set_applied)
    try:
      yield persistent_apply_batch()
    except FailedBatch as batch_error:
      raise AppScaleDBConnectionError(str(batch_error))

    persistent_apply_mutations = custom_retry_coroutine(self.apply_mutations)
    try:
      yield persistent_apply_mutations(mutations, txn)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during large batch'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

    try:
      yield large_batch.cleanup()
    except FailedBatch:
      # This should not raise an exception since the batch is already applied.
      logger.exception('Unable to clear batch status')

    clear_batch = (
      'DELETE FROM batches '
      'WHERE app = %(app)s AND transaction = %(transaction)s'
    )
    parameters = {'app': app, 'transaction': txn}
    try:
      yield self.tornado_cassandra.execute(clear_batch, parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      logger.exception('Unable to clear batch log')

  @gen.coroutine
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
    query = SimpleStatement(statement, retry_policy=BASIC_RETRIES)
    parameters = (ValueSequence(row_keys_bytes),)

    try:
      yield self.tornado_cassandra.execute(query, parameters=parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during batch_delete'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
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

    statement = 'DROP TABLE IF EXISTS "{table}"'.format(table=table_name)
    query = SimpleStatement(statement, retry_policy=BASIC_RETRIES)

    try:
      yield self.tornado_cassandra.execute(query)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during delete_table'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
  def create_table(self, table_name, column_names):
    """
    Creates a table if it doesn't already exist.

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

    statement = (
      'CREATE TABLE IF NOT EXISTS "{table}" ('
      '{key} blob,'
      '{column} text,'
      '{value} blob,'
      'PRIMARY KEY ({key}, {column})'
      ') WITH COMPACT STORAGE'
    ).format(
      table=table_name,
      key=ThriftColumn.KEY,
      column=ThriftColumn.COLUMN_NAME,
      value=ThriftColumn.VALUE
    )
    query = SimpleStatement(statement, retry_policy=NO_RETRIES)

    try:
      yield self.tornado_cassandra.execute(query, timeout=SCHEMA_CHANGE_TIMEOUT)
    except cassandra.OperationTimedOut:
      logger.warning(
        'Encountered an operation timeout while creating a table. Waiting {} '
        'seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
      time.sleep(SCHEMA_CHANGE_TIMEOUT)
      raise AppScaleDBConnectionError('Exception during create_table')
    except (error for error in dbconstants.TRANSIENT_CASSANDRA_ERRORS
            if error != cassandra.OperationTimedOut):
      message = 'Exception during create_table'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
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
    if not isinstance(table_name, str):
      raise TypeError('table_name must be a string')
    if not isinstance(column_names, list):
      raise TypeError('column_names must be a list')
    if not isinstance(start_key, str):
      raise TypeError('start_key must be a string')
    if not isinstance(end_key, str):
      raise TypeError('end_key must be a string')
    if not isinstance(limit, (int, long)) and limit is not None:
      raise TypeError('limit must be int, long, or NoneType')
    if not isinstance(offset, (int, long)):
      raise TypeError('offset must be int or long')

    if start_inclusive:
      gt_compare = '>='
    else:
      gt_compare = '>'

    if end_inclusive:
      lt_compare = '<='
    else:
      lt_compare = '<'

    query_limit = ''
    if limit is not None:
      query_limit = 'LIMIT {}'.format(len(column_names) * limit)

    statement = (
      'SELECT * FROM "{table}" WHERE '
      'token({key}) {gt_compare} %s AND '
      'token({key}) {lt_compare} %s AND '
      '{column} IN %s '
      '{limit} '
      'ALLOW FILTERING'
    ).format(table=table_name,
             key=ThriftColumn.KEY,
             gt_compare=gt_compare,
             lt_compare=lt_compare,
             column=ThriftColumn.COLUMN_NAME,
             limit=query_limit)

    query = SimpleStatement(statement, retry_policy=BASIC_RETRIES)
    parameters = (bytearray(start_key), bytearray(end_key),
                  ValueSequence(column_names))

    try:
      results = yield self.tornado_cassandra.execute(
        query, parameters=parameters)

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
      raise gen.Return(results_list[offset:])
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during range_query'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
  def get_metadata(self, key):
    """ Retrieve a value from the datastore metadata table.

    Args:
      key: A string containing the key to fetch.
    Returns:
      A string containing the value or None if the key is not present.
    """
    statement = (
      'SELECT {value} FROM "{table}" '
      'WHERE {key} = %s '
      'AND {column} = %s'
    ).format(
      value=ThriftColumn.VALUE,
      table=dbconstants.DATASTORE_METADATA_TABLE,
      key=ThriftColumn.KEY,
      column=ThriftColumn.COLUMN_NAME
    )
    try:
      results = yield self.tornado_cassandra.execute(
        statement, (bytearray(key), key))
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Unable to fetch {} from datastore metadata'.format(key)
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

    try:
      raise gen.Return(results[0].value)
    except IndexError:
      return

  @gen.coroutine
  def set_metadata(self, key, value):
    """ Set a datastore metadata value.

    Args:
      key: A string containing the key to set.
      value: A string containing the value to set.
    """
    if not isinstance(key, str):
      raise TypeError('key should be a string')

    if not isinstance(value, str):
      raise TypeError('value should be a string')

    statement = (
      'INSERT INTO "{table}" ({key}, {column}, {value}) '
      'VALUES (%(key)s, %(column)s, %(value)s)'
    ).format(
      table=dbconstants.DATASTORE_METADATA_TABLE,
      key=ThriftColumn.KEY,
      column=ThriftColumn.COLUMN_NAME,
      value=ThriftColumn.VALUE
    )
    parameters = {'key': bytearray(key),
                  'column': key,
                  'value': bytearray(value)}
    try:
      yield self.tornado_cassandra.execute(statement, parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Unable to set datastore metadata for {}'.format(key)
      logger.exception(message)
      raise AppScaleDBConnectionError(message)
    except cassandra.InvalidRequest:
      yield self.create_table(dbconstants.DATASTORE_METADATA_TABLE,
                              dbconstants.DATASTORE_METADATA_SCHEMA)
      yield self.tornado_cassandra.execute(statement, parameters)

  @gen.coroutine
  def valid_data_version(self):
    """ Checks whether or not the data layout can be used.

    Returns:
      A boolean.
    """
    try:
      version = yield self.get_metadata(VERSION_INFO_KEY)
    except cassandra.InvalidRequest:
      raise gen.Return(False)

    is_expected_version = (
      version is not None and
      float(version) == CURRENT_VERSION
    )
    raise gen.Return(is_expected_version)

  @gen.coroutine
  def group_updates(self, groups):
    """ Fetch the latest transaction IDs for each group.

    Args:
      groups: An interable containing encoded Reference objects.
    Returns:
      A set of integers specifying transaction IDs.
    """
    query = 'SELECT * FROM group_updates WHERE group=%s'
    results = yield [
      self.tornado_cassandra.execute(query, [bytearray(group)])
      for group in groups
    ]
    updates = set(rows[0].last_update for rows in results if rows)
    raise gen.Return(updates)

  @gen.coroutine
  def start_transaction(self, app, txid, is_xg, in_progress):
    """ Persist transaction metadata.

    Args:
      app: A string containing an application ID.
      txid: An integer specifying the transaction ID.
      is_xg: A boolean specifying that the transaction is cross-group.
      in_progress: An iterable containing transaction IDs.
    """
    if in_progress:
      in_progress_bin = bytearray(
        struct.pack('q' * len(in_progress), *in_progress))
    else:
      in_progress_bin = None

    insert = (
      'INSERT INTO transactions (txid_hash, operation, namespace, path,'
      '                          start_time, is_xg, in_progress)'
      'VALUES (%(txid_hash)s, %(operation)s, %(namespace)s, %(path)s,'
      '        %(start_time)s, %(is_xg)s, %(in_progress)s)'
      'USING TTL {ttl}'
    ).format(ttl=dbconstants.MAX_TX_DURATION * 2)
    parameters = {'txid_hash': tx_partition(app, txid),
                  'operation': TxnActions.START,
                  'namespace': '',
                  'path': bytearray(''),
                  'start_time': datetime.datetime.utcnow(),
                  'is_xg': is_xg,
                  'in_progress': in_progress_bin}

    try:
      yield self.tornado_cassandra.execute(insert, parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception while starting a transaction'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
  def put_entities_tx(self, app, txid, entities):
    """ Update transaction metadata with new put operations.

    Args:
      app: A string containing an application ID.
      txid: An integer specifying the transaction ID.
      entities: A list of entities that will be put upon commit.
    """
    batch = BatchStatement(consistency_level=ConsistencyLevel.QUORUM,
                           retry_policy=BASIC_RETRIES)
    insert = self.session.prepare("""
      INSERT INTO transactions (txid_hash, operation, namespace, path, entity)
      VALUES (?, ?, ?, ?, ?)
      USING TTL {ttl}
    """.format(ttl=dbconstants.MAX_TX_DURATION * 2))

    for entity in entities:
      args = (tx_partition(app, txid),
              TxnActions.MUTATE,
              entity.key().name_space(),
              bytearray(entity.key().path().Encode()),
              bytearray(entity.Encode()))
      batch.add(insert, args)

    try:
      yield self.tornado_cassandra.execute(batch)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception while putting entities in a transaction'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
  def delete_entities_tx(self, app, txid, entity_keys):
    """ Update transaction metadata with new delete operations.

    Args:
      app: A string containing an application ID.
      txid: An integer specifying the transaction ID.
      entity_keys: A list of entity keys that will be deleted upon commit.
    """
    batch = BatchStatement(consistency_level=ConsistencyLevel.QUORUM,
                           retry_policy=BASIC_RETRIES)
    insert = self.session.prepare("""
      INSERT INTO transactions (txid_hash, operation, namespace, path, entity)
      VALUES (?, ?, ?, ?, ?)
      USING TTL {ttl}
    """.format(ttl=dbconstants.MAX_TX_DURATION * 2))

    for key in entity_keys:
      # The None value overwrites previous puts.
      args = (tx_partition(app, txid),
              TxnActions.MUTATE,
              key.name_space(),
              bytearray(key.path().Encode()),
              None)
      batch.add(insert, args)

    try:
      yield self.tornado_cassandra.execute(batch)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception while deleting entities in a transaction'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
  def transactional_tasks_count(self, app, txid):
    """ Count the number of existing tasks associated with the transaction.

    Args:
      app: A string specifying an application ID.
      txid: An integer specifying a transaction ID.
    Returns:
      An integer specifying the number of existing tasks.
    """
    select = (
      'SELECT count(*) FROM transactions '
      'WHERE txid_hash = %(txid_hash)s '
      'AND operation = %(operation)s'
    )
    parameters = {'txid_hash': tx_partition(app, txid),
                  'operation': TxnActions.ENQUEUE_TASK}
    try:
      result = yield self.tornado_cassandra.execute(select, parameters)
      raise gen.Return(result[0].count)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception while fetching task count'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
  def add_transactional_tasks(self, app, txid, tasks, service_id, version_id):
    """ Add tasks to be enqueued upon the completion of a transaction.

    Args:
      app: A string specifying an application ID.
      txid: An integer specifying a transaction ID.
      tasks: A list of TaskQueueAddRequest objects.
      service_id: A string specifying the client's service ID.
      version_id: A string specifying the client's version ID.
    """
    batch = BatchStatement(consistency_level=ConsistencyLevel.QUORUM,
                           retry_policy=BASIC_RETRIES)
    query_str = (
      'INSERT INTO transactions (txid_hash, operation, namespace, path, task) '
      'VALUES (?, ?, ?, ?, ?) '
      'USING TTL {ttl}'
    ).format(ttl=dbconstants.MAX_TX_DURATION * 2)
    insert = self.session.prepare(query_str)

    for task in tasks:
      task.clear_transaction()

      # The path for the task entry doesn't matter as long as it's unique.
      path = bytearray(str(uuid.uuid4()))

      task_payload = '_'.join([service_id, version_id, task.Encode()])
      args = (tx_partition(app, txid),
              TxnActions.ENQUEUE_TASK,
              '',
              path,
              task_payload)
      batch.add(insert, args)

    try:
      yield self.tornado_cassandra.execute(batch)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception while adding tasks in a transaction'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
  def record_reads(self, app, txid, group_keys):
    """ Keep track of which entity groups were read in a transaction.

    Args:
      app: A string specifying an application ID.
      txid: An integer specifying a transaction ID.
      group_keys: An iterable containing Reference objects.
    """
    batch = BatchStatement(consistency_level=ConsistencyLevel.QUORUM,
                           retry_policy=BASIC_RETRIES)
    insert = self.session.prepare("""
      INSERT INTO transactions (txid_hash, operation, namespace, path)
      VALUES (?, ?, ?, ?)
      USING TTL {ttl}
    """.format(ttl=dbconstants.MAX_TX_DURATION * 2))

    for group_key in group_keys:
      if not isinstance(group_key, entity_pb.Reference):
        group_key = entity_pb.Reference(group_key)

      args = (tx_partition(app, txid),
              TxnActions.GET,
              group_key.name_space(),
              bytearray(group_key.path().Encode()))
      batch.add(insert, args)

    try:
      yield self.tornado_cassandra.execute(batch)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception while recording reads in a transaction'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

  @gen.coroutine
  def get_transaction_metadata(self, app, txid):
    """ Fetch transaction state.

    Args:
      app: A string specifying an application ID.
      txid: An integer specifying a transaction ID.
    Returns:
      A dictionary containing transaction state.
    """
    select = (
      'SELECT namespace, operation, path, start_time, is_xg, in_progress, '
      '       entity, task '
      'FROM transactions '
      'WHERE txid_hash = %(txid_hash)s '
    )
    parameters = {'txid_hash': tx_partition(app, txid)}
    try:
      results = yield self.tornado_cassandra.execute(select, parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception while inserting entities in a transaction'
      logger.exception(message)
      raise AppScaleDBConnectionError(message)

    metadata = {'puts': {}, 'deletes': [], 'tasks': [], 'reads': set()}
    for result in results:
      if result.operation == TxnActions.START:
        metadata['start'] = result.start_time
        metadata['is_xg'] = result.is_xg
        metadata['in_progress'] = set()
        if metadata['in_progress'] is not None:
          metadata['in_progress'] = set(
            struct.unpack('q' * int(len(result.in_progress) / 8),
                          result.in_progress))
      if result.operation == TxnActions.MUTATE:
        key = create_key(app, result.namespace, result.path)
        if result.entity is None:
          metadata['deletes'].append(key)
        else:
          metadata['puts'][key.Encode()] = result.entity
      if result.operation == TxnActions.GET:
        group_key = create_key(app, result.namespace, result.path)
        metadata['reads'].add(group_key.Encode())
      if result.operation == TxnActions.ENQUEUE_TASK:
        service_id, version_id, task_pb = result.task.split('_', 2)
        task_metadata = {
          'service_id': service_id,
          'version_id': version_id,
          'task': taskqueue_service_pb.TaskQueueAddRequest(task_pb)}
        metadata['tasks'].append(task_metadata)
    raise gen.Return(metadata)
