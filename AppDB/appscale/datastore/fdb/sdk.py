"""
This module contains code copied from the Python SDK to facilitate query
operations.
"""
import logging
import sys
import threading

from appscale.datastore import dbconstants
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import datastore_pb, entity_pb
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


def IndexListForQuery(query):
  """Get the composite index definition used by the query, if any, as a list.

  Args:
    query: the datastore_pb.Query to compute the index list for

  Returns:
    A singleton list of the composite index definition pb used by the query,
  """
  required, kind, ancestor, props = (
      datastore_index.CompositeIndexForQuery(query))
  if not required:
    return []

  index_pb = entity_pb.Index()
  index_pb.set_entity_type(kind)
  index_pb.set_ancestor(bool(ancestor))
  for name, direction in datastore_index.GetRecommendedIndexProperties(props):
    prop_pb = entity_pb.Index_Property()
    prop_pb.set_name(name)
    prop_pb.set_direction(direction)
    index_pb.property_list().append(prop_pb)
  return [index_pb]


def FindIndexToUse(query, indexes):
  """ Matches the query with one of the composite indexes.

  Args:
    query: A datastore_pb.Query.
    indexes: A list of entity_pb.CompsiteIndex.
  Returns:
    The composite index of the list for which the composite index matches
    the query. Returns None if there is no match.
  """
  if not query.has_kind():
    return None

  index_list = IndexListForQuery(query)
  if not index_list:
    return None

  index_match = index_list[0]
  for index in indexes:
    if index_match.Equals(index.definition()):
      return index

  _, kind, ancestor, (prefix, (ordered, group_by, unordered)) = (
    datastore_index.CompositeIndexForQuery(query))
  # TODO: Support group_by and unordered.
  if group_by or unordered:
    raise dbconstants.NeedsIndex(u'Query requires an index')

  prefix = sorted(prefix)
  for index in indexes:
    if index.definition().entity_type() != kind:
      continue

    if index.definition().ancestor() != ancestor:
      continue

    if index.definition().property_size() != len(prefix) + len(ordered):
      continue

    index_prefix = sorted([prop.name() for prop in
                           index.definition().property_list()[:len(prefix)]])
    if index_prefix != prefix:
      continue

    index_matches = True
    for offset, (prop_name, direction) in enumerate(ordered):
      index_prop = index.definition().property(len(prefix) + offset)
      if index_prop.name() != prop_name:
        index_matches = False
        break

      if direction is not None and direction != index_prop.direction():
        index_matches = False
        break

    if index_matches:
      return index

  raise dbconstants.NeedsIndex(u'Query requires an index')
