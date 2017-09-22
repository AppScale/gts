""" A wrapper that converts Cassandra futures to Tornado futures. """
from tornado.concurrent import Future as TornadoFuture


class TornadoCassandra(object):
  """ A wrapper that converts Cassandra futures to Tornado futures. """
  def __init__(self, session):
    """ Create a new TornadoCassandra manager.

    Args:
      session: A Cassandra driver session.
    """
    self._session = session

  def execute(self, *args, **kwargs):
    """ Runs a Cassandra query asynchronously.

    Returns:
      A Tornado future.
    """
    tornado_future = TornadoFuture()
    cassandra_future = self._session.execute_async(*args, **kwargs)
    cassandra_future.add_callbacks(
      self._handle_success, self._handle_failure,
      callback_args=(tornado_future,), errback_args=(tornado_future,))
    return tornado_future

  @staticmethod
  def _handle_success(result_set, tornado_future):
    """ Assigns the Cassandra result to the Tornado future.

    Args:
      result_set: A Cassandra result set.
      tornado_future: A Tornado future.
    """
    tornado_future.set_result(result_set)

  @staticmethod
  def _handle_failure(error, tornado_future):
    """ Assigns the Cassandra exception to the Tornado future.

    Args:
      error: A Python exception.
      tornado_future: A Tornado future.
    """
    tornado_future.set_exception(error)
