""" UA Server data backup. """

import argparse
import csv
import datetime
import errno
import logging
import os
import time

from kazoo.client import KazooClient
import psycopg2
from tornado import gen


from appscale.common import appscale_info, retrying
from appscale.common.constants import LOG_FORMAT, ZK_PERSISTENT_RECONNECTS
from appscale.datastore import appscale_datastore
from appscale.datastore.dbconstants import (
  AppScaleDBConnectionError,
  USERS_SCHEMA,
  USERS_TABLE
)
from appscale.datastore.utils import tornado_synchronous

# The location where the backup files will be stored.
BACKUP_FILE_LOCATION = "/opt/appscale/backups/"

logger = logging.getLogger(__name__)

zk_client = None

table_name = "ua_users"


def is_connection_error(err):
  """ This function is used as retry criteria.

  Args:
    err: an instance of Exception.
  Returns:
    True if error is related to connection, False otherwise.
  """
  return isinstance(err, psycopg2.InterfaceError)


retry_pg_connection = retrying.retry(
    retrying_timeout=10, retry_on_exception=is_connection_error
)


class PostgresConnectionWrapper(object):
  """ Implements automatic reconnection to Postgresql server. """

  def __init__(self, dsn=None):
    self._dsn = dsn
    self._connection = None

  def set_dsn(self, dsn):
    """ Resets PostgresConnectionWrapper to use new DSN string.
    Args:
      dsn: a str representing Postgres DSN string.
    """
    if self._connection and not self._connection.closed:
      self.close()
      self._connection = None
    self._dsn = dsn

  def get_connection(self):
    """ Provides postgres connection. It can either return existing
    working connection or establish new one.
    Returns:
      An instance of psycopg2 connection.
    """
    if not self._connection or self._connection.closed:
      logger.info('Establishing new connection to Postgres server')
      self._connection = psycopg2.connect(dsn=self._dsn)
    return self._connection

  def close(self):
    """ Closes psycopg2 connection.
    """
    return self._connection.close()


pg_connection_wrapper = None


def connect_to_postgres(zk_client):
  global pg_connection_wrapper
  global_dsn_node = '/appscale/ua_server/postgres_dsn'
  if zk_client.exists(global_dsn_node):
    pg_dsn = zk_client.get(global_dsn_node)
    logger.info('Using PostgreSQL as a backend for UA Server')
  else:
    pg_dsn = None
    logger.info('Using Cassandra as a backend for UA Server')
  if pg_dsn:
    pg_connection_wrapper = (
        PostgresConnectionWrapper(dsn=pg_dsn[0])
    )


@retry_pg_connection
@tornado_synchronous
@gen.coroutine
def get_table_sync(datastore, table_name, schema):
  """ Gets data from datastore.

  Args:
    datastore: Cassandra adapter.
    table_name: Table name in datastore.
    schema: Table schema.
  """
  if pg_connection_wrapper:
    with pg_connection_wrapper.get_connection() as pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'SELECT {columns} FROM "{table}" '
          .format(table=table_name, columns=', '.join(schema))
        )
        result = pg_cursor.fetchall()
    raise gen.Return(result)

  result = yield datastore.get_table(table_name, schema)
  raise gen.Return(result)

def reshape(array, step):
  """ Reshapes array of size n to matrix with dimensions n/step by step.

  Args:
    array: List to reshape.
    step: Number of elements in row after reshaping.
  """
  result = []
  for i in range(0, len(array), step):
    result.append(array[i:i+step])
  return result

def create_backup_dir(backup_dir):
  """ Creates backup directory.

  Args:
    backup_dir: Backup directory name.
  """
  try:
    os.makedirs(backup_dir)
  except OSError as os_error:
    if os_error.errno != errno.EEXIST:
      raise

  logger.info("Backup dir created: {0}".format(backup_dir))

def prepare_for_backup(rows):
  """ Converts date fields to timestamp and application list to str.

  Args:
    rows: A tuple of all rows in postgres database.
  """
  # todo: delete it after removal of Cassandra
  for row in rows:
    # 2 - 4 indexes of dates
    row[2] = datetime.datetime.fromtimestamp(row[2])
    row[3] = datetime.datetime.fromtimestamp(row[3])
    row[4] = datetime.datetime.fromtimestamp(row[4])
    # 5 index of applications list
    if row[5]:
      row[5] = row[5].split(':')


def main():
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser(description='Backup UA Server data.')
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  # Configure zookeeper and db access
  zk_client = KazooClient(
    hosts=','.join(appscale_info.get_zk_node_ips()),
    connection_retry=ZK_PERSISTENT_RECONNECTS)
  zk_client.start()
  connect_to_postgres(zk_client)

  datastore_type = 'cassandra'

  ERROR_CODES = appscale_datastore.DatastoreFactory.error_codes()

  db = appscale_datastore.DatastoreFactory.getDatastore(datastore_type)

  # Keep trying until it gets the schema.
  backoff = 5
  retries = 3
  while retries >= 0:
    try:
      user_schema = db.get_schema_sync(USERS_TABLE)
    except AppScaleDBConnectionError:
      retries -= 1
      time.sleep(backoff)
      continue

    if user_schema[0] in ERROR_CODES:
      user_schema = user_schema[1:]
    else:
      retries -= 1
      time.sleep(backoff)
      continue
    break

  # If no response from cassandra
  if retries == -1:
    raise AppScaleDBConnectionError('No response from cassandra.')

  schema_cols_num = len(USERS_SCHEMA)

  if pg_connection_wrapper:
    table = get_table_sync(db, table_name, USERS_SCHEMA)
  else:
    table = get_table_sync(db, USERS_TABLE, user_schema)[1:]
    reshaped_table = reshape(table, schema_cols_num)

  create_backup_dir(BACKUP_FILE_LOCATION)

  backup_timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
  output_file = '{0}ua_server_{1}.csv'.\
    format(BACKUP_FILE_LOCATION, backup_timestamp)

  # v1 output format
  with open(output_file, 'w') as fout:
    writer = csv.DictWriter(fout, delimiter=',', fieldnames=USERS_SCHEMA)
    writer.writeheader()
    if pg_connection_wrapper:
      rows = [dict(zip(USERS_SCHEMA, row)) for row in table]
    else:
      prepare_for_backup(reshaped_table)
      rows = [dict(zip(USERS_SCHEMA, row)) for row in reshaped_table]
    writer.writerows(rows)
