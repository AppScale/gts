"""
This module contains code copied from the Python SDK to facilitate query
operations.
"""
import logging
import sys
import threading

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.runtime import apiproxy_errors

logger = logging.getLogger(__name__)


def _GuessOrders(filters, orders):
  """Guess any implicit ordering.

  The datastore gives a logical, but not necessarily predictable, ordering when
  orders are not completely explicit. This function guesses at that ordering
  (which is better then always ordering by __key__ for tests).

  Args:
    filters: The datastore_pb.Query_Filter that have already been normalized and
      checked.
    orders: The datastore_pb.Query_Order that have already been normalized and
      checked. Mutated in place.
  """
  orders = orders[:]


  if not orders:
    for filter_pb in filters:
      if filter_pb.op() != datastore_pb.Query_Filter.EQUAL:

        order = datastore_pb.Query_Order()
        order.set_property(filter_pb.property(0).name())
        orders.append(order)
        break


  exists_props = (filter_pb.property(0).name() for filter_pb in filters
                  if filter_pb.op() == datastore_pb.Query_Filter.EXISTS)
  for prop in sorted(exists_props):
    order = datastore_pb.Query_Order()
    order.set_property(prop)
    orders.append(order)


  if not orders or orders[-1].property() != '__key__':
    order = datastore_pb.Query_Order()
    order.set_property('__key__')
    orders.append(order)
  return orders


def order_property_names(query):
  """ Generates a list of relevant order properties from the query.

  Returns:
    A set of Property objects.
  """
  filters, orders = datastore_index.Normalize(query.filter_list(),
    query.order_list(), [])
  orders = _GuessOrders(filters, orders)
  return set(order.property()
             for order in orders if order.property() != '__key__')


class BaseCursor(object):
  """A base query cursor over a list of entities.

  Public properties:
    cursor: the integer cursor
    app: the app for which this cursor was created

  Class attributes:
    _next_cursor: the next cursor to allocate
    _next_cursor_lock: protects _next_cursor
  """
  _next_cursor = 1
  _next_cursor_lock = threading.Lock()

  def __init__(self, app):
    """Constructor.

    Args:
      app: The app this cursor is being created for.
    """
    self.app = app
    self.cursor = self._AcquireCursorID()

  def PopulateCursor(self, query_result):
    """ Creates cursor for the given query result. """
    if query_result.more_results():
      cursor = query_result.mutable_cursor()
      cursor.set_app(self.app)
      cursor.set_cursor(self.cursor)

  @classmethod
  def _AcquireCursorID(cls):
    """Acquires the next cursor id in a thread safe manner."""
    cls._next_cursor_lock.acquire()
    try:
      cursor_id = cls._next_cursor
      cls._next_cursor += 1
    finally:
      cls._next_cursor_lock.release()
    return cursor_id


def Check(test, msg='', error_code=datastore_pb.Error.BAD_REQUEST):
  """Raises an apiproxy_errors.ApplicationError if the condition is false.

  Args:
    test: A condition to test.
    msg: A string to return with the error.
    error_code: One of datastore_pb.Error to use as an error code.

  Raises:
    apiproxy_errors.ApplicationError: If test is false.
  """
  if not test:
    raise apiproxy_errors.ApplicationError(error_code, msg)


class ListCursor(BaseCursor):
    """A query cursor over a list of entities.

    Public properties:
      keys_only: whether the query is keys_only
    """

    def __init__(self, query):
        """Constructor.

        Args:
          query: the query request proto
        """
        super(ListCursor, self).__init__(query.app())

        self.__order_property_names = order_property_names(query)
        if query.has_compiled_cursor() and query.compiled_cursor().position_list():
            self.__last_result, _ = (self._DecodeCompiledCursor(
                query.compiled_cursor()))
        else:
            self.__last_result = None

        if query.has_end_compiled_cursor():
            if query.end_compiled_cursor().position_list():
                self.__end_result, _ = self._DecodeCompiledCursor(
                    query.end_compiled_cursor())
        else:
            self.__end_result = None

        self.__query = query
        self.__offset = 0
        self.__count = query.limit()

        self.keys_only = query.keys_only()

    def _GetLastResult(self):
        """ Protected access to private member. """
        return self.__last_result

    def _GetEndResult(self):
        """ Protected access to private member for last entity. """
        return self.__end_result

    @staticmethod
    def _GetCursorOffset(results, cursor_entity, inclusive, compare):
        """Converts a cursor entity into a offset into the result set even if the
        cursor_entity no longer exists.

        Args:
          results: the query's results (sequence of datastore_pb.EntityProto)
          cursor_entity: the datastore_pb.EntityProto from the compiled query
          inclusive: boolean that specifies if to offset past the cursor_entity
          compare: a function that takes two datastore_pb.EntityProto and compares
            them.
        Returns:
          the integer offset
        """
        lo = 0
        hi = len(results)
        if inclusive:

            while lo < hi:
                mid = (lo + hi) // 2
                if compare(results[mid], cursor_entity) < 0:
                    lo = mid + 1
                else:
                    hi = mid
        else:

            while lo < hi:
                mid = (lo + hi) // 2
                if compare(cursor_entity, results[mid]) < 0:
                    hi = mid
                else:
                    lo = mid + 1
        return lo

    def _DecodeCompiledCursor(self, compiled_cursor):
        """Converts a compiled_cursor into a cursor_entity.

        Args:
          compiled_cursor: The datastore_pb.CompiledCursor to decode.

        Returns:
          (cursor_entity, inclusive): a datastore_pb.EntityProto and if it should
          be included in the result set.
        """
        assert len(compiled_cursor.position_list()) == 1

        position = compiled_cursor.position(0)

        remaining_properties = self.__order_property_names.copy()
        cursor_entity = datastore_pb.EntityProto()
        cursor_entity.mutable_key().CopyFrom(position.key())
        for indexvalue in position.indexvalue_list():
            property = cursor_entity.add_property()
            property.set_name(indexvalue.property())
            property.mutable_value().CopyFrom(indexvalue.value())
            remaining_properties.remove(indexvalue.property())

        Check(not remaining_properties,
              'Cursor does not match query: missing values for %r' %
              remaining_properties)

        return (cursor_entity, position.start_inclusive())

    def Count(self):
        """Counts results, up to the query's limit.

        Note this method does not deduplicate results, so the query it was generated
        from should have the 'distinct' clause applied.

        Returns:
          int: Result count.
        """
        return self.__count