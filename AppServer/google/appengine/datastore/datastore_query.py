#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""A thin wrapper around datastore query RPC calls.

This provides wrappers around the internal only datastore_pb library and is
designed to be the lowest-level API to be used by all Python datastore client
libraries for executing queries. It provides a layer of protection so the actual
RPC syntax can change without affecting client libraries.

Any class, function, field or argument starting with an '_' is for INTERNAL use
only and should not be used by developers!
"""







__all__ = ['Batch',
           'Batcher',
           'CompositeFilter',
           'CompositeOrder',
           'Cursor',
           'FetchOptions',
           'FilterPredicate',
           'Order',
           'PropertyFilter',
           'PropertyOrder',
           'Query',
           'QueryOptions',
           'ResultsIterator',
           'make_filter',
          ]

import base64
import pickle

from google.appengine.datastore import entity_pb
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_rpc


class _BaseComponent(object):
  """A base class for query components.

  Currently just implements basic == and != functions.
  """

  def __eq__(self, other):
    if self.__class__ is not other.__class__:
      return NotImplemented
    return self is other or self.__dict__ == other.__dict__

  def __ne__(self, other):
    equal = self.__eq__(other)
    if equal is NotImplemented:
      return equal
    return not equal


def make_filter(name, op, values):
  """Constructs a FilterPredicate from the given name, op and values.

  Args:
    name: A non-empty string, the name of the property to filter.
    op: One of PropertyFilter._OPERATORS.keys(), the operator to use.
    values: A supported value, the value to compare against.

  Returns:
    if values is a list, a CompositeFilter that uses AND to combine all
    values, otherwise a PropertyFilter for the single value.

  Raises:
    datastore_errors.BadPropertyError: if the property name is invalid.
    datastore_errors.BadValueError: if the property did not validate correctly
      or the value was an empty list.
    Other exception types (like OverflowError): if the property value does not
      meet type-specific criteria.
  """
  datastore_types.ValidateProperty(name, values, read_only=True)
  properties = datastore_types.ToPropertyPb(name, values)
  if isinstance(properties, list):
    filters = [PropertyFilter(op, prop) for prop in properties]
    return CompositeFilter(CompositeFilter.AND, filters)
  else:
    return PropertyFilter(op, properties)


class FilterPredicate(_BaseComponent):
  """An abstract base class for all query filters.

  All sub-classes must be immutable as these are often stored without creating a
  defensive copying.
  """

  def _to_pb(self):
    """Internal only function to generate a filter pb."""
    raise NotImplementedError

  def _to_pbs(self):
    """Internal only function to generate a list of filter pbs."""
    return [self._to_pb()]

  def __eq__(self, other):

    if self.__class__ is other.__class__:
      return super(FilterPredicate, self).__eq__(other)

    if other.__class__ is CompositeFilter:
      return other._op in [CompositeFilter.AND] and [self] == other._filters

    if (self.__class__ is CompositeFilter and
        isinstance(other, FilterPredicate)):
      return self._op == CompositeFilter.AND and self._filters == [other]
    return NotImplemented


class PropertyFilter(FilterPredicate):
  """An immutable filter predicate that constrains a single property."""

  _OPERATORS = {
      '<': datastore_pb.Query_Filter.LESS_THAN,
      '<=': datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL,
      '>': datastore_pb.Query_Filter.GREATER_THAN,
      '>=': datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL,
      '=': datastore_pb.Query_Filter.EQUAL,
      }

  _INEQUALITY_OPERATORS = frozenset(['<', '<=', '>', '>='])
  _UPPERBOUND_INEQUALITY_OPERATORS = frozenset(['<', '<='])

  def __init__(self, op, value):
    """Constructor.

    Args:
      op: A string representing the operator to use.
      value: A entity_pb.Property, the property and value to compare against.

    Raises:
      datastore_errors.BadArgumentError if op has an unsupported value or value
      is not an entity_pb.Property.
    """
    if op not in self._OPERATORS:
      raise datastore_errors.BadArgumentError('unknown operator: %r' % (op,))
    if not isinstance(value, entity_pb.Property):
      raise datastore_errors.BadArgumentError(
          'value argument should be entity_pb.Property (%r)' % (value,))

    super(PropertyFilter, self).__init__()
    self.__filter = datastore_pb.Query_Filter()
    self.__filter.set_op(self._OPERATORS[op])
    self.__filter.add_property().CopyFrom(value)

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of datastore_query.PropertyFilter is unsupported.')

  def _to_pb(self):
    """Returns the internal only pb representation."""
    return self.__filter


class CompositeFilter(FilterPredicate):
  """An immutable filter predicate that combines other predicates.

  This class proactively merges sub-filters that are combined using the same
  operator. For example:
    CompositeFilter(AND, [f1, f2, CompositeFilter(AND, [f3, f4]), f5, f6])
  is equivalent to:
    CompositeFilter(AND, [f1, f2, f3, f4, f5, f6])

  Currently filters can only be combined using an AND operator.
  """

  AND = 'and'
  _OPERATORS = frozenset([AND])

  def __init__(self, op, filters):
    """Constructor.

    Args:
      op: The operator to use to combine the given filters
      filters: A list of one or more filters to combine

    Raises:
      datastore_errors.BadArgumentError if op is not in CompsiteFilter.OPERATORS
      or filters is not a non-empty list containing only FilterPredicates.
    """
    if not op in self._OPERATORS:
      raise datastore_errors.BadArgumentError('unknown operator: %r' % (op,))
    if not filters or not isinstance(filters, list):
      raise datastore_errors.BadArgumentError(
          'filters argument should be a non-empty list (%r)' % (filters,))

    super(CompositeFilter, self).__init__()
    self._op = op
    self._filters = []
    for f in filters:
      if isinstance(f, CompositeFilter) and f._op == self._op:


        self._filters.extend(f._filters)
      elif isinstance(f, FilterPredicate):
        self._filters.append(f)
      else:
        raise datastore_errors.BadArgumentError(
            'filters argument must be a list of FilterPredicates, found (%r)' %
            (f,))

  def _to_pbs(self):
    """Returns the internal only pb representation."""



    return [f._to_pb() for f in self._filters]


class Order(_BaseComponent):
  """A base class that represents a sort order on a query.

  All sub-classes must be immutable as these are often stored without creating a
  defensive copying.
  """

  def _to_pb(self):
    """Internal only function to generate a filter pb."""
    raise NotImplementedError

  def __eq__(self, other):
    if self.__class__ is other.__class__:
      return super(Order, self).__eq__(other)

    if other.__class__ is CompositeOrder:
      return [self] == other._orders

    if (self.__class__ is CompositeOrder and
        isinstance(other, Order)):
      return self._orders == [other]
    return NotImplemented


class PropertyOrder(Order):
  """An immutable class that represents a sort order for a single property."""

  ASCENDING = datastore_pb.Query_Order.ASCENDING
  DESCENDING = datastore_pb.Query_Order.DESCENDING
  _DIRECTIONS = frozenset([ASCENDING, DESCENDING])

  def __init__(self, prop, direction=ASCENDING):
    """Constructor.

    Args:
      prop: the name of the prop by which to sort.
      direction: the direction in which to sort the given prop.

    Raises:
      datastore_errors.BadArgumentError if the prop name or direction is
      invalid.
    """
    datastore_types.ValidateString(prop,
                                   'prop',
                                   datastore_errors.BadArgumentError)
    if not direction in self._DIRECTIONS:
      raise datastore_errors.BadArgumentError('unknown direction: %r' %
                                              (direction,))
    super(PropertyOrder, self).__init__()
    self.__order = datastore_pb.Query_Order()
    self.__order.set_property(prop.encode('utf-8'))
    self.__order.set_direction(direction)

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of datastore_query.PropertyOrder is unsupported.')

  def _to_pb(self):
    """Returns the internal only pb representation."""
    return self.__order


class CompositeOrder(Order):
  """An immutable class that represents a sequence of Orders.

  This class proactively flattens sub-orders that are of type CompositeOrder.
  For example:
    CompositeOrder([O1, CompositeOrder([02, 03]), O4])
  is equivalent to:
    CompositeOrder([O1, 02, 03, O4])
  """

  def __init__(self, orders):
    """Constructor.

    Args:
      orders: A list of Orders which are applied in order.
    """
    if not isinstance(orders, list):
      raise datastore_errors.BadArgumentError(
          'orders argument should be list (%r)' % (orders,))

    super(CompositeOrder, self).__init__()
    self._orders = []
    for order in orders:
      if isinstance(order, CompositeOrder):
        self._orders.extend(order._orders)
      elif isinstance(order, Order):
        self._orders.append(order)
      else:
        raise datastore_errors.BadArgumentError(
            'orders argument should only contain Order (%r)' % (order,))

  def size(self):
    """Returns the number of sub-orders the instance contains."""
    return len(self._orders)

  def _to_pbs(self):
    """Returns an ordered list of internal only pb representations."""
    return [order._to_pb() for order in self._orders]


class FetchOptions(datastore_rpc.Configuration):
  """An immutable class that contains all options for fetching results.

  These options apply to any request that pulls results from a query.

  This class reserves the right to define configuration options of any name
  except those that start with 'user_'. External subclasses should only define
  function or variables with names that start with in 'user_'.

  Options are set by passing keyword arguments to the constructor corresponding
  to the configuration options defined below and in datastore_rpc.Configuration.

  This object can be used as the default config for a datastore_rpc.Connection
  but in that case some options will be ignored, see option documentation below
  for details.
  """

  @datastore_rpc.ConfigOption
  def produce_cursors(value):
    """If a Cursor should be returned with the fetched results.

    Raises:
      datastore_errors.BadArgumentError if value is not a bool.
    """
    if not isinstance(value, bool):
      raise datastore_errors.BadArgumentError(
          'produce_cursors argument should be bool (%r)' % (value,))
    return value

  @datastore_rpc.ConfigOption
  def offset(value):
    """The number of results to skip before returning the first result.

    Only applies to the first request it is used with and is ignored if present
    on datastore_rpc.Connection.config.

    Raises:
      datastore_errors.BadArgumentError if value is not a integer or is less
      than zero.
    """
    datastore_types.ValidateInteger(value,
                                    'offset',
                                    datastore_errors.BadArgumentError,
                                    zero_ok=True)
    return value

  @datastore_rpc.ConfigOption
  def batch_size(value):
    """The number of results to attempt to retrieve in a batch.

    Raises:
      datastore_errors.BadArgumentError if value is not a integer or is not
      greater than zero.
    """
    datastore_types.ValidateInteger(value,
                                    'batch_size',
                                    datastore_errors.BadArgumentError)
    return value


class QueryOptions(FetchOptions):
  """An immutable class that contains all options for running a query.

  This class reserves the right to define configuration options of any name
  except those that start with 'user_'. External subclasses should only define
  function or variables with names that start with in 'user_'.

  Options are set by passing keyword arguments to the constructor corresponding
  to the configuration options defined below and in FetchOptions and
  datastore_rpc.Configuration.

  This object can be used as the default config for a datastore_rpc.Connection
  but in that case some options will be ignored, see below for details.
  """


  ORDER_FIRST = datastore_pb.Query.ORDER_FIRST
  ANCESTOR_FIRST = datastore_pb.Query.ANCESTOR_FIRST
  FILTER_FIRST = datastore_pb.Query.FILTER_FIRST
  _HINTS = frozenset([ORDER_FIRST, ANCESTOR_FIRST, FILTER_FIRST])

  @datastore_rpc.ConfigOption
  def keys_only(value):
    """If the query should only return keys.

    Raises:
      datastore_errors.BadArgumentError if value is not a bool.
    """
    if not isinstance(value, bool):
      raise datastore_errors.BadArgumentError(
          'keys_only argument should be bool (%r)' % (value,))
    return value

  @datastore_rpc.ConfigOption
  def limit(value):
    """Limit on the number of results to return.

    Raises:
      datastore_errors.BadArgumentError if value is not an integer or is less
      than zero.
    """
    datastore_types.ValidateInteger(value,
                                    'limit',
                                    datastore_errors.BadArgumentError,
                                    zero_ok=True)
    return value

  @datastore_rpc.ConfigOption
  def prefetch_size(value):
    """Number of results to attempt to return on the initial request.

    Raises:
      datastore_errors.BadArgumentError if value is not an integer or is not
      greater than zero.
    """
    datastore_types.ValidateInteger(value,
                                    'prefetch_size',
                                    datastore_errors.BadArgumentError,
                                    zero_ok=True)
    return value

  @datastore_rpc.ConfigOption
  def start_cursor(value):
    """Cursor to use a start position.

    Ignored if present on datastore_rpc.Connection.config.

    Raises:
      datastore_errors.BadArgumentError if value is not a Cursor.
    """
    if not isinstance(value, Cursor):
      raise datastore_errors.BadArgumentError(
          'start_cursor argument should be datastore_query.Cursor (%r)' %
          (value,))
    return value

  @datastore_rpc.ConfigOption
  def end_cursor(value):
    """Cursor to use as an end position.

    Ignored if present on datastore_rpc.Connection.config.

    Raises:
      datastore_errors.BadArgumentError if value is not a Cursor.
    """
    if not isinstance(value, Cursor):
      raise datastore_errors.BadArgumentError(
          'end_cursor argument should be datastore_query.Cursor (%r)' %
          (value,))
    return value

  @datastore_rpc.ConfigOption
  def hint(value):
    """Hint on how the datastore should plan the query.

    Raises:
      datastore_errors.BadArgumentError if value is not a known hint.
    """
    if value not in QueryOptions._HINTS:
      raise datastore_errors.BadArgumentError('Unknown query hint (%r)' %
                                              (value,))
    return value


class Cursor(_BaseComponent):
  """An immutable class that represents a relative position in a query.

  The position denoted by a Cursor is relative to a result in a query even
  if the result has been removed from the given query. Usually to position
  immediately after the last result returned by a batch.

  A cursor should only be used on a query with an identical signature to the
  one that produced it.
  """

  @datastore_rpc._positional(1)
  def __init__(self, _cursor_pb=None):
    """Constructor.

    A Cursor constructed with no arguments points the first result of any
    query. If such a Cursor is used as an end_cursor no results will ever be
    returned.
    """


    super(Cursor, self).__init__()
    if _cursor_pb is not None:
      if not isinstance(_cursor_pb, datastore_pb.CompiledCursor):
        raise datastore_errors.BadArgumentError(
            '_cursor_pb argument should be datastore_pb.CompiledCursor (%r)' %
            (_cursor_pb,))
      self.__compiled_cursor = _cursor_pb
    else:
      self.__compiled_cursor = datastore_pb.CompiledCursor()

  def to_bytes(self):
    """Serialize cursor as a byte string."""
    return self.__compiled_cursor.Encode()

  @staticmethod
  def from_bytes(cursor):
    """Gets a Cursor given its byte string serialized form.

    The serialized form of a cursor may change in a non-backwards compatible
    way. In this case cursors must be regenerated from a new Query request.

    Args:
      cursor: A serialized cursor as returned by .to_bytes.

    Returns:
      A Cursor.

    Raises:
      datastore_errors.BadValueError if the cursor argument does not represent a
      serialized cursor.
    """
    try:
      cursor_pb = datastore_pb.CompiledCursor(cursor)
    except (ValueError, TypeError), e:
      raise datastore_errors.BadValueError(
          'Invalid cursor %s. Details: %s' % (cursor, e))
    except Exception, e:






      if e.__class__.__name__ == 'ProtocolBufferDecodeError':
        raise datastore_errors.BadValueError(
            'Invalid cursor %s. Details: %s' % (cursor, e))
      else:
        raise
    return Cursor(_cursor_pb=cursor_pb)

  def to_websafe_string(self):
    """Serialize cursor as a websafe string.

    Returns:
      A base64-encoded serialized cursor.
    """
    return base64.urlsafe_b64encode(self.to_bytes())

  @staticmethod
  def from_websafe_string(cursor):
    """Gets a Cursor given its websafe serialized form.

    The serialized form of a cursor may change in a non-backwards compatible
    way. In this case cursors must be regenerated from a new Query request.

    Args:
      cursor: A serialized cursor as returned by .to_websafe_string.

    Returns:
      A Cursor.

    Raises:
      datastore_errors.BadValueError if the cursor argument is not a string
      type of does not represent a serialized cursor.
    """
    if not isinstance(cursor, basestring):
      raise datastore_errors.BadValueError(
          'cursor argument should be str or unicode (%r)' % (cursor,))

    try:


      decoded_bytes = base64.b64decode(str(cursor).replace('-', '+').replace('_', '/'))
    except (ValueError, TypeError), e:
      raise datastore_errors.BadValueError(
          'Invalid cursor %s. Details: %s' % (cursor, e))
    return Cursor.from_bytes(decoded_bytes)

  @staticmethod
  def _from_query_result(query_result):
    if query_result.has_compiled_cursor():
      return Cursor(_cursor_pb=query_result.compiled_cursor())
    return None

  def advance(self, offset, query, conn):
    """Advances a Cursor by the given offset.

    Args:
      offset: The amount to advance the current query.
      query: A Query identical to the one this cursor was created from.
      conn: The datastore_rpc.Connection to use.

    Returns:
      A new cursor that is advanced by offset using the given query.
    """
    datastore_types.ValidateInteger(offset,
                                    'offset',
                                    datastore_errors.BadArgumentError)
    if not isinstance(query, Query):
      raise datastore_errors.BadArgumentError(
          'query argument should be datastore_query.Query (%r)' % (query,))

    query_options = QueryOptions(
        start_cursor=self, offset=offset, limit=0, produce_cursors=True)
    return query.run(conn, query_options).next_batch(0).cursor(0)

  def _to_pb(self):
    """Returns the internal only pb representation."""
    return self.__compiled_cursor


class Query(_BaseComponent):
  """An immutable class that represents a query signature.

  A query signature consists of a source of entities (specified as app,
  namespace and optionally kind and ancestor) as well as a FilterPredicate
  and a desired ordering.
  """

  @datastore_rpc._positional(1)
  def __init__(self, app=None, namespace=None, kind=None, ancestor=None,
               filter_predicate=None, order=None):
    """Constructor.

    Args:
      app: Optional app to query, derived from the environment if not specified.
      namespace: Optional namespace to query, derived from the environment if
        not specified.
      kind: Optional kind to query.
      ancestor: Optional ancestor to query.
      filter_predicate: Optional FilterPredicate by which to restrict the query.
      order: Optional Order in which to return results.

    Raises:
      datastore_errors.BadArgumentError if any argument is invalid.
    """
    if kind is not None:
      datastore_types.ValidateString(kind,
                                     'kind',
                                     datastore_errors.BadArgumentError)
    if ancestor is not None and not isinstance(ancestor, entity_pb.Reference):
      raise datastore_errors.BadArgumentError(
          'ancestor argument should be entity_pb.Reference (%r)' % (ancestor,))

    if filter_predicate is not None and not isinstance(filter_predicate,
                                                       FilterPredicate):
      raise datastore_errors.BadArgumentError(
          'filter_predicate should be datastore_query.FilterPredicate (%r)' %
          (ancestor,))

    super(Query, self).__init__()
    if isinstance(order, CompositeOrder):
      if order.size() == 0:
        order = None
    elif isinstance(order, Order):
      order = CompositeOrder([order])
    elif order is not None:
      raise datastore_errors.BadArgumentError(
          'order should be Order (%r)' % (order,))

    self.__app = datastore_types.ResolveAppId(app)
    self.__namespace = datastore_types.ResolveNamespace(namespace)
    self.__kind = kind
    self.__ancestor = ancestor
    self.__order = order
    self.__filter_predicate = filter_predicate

  def run(self, conn, query_options=None):
    """Runs the query using provided datastore_rpc.Connection.

    Args:
      conn: The datastore_rpc.Connection to use
      query_options: Optional query options to use

    Returns:
      A Batcher that implicitly fetches query results asynchronously.

    Raises:
      datastore_errors.BadArgumentError if any of the arguments are invalid.
    """
    return Batcher(query_options, self.run_async(conn, query_options))

  def run_async(self, conn, query_options=None):
    """Runs the query using the provided datastore_rpc.Connection.

    Args:
      conn: the datastore_rpc.Connection on which to run the query.
      query_options: Optional QueryOptions with which to run the query.

    Returns:
      An async object that can be used to grab the first Batch. Additional
      batches can be retrieved by calling Batch.next_batch/next_batch_async.

    Raises:
      datastore_errors.BadArgumentError if any of the arguments are invalid.
    """
    if not isinstance(conn, datastore_rpc.BaseConnection):
      raise datastore_errors.BadArgumentError(
          'conn should be a datastore_rpc.BaseConnection (%r)' % (conn,))

    if not isinstance(query_options, QueryOptions):


      query_options = QueryOptions(config=query_options)

    start_cursor = query_options.start_cursor
    if not start_cursor and query_options.produce_cursors:
      start_cursor = Cursor()

    batch0 = Batch(query_options, self, conn, start_cursor)
    req = self._to_pb(conn, query_options)
    return batch0._make_query_result_rpc_call('RunQuery', query_options, req)

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of datastore_query.Query is unsupported.')

  def _to_pb(self, conn, query_options):
    """Returns the internal only pb representation."""
    pb = datastore_pb.Query()


    pb.set_app(self.__app.encode('utf-8'))
    datastore_types.SetNamespace(pb, self.__namespace)
    if self.__kind is not None:
      pb.set_kind(self.__kind.encode('utf-8'))
    if self.__ancestor:
      pb.mutable_ancestor().CopyFrom(self.__ancestor)


    if self.__filter_predicate:
      for f in self.__filter_predicate._to_pbs():
        pb.add_filter().CopyFrom(f)


    if self.__order:
      for order in self.__order._to_pbs():
        pb.add_order().CopyFrom(order)


    if QueryOptions.keys_only(query_options, conn.config):
      pb.set_keys_only(True)

    if QueryOptions.produce_cursors(query_options, conn.config):
      pb.set_compile(True)

    limit = QueryOptions.limit(query_options, conn.config)
    if limit is not None:
      pb.set_limit(limit)

    count = QueryOptions.prefetch_size(query_options, conn.config)
    if count is None:
      count = QueryOptions.batch_size(query_options, conn.config)
    if count is not None:
      pb.set_count(count)


    if query_options.offset:
      pb.set_offset(query_options.offset)


    if query_options.start_cursor is not None:
      pb.mutable_compiled_cursor().CopyFrom(query_options.start_cursor._to_pb())


    if query_options.end_cursor is not None:
      pb.mutable_end_compiled_cursor().CopyFrom(
          query_options.end_cursor._to_pb())


    if ((query_options.hint == QueryOptions.ORDER_FIRST and self.__order) or
        (query_options.hint == QueryOptions.ANCESTOR_FIRST and
         self.__ancestor) or
        (query_options.hint == QueryOptions.FILTER_FIRST and pb.
         filter_size() > 0)):
      pb.set_hint(query_options.hint)


    conn._set_request_read_policy(pb, query_options)
    conn._set_request_transaction(pb)

    return pb


class Batch(object):
  """A batch of results returned by a query.

  This class contains a batch of results returned from the datastore and
  relevant metadata. This metadata includes:
    query: The query that produced this batch
    query_options: The QueryOptions used to run the query. This does not
      contained any options passed to the .next_batch() call that created the
      current batch.
    start_cursor, end_cursor: These are the cursors that can be used
      with a query to re-fetch this batch. They can also be used to
      find all entities before or after the given batch (by use start_cursor as
      an end cursor or vice versa). start_cursor can also be advanced to
      point to a position within the batch using Cursor.advance().
    skipped_results: the number of result skipped because of the offset
      given to the request that generated it. This can be set either on
      the original Query.run() request or in subsequent .next_batch() calls.
    more_results: If this is true there are more results that can be retrieved
      either by .next_batch() or Batcher.next().

  This class is also able to fetch the next batch of the query using
  .next_batch(). As batches of results must be fetched serially, .next_batch()
  can only be called once. Additional calls to .next_batch() will return None.
  When there are no more batches .next_batch() will return None as well. Note
  that batches returned by iterating over Batcher will always return None for
  .next_batch() as the Bather handles fetching the next batch automatically.

  A Batch typically represents the result of a single RPC request. The datastore
  operates on a "best effort" basis so the batch returned by .next_batch()
  or Query.run_async().get_result() may not have satisfied the requested offset
  or number of results (specified through FetchOptions.offset and
  FetchOptions.batch_size respectively). To satisfy these restrictions
  additional batches may be needed (with FetchOptions that specify the remaining
  offset or results needed). The Batcher class hides these limitations.
  """

  def __init__(self, query_options, query, conn,
               start_cursor=Cursor(), _compiled_query=None):
    """Constructor.

    This class is constructed in stages (one when an RPC is sent and another
    when an rpc is completed) and should not be constructed directly!!
    Use Query.run_async().get_result() to create a Batch or Query.run()
    to use a batcher.

    This constructor does not perform verification.

    Args:
      query_options: The QueryOptions used to run the given query.
      query: The Query the batch is derived from.
      conn: A datastore_rpc.Connection to use.
      start_cursor: Optional cursor pointing before this batch.
    """


    self.__query = query
    self.__conn = conn
    self.__query_options = query_options
    self.__start_cursor = start_cursor
    self._compiled_query = _compiled_query

  @property
  def query_options(self):
    """The QueryOptions used to retrieve the first batch."""
    return self.__query_options

  @property
  def query(self):
    """The query the current batch came from."""
    return self.__query

  @property
  def results(self):
    """A list of entities in this batch."""
    return self.__results

  @property
  def keys_only(self):
    """Whether the entities in this batch only contain keys."""
    return self.__keys_only

  @property
  def start_cursor(self):
    """A cursor that points to the position just before the current batch."""
    return self.__start_cursor

  def cursor(self, index):
    """Gets the cursor that points to the result at the given index.

    The index is relative to first result in .results. Since start_cursor
    points to the position before the first skipped result and the end_cursor
    points to the position after the last result, the range of indexes this
    function supports is limited to [-skipped_results, len(results)].

    Args:
      index: An int, the index relative to the first result before which the
        cursor should point.

    Returns:
      A Cursor that points just before the result at the given index which if
      used as a start_cursor will cause the first result to result[index].
    """
    if not isinstance(index, (int, long)):
      raise datastore_errors.BadArgumentError(
          'index argument should be entity_pb.Reference (%r)' % (index,))
    if not -self.__skipped_results <= index <= len(self.__results):
      raise datastore_errors.BadArgumentError(
          'index argument must be in the inclusive range [%d, %d]' %
          (-self.__skipped_results, len(self.__results)))

    if index == len(self.__results):
      return self.__end_cursor
    elif index == -self.__skipped_results:
      return self.__start_cursor
    else:
      return self.__start_cursor.advance(index + self.__skipped_results,
                                         self.__query, self.__conn)

  @property
  def end_cursor(self):
    """A cursor that points to the position just after the current batch."""
    return self.__end_cursor

  @property
  def skipped_results(self):
    """The number of results skipped because of an offset in the request.

    An offset is satisfied before any results are returned. The start_cursor
    points to the position in the query before the skipped results.
    """
    return self.__skipped_results

  @property
  def more_results(self):
    """Whether more results can be retrieved from the query."""
    return self.__more_results

  def next_batch(self, fetch_options=None):
    """Synchronously get the next batch or None if there are no more batches.

    Args:
      fetch_options: Optional fetch options to use when fetching the next batch.
        Merged with both the fetch options on the original call and the
        connection.

    Returns:
      A new Batch of results or None if either the next batch has already been
      fetched or there are no more results.
    """
    async = self.next_batch_async(fetch_options)
    if async is None:
      return None
    return async.get_result()

  def next_batch_async(self, fetch_options=None):
    """Asynchronously get the next batch or None if there are no more batches.

    Args:
      fetch_options: Optional fetch options to use when fetching the next batch.
        Merged with both the fetch options on the original call and the
        connection.

    Returns:
      An async object that can be used to get the next Batch or None if either
      the next batch has already been fetched or there are no more results.
    """
    if not self.__datastore_cursor:
      return None

    req = self._to_pb(fetch_options)


    next_batch = Batch(self.__query_options, self.__query, self.__conn,
                       self.__end_cursor, self._compiled_query)

    config = datastore_rpc.Configuration.merge(self.__query_options,
                                               fetch_options)
    return next_batch._make_query_result_rpc_call(
        'Next', config, req)

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of datastore_query.Batch is unsupported.')

  def _to_pb(self, fetch_options=None):
    req = datastore_pb.NextRequest()

    if FetchOptions.produce_cursors(fetch_options,
                                    self.__query_options,
                                    self.__conn.config):
      req.set_compile(True)

    count = FetchOptions.batch_size(fetch_options,
                                    self.__query_options,
                                    self.__conn.config)
    if count is not None:
      req.set_count(count)

    if fetch_options is not None and fetch_options.offset:
      req.set_offset(fetch_options.offset)

    req.mutable_cursor().CopyFrom(self.__datastore_cursor)
    self.__datastore_cursor = None
    return req

  def _make_query_result_rpc_call(self, name, config, req):
    """Makes either a RunQuery or Next call that will modify the instance.

    Args:
      name: A string, the name of the call to invoke.
      config: The datastore_rpc.Configuration to use for the call.
      req: The request to send with the call.

    Returns:
      A UserRPC object that can be used to fetch the result of the RPC.
    """
    return self.__conn.make_rpc_call(config, name, req,
                                     datastore_pb.QueryResult(),
                                     self.__query_result_hook)

  def _extend(self, next_batch):
    """Combines the current batch with the next one. Called by batcher."""
    self.__datastore_cursor = next_batch.__datastore_cursor
    next_batch.__datastore_cursor = None
    self.__more_results = next_batch.__more_results
    self.__results.extend(next_batch.__results)
    self.__end_cursor = next_batch.__end_cursor
    self.__skipped_results += next_batch.__skipped_results

  def __query_result_hook(self, rpc):
    """Internal method used as get_result_hook for RunQuery/Next operation."""
    try:
      self.__conn.check_rpc_success(rpc)
    except datastore_errors.NeedIndexError, exc:

      if isinstance(rpc.request, datastore_pb.Query):
        yaml = datastore_index.IndexYamlForQuery(
            *datastore_index.CompositeIndexForQuery(rpc.request)[1:-1])
        raise datastore_errors.NeedIndexError(
            str(exc) + '\nThis query needs this index:\n' + yaml)
      raise

    query_result = rpc.response
    self.__keys_only = query_result.keys_only()
    self.__end_cursor = Cursor._from_query_result(query_result)
    self.__skipped_results = query_result.skipped_results()
    self.__results = [
        self.__conn.adapter.pb_to_query_result(result, self.__keys_only)
        for result in query_result.result_list()]
    if query_result.has_compiled_query():
      self._compiled_query = query_result.compiled_query



    if (query_result.more_results() and
        (isinstance(rpc.request, datastore_pb.Query) or
         query_result.skipped_results() or
         query_result.result_size())):
      self.__datastore_cursor = query_result.cursor()
      self.__more_results = True
    else:
      self.__datastore_cursor = None
      self.__more_results = False
    return self


class Batcher(object):
  """A class that implements the Iterator interface for Batches.

  Typically constructed by a call to Query.run().

  The class hides the "best effort" nature of the datastore by potentially
  making multiple requests to the datastore and merging the resulting batches.
  This is accomplished efficiently by prefetching results and mixing both
  non-blocking and blocking calls to the datastore as needed.

  Iterating through batches is almost always more efficient than pulling all
  results at once as RPC latency is hidden by asynchronously prefetching
  results.

  The batches produce by this class cannot be used to fetch the next batch
  (through Batch.next_batch()) as before the current batch is returned the
  request for the next batch has already been sent.
  """

  def __init__(self, query_options, first_async_batch):
    """Constructor.

    Although this class can be manually constructed, it is preferable to use
    Query.run(query_options).

    Args:
      query_options: The QueryOptions used to create the first batch.
      first_async_batch: The first batch produced by
        Query.run_asyn(query_options).
    """
    self.__next_batch = first_async_batch
    self.__initial_offset = QueryOptions.offset(query_options) or 0
    self.__skipped_results = 0

  def next(self):
    """Get the next batch. See .next_batch()."""
    return self.next_batch(1)

  def next_batch(self, min_batch_size):
    """Get the next batch.

    The batch returned by this function cannot be used to fetch the next batch
    (through Batch.next_batch()). Instead this function will always return None.
    To retrieve the next batch use .next() or .next_batch(N).

    This function may return a batch larger than min_to_fetch, but will never
    return smaller unless there are no more results.

    Args:
      min_batch_size: The minimum number of results to retrieve.

    Returns:
      The next Batch of results.
    """
    datastore_types.ValidateInteger(min_batch_size,
                                    'min_batch_size',
                                    datastore_errors.BadArgumentError,
                                    zero_ok=True)
    if not self.__next_batch:
      raise StopIteration


    batch = self.__next_batch.get_result()
    self.__next_batch = None
    self.__skipped_results += batch.skipped_results


    needed_results = min_batch_size - len(batch.results)
    while (batch.more_results and
           (self.__skipped_results < self.__initial_offset or
            needed_results > 0)):
      if batch.query_options.batch_size:

        batch_size = max(batch.query_options.batch_size, needed_results)
      elif needed_results:

        batch_size = needed_results
      else:
        batch_size = None
      next_batch = batch.next_batch(FetchOptions(
          offset=max(0, self.__initial_offset - self.__skipped_results),
          batch_size=batch_size))
      self.__skipped_results += next_batch.skipped_results
      needed_results = max(0, needed_results - len(next_batch.results))
      batch._extend(next_batch)




    self.__next_batch = batch.next_batch_async()
    return batch

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of datastore_query.Batcher is unsupported.')

  def __iter__(self):
    return self


class ResultsIterator(object):
  """An iterator over the results from Batches obtained from a Batcher.

  ResultsIterator implements Python's iterator protocol, so results can be
  accessed with the for-statement:

  > it = ResultsIterator(Query(kind='Person').run())
  > for person in it:
  >   print 'Hi, %s!' % person['name']

  At any time ResultsIterator.cursor() can be used to grab the Cursor that
  points just after the last result returned by the iterator.
  """

  def __init__(self, batcher):
    """Constructor.

    Args:
      batcher: A datastore_query.Bather
    """
    if not isinstance(batcher, Batcher):
      raise datastore_errors.BadArgumentError(
          'batcher argument should be datastore_query.Batcher (%r)' %
          (batcher,))

    self.__batcher = batcher
    self.__current_batch = None
    self.__current_pos = 0

  def cursor(self):
    """Returns a cursor that points just after the last result returned."""

    if not self.__current_batch:
      self.__current_batch = self.__batcher.next()
      self.__current_pos = 0
    return self.__current_batch.cursor(self.__current_pos)

  def _compiled_query(self):
    """Returns the compiled query associated with the iterator.

    Internal only do not use.
    """
    if not self.__current_batch:
      self.__current_batch = self.__batcher.next()
      self.__current_pos = 0
    return self.__current_batch._compiled_query


  def next(self):
    """Returns the next query result."""
    if (not self.__current_batch or
        self.__current_pos >= len(self.__current_batch.results)):

      next_batch = self.__batcher.next()
      if not next_batch:


        raise StopIteration

      self.__current_pos = 0
      self.__current_batch = next_batch
      if not self.__current_batch.results:
        raise StopIteration

    result = self.__current_batch.results[self.__current_pos]
    self.__current_pos += 1
    return result

  def __iter__(self):
    return self
