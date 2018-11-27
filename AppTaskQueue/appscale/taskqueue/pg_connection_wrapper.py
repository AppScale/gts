"""
Postgres connection wrapper with autoreconnect functionality.
"""
import functools
import psycopg2
from psycopg2 import errorcodes

from appscale.taskqueue.utils import logger


class PostgresConnectionWrapper(object):

  def __init__(self, *args, **kwargs):
    self._args = args
    self._kwargs = kwargs
    self._connection = None

  def get_connection(self):
    if not self._connection or self._connection.closed:
      logger.info('Establishing new connection to Postgres server')
      self._connection = psycopg2.connect(*self._args, **self._kwargs)
    return self._connection

  def close(self):
    return self._connection.close()
