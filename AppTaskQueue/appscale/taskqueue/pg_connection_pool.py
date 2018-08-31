"""
Postgres connection pool with autoreconnect functionality.
"""
import functools
import psycopg2
from psycopg2 import errorcodes, pool

from appscale.taskqueue.utils import logger


class PostgresConnectionPool(pool.SimpleConnectionPool):
  """
  It works just like a base class but it makes sure it doesn't return
  broken connection.
  To make it possible it uses _PostgresConnectionWrapper which marks
  connection as failed if any connection-related error occurred,
  so getconn method can check if connection is failed
  before returning it user.
  """

  def _connect(self, key=None):
    """ Creates a new connection and assigns it to 'key' if not None.

    Args:
      key: a string representing symbolic name of the connection.
    Returns:
      an instance of _PostgresConnectionWrapper.
    """
    logger.info('Establishing new connection to Postgres server')
    conn = psycopg2.connect(*self._args, **self._kwargs)
    wrapped_connection = _PostgresConnectionWrapper(conn)
    if key is not None:
      self._used[key] = wrapped_connection
      self._rused[id(wrapped_connection)] = key
    else:
      self._pool.append(wrapped_connection)
    return wrapped_connection

  def getconn(self, key=None):
    """ Gets a free connection and assigns it to 'key' if not None.

    Args:
      key: a string representing a symbolic name of the connection.
    Returns:
      an instance of _PostgresConnectionWrapper.
    """
    conn = super(PostgresConnectionPool, self).getconn(key)
    if conn.failure_info:
      logger.info('Removing problematic ({err}) connection from the pool'
                  .format(err=conn.failure_info))
      self.putconn(conn, key, close=True)
      # Get new connection
      conn = super(PostgresConnectionPool, self).getconn(key)
    return conn


def _is_connection_error(exception):
  """ Determines if postgres error is connection-related

  Args:
    exception: an instance if psycopg2.extensions.Error.
  Returns:
    a boolean indicating if error is connection-related.
  """
  if exception.pgcode:
    error_class = errorcodes.lookup(exception.pgcode[:2])
    return error_class in [
      'CLASS_CONNECTION_EXCEPTION',
      'CLASS_OPERATOR_INTERVENTION'
    ]
  return 'connection already closed' in exception.message


class _PostgresConnectionWrapper(object):
  """
  This class is proxy to psycopg2 connection.
  It wraps cursor, commit and rollback methods of original connection
  so if any connection-related error occurred it marks itself as failed.
  """

  def __init__(self, connection):
    # Original connection to wrap
    self._connection = connection

    # Wrap connection methods
    self.cursor = self._catch_connection_problem(connection.cursor)
    self.commit = self._catch_connection_problem(connection.commit)
    self.rollback = self._catch_connection_problem(connection.rollback)

    self._connection_failure_info = None

  @property
  def failure_info(self):
    return self._connection_failure_info

  def _catch_connection_problem(self, connection_method):
    """ Decorates connection_method with try-except which
    marks connection as failed if connection-related error occurred.
    It raises again whatever was caught.

    Args:
      connection_method: a method of original psycopg2 connection.
    Returns:
      a wrapped method.
    """

    @functools.wraps(connection_method)
    def wrapped(*args, **kwargs):
      try:
        return connection_method(*args, **kwargs)
      except psycopg2.Error as pg_error:
        if self._connection.closed or _is_connection_error(pg_error):
          # Mark connection as failed, so connection pool can handle it
          self._connection_failure_info = pg_error
        raise

    return wrapped

  def __getattr__(self, item_name):
    """ Everything apart from what was explicitly defined for
    _PostgresConnectionWrapper should be just the same
    as for original connection.

    Args:
      item_name: a string representing attribute ot method name.
    Returns:
      whatever original connection returns.
    """
    return getattr(self._connection, item_name)
