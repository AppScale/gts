"""
Postgres connection wrapper with autoreconnect functionality.
"""
import psycopg2
from tornado.ioloop import IOLoop

from appscale.common import retrying
from appscale.taskqueue.utils import logger


class NoDSNSpecified(Exception):
  pass


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

  @retrying.retry(retrying_timeout=60, backoff_multiplier=1)
  def get_connection(self):
    """ Provides postgres connection. It can either return existing
    working connection or establish new one.

    Returns:
      An instance of psycopg2 connection.
    """
    if not self._connection or self._connection.closed:
      logger.info('Establishing new connection to Postgres server')
      self._connection = psycopg2.connect(
        dsn=self._dsn,
        connect_timeout=10,
        options='-c statement_timeout=60000',
        keepalives_idle=60,
        keepalives_interval=15,
        keepalives_count=4
      )
    return self._connection

  def close(self):
    """ Closes psycopg2 connection.
    """
    return self._connection.close()


def start_postgres_dsn_watch(zk_client):
  """ Created zookeeper DataWatch for updating pg_wrapper
  when Postgres DSN string is updated.

  Args:
    zk_client: an instance of zookeeper client.
  """
  zk_client.ensure_path('/appscale/tasks')
  zk_client.DataWatch('/appscale/tasks/postgres_dsn', _update_dsn_watch)


def _update_dsn(new_dsn):
  """ Updates Postgres DSN string to be used
  for establishing connection to Postgresql server.

  Args:
    new_dsn: A bytes array representing new DSN string.
  """
  if not new_dsn:
    raise NoDSNSpecified('No DSN string was found at zookeeper node '
                         '"/appscale/tasks/postgres_dsn"')
  pg_wrapper.set_dsn(new_dsn.decode('utf-8'))


def _update_dsn_watch(new_dsn, _):
  """ Schedules update of Postgres DSN to be executed in tornado IO loop.

  Args:
    new_dsn: A bytes array representing new DSN string.
  """
  main_io_loop = IOLoop.instance()
  main_io_loop.add_callback(_update_dsn, new_dsn)


pg_wrapper = PostgresConnectionWrapper()
