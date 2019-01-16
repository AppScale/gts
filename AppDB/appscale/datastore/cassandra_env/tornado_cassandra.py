""" A wrapper that converts Cassandra futures to Tornado futures. """
import logging
from tornado.concurrent import Future as TornadoFuture
from tornado.ioloop import IOLoop

logger = logging.getLogger(__name__)


class TornadoCassandra(object):
  """ A wrapper that converts Cassandra futures to Tornado futures. """

  def __init__(self, session):
    """ Create a new TornadoCassandra manager.

    Args:
      session: A Cassandra driver session.
    """
    self._session = session

  def execute(self, query, parameters=None, *args, **kwargs):
    """ Runs a Cassandra query asynchronously.

    Returns:
      A Tornado future.
    """
    tornado_future = TornadoFuture()
    io_loop = IOLoop.current()
    cassandra_future = self._session.execute_async(
      query, parameters, *args, **kwargs)

    # This list is passed around in order to collect each page of results.
    results = []
    cassandra_future.add_callbacks(
      self._handle_page, self._handle_failure,
      callback_args=(io_loop, tornado_future, cassandra_future, results),
      errback_args=(io_loop, tornado_future, query)
    )
    return tornado_future

  @staticmethod
  def _handle_page(page_results, io_loop, tornado_future, cassandra_future,
                   all_results):
    """ Processes a page from a Cassandra statement and finalizes the Tornado
        future upon statement completion.

    Args:
      page_results: A list of the page's result rows
        (limited version of ResultSet).
      io_loop: An instance of tornado IOLoop where execute was initially called.
      tornado_future: A Tornado future.
      cassandra_future: A Cassandra future containing ResultSet.
      all_results: The complete list of results collected so far.
    """
    try:
      all_results.extend(page_results)
    except TypeError:
      # page_results are not iterable for insert statements.
      pass

    if cassandra_future.has_more_pages:
      cassandra_future.start_fetching_next_page()
      logger.debug("Fetching next page of cassandra response")
      return

    # When possible, this should use the ResultSet object to preserve all the
    # attributes. When the ResultSet does not contain all the results, use a
    # bare list of results.
    if page_results is not None and len(all_results) > len(page_results):
      io_loop.add_callback(tornado_future.set_result, all_results)
    else:
      result = cassandra_future.result()
      io_loop.add_callback(tornado_future.set_result, result)

  @staticmethod
  def _handle_failure(error, io_loop, tornado_future, query):
    """ Assigns the Cassandra exception to the Tornado future.

    Args:
      error: A Python exception.
      io_loop: An instance of tornado IOLoop where execute was initially called.
      tornado_future: A Tornado future.
      query: An instance of Cassandra query.
    """
    logger.error(u"Failed to run query: {} ({})".format(query, error))
    io_loop.add_callback(tornado_future.set_exception, error)
