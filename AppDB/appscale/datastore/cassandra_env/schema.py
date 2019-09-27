""" Create Cassandra keyspace and initial tables. """

import cassandra
import logging
import sys
import time
from collections import defaultdict

from kazoo.client import KazooClient

import cassandra_interface

from appscale.common import appscale_info
from appscale.common.constants import SCHEMA_CHANGE_TIMEOUT
from appscale.common.datastore_index import DatastoreIndex, merge_indexes
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.cluster import SimpleStatement
from cassandra.policies import FallthroughRetryPolicy, RetryPolicy
from .cassandra_interface import IndexStates
from .cassandra_interface import INITIAL_CONNECT_RETRIES
from .cassandra_interface import KEYSPACE
from .cassandra_interface import ScatterPropStates
from .cassandra_interface import ThriftColumn
from .constants import CURRENT_VERSION, LB_POLICY
from .. import dbconstants

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb
from google.net.proto.ProtocolBuffer import ProtocolBufferDecodeError

# A policy that does not retry statements.
NO_RETRIES = FallthroughRetryPolicy()

logger = logging.getLogger(__name__)

# The number of times to retry idempotent statements.
BASIC_RETRY_COUNT = 5


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
    if retry_num >= BASIC_RETRY_COUNT:
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
    if retry_num >= BASIC_RETRY_COUNT:
      return self.RETHROW, None
    else:
      return self.RETRY, consistency

  def on_unavailable(self, query, consistency, required_replicas,
                     alive_replicas, retry_num):
    """ The coordinator has detected an insufficient number of live replicas.

    Args:
      query: A statement that timed out.
      consistency: The consistency level of the statement.
      required_replicas: The number of replicas required to complete query.
      alive_replicas: The number of replicas that are ready to complete query.
      retry_num: The number of times the statement has been tried.
    """
    if retry_num >= BASIC_RETRY_COUNT:
      return self.RETHROW, None
    else:
      return self.RETRY, consistency


# A basic policy that retries idempotent operations.
BASIC_RETRIES = IdempotentRetryPolicy()


def define_ua_schema(session):
  """ Populate the schema table for the UAServer.

  Args:
    session: A cassandra-driver session.
  """
  uaserver_tables = [
    {'name': dbconstants.USERS_TABLE, 'schema': dbconstants.USERS_SCHEMA}
  ]
  for table in uaserver_tables:
    key = bytearray('/'.join([dbconstants.SCHEMA_TABLE, table['name']]))
    columns = bytearray(':'.join(table['schema']))
    define_schema = """
        INSERT INTO "{table}" ({key}, {column}, {value})
        VALUES (%(key)s, %(column)s, %(value)s)
      """.format(table=dbconstants.SCHEMA_TABLE,
                 key=ThriftColumn.KEY,
                 column=ThriftColumn.COLUMN_NAME,
                 value=ThriftColumn.VALUE)
    values = {'key': key,
              'column': dbconstants.SCHEMA_TABLE_SCHEMA[0],
              'value': columns}
    session.execute(define_schema, values)


def create_batch_tables(cluster, session):
  """ Create the tables required for large batches.

  Args:
    cluster: A cassandra-driver cluster.
    session: A cassandra-driver session.
  """
  keyspace_metadata = cluster.metadata.keyspaces[KEYSPACE]
  if 'batches' in keyspace_metadata.tables:
    columns = keyspace_metadata.tables['batches'].columns
    if ('transaction' in columns and
        columns['transaction'].cql_type != 'bigint'):
      session.execute('DROP TABLE batches', timeout=SCHEMA_CHANGE_TIMEOUT)

  logger.info('Trying to create batches')
  create_table = """
    CREATE TABLE IF NOT EXISTS batches (
      app text,
      transaction bigint,
      namespace text,
      path blob,
      old_value blob,
      new_value blob,
      exclude_indices text,
      PRIMARY KEY ((app, transaction), namespace, path)
    )
  """
  statement = SimpleStatement(create_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except cassandra.OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating batches table. '
      'Waiting {} seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise

  if ('batch_status' in keyspace_metadata.tables and
      'txid_hash' not in keyspace_metadata.tables['batch_status'].columns):
    session.execute('DROP TABLE batch_status', timeout=SCHEMA_CHANGE_TIMEOUT)

  logger.info('Trying to create batch_status')
  create_table = """
    CREATE TABLE IF NOT EXISTS batch_status (
      txid_hash blob PRIMARY KEY,
      applied boolean,
      op_id uuid
    )
  """
  statement = SimpleStatement(create_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except cassandra.OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating batch_status table. '
      'Waiting {} seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise


def create_groups_table(session):
  create_table = """
    CREATE TABLE IF NOT EXISTS group_updates (
      group blob PRIMARY KEY,
      last_update bigint
    )
  """
  statement = SimpleStatement(create_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except cassandra.OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating group_updates table. '
      'Waiting {} seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise


def create_transactions_table(session):
  """ Create the table used for storing transaction metadata.

  Args:
    session: A cassandra-driver session.
  """
  create_table = """
    CREATE TABLE IF NOT EXISTS transactions (
      txid_hash blob,
      operation tinyint,
      namespace text,
      path blob,
      start_time timestamp,
      is_xg boolean,
      in_progress blob,
      entity blob,
      task blob,
      PRIMARY KEY (txid_hash, operation, namespace, path)
    ) WITH gc_grace_seconds = 120
  """
  statement = SimpleStatement(create_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except cassandra.OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating transactions table. '
      'Waiting {} seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise


def create_entity_ids_table(session):
  create_table = """
    CREATE TABLE IF NOT EXISTS reserved_ids (
      project text,
      scattered boolean,
      last_reserved bigint,
      op_id uuid,
      PRIMARY KEY ((project, scattered))
    )
  """
  statement = SimpleStatement(create_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except cassandra.OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating entity_ids table. '
      'Waiting {} seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise


def current_datastore_version(session):
  """ Retrieves the existing datastore version value.

  Args:
    session: A cassandra-driver session.
  Returns:
    A float specifying the existing datastore version or None.
  """
  key = cassandra_interface.VERSION_INFO_KEY
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
  results = session.execute(statement, (bytearray(key), key))
  try:
    return float(results[0].value)
  except IndexError:
    return None


def migrate_composite_index_metadata(cluster, session, zk_client):
  """  Moves any existing datastore index metadata to ZooKeeper.

  Args:
    cluster: A cassandra.cluster.Cluster object.
    session: A cassandra.cluster.Session object.
    zk_client: A kazoo.client.KazooClient object.
  """
  keyspace_metadata = cluster.metadata.keyspaces[KEYSPACE]
  if dbconstants.METADATA_TABLE not in keyspace_metadata.tables:
    return

  logging.info('Fetching previously-defined index definitions')
  results = session.execute(
    'SELECT * FROM "{}"'.format(dbconstants.METADATA_TABLE))
  indexes_by_project = defaultdict(list)
  for result in results:
    try:
      index_pb = entity_pb.CompositeIndex(result.value)
    except ProtocolBufferDecodeError:
      logging.warning('Invalid composite index: {}'.format(result.value))
      continue

    index = DatastoreIndex.from_pb(index_pb)
    # Assume the index is complete.
    index.ready = True
    indexes_by_project[index.project_id].append(index)

  for project_id, indexes in indexes_by_project.items():
    logging.info('Adding indexes for {}'.format(project_id))
    merge_indexes(zk_client, project_id, indexes)

  logging.info('Removing previously-defined index definitions from Cassandra')
  session.execute('DROP TABLE "{}"'.format(dbconstants.METADATA_TABLE),
                  timeout=SCHEMA_CHANGE_TIMEOUT)


def prime_cassandra(replication):
  """ Create Cassandra keyspace and initial tables.

  Args:
    replication: An integer specifying the replication factor for the keyspace.
  Raises:
    AppScaleBadArg if replication factor is not greater than 0.
    TypeError if replication is not an integer.
  """
  if not isinstance(replication, int):
    raise TypeError('Replication must be an integer')

  if int(replication) <= 0:
    raise dbconstants.AppScaleBadArg('Replication must be greater than zero')

  zk_client = KazooClient(hosts=appscale_info.get_zk_node_ips())
  zk_client.start()

  hosts = appscale_info.get_db_ips()

  remaining_retries = INITIAL_CONNECT_RETRIES
  while True:
    try:
      cluster = Cluster(hosts, load_balancing_policy=LB_POLICY)
      session = cluster.connect()
      break
    except cassandra.cluster.NoHostAvailable as connection_error:
      remaining_retries -= 1
      if remaining_retries < 0:
        raise connection_error
      time.sleep(3)
  session.default_consistency_level = ConsistencyLevel.QUORUM

  create_keyspace = """
    CREATE KEYSPACE IF NOT EXISTS "{keyspace}"
    WITH REPLICATION = %(replication)s
  """.format(keyspace=KEYSPACE)
  keyspace_replication = {'class': 'SimpleStrategy',
                          'replication_factor': replication}
  session.execute(create_keyspace, {'replication': keyspace_replication},
                  timeout=SCHEMA_CHANGE_TIMEOUT)
  session.set_keyspace(KEYSPACE)

  logger.info('Waiting for all hosts to be connected')
  deadline = time.time() + SCHEMA_CHANGE_TIMEOUT
  while True:
    if time.time() > deadline:
      logger.warning('Timeout when waiting for hosts to join. Continuing '
                      'with connected hosts.')
      break

    if len(session.get_pool_state()) == len(hosts):
      break

    time.sleep(1)

  for table in dbconstants.INITIAL_TABLES:
    create_table = """
      CREATE TABLE IF NOT EXISTS "{table}" (
        {key} blob,
        {column} text,
        {value} blob,
        PRIMARY KEY ({key}, {column})
      ) WITH COMPACT STORAGE
    """.format(table=table,
               key=ThriftColumn.KEY,
               column=ThriftColumn.COLUMN_NAME,
               value=ThriftColumn.VALUE)
    statement = SimpleStatement(create_table, retry_policy=NO_RETRIES)

    logger.info('Trying to create {}'.format(table))
    try:
      session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
    except cassandra.OperationTimedOut:
      logger.warning(
        'Encountered an operation timeout while creating {} table. Waiting {} '
        'seconds for schema to settle.'.format(table, SCHEMA_CHANGE_TIMEOUT))
      time.sleep(SCHEMA_CHANGE_TIMEOUT)
      raise

  migrate_composite_index_metadata(cluster, session, zk_client)
  create_batch_tables(cluster, session)
  create_groups_table(session)
  create_transactions_table(session)
  create_entity_ids_table(session)

  first_entity = session.execute(
    'SELECT * FROM "{}" LIMIT 1'.format(dbconstants.APP_ENTITY_TABLE))
  existing_entities = len(list(first_entity)) == 1

  define_ua_schema(session)

  metadata_insert = """
    INSERT INTO "{table}" ({key}, {column}, {value})
    VALUES (%(key)s, %(column)s, %(value)s)
  """.format(
    table=dbconstants.DATASTORE_METADATA_TABLE,
    key=ThriftColumn.KEY,
    column=ThriftColumn.COLUMN_NAME,
    value=ThriftColumn.VALUE
  )

  if existing_entities:
    current_version = current_datastore_version(session)
    if current_version == 1.0:
      # Instruct the groomer to reclean the indexes.
      parameters = {'key': bytearray(cassandra_interface.INDEX_STATE_KEY),
                    'column': cassandra_interface.INDEX_STATE_KEY,
                    'value': bytearray(str(IndexStates.DIRTY))}
      session.execute(metadata_insert, parameters)

      parameters = {'key': bytearray(cassandra_interface.VERSION_INFO_KEY),
                    'column': cassandra_interface.VERSION_INFO_KEY,
                    'value': bytearray(str(CURRENT_VERSION))}
      session.execute(metadata_insert, parameters)
  else:
    parameters = {'key': bytearray(cassandra_interface.VERSION_INFO_KEY),
                  'column': cassandra_interface.VERSION_INFO_KEY,
                  'value': bytearray(str(CURRENT_VERSION))}
    session.execute(metadata_insert, parameters)

    # Mark the newly created indexes as clean.
    parameters = {'key': bytearray(cassandra_interface.INDEX_STATE_KEY),
                  'column': cassandra_interface.INDEX_STATE_KEY,
                  'value': bytearray(str(IndexStates.CLEAN))}
    session.execute(metadata_insert, parameters)

    # Indicate that scatter property values do not need to be populated.
    parameters = {'key': bytearray(cassandra_interface.SCATTER_PROP_KEY),
                  'column': cassandra_interface.SCATTER_PROP_KEY,
                  'value': bytearray(ScatterPropStates.POPULATED)}
    session.execute(metadata_insert, parameters)

  # Indicate that the database has been successfully primed.
  parameters = {'key': bytearray(cassandra_interface.PRIMED_KEY),
                'column': cassandra_interface.PRIMED_KEY,
                'value': bytearray(str(CURRENT_VERSION))}
  session.execute(metadata_insert, parameters)
  logger.info('Cassandra is primed.')


def primed():
  """ Check if the required keyspace and tables are present.

  Returns:
    A boolean indicating that Cassandra has been primed.
  """
  try:
    db_access = cassandra_interface.DatastoreProxy()
  except cassandra.InvalidRequest:
    return False

  try:
    primed_version = db_access.get_metadata_sync(cassandra_interface.PRIMED_KEY)
    return primed_version == str(CURRENT_VERSION)
  finally:
    db_access.close()
