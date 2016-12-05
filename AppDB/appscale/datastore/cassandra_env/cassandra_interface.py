# Programmer: Navraj Chohan <nlake44@gmail.com>

"""
 Cassandra Interface for AppScale
"""
import cassandra
import logging
import sys
import time

from cassandra.cluster import Cluster
from cassandra.concurrent import execute_concurrent
from cassandra.policies import FallthroughRetryPolicy
from cassandra.policies import RetryPolicy
from cassandra.query import BatchStatement
from cassandra.query import ConsistencyLevel
from cassandra.query import SimpleStatement
from cassandra.query import ValueSequence
from .. import dbconstants
from .. import helper_functions
from ..dbconstants import AppScaleDBConnectionError
from ..dbconstants import TxnActions
from ..dbinterface import AppDBInterface
from ..unpackaged import APPSCALE_LIB_DIR
from ..utils import clean_app_id
from ..utils import encode_index_pb
from ..utils import get_composite_index_keys
from ..utils import get_composite_indexes_rows
from ..utils import get_entity_key
from ..utils import get_entity_kind
from ..utils import get_index_kv_from_tuple
from ..utils import get_kind_key

sys.path.append(APPSCALE_LIB_DIR)
import appscale_info

# The directory Cassandra is installed to.
CASSANDRA_INSTALL_DIR = '/opt/cassandra'

# Full path for the nodetool binary.
NODE_TOOL = '{}/cassandra/bin/nodetool'.format(CASSANDRA_INSTALL_DIR)

# The keyspace used for all tables
KEYSPACE = "Keyspace1"

# Cassandra watch name.
CASSANDRA_MONIT_WATCH_NAME = "cassandra-9999"

# The number of times to retry connecting to Cassandra.
INITIAL_CONNECT_RETRIES = 20

# The data layout version that the datastore expects.
EXPECTED_DATA_VERSION = 1.0

# The metadata key for the data layout version.
VERSION_INFO_KEY = 'version'

# The metadata key indicating that the database has been primed.
PRIMED_KEY = 'primed'

# The size in bytes that a batch must be to use the batches table.
LARGE_BATCH_THRESHOLD = 5 << 10


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


def deletions_for_entity(entity, composite_indices=()):
  """ Get a list of deletions needed across tables for deleting an entity.

  Args:
    entity: An entity object.
    composite_indices: A list or tuple of composite indices.
  Returns:
    A list of dictionaries representing mutation operations.
  """
  deletions = []
  app_id = clean_app_id(entity.key().app())
  namespace = entity.key().name_space()
  prefix = dbconstants.KEY_DELIMITER.join([app_id, namespace])

  asc_rows = get_index_kv_from_tuple([(prefix, entity)])
  for entry in asc_rows:
    deletions.append({'table': dbconstants.ASC_PROPERTY_TABLE,
                      'key': entry[0],
                      'operation': TxnActions.DELETE})

  dsc_rows = get_index_kv_from_tuple(
    [(prefix, entity)], reverse=True)
  for entry in dsc_rows:
    deletions.append({'table': dbconstants.DSC_PROPERTY_TABLE,
                      'key': entry[0],
                      'operation': TxnActions.DELETE})

  for key in get_composite_indexes_rows([entity], composite_indices):
    deletions.append({'table': dbconstants.COMPOSITE_TABLE,
                      'key': key,
                      'operation': TxnActions.DELETE})

  entity_key = get_entity_key(prefix, entity.key().path())
  deletions.append({'table': dbconstants.APP_ENTITY_TABLE,
                    'key': entity_key,
                    'operation': TxnActions.DELETE})

  kind_key = get_kind_key(prefix, entity.key().path())
  deletions.append({'table': dbconstants.APP_KIND_TABLE,
                    'key': kind_key,
                    'operation': TxnActions.DELETE})

  return deletions


def index_deletions(old_entity, new_entity, composite_indices=()):
  """ Get a list of index deletions needed for updating an entity. For changing
  an existing entity, this involves examining the property list of both
  entities to see which index entries need to be removed.

  Args:
    old_entity: An entity object.
    new_entity: An entity object.
    composite_indices: A list or tuple of composite indices.
  Returns:
    A list of dictionaries representing mutation operations.
  """
  deletions = []
  app_id = clean_app_id(old_entity.key().app())
  namespace = old_entity.key().name_space()
  kind = get_entity_kind(old_entity.key())
  entity_key = str(encode_index_pb(old_entity.key().path()))

  new_props = {}
  for prop in new_entity.property_list():
    if prop.name() not in new_props:
      new_props[prop.name()] = []
    new_props[prop.name()].append(prop)

  changed_props = {}
  for prop in old_entity.property_list():
    if prop.name() in new_props and prop in new_props[prop.name()]:
      continue

    if prop.name() not in changed_props:
      changed_props[prop.name()] = []
    changed_props[prop.name()].append(prop)

    value = str(encode_index_pb(prop.value()))

    key = dbconstants.KEY_DELIMITER.join(
      [app_id, namespace, kind, prop.name(), value, entity_key])
    deletions.append({'table': dbconstants.ASC_PROPERTY_TABLE,
                      'key': key,
                      'operation': TxnActions.DELETE})

    reverse_key = dbconstants.KEY_DELIMITER.join(
      [app_id, namespace, kind, prop.name(),
       helper_functions.reverse_lex(value), entity_key])
    deletions.append({'table': dbconstants.DSC_PROPERTY_TABLE,
                      'key': reverse_key,
                      'operation': TxnActions.DELETE})

  changed_prop_names = set(changed_props.keys())
  for index in composite_indices:
    if index.definition().entity_type() != kind:
      continue

    index_props = set(prop.name() for prop
                      in index.definition().property_list())
    if index_props.isdisjoint(changed_prop_names):
      continue

    old_entries = set(get_composite_index_keys(index, old_entity))
    new_entries = set(get_composite_index_keys(index, new_entity))
    for entry in (old_entries - new_entries):
      deletions.append({'table': dbconstants.COMPOSITE_TABLE,
                        'key': entry,
                        'operation': TxnActions.DELETE})

  return deletions


def mutations_for_entity(entity, txn, current_value=None,
                         composite_indices=()):
  """ Get a list of mutations needed across tables for an entity change.

  Args:
    entity: An entity object.
    txn: A transaction ID handler.
    current_value: The entity object currently stored.
    composite_indices: A list of composite indices for the entity kind.
  Returns:
    A list of dictionaries representing mutations.
  """
  mutations = []
  if current_value is not None:
    mutations.extend(
      index_deletions(current_value, entity, composite_indices))

  app_id = clean_app_id(entity.key().app())
  namespace = entity.key().name_space()
  encoded_path = str(encode_index_pb(entity.key().path()))
  prefix = dbconstants.KEY_DELIMITER.join([app_id, namespace])
  entity_key = dbconstants.KEY_DELIMITER.join([prefix, encoded_path])
  entity_value = {dbconstants.APP_ENTITY_SCHEMA[0]: entity.Encode(),
                  dbconstants.APP_ENTITY_SCHEMA[1]: str(txn)}
  mutations.append({'table': dbconstants.APP_ENTITY_TABLE,
                    'key': entity_key,
                    'operation': TxnActions.PUT,
                    'values': entity_value})

  reference_value = {'reference': entity_key}

  kind_key = get_kind_key(prefix, entity.key().path())
  mutations.append({'table': dbconstants.APP_KIND_TABLE,
                    'key': kind_key,
                    'operation': TxnActions.PUT,
                    'values': reference_value})

  asc_rows = get_index_kv_from_tuple([(prefix, entity)])
  for entry in asc_rows:
    mutations.append({'table': dbconstants.ASC_PROPERTY_TABLE,
                      'key': entry[0],
                      'operation': TxnActions.PUT,
                      'values': reference_value})

  dsc_rows = get_index_kv_from_tuple([(prefix, entity)], reverse=True)
  for entry in dsc_rows:
    mutations.append({'table': dbconstants.DSC_PROPERTY_TABLE,
                      'key': entry[0],
                      'operation': TxnActions.PUT,
                      'values': reference_value})

  for key in get_composite_indexes_rows([entity], composite_indices):
    mutations.append({'table': dbconstants.COMPOSITE_TABLE,
                      'key': key,
                      'operation': TxnActions.PUT,
                      'values': reference_value})

  return mutations


class FailedBatch(Exception):
  pass


class IdempotentRetryPolicy(RetryPolicy):
  """ A policy used for retrying idempotent statements. """
  def on_read_timeout(self, query, consistency, required_responses,
                      received_responses, data_retrieved, retry_num):
    """ This is called when a ReadTimeout occurs.

    Args:
      query: A statement that timed out.
      consistency: The consistency level of the statement.
      required_responses: The number of responses required.
      received_responses: The number of responses received.
      data_retrieved: Indicates whether any responses contained data.
      retry_num: The number of times the statement has been tried.
    """
    if retry_num >= 5:
      return self.RETHROW, None
    else:
      return self.RETRY, consistency

  def on_write_timeout(self, query, consistency, write_type,
                       required_responses, received_responses, retry_num):
    """ This is called when a WriteTimeout occurs.

    Args:
      query: A statement that timed out.
      consistency: The consistency level of the statement.
      required_responses: The number of responses required.
      received_responses: The number of responses received.
      data_retrieved: Indicates whether any responses contained data.
      retry_num: The number of times the statement has been tried.
      """
    if retry_num >= 5:
      return self.RETHROW, None
    else:
      return self.RETRY, consistency


class ThriftColumn(object):
  """ Columns created by default with thrift interface. """
  KEY = 'key'
  COLUMN_NAME = 'column1'
  VALUE = 'value'


class DatastoreProxy(AppDBInterface):
  """ 
    Cassandra implementation of the AppDBInterface
  """
  def __init__(self, log_level=logging.INFO):
    """
    Constructor.
    """
    class_name = self.__class__.__name__
    self.logger = logging.getLogger(class_name)
    self.logger.setLevel(log_level)
    self.logger.info('Starting {}'.format(class_name))

    self.hosts = appscale_info.get_db_ips()
    self.retry_policy = IdempotentRetryPolicy()
    self.no_retries = FallthroughRetryPolicy()

    remaining_retries = INITIAL_CONNECT_RETRIES
    while True:
      try:
        self.cluster = Cluster(self.hosts,
                               default_retry_policy=self.retry_policy)
        self.session = self.cluster.connect(KEYSPACE)
        break
      except cassandra.cluster.NoHostAvailable as connection_error:
        remaining_retries -= 1
        if remaining_retries < 0:
          raise connection_error
        time.sleep(3)

    self.session.default_consistency_level = ConsistencyLevel.QUORUM

  def close(self):
    """ Close all sessions and connections to Cassandra. """
    self.cluster.shutdown()

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
    query = SimpleStatement(statement, retry_policy=self.retry_policy)
    parameters = (ValueSequence(row_keys_bytes), ValueSequence(column_names))

    try:
      results = self.session.execute(query, parameters=parameters)

      results_dict = {row_key: {} for row_key in row_keys}
      for (key, column, value) in results:
        if key not in results_dict:
          results_dict[key] = {}
        results_dict[key][column] = value

      return results_dict
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during batch_get_entity'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

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

    insert_str = """
      INSERT INTO "{table}" ({key}, {column}, {value})
      VALUES (?, ?, ?)
    """.format(table=table_name,
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
      execute_concurrent(self.session, statements_and_params,
                         raise_on_first_error=True)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during batch_put_entity'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

  def prepare_insert(self, table):
    """ Prepare an insert statement.

    Args:
      table: A string containing the table name.
    Returns:
      A PreparedStatement object.
    """
    statement = """
      INSERT INTO "{table}" ({key}, {column}, {value})
      VALUES (?, ?, ?)
    """.format(table=table,
               key=ThriftColumn.KEY,
               column=ThriftColumn.COLUMN_NAME,
               value=ThriftColumn.VALUE)
    return self.session.prepare(statement)

  def prepare_delete(self, table):
    """ Prepare a delete statement.

    Args:
      table: A string containing the table name.
    Returns:
      A PreparedStatement object.
    """
    statement = """
      DELETE FROM "{table}" WHERE {key} = ?
    """.format(table=table, key=ThriftColumn.KEY)
    return self.session.prepare(statement)

  def _normal_batch(self, mutations):
    """ Use Cassandra's native batch statement to apply mutations atomically.

    Args:
      mutations: A list of dictionaries representing mutations.
    """
    self.logger.debug('Normal batch: {} mutations'.format(len(mutations)))
    batch = BatchStatement(consistency_level=ConsistencyLevel.QUORUM,
                           retry_policy=self.retry_policy)
    prepared_statements = {'insert': {}, 'delete': {}}
    for mutation in mutations:
      table = mutation['table']
      if mutation['operation'] == TxnActions.PUT:
        if table not in prepared_statements['insert']:
          prepared_statements['insert'][table] = self.prepare_insert(table)
        values = mutation['values']
        for column in values:
          batch.add(
            prepared_statements['insert'][table],
            (bytearray(mutation['key']), column, bytearray(values[column]))
          )
      elif mutation['operation'] == TxnActions.DELETE:
        if table not in prepared_statements['delete']:
          prepared_statements['delete'][table] = self.prepare_delete(table)
        batch.add(
          prepared_statements['delete'][table],
          (bytearray(mutation['key']),)
        )

    try:
      self.session.execute(batch)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during batch_mutate'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

  def apply_mutations(self, mutations):
    """ Apply mutations across tables.

    Args:
      mutations: A list of dictionaries representing mutations.
    """
    prepared_statements = {'insert': {}, 'delete': {}}
    statements_and_params = []
    for mutation in mutations:
      table = mutation['table']
      if mutation['operation'] == TxnActions.PUT:
        if table not in prepared_statements['insert']:
          prepared_statements['insert'][table] = self.prepare_insert(table)
        values = mutation['values']
        for column in values:
          params = (bytearray(mutation['key']), column,
                    bytearray(values[column]))
          statements_and_params.append(
            (prepared_statements['insert'][table], params))
      elif mutation['operation'] == TxnActions.DELETE:
        if table not in prepared_statements['delete']:
          prepared_statements['delete'][table] = self.prepare_delete(table)
        params = (bytearray(mutation['key']),)
        statements_and_params.append(
          (prepared_statements['delete'][table], params))

    execute_concurrent(self.session, statements_and_params,
                       raise_on_first_error=True)

  def _large_batch(self, app, mutations, entity_changes, txn):
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
    set_status = """
      INSERT INTO batch_status (app, transaction, applied)
      VALUES (%(app)s, %(transaction)s, False)
      IF NOT EXISTS
    """
    parameters = {'app': app, 'transaction': txn}
    result = self.session.execute(set_status, parameters)
    if not result.was_applied:
      raise FailedBatch('A batch for transaction {} already exists'.
                        format(txn))

    insert_item = """
      INSERT INTO batches (app, transaction, namespace, path,
                           old_value, new_value)
      VALUES (?, ?, ?, ?, ?, ?)
    """
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
      execute_concurrent(self.session, statements_and_params,
                         raise_on_first_error=True)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during large batch'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

    update_status = """
      UPDATE batch_status
      SET applied = True
      WHERE app = %(app)s
      AND transaction = %(transaction)s
      IF applied = False
    """
    parameters = {'app': app, 'transaction': txn}
    result = self.session.execute(update_status, parameters)
    if not result.was_applied:
      raise FailedBatch('Another process modified batch for transaction {}'.
                        format(txn))

    try:
      self.apply_mutations(mutations)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during large batch'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

    clear_batch = """
      DELETE FROM batches
      WHERE app = %(app)s AND transaction = %(transaction)s
    """
    parameters = {'app': app, 'transaction': txn}
    self.session.execute(clear_batch, parameters)

    clear_status = """
      DELETE FROM batch_status
      WHERE app = %(app)s and transaction = %(transaction)s
    """
    parameters = {'app': app, 'transaction': txn}
    self.session.execute(clear_status, parameters)

  def batch_mutate(self, app, mutations, entity_changes, txn):
    """ Insert or delete multiple rows across tables in an atomic statement.

    Args:
      app: A string containing the application ID.
      mutations: A list of dictionaries representing mutations.
      entity_changes: A list of changes at the entity level.
      txn: A transaction ID handler.
    """
    size = batch_size(mutations)
    self.logger.debug('batch_size: {}'.format(size))
    if size > LARGE_BATCH_THRESHOLD:
      self._large_batch(app, mutations, entity_changes, txn)
    else:
      self._normal_batch(mutations)

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
    query = SimpleStatement(statement, retry_policy=self.retry_policy)
    parameters = (ValueSequence(row_keys_bytes),)

    try:
      self.session.execute(query, parameters=parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
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

    statement = 'DROP TABLE IF EXISTS "{table}"'.format(table=table_name)
    query = SimpleStatement(statement, retry_policy=self.retry_policy)

    try:
      self.session.execute(query)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during delete_table'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

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

    statement = 'CREATE TABLE IF NOT EXISTS "{table}" ('\
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
    query = SimpleStatement(statement, retry_policy=self.no_retries)

    try:
      self.session.execute(query)
    except cassandra.OperationTimedOut:
      logging.warning('Encountered an operation timeout while creating a '
                      'table. Waiting 1 minute for schema to settle.')
      time.sleep(60)
      raise AppScaleDBConnectionError('Exception during create_table')
    except (error for error in dbconstants.TRANSIENT_CASSANDRA_ERRORS
            if error != cassandra.OperationTimedOut):
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

    statement = """
      SELECT * FROM "{table}" WHERE
      token({key}) {gt_compare} %s AND
      token({key}) {lt_compare} %s AND
      {column} IN %s
      {limit}
      ALLOW FILTERING
    """.format(table=table_name,
               key=ThriftColumn.KEY,
               gt_compare=gt_compare,
               lt_compare=lt_compare,
               column=ThriftColumn.COLUMN_NAME,
               limit=query_limit)

    query = SimpleStatement(statement, retry_policy=self.retry_policy)
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
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Exception during range_query'
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

  def get_metadata(self, key):
    """ Retrieve a value from the datastore metadata table.

    Args:
      key: A string containing the key to fetch.
    Returns:
      A string containing the value or None if the key is not present.
    """
    statement = """
      SELECT {value} FROM "{table}"
      WHERE {key} = %s
      AND {column} = %s
    """.format(
      value=ThriftColumn.VALUE,
      table=dbconstants.DATASTORE_METADATA_TABLE,
      key=ThriftColumn.KEY,
      column=ThriftColumn.COLUMN_NAME
    )
    try:
      results = self.session.execute(statement, (bytearray(key), key))
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Unable to fetch {} from datastore metadata'.format(key)
      logging.exception(message)
      raise AppScaleDBConnectionError(message)

    try:
      return results[0].value
    except IndexError:
      return None

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

    statement = """
      INSERT INTO "{table}" ({key}, {column}, {value})
      VALUES (%(key)s, %(column)s, %(value)s)
    """.format(
      table=dbconstants.DATASTORE_METADATA_TABLE,
      key=ThriftColumn.KEY,
      column=ThriftColumn.COLUMN_NAME,
      value=ThriftColumn.VALUE
    )
    parameters = {'key': bytearray(key),
                  'column': key,
                  'value': bytearray(value)}
    try:
      self.session.execute(statement, parameters)
    except dbconstants.TRANSIENT_CASSANDRA_ERRORS:
      message = 'Unable to set datastore metadata for {}'.format(key)
      logging.exception(message)
      raise AppScaleDBConnectionError(message)
    except cassandra.InvalidRequest:
      self.create_table(dbconstants.DATASTORE_METADATA_TABLE,
                        dbconstants.DATASTORE_METADATA_SCHEMA)
      self.session.execute(statement, parameters)

  def get_indices(self, app_id):
    """ Gets the indices of the given application.

    Args:
      app_id: Name of the application.
    Returns:
      Returns a list of encoded entity_pb.CompositeIndex objects.
    """
    start_key = dbconstants.KEY_DELIMITER.join([app_id, 'index', ''])
    end_key = dbconstants.KEY_DELIMITER.join(
      [app_id, 'index', dbconstants.TERMINATING_STRING])
    result = self.range_query(
      dbconstants.METADATA_TABLE,
      dbconstants.METADATA_SCHEMA,
      start_key,
      end_key,
      dbconstants.MAX_NUMBER_OF_COMPOSITE_INDEXES,
      offset=0,
      start_inclusive=True,
      end_inclusive=True)
    list_result = []
    for list_item in result:
      for key, value in list_item.iteritems():
        list_result.append(value['data'])
    return list_result

  def valid_data_version(self):
    """ Checks whether or not the data layout can be used.

    Returns:
      A boolean.
    """
    try:
      version = self.get_metadata(VERSION_INFO_KEY)
    except cassandra.InvalidRequest:
      return False

    return version is not None and float(version) == EXPECTED_DATA_VERSION
