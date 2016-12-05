""" Create Cassandra keyspace and initial tables. """

import cassandra
import logging
import sys
import time

import cassandra_interface

from appscale.taskqueue.distributed_tq import create_pull_queue_tables
from cassandra import ConsistencyLevel
from cassandra.cluster import Cluster
from cassandra.cluster import SimpleStatement
from cassandra.policies import FallthroughRetryPolicy
from .cassandra_interface import INITIAL_CONNECT_RETRIES
from .cassandra_interface import KEYSPACE
from .cassandra_interface import ThriftColumn
from .. import dbconstants
from ..unpackaged import APPSCALE_LIB_DIR

sys.path.append(APPSCALE_LIB_DIR)
import appscale_info

# The data layout version to set after removing the journal table.
POST_JOURNAL_VERSION = 1.0

# A policy that does not retry statements.
NO_RETRIES = FallthroughRetryPolicy()


def define_ua_schema(session):
  """ Populate the schema table for the UAServer.

  Args:
    session: A cassandra-driver session.
  """
  uaserver_tables = [
    {'name': dbconstants.APPS_TABLE, 'schema': dbconstants.APPS_SCHEMA},
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
  logging.info('Trying to create batches')
  create_table = """
    CREATE TABLE IF NOT EXISTS batches (
      app text,
      transaction int,
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
    session.execute(statement)
  except cassandra.OperationTimedOut:
    logging.warning(
      'Encountered an operation timeout while creating batches table. '
      'Waiting 1 minute for schema to settle.')
    time.sleep(60)
    raise

  logging.info('Trying to create batch_status')
  create_table = """
    CREATE TABLE IF NOT EXISTS batch_status (
      app text,
      transaction int,
      applied boolean,
      PRIMARY KEY ((app), transaction)
    )
  """
  statement = SimpleStatement(create_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement)
  except cassandra.OperationTimedOut:
    logging.warning(
      'Encountered an operation timeout while creating batch_status table. '
      'Waiting 1 minute for schema to settle.')
    time.sleep(60)
    raise


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

  hosts = appscale_info.get_db_ips()

  cluster = None
  session = None
  remaining_retries = INITIAL_CONNECT_RETRIES
  while True:
    try:
      cluster = Cluster(hosts)
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
  session.execute(create_keyspace, {'replication': keyspace_replication})
  session.set_keyspace(KEYSPACE)

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

    logging.info('Trying to create {}'.format(table))
    try:
      session.execute(statement)
    except cassandra.OperationTimedOut:
      logging.warning(
        'Encountered an operation timeout while creating {} table. '
        'Waiting 1 minute for schema to settle.'.format(table))
      time.sleep(60)
      raise

  create_batch_tables(cluster, session)
  create_pull_queue_tables(cluster, session)

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

  if not existing_entities:
    parameters = {'key': bytearray(cassandra_interface.VERSION_INFO_KEY),
                  'column': cassandra_interface.VERSION_INFO_KEY,
                  'value': bytearray(str(POST_JOURNAL_VERSION))}
    session.execute(metadata_insert, parameters)

  # Indicate that the database has been successfully primed.
  parameters = {'key': bytearray(cassandra_interface.PRIMED_KEY),
                'column': cassandra_interface.PRIMED_KEY,
                'value': bytearray('true')}
  session.execute(metadata_insert, parameters)
  logging.info('Cassandra is primed.')


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
    return db_access.get_metadata(cassandra_interface.PRIMED_KEY) == 'true'
  finally:
    db_access.close()
