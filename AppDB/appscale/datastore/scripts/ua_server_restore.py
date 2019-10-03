""" UA Server data restore. """

import argparse
import csv
import datetime
import logging
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
def put_entity_sync(datastore, table_name, user, schema, user_data):
  """ Puts data of specified user from backup to datastore.

  Args:
    datastore: Datastore entity.
    table_name: Table name in datastore.
    user: User name.
    schema: Table schema.
    user_data: List or dict (if postgres role is enabled) of all user's fields.
  """
  if pg_connection_wrapper:
    with pg_connection_wrapper.get_connection() as pg_connection:
      with pg_connection.cursor() as pg_cursor:
        pg_cursor.execute(
          'INSERT INTO "{table}" ({columns}) '
          'VALUES ( '
          '  %(email)s, %(pw)s, %(date_creation)s, %(date_change)s, '
          '  %(date_last_login)s, %(applications)s, %(appdrop_rem_token)s, '
          '  %(appdrop_rem_token_exp)s, %(visit_cnt)s, %(cookie)s, '
          '  %(cookie_ip)s, %(cookie_exp)s, %(cksum)s, %(enabled)s, %(type)s, '
          '  %(is_cloud_admin)s, %(capabilities)s '
          ') '
          'RETURNING date_last_login'
          .format(table=table_name, columns=', '.join(schema)),
          vars=user_data
        )
        result = pg_cursor.fetchone()
    raise gen.Return(result)
  result = yield datastore.put_entity(table_name, user, schema, user_data)
  raise gen.Return(result)

def main():
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser(description='Restore UA Server data.')
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
  parser.add_argument(
    '-i', '--input', help='File with UA Server backup', required=True)
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

  input_file = args.input

  with open(input_file, 'r') as fin:
    reader = csv.DictReader(fin, delimiter=',')
    # Iterate through all users in file
    for row in reader:
      if pg_connection_wrapper:
        if not row['applications']:
          row['applications'] = None
        else:
          # delete square brackets added by csv module
          apps = row['applications'][1:-1]
          # csv module adds extra quotes each time
          apps = apps.replace("'", "")
          row['applications'] = '{' + apps + '}'
        put_entity_sync(db, table_name, row['email'], USERS_SCHEMA, row)
      else:
        # Convert dates to timestamp
        t = str(time.mktime(datetime.datetime.strptime(
          row['date_creation'], '%Y-%m-%d %H:%M:%S').timetuple()))
        row['date_creation'] = t
        t = str(time.mktime(datetime.datetime.strptime(
          row['date_change'], '%Y-%m-%d %H:%M:%S').timetuple()))
        row['date_change'] = t
        t = str(time.mktime(datetime.datetime.strptime(
          row['date_last_login'], '%Y-%m-%d %H:%M:%S').timetuple()))
        row['date_last_login'] = t

        apps = row['applications'][1:-1]
        apps = apps.replace("'", "").replace(', ', ':')
        row['applications'] = apps

        array = [row[key] for key in USERS_SCHEMA]
        put_entity_sync(db, USERS_TABLE, array[0], user_schema, array)
