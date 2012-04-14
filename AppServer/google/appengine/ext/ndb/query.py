"""Higher-level Query wrapper.

There are perhaps too many query APIs in the world.

The fundamental API here overloads the 6 comparisons operators to
represent filters on property values, and supports AND and OR
operations (implemented as functions -- Python's 'and' and 'or'
operators cannot be overloaded, and the '&' and '|' operators have a
priority that conflicts with the priority of comparison operators).
For example:

  class Employee(Model):
    name = StringProperty()
    age = IntegerProperty()
    rank = IntegerProperty()

    @classmethod
    def demographic(cls, min_age, max_age):
      return cls.query().filter(AND(cls.age >= min_age, cls.age <= max_age))

    @classmethod
    def ranked(cls, rank):
      return cls.query(cls.rank == rank).order(cls.age)

  for emp in Employee.seniors(42, 5):
    print emp.name, emp.age, emp.rank

The 'in' operator cannot be overloaded, but is supported through the
IN() method.  For example:

  Employee.query().filter(Employee.rank.IN([4, 5, 6]))

Sort orders are supported through the order() method; unary minus is
overloaded on the Property class to represent a descending order:

  Employee.query().order(Employee.name, -Employee.age)

Besides using AND() and OR(), filters can also be combined by
repeatedly calling .filter():

  q1 = Employee.query()  # A query that returns all employees
  q2 = q1.filter(Employee.age >= 30)  # Only those over 30
  q3 = q2.filter(Employee.age < 40)  # Only those in their 30s

A further shortcut is calling .filter() with multiple arguments; this
implies AND():

  q1 = Employee.query()  # A query that returns all employees
  q3 = q1.filter(Employee.age >= 30,
                 Employee.age < 40)  # Only those in their 30s

And finally you can also pass one or more filter expressions directly
to the .query() method:

  q3 = Employee.query(Employee.age >= 30,
                      Employee.age < 40)  # Only those in their 30s

Query objects are immutable, so these methods always return a new
Query object; the above calls to filter() do not affect q1.  (On the
other hand, operations that are effectively no-ops may return the
original Query object.)

Sort orders can also be combined this way, and .filter() and .order()
calls may be intermixed:

  q4 = q3.order(-Employee.age)
  q5 = q4.order(Employee.name)
  q6 = q5.filter(Employee.rank == 5)

Again, multiple .order() calls can be combined:

  q5 = q3.order(-Employee.age, Employee.name)

The simplest way to retrieve Query results is a for-loop:

  for emp in q3:
    print emp.name, emp.age

Some other methods to run a query and access its results:

  q.iter() # Return an iterator; same as iter(q) but more flexible
  q.map(callback) # Call the callback function for each query result
  q.fetch(N) # Return a list of the first N results
  q.get() # Return the first result
  q.count(N) # Return the number of results, with a maximum of N
  q.fetch_page(N, start_cursor=cursor) # Return (results, cursor, has_more)

All of the above methods take a standard set of additional query
options, either in the form of keyword arguments such as
keys_only=True, or as QueryOptions object passed with
options=QueryOptions(...).  The most important query options are:

  keys_only: bool, if set the results are keys instead of entities
  limit: int, limits the number of results returned
  offset: int, skips this many results first
  start_cursor: Cursor, start returning results after this position
  end_cursor: Cursor, stop returning results after this position
  batch_size: int, hint for the number of results returned per RPC
  prefetch_size: int, hint for the number of results in the first RPC
  produce_cursors: bool, return Cursor objects with the results

For additional (obscure) query options and more details on them,
including an explanation of Cursors, see datastore_query.py.

All of the above methods except for iter() have asynchronous variants
as well, which return a Future; to get the operation's ultimate
result, yield the Future (when inside a tasklet) or call the Future's
get_result() method (outside a tasklet):

  q.map_async(callback)  # Callback may be a task or a plain function
  q.fetch_async(N)
  q.get_async()
  q.count_async(N)
  q.fetch_page_async(N, start_cursor=cursor)

Finally, there's an idiom to efficiently loop over the Query results
in a tasklet, properly yielding when appropriate:

  it = q.iter()
  while (yield it.has_next_async()):
    emp = it.next()
    print emp.name, emp.age
"""

from __future__ import with_statement

__author__ = 'guido@google.com (Guido van Rossum)'

import heapq
import itertools
import sys

from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.datastore import datastore_query
from google.appengine.datastore import datastore_rpc
from google.appengine.ext import gql

from . import model
from . import tasklets

__all__ = ['Binding', 'AND', 'OR', 'parse_gql', 'Query',
           'QueryOptions', 'Cursor']

# Re-export some useful classes from the lower-level module.
QueryOptions = datastore_query.QueryOptions
Cursor = datastore_query.Cursor

# Some local renamings.
_ASC = datastore_query.PropertyOrder.ASCENDING
_DESC = datastore_query.PropertyOrder.DESCENDING
_AND = datastore_query.CompositeFilter.AND
_KEY = datastore_types._KEY_SPECIAL_PROPERTY

# Table of supported comparison operators.
_OPS = frozenset(['=', '!=', '<', '<=', '>', '>=', 'in'])

# Default limit value.  (Yes, the datastore uses int32!)
_MAX_LIMIT = 2 ** 31 - 1


# TODO: Once CL/21689469 is submitted, get rid of this and its callers.
def _make_unsorted_key_value_map(pb, property_names):
  """Like _make_key_value_map() but doesn't sort the values."""
  value_map = dict((name, []) for name in property_names)

  # Building comparable values from pb properties.
  # NOTE: Unindexed properties are skipped.
  for prop in pb.property_list():
    prop_name = prop.name()
    if prop_name in value_map:
      value_map[prop_name].append(
        datastore_types.PropertyValueToKeyValue(prop.value()))

  # Adding special key property (if requested).
  if _KEY in value_map:
    value_map[_KEY] = [datastore_types.ReferenceToKeyValue(pb.key())]

  return value_map


class RepeatedStructuredPropertyPredicate(datastore_query.FilterPredicate):

  def __init__(self, match_keys, pb, key_prefix):
    super(RepeatedStructuredPropertyPredicate, self).__init__()
    self.match_keys = match_keys
    stripped_keys = []
    for key in match_keys:
      if not key.startswith(key_prefix):
        raise ValueError('key %r does not begin with the specified prefix of %s'
                         % (key, key_prefix))
      stripped_keys.append(key[len(key_prefix):])
    value_map = _make_unsorted_key_value_map(pb, stripped_keys)
    self.match_values = tuple(value_map[key][0] for key in stripped_keys)

  def _get_prop_names(self):
    return frozenset(self.match_keys)

  def __call__(self, pb):
    return self._apply(_make_unsorted_key_value_map(pb, self.match_keys))

  def _apply(self, key_value_map):
    """Apply the filter to values extracted from an entity.

    Think of self.match_keys and self.match_values as representing a
    table with one row.  For example:

      match_keys = ('name', 'age', 'rank')
      match_values = ('Joe', 24, 5)

    (Except that in reality, the values are represented by tuples
    produced by datastore_types.PropertyValueToKeyValue().)

    represents this table:

      |  name   |  age  |  rank  |
      +---------+-------+--------+
      |  'Joe'  |   24  |     5  |

    Think of key_value_map as a table with the same structure but
    (potentially) many rows.  This represents a repeated structured
    property of a single entity.  For example:

      {'name': ['Joe', 'Jane', 'Dick'],
       'age': [24, 21, 23],
       'rank': [5, 1, 2]}

    represents this table:

      |  name   |  age  |  rank  |
      +---------+-------+--------+
      |  'Joe'  |   24  |     5  |
      |  'Jane' |   21  |     1  |
      |  'Dick' |   23  |     2  |

    We must determine wheter at least one row of the second table
    exactly matches the first table.  We need this class because the
    datastore, when asked to find an entity with name 'Joe', age 24
    and rank 5, will include entities that have 'Joe' somewhere in the
    name column, 24 somewhere in the age column, and 5 somewhere in
    the rank column, but not all aligned on a single row.  Such an
    entity should not be considered a match.
    """
    columns = []
    for key in self.match_keys:
      column = key_value_map.get(key)
      if not column:  # None, or an empty list.
        return False  # If any column is empty there can be no match.
      columns.append(column)
    # Use izip to transpose the columns into rows.
    return self.match_values in itertools.izip(*columns)

  # Don't implement _prune()!  It would mess up the row correspondence
  # within columns.


class CompositePostFilter(datastore_query.CompositeFilter):

  def __call__(self, pb):
    key_value_map = _make_unsorted_key_value_map(pb, self._get_prop_names())
    return self._apply(key_value_map)


class Binding(object):
  """Used with GQL; for now unsupported."""

  def __init__(self, value=None, key=None):
    """Constructor.  The value may be changed later."""
    self.value = value
    self.key = key

  def __repr__(self):
    return '%s(%r, %r)' % (self.__class__.__name__, self.value, self.key)

  def __eq__(self, other):
    # TODO: When comparing tree nodes containing Bindings, Bindings
    # should be compared by object identity?
    if not isinstance(other, Binding):
      return NotImplemented
    return self.value == other.value and self.key == other.key

  def resolve(self):
    """Return the value currently associated with this Binding."""
    value = self.value
    if isinstance(value, Binding):
      raise RuntimeError('Recursive Binding.')
    return value


class Node(object):
  """Base class for filter expression tree nodes.

  Tree nodes are considered immutable, even though they can contain
  Binding instances, which are not.  In particular, two identical
  trees may be represented by the same Node object in different
  contexts.
  """

  def __new__(cls):
    if cls is Node:
      raise TypeError('Cannot instantiate Node, only a subclass.')
    return super(Node, cls).__new__(cls)

  def __eq__(self, other):
    raise NotImplementedError

  def __ne__(self, other):
    eq = self.__eq__(other)
    if eq is not NotImplemented:
      eq = not eq
    return eq

  def __unordered(self, unused_other):
    raise TypeError('Nodes cannot be ordered')
  __le__ = __lt__ = __ge__ = __gt__ = __unordered

  def _to_filter(self, bindings, post=False):
    """Helper to convert to datastore_query.Filter, or None."""
    raise NotImplementedError

  def _post_filters(self):
    """Helper to extract post-filter Nodes, if any."""
    return None

  def resolve(self):
    """Extract the Binding's value if necessary."""
    raise NotImplementedError


class FalseNode(Node):
  """Tree node for an always-failing filter."""

  def __new__(cls):
    return super(Node, cls).__new__(cls)

  def __eq__(self, other):
    if not isinstance(other, FalseNode):
      return NotImplemented
    return True

  def _to_filter(self, unused_bindings, post=False):
    if post:
      return None
    # Because there's no point submitting a query that will never
    # return anything.
    raise datastore_errors.BadQueryError(
      'Cannot convert FalseNode to predicate')

  def resolve(self):
    return self


class FilterNode(Node):
  """Tree node for a single filter expression."""

  def __new__(cls, name, opsymbol, value):
    if opsymbol == '!=':
      n1 = FilterNode(name, '<', value)
      n2 = FilterNode(name, '>', value)
      return DisjunctionNode(n1, n2)
    if opsymbol == 'in' and not isinstance(value, Binding):
      if not isinstance(value, (list, tuple, set, frozenset)):
        raise TypeError('in expected a list, tuple or set of values; '
                        'received %r' % value)
      nodes = [FilterNode(name, '=', v) for v in value]
      if not nodes:
        return FalseNode()
      if len(nodes) == 1:
        return nodes[0]
      return DisjunctionNode(*nodes)
    self = super(FilterNode, cls).__new__(cls)
    self.__name = name
    self.__opsymbol = opsymbol
    self.__value = value
    return self

  def _sort_key(self):
    return self.__name, self.__opsymbol, self.__value

  def __repr__(self):
    return '%s(%r, %r, %r)' % (self.__class__.__name__,
                               self.__name, self.__opsymbol, self.__value)

  def __eq__(self, other):
    if not isinstance(other, FilterNode):
      return NotImplemented
    # TODO: Should nodes with values that compare equal but have
    # different types really be considered equal?  IIUC the datastore
    # doesn't consider 1 equal to 1.0 when it compares property values.
    return (self.__name == other.__name and
            self.__opsymbol == other.__opsymbol and
            self.__value == other.__value)

  def _to_filter(self, bindings, post=False):
    if post:
      return None
    if self.__opsymbol in ('!=', 'in'):
      raise NotImplementedError('Inequality filters are not single filter '
                                'expressions and therefore cannot be converted '
                                'to a single filter (%r)' % self.__opsymbol)
    value = self.__value
    if isinstance(value, Binding):
      bindings[value.key] = value
      value = value.resolve()
      # TODO: validate the resolved value.
    return datastore_query.make_filter(self.__name.decode('utf-8'),
                                       self.__opsymbol, value)

  def resolve(self):
    if self.__opsymbol == 'in':
      if isinstance(self.__value, Binding):
        raise RuntimeError('Unexpanded non-Binding IN.')
      return FilterNode(self.__name, self.__opsymbol, self.__value.resolve())
    else:
      return self


class PostFilterNode(Node):
  """Tree node representing an in-memory filtering operation.

  This is used to represent filters that cannot be executed by the
  datastore, for example a query for a structured value.
  """

  def __new__(cls, predicate):
    self = super(PostFilterNode, cls).__new__(cls)
    self.predicate = predicate
    return self

  def __repr__(self):
    return '%s(%s)' % (self.__class__.__name__, self.predicate)

  def __eq__(self, other):
    if not isinstance(other, PostFilterNode):
      return NotImplemented
    return self is other

  def _to_filter(self, unused_bindings, post=False):
    if post:
      return self.predicate
    else:
      return None

  def resolve(self):
    return self


class ConjunctionNode(Node):
  """Tree node representing a Boolean AND operator on two or more nodes."""

  def __new__(cls, *nodes):
    if not nodes:
      raise TypeError('ConjunctionNode() requires at least one node.')
    elif len(nodes) == 1:
      return nodes[0]
    clauses = [[]]  # Outer: Disjunction; inner: Conjunction.
    # TODO: Remove duplicates?
    for node in nodes:
      if not isinstance(node, Node):
        raise TypeError('ConjunctionNode() expects Node instances as arguments;'
                        ' received a non-Node instance %r' % node)
      if isinstance(node, DisjunctionNode):
        # Apply the distributive law: (X or Y) and (A or B) becomes
        # (X and A) or (X and B) or (Y and A) or (Y and B).
        new_clauses = []
        for clause in clauses:
          for subnode in node:
            new_clause = clause + [subnode]
            new_clauses.append(new_clause)
        clauses = new_clauses
      elif isinstance(node, ConjunctionNode):
        # Apply half of the distributive law: (X or Y) and A becomes
        # (X and A) or (Y and A).
        for clause in clauses:
          clause.extend(node.__nodes)
      else:
        # Ditto.
        for clause in clauses:
          clause.append(node)
    if not clauses:
      return FalseNode()
    if len(clauses) > 1:
      return DisjunctionNode(*[ConjunctionNode(*clause) for clause in clauses])
    self = super(ConjunctionNode, cls).__new__(cls)
    self.__nodes = clauses[0]
    return self

  def __iter__(self):
    return iter(self.__nodes)

  def __repr__(self):
    return 'AND(%s)' % (', '.join(map(str, self.__nodes)))

  def __eq__(self, other):
    if not isinstance(other, ConjunctionNode):
      return NotImplemented
    return self.__nodes == other.__nodes

  def _to_filter(self, bindings, post=False):
    filters = filter(None,
                     (node._to_filter(bindings, post=post)
                      for node in self.__nodes
                      if isinstance(node, PostFilterNode) == post))
    if not filters:
      return None
    if len(filters) == 1:
      return filters[0]
    if post:
      return CompositePostFilter(_AND, filters)
    return datastore_query.CompositeFilter(_AND, filters)

  def _post_filters(self):
    post_filters = [node for node in self.__nodes
                    if isinstance(node, PostFilterNode)]
    if not post_filters:
      return None
    if len(post_filters) == 1:
      return post_filters[0]
    if post_filters == self.__nodes:
      return self
    return ConjunctionNode(*post_filters)

  def resolve(self):
    nodes = [node.resolve() for node in self.__nodes]
    if nodes == self.__nodes:
      return self
    return ConjunctionNode(*nodes)


class DisjunctionNode(Node):
  """Tree node representing a Boolean OR operator on two or more nodes."""

  def __new__(cls, *nodes):
    if not nodes:
      raise TypeError('DisjunctionNode() requires at least one node')
    elif len(nodes) == 1:
      return nodes[0]
    self = super(DisjunctionNode, cls).__new__(cls)
    self.__nodes = []
    # TODO: Remove duplicates?
    for node in nodes:
      if not isinstance(node, Node):
        raise TypeError('DisjunctionNode() expects Node instances as arguments;'
                        ' received a non-Node instance %r' % node)
      if isinstance(node, DisjunctionNode):
        self.__nodes.extend(node.__nodes)
      else:
        self.__nodes.append(node)
    return self

  def __iter__(self):
    return iter(self.__nodes)

  def __repr__(self):
    return 'OR(%s)' % (', '.join(map(str, self.__nodes)))

  def __eq__(self, other):
    if not isinstance(other, DisjunctionNode):
      return NotImplemented
    return self.__nodes == other.__nodes

  def resolve(self):
    nodes = [node.resolve() for node in self.__nodes]
    if nodes == self.__nodes:
      return self
    return DisjunctionNode(*nodes)


# AND and OR are preferred aliases for these.
AND = ConjunctionNode
OR = DisjunctionNode


def _args_to_val(func, args, bindings):
  """Helper for GQL parsing."""
  vals = []
  for arg in args:
    if isinstance(arg, (int, long, basestring)):
      if arg in bindings:
        val = bindings[arg]
      else:
        val = Binding(None, arg)
        bindings[arg] = val
    elif isinstance(arg, gql.Literal):
      val = arg.Get()
    else:
      raise TypeError('Unexpected arg (%r)' % arg)
    vals.append(val)
  if func == 'nop':
    if len(vals) != 1:
      raise TypeError('"nop" requires exactly one value')
    return vals[0]
  if func == 'list':
    return vals
  if func == 'key':
    if len(vals) == 1 and isinstance(vals[0], basestring):
      return model.Key(urlsafe=vals[0])
    raise TypeError('Unexpected key args (%r)' % vals)
  raise ValueError('Unexpected func (%r)' % func)


# TODO: Not everybody likes GQL.

# TODO: GQL doesn't support querying for structured property values.

def parse_gql(query_string):
  """Parse a GQL query string.

  Args:
    query_string: Full GQL query, e.g. 'SELECT * FROM Kind WHERE prop = 1'.

  Returns:
    A tuple (query, options, bindings) where query is a Query instance,
    options a datastore_query.QueryOptions instance, and bindings a dict
    mapping integers and strings to Binding instances.
  """
  gql_qry = gql.GQL(query_string)
  ancestor = None
  flt = gql_qry.filters()
  bindings = {}
  filters = []
  for ((name, op), values) in flt.iteritems():
    op = op.lower()
    if op == 'is' and name == gql.GQL._GQL__ANCESTOR:
      if len(values) != 1:
        raise ValueError('"is" requires exactly one value')
      [(func, args)] = values
      ancestor = _args_to_val(func, args, bindings)
      continue
    if op not in _OPS:
      raise NotImplementedError('Operation %r is not supported.' % op)
    for (func, args) in values:
      val = _args_to_val(func, args, bindings)
      filters.append(FilterNode(name, op, val))
  if filters:
    filters.sort(key=lambda x: x._sort_key())  # For predictable tests.
    filters = ConjunctionNode(*filters)
  else:
    filters = None
  orders = _orderings_to_orders(gql_qry.orderings())
  qry = Query(kind=gql_qry._kind,
              ancestor=ancestor,
              filters=filters,
              orders=orders)
  offset = gql_qry.offset()
  if offset < 0:
    offset = None
  limit = gql_qry.limit()
  if limit < 0:
    limit = None
  options = QueryOptions(offset=offset, limit=limit)
  return qry, options, bindings


class Query(object):
  """Query object.

  Usually constructed by calling Model.query().

  See module docstring for examples.

  Note that not all operations on Queries are supported by _MultiQuery
  instances; the latter are generated as necessary when any of the
  operators !=, IN or OR is used.
  """

  @datastore_rpc._positional(1)
  def __init__(self, kind=None, ancestor=None, filters=None, orders=None,
               app=None, namespace=None):
    """Constructor.

    Args:
      kind: Optional kind string.
      ancestor: Optional ancestor Key.
      filters: Optional Node representing a filter expression tree.
      orders: Optional datastore_query.Order object.
      app: Optional app id.
      namespace: Optional namespace.
    """
    if ancestor is not None and not isinstance(ancestor, Binding):
      if not ancestor.id():
        raise TypeError('ancestor cannot be an incomplete key')
      if app is not None:
        if app != ancestor.app():
          raise TypeError('app/ancestor mismatch')
      if namespace is not None:
        if namespace != ancestor.namespace():
          raise TypeError('namespace/ancestor mismatch')
    if filters is not None:
      if not isinstance(filters, Node):
        raise TypeError('filters must be a query Node or None; received %r' %
                        filters)
    if orders is not None:
      if not isinstance(orders, datastore_query.Order):
        raise TypeError('orders must be an Order instance or None; received %r'
                        % orders)
    self.__kind = kind  # String
    self.__ancestor = ancestor  # Key
    self.__filters = filters  # None or Node subclass
    self.__orders = orders  # None or datastore_query.Order instance
    self.__app = app
    self.__namespace = namespace

  def __repr__(self):
    args = []
    if self.__kind is not None:
      args.append('kind=%r' % self.__kind)
    if self.__ancestor is not None:
      args.append('ancestor=%r' % self.__ancestor)
    if self.__filters is not None:
      args.append('filters=%r' % self.__filters)
    if self.__orders is not None:
      args.append('orders=...')  # PropertyOrder doesn't have a good repr().
    if self.__app is not None:
      args.append('app=%r' % self.__app)
    if self.__namespace is not None:
      args.append('namespace=%r' % self.__namespace)
    return '%s(%s)' % (self.__class__.__name__, ', '.join(args))

  def _get_query(self, connection):
    kind = self.__kind
    ancestor = self.__ancestor
    bindings = {}
    if isinstance(ancestor, Binding):
      bindings[ancestor.key] = ancestor
      ancestor = ancestor.resolve()
    if ancestor is not None:
      ancestor = connection.adapter.key_to_pb(ancestor)
    filters = self.__filters
    post_filters = None
    if filters is not None:
      post_filters = filters._post_filters()
      filters = filters._to_filter(bindings)
    dsquery = datastore_query.Query(app=self.__app,
                                    namespace=self.__namespace,
                                    kind=kind.decode('utf-8'),
                                    ancestor=ancestor,
                                    filter_predicate=filters,
                                    order=self.__orders)
    if post_filters is not None:
      dsquery = datastore_query._AugmentedQuery(
        dsquery,
        in_memory_filter=post_filters._to_filter(bindings, post=True))
    return dsquery

  @tasklets.tasklet
  def run_to_queue(self, queue, conn, options=None, dsquery=None):
    """Run this query, putting entities into the given queue."""
    try:
      multiquery = self._maybe_multi_query()
      if multiquery is not None:
        yield multiquery.run_to_queue(queue, conn, options=options)
        return

      if dsquery is None:
        dsquery = self._get_query(conn)
      rpc = dsquery.run_async(conn, options)
      while rpc is not None:
        batch = yield rpc
        rpc = batch.next_batch_async(options)
        for i, result in enumerate(batch.results):
          queue.putq((batch, i, result))
      queue.complete()

    except Exception:
      if not queue.done():
        _, e, tb = sys.exc_info()
        queue.set_exception(e, tb)
      raise

  def _maybe_multi_query(self):
    filters = self.__filters
    if filters is not None:
      filters = filters.resolve()
      if isinstance(filters, DisjunctionNode):
        # Switch to a _MultiQuery.
        subqueries = []
        for subfilter in filters:
          subquery = Query(kind=self.__kind, ancestor=self.__ancestor,
                           filters=subfilter, orders=self.__orders)
          subqueries.append(subquery)
        return _MultiQuery(subqueries)
    return None

  @property
  def kind(self):
    """Accessor for the kind (a string or None)."""
    return self.__kind

  @property
  def namespace(self):
    """Accessor for the namespace (a string or None)."""
    return self.__namespace

  @property
  def ancestor(self):
    """Accessor for the ancestor (a Key or None)."""
    return self.__ancestor

  @property
  def filters(self):
    """Accessor for the filters (a Node or None)."""
    return self.__filters

  @property
  def orders(self):
    """Accessor for the filters (a datastore_query.Order or None)."""
    return self.__orders

  def filter(self, *args):
    """Return a new Query with additional filter(s) applied."""
    if not args:
      return self
    preds = []
    f = self.filters
    if f:
      preds.append(f)
    for arg in args:
      if not isinstance(arg, Node):
        raise TypeError('Cannot filter a non-Node argument; received %r' % arg)
      preds.append(arg)
    if not preds:
      pred = None
    elif len(preds) == 1:
      pred = preds[0]
    else:
      pred = ConjunctionNode(*preds)
    return self.__class__(kind=self.kind, ancestor=self.ancestor,
                          orders=self.orders, filters=pred,
                          namespace=self.namespace)

  def order(self, *args):
    """Return a new Query with additional sort order(s) applied."""
    # q.order(Employee.name, -Employee.age)
    if not args:
      return self
    orders = []
    o = self.__orders
    if o:
      orders.append(o)
    for arg in args:
      if isinstance(arg, model.Property):
        orders.append(datastore_query.PropertyOrder(arg._name, _ASC))
      elif isinstance(arg, datastore_query.Order):
        orders.append(arg)
      else:
        raise TypeError('order() expects a Property or query Order; '
                        'received %r' % arg)
    if not orders:
      orders = None
    elif len(orders) == 1:
      orders = orders[0]
    else:
      orders = datastore_query.CompositeOrder(orders)
    return self.__class__(kind=self.kind, ancestor=self.ancestor,
                          filters=self.filters, orders=orders,
                          namespace=self.namespace)

  # Datastore API using the default context.

  def iter(self, **q_options):
    """Construct an iterator over the query.

    Args:
      **q_options: All query options keyword arguments are supported.

    Returns:
      A QueryIterator object.
    """
    return QueryIterator(self, **q_options)

  __iter__ = iter

  @datastore_rpc._positional(2)
  def map(self, callback, merge_future=None, **q_options):
    """Map a callback function or tasklet over the query results.

    Args:
      callback: A function or tasklet to be applied to each result; see below.
      merge_future: Optional Future subclass; see below.
      **q_options: All query options keyword arguments are supported.

    Callback signature: The callback is normally called with an entity
    as argument.  However if keys_only=True is given, it is called
    with a Key.  Also, when produce_cursors=True is given, it is
    called with three arguments: the current batch, the index within
    the batch, and the entity or Key at that index.  The callback can
    return whatever it wants.

    Optional merge future: The merge_future is an advanced argument
    that can be used to override how the callback results are combined
    into the overall map() return value.  By default a list of
    callback return values is produced.  By substituting one of a
    small number of specialized alternatives you can arrange
    otherwise.  See tasklets.MultiFuture for the default
    implementation and a description of the protocol the merge_future
    object must implement the default.  Alternatives from the same
    module include QueueFuture, SerialQueueFuture and ReducingFuture.

    Returns:
      When the query has run to completion and all callbacks have
      returned, map() returns a list of the results of all callbacks.
      (But see 'optional merge future' above.)
    """
    return self.map_async(callback, merge_future=merge_future,
                          **q_options).get_result()

  @datastore_rpc._positional(2)
  def map_async(self, callback, merge_future=None, **q_options):
    """Map a callback function or tasklet over the query results.

    This is the asynchronous version of Query.map().
    """
    return tasklets.get_context().map_query(self, callback,
                                            options=_make_options(q_options),
                                            merge_future=merge_future)

  @datastore_rpc._positional(2)
  def fetch(self, limit=None, **q_options):
    """Fetch a list of query results, up to a limit.

    Args:
      limit: How many results to retrieve at most.
      **q_options: All query options keyword arguments are supported.

    Returns:
      A list of results.
    """
    return self.fetch_async(limit, **q_options).get_result()

  @tasklets.tasklet
  @datastore_rpc._positional(2)
  def fetch_async(self, limit=None, **q_options):
    """Fetch a list of query results, up to a limit.

    This is the asynchronous version of Query.fetch().
    """
    if 'limit' in q_options:
      raise TypeError('Cannot specify limit as a non-keyword argument and as a '
                      'keyword argument simultaneously.')
    elif limit is None:
      limit = _MAX_LIMIT
    q_options['limit'] = limit
    q_options.setdefault('prefetch_size', limit)
    q_options.setdefault('batch_size', limit)
    res = []
    it = self.iter(**q_options)
    while (yield it.has_next_async()):
      res.append(it.next())
      if len(res) >= limit:
        break
    raise tasklets.Return(res)

  def get(self, **q_options):
    """Get the first query result, if any.

    This is similar to calling q.fetch(1) and returning the first item
    of the list of results, if any, otherwise None.

    Args:
      **q_options: All query options keyword arguments are supported.

    Returns:
      A single result, or None if there are no results.
    """
    return self.get_async(**q_options).get_result()

  @tasklets.tasklet
  def get_async(self, **q_options):
    """Get the first query result, if any.

    This is the asynchronous version of Query.get().
    """
    res = yield self.fetch_async(1, **q_options)
    if not res:
      raise tasklets.Return(None)
    raise tasklets.Return(res[0])

  @datastore_rpc._positional(2)
  def count(self, limit=None, **q_options):
    """Count the number of query results, up to a limit.

    This returns the same result as len(q.fetch(limit)) but more
    efficiently.

    Note that you must pass a maximum value to limit the amount of
    work done by the query.

    Args:
      limit: How many results to count at most.
      **q_options: All query options keyword arguments are supported.

    Returns:
    """
    return self.count_async(limit, **q_options).get_result()

  @tasklets.tasklet
  @datastore_rpc._positional(2)
  def count_async(self, limit=None, **q_options):
    """Count the number of query results, up to a limit.

    This is the asynchronous version of Query.count().
    """
    # TODO: Support offset by incorporating it to the limit.
    if 'offset' in q_options:
      raise NotImplementedError('.count() and .count_async() do not support '
                                'offsets at present.')
    if 'limit' in q_options:
      raise TypeError('Cannot specify limit as a non-keyword argument and as a '
                      'keyword argument simultaneously.')
    elif limit is None:
      limit = _MAX_LIMIT
    if (self.__filters is not None and
        isinstance(self.__filters, DisjunctionNode)):
      # _MultiQuery does not support iterating over result batches,
      # so just fetch results and count them.
      # TODO: Use QueryIterator to avoid materializing the results list.
      q_options.setdefault('prefetch_size', limit)
      q_options.setdefault('batch_size', limit)
      q_options.setdefault('keys_only', True)
      results = yield self.fetch_async(limit, **q_options)
      raise tasklets.Return(len(results))

    # Issue a special query requesting 0 results at a given offset.
    # The skipped_results count will tell us how many hits there were
    # before that offset without fetching the items.
    q_options['offset'] = limit
    q_options['limit'] = 0
    options = _make_options(q_options)
    conn = tasklets.get_context()._conn
    dsquery = self._get_query(conn)
    rpc = dsquery.run_async(conn, options)
    total = 0
    while rpc is not None:
      batch = yield rpc
      rpc = batch.next_batch_async(options)
      total += batch.skipped_results
    raise tasklets.Return(total)

  @datastore_rpc._positional(2)
  def fetch_page(self, page_size, **q_options):
    """Fetch a page of results.

    This is a specialized method for use by paging user interfaces.

    Args:
      page_size: The requested page size.  At most this many results
        will be returned.

    In addition, any keyword argument supported by the QueryOptions
    class is supported.  In particular, to fetch the next page, you
    pass the cursor returned by one call to the next call using
    start_cursor=<cursor>.  A common idiom is to pass the cursor to
    the client using <cursor>.to_websafe_string() and to reconstruct
    that cursor on a subsequent request using
    Cursor.from_websafe_string(<string>).

    Returns:
      A tuple (results, cursor, more) where results is a list of query
      results, cursor is a cursor pointing just after the last result
      returned, and more is a bool indicating whether there are
      (likely) more results after that.
    """
    # NOTE: page_size can't be passed as a keyword.
    return self.fetch_page_async(page_size, **q_options).get_result()

  @tasklets.tasklet
  @datastore_rpc._positional(2)
  def fetch_page_async(self, page_size, **q_options):
    """Fetch a page of results.

    This is the asynchronous version of Query.fetch_page().
    """
    q_options.setdefault('batch_size', page_size)
    q_options.setdefault('produce_cursors', True)
    it = self.iter(limit=page_size + 1, **q_options)
    results = []
    while (yield it.has_next_async()):
      results.append(it.next())
      if len(results) >= page_size:
        break
    try:
      cursor = it.cursor_after()
    except datastore_errors.BadArgumentError:
      cursor = None
    raise tasklets.Return(results, cursor, it.probably_has_next())


def _make_options(q_options):
  """Helper to construct a QueryOptions object from keyword arguents.

  Args:
    q_options: a dict of keyword arguments.

  Note that either 'options' or 'config' can be used to pass another
  QueryOptions object, but not both.  If another QueryOptions object is
  given it provides default values.

  Returns:
    A QueryOptions object, or None if q_options is empty.
  """
  if not q_options:
    return None
  if 'options' in q_options:
    # Move 'options' to 'config' since that is what QueryOptions() uses.
    if 'config' in q_options:
      raise TypeError('The options pertaining to a config option must be '
                      'given independently instead of using a config argument.')
    q_options['config'] = q_options.pop('options')
  return QueryOptions(**q_options)


class QueryIterator(object):
  """This iterator works both for synchronous and async callers!

  For synchronous callers, just use:

    for entity in Account.query():
      <use entity>

  Async callers use this idiom:

    it = iter(Account.query())
    while (yield it.has_next_async()):
      entity = it.next()
      <use entity>

  You can also use q.iter([options]) instead of iter(q); this allows
  passing query options such as keys_only or produce_cursors.

  When keys_only is set, it.next() returns a key instead of an entity.

  When produce_cursors is set, the methods it.cursor_before() and
  it.cursor_after() return Cursor objects corresponding to the query
  position just before and after the item returned by it.next().
  Before it.next() is called for the first time, both raise an
  exception.  Once the loop is exhausted, both return the cursor after
  the last item returned.  Calling it.has_next() does not affect the
  cursors; you must call it.next() before the cursors move.  Note that
  sometimes requesting a cursor requires a datastore roundtrip (but
  not if you happen to request a cursor corresponding to a batch
  boundary).  If produce_cursors is not set, both methods always raise
  an exception.

  Note that queries requiring in-memory merging of multiple queries
  (i.e. queries using the IN, != or OR operators) do not support query
  options.
  """

  # When produce_cursors is set, _lookahead collects (batch, index)
  # pairs passed to _extended_callback(), and (_batch, _index)
  # contain the info pertaining to the current item.
  _lookahead = None
  _batch = None
  _index = None

  # Indicate the loop is exhausted.
  _exhausted = False

  @datastore_rpc._positional(2)
  def __init__(self, query, **q_options):
    """Constructor.  Takes a Query and query options.

    This is normally called by Query.iter() or Query.__iter__().
    """
    ctx = tasklets.get_context()
    callback = None
    options = _make_options(q_options)
    if options is not None and options.produce_cursors:
      callback = self._extended_callback
    self._iter = ctx.iter_query(query, callback=callback, options=options)
    self._fut = None

  def _extended_callback(self, batch, index, ent):
    if self._exhausted:
      raise RuntimeError('QueryIterator is already exhausted')
    # TODO: Make _lookup a deque.
    if self._lookahead is None:
      self._lookahead = []
    self._lookahead.append((batch, index))
    return ent

  def _consume_item(self):
    if self._lookahead:
      self._batch, self._index = self._lookahead.pop(0)
    else:
      self._batch = self._index = None

  def cursor_before(self):
    """Return the cursor before the current item.

    You must pass a QueryOptions object with produce_cursors=True
    for this to work.

    If there is no cursor or no current item, raise BadArgumentError.
    Before next() has returned there is no cursor.  Once the loop is
    exhausted, this returns the cursor after the last item.
    """
    if self._batch is None:
      raise datastore_errors.BadArgumentError('There is no cursor currently')
    # TODO: if cursor_after() was called for the previous item
    # reuse that result instead of computing it from scratch.
    # (Some cursor() calls make a datastore roundtrip.)
    return self._batch.cursor(self._index + self._exhausted)

  def cursor_after(self):
    """Return the cursor after the current item.

    You must pass a QueryOptions object with produce_cursors=True
    for this to work.

    If there is no cursor or no current item, raise BadArgumentError.
    Before next() has returned there is no cursor.    Once the loop is
    exhausted, this returns the cursor after the last item.
    """
    if self._batch is None:
      raise datastore_errors.BadArgumentError('There is no cursor currently')
    return self._batch.cursor(self._index + 1)

  def __iter__(self):
    """Iterator protocol: get the iterator for this iterator, i.e. self."""
    return self

  def probably_has_next(self):
    """Return whether a next item is (probably) available.

    This is not quite the same as has_next(), because when
    produce_cursors is set, some shortcuts are possible.  However, in
    some cases (e.g. when the query has a post_filter) we can get a
    false positive (returns True but next() will raise StopIteration).
    There are no false negatives, if Batch.more_results doesn't lie.
    """
    if self._lookahead:
      return True
    if self._batch is not None:
      return self._batch.more_results
    return self.has_next()

  def has_next(self):
    """Return whether a next item is available.

    See the module docstring for the usage pattern.
    """
    return self.has_next_async().get_result()

  @tasklets.tasklet
  def has_next_async(self):
    """Return a Future whose result will say whether a next item is available.

    See the module docstring for the usage pattern.
    """
    if self._fut is None:
      self._fut = self._iter.getq()
    flag = True
    try:
      yield self._fut
    except EOFError:
      flag = False
    raise tasklets.Return(flag)

  def next(self):
    """Iterator protocol: get next item or raise StopIteration."""
    if self._fut is None:
      self._fut = self._iter.getq()
    try:
      try:
        ent = self._fut.get_result()
        self._consume_item()
        return ent
      except EOFError:
        self._exhausted = True
        raise StopIteration
    finally:
      self._fut = None


class _SubQueryIteratorState(object):
  """Helper class for _MultiQuery."""

  def __init__(self, batch_i_entity, iterator, dsquery, orders):
    batch, index, entity = batch_i_entity
    self.batch = batch
    self.index = index
    self.entity = entity
    self.iterator = iterator
    self.dsquery = dsquery
    self.orders = orders

  def __cmp__(self, other):
    if not isinstance(other, _SubQueryIteratorState):
      raise NotImplementedError('Can only compare _SubQueryIteratorState '
                                'instances to other _SubQueryIteratorState '
                                'instances; not %r' % other)
    if not self.orders == other.orders:
      raise NotImplementedError('Cannot compare _SubQueryIteratorStates with '
                                'differing orders (%r != %r)' %
                                (self.orders, other.orders))
    lhs = self.entity._orig_pb
    rhs = other.entity._orig_pb
    lhs_filter = self.dsquery._filter_predicate
    rhs_filter = other.dsquery._filter_predicate
    names = self.orders._get_prop_names()
    # TODO: In some future version, there won't be a need to add the
    # filters' names.
    if lhs_filter is not None:
      names |= lhs_filter._get_prop_names()
    if rhs_filter is not None:
      names |= rhs_filter._get_prop_names()
    lhs_value_map = datastore_query._make_key_value_map(lhs, names)
    rhs_value_map = datastore_query._make_key_value_map(rhs, names)
    if lhs_filter is not None:
      lhs_filter._prune(lhs_value_map)
    if rhs_filter is not None:
      rhs_filter._prune(rhs_value_map)
    return self.orders._cmp(lhs_value_map, rhs_value_map)


class _MultiQuery(object):
  """Helper class to run queries involving !=, IN or OR operators."""

  # This is not instantiated by the user directly, but implicitly when
  # iterating over a query with at least one filter using an IN, OR or
  # != operator.  Note that some options must be interpreted by
  # _MultiQuery instead of passed to the underlying Queries' methods,
  # e.g. offset (though not necessarily limit, and I'm not sure about
  # cursors).

  # TODO: Need a way to specify the unification of two queries that
  # are identical except one has an ancestor and the other doesn't.
  # The HR datastore makes that a useful special case.

  def __init__(self, subqueries):
    if not isinstance(subqueries, list):
      raise TypeError('subqueries must be a list; received %r' % subqueries)
    for subq in subqueries:
      if not isinstance(subq, Query):
        raise TypeError('Each subquery must be a Query instances; received  %r'
                        % subq)
    first_subquery = subqueries[0]
    kind = first_subquery.kind
    orders = first_subquery.orders
    if not kind:
      raise ValueError('Subquery kind cannot be missing')
    for subq in subqueries[1:]:
      if subq.kind != kind:
        raise ValueError('Subqueries must be for a common kind (%s != %s)' %
                         (subq.kind, kind))
      elif subq.orders != orders:
        raise ValueError('Subqueries must have the same order(s) (%s != %s)' %
                         (subq.orders, orders))
    # TODO: Ensure that app and namespace match, when we support them.
    self.__subqueries = subqueries
    self.__orders = orders
    self.ancestor = None  # Hack for map_query().

  @property
  def orders(self):
    return self.__orders

  @tasklets.tasklet
  def run_to_queue(self, queue, conn, options=None):
    """Run this query, putting entities into the given queue."""
    if options is None:
      # Default options.
      offset = None
      limit = None
      keys_only = None
    else:
      # Capture options we need to simulate.
      offset = options.offset
      limit = options.limit
      keys_only = options.keys_only

      # Cursors are supported for certain orders only.
      if (options.start_cursor or options.end_cursor or
          options.produce_cursors):
        names = set()
        if self.__orders is not None:
          names = self.__orders._get_prop_names()
        if '__key__' not in names:
          raise datastore_errors.BadArgumentError(
            '_MultiQuery with cursors requires __key__ order')

    # Decide if we need to modify the options passed to subqueries.
    # NOTE: It would seem we can sometimes let the datastore handle
    # the offset natively, but this would thwart the duplicate key
    # detection, so we always have to emulate the offset here.
    # We can set the limit we pass along to offset + limit though,
    # since that is the maximum number of results from a single
    # subquery we will ever have to consider.
    modifiers = {}
    if offset:
      modifiers['offset'] = None
      if limit is not None:
        modifiers['limit'] = min(_MAX_LIMIT, offset + limit)
    if keys_only and self.__orders is not None:
      modifiers['keys_only'] = None
    if modifiers:
      options = QueryOptions(config=options, **modifiers)

    if offset is None:
      offset = 0

    if limit is None:
      limit = _MAX_LIMIT

    if self.__orders is None:
      # Run the subqueries sequentially; there is no order to keep.
      keys_seen = set()
      for subq in self.__subqueries:
        if limit <= 0:
          break
        subit = tasklets.SerialQueueFuture('_MultiQuery.run_to_queue[ser]')
        subq.run_to_queue(subit, conn, options=options)
        while limit > 0:
          try:
            batch, index, result = yield subit.getq()
          except EOFError:
            break
          if keys_only:
            key = result
          else:
            key = result._key
          if key not in keys_seen:
            keys_seen.add(key)
            if offset > 0:
              offset -= 1
            else:
              limit -= 1
              queue.putq((None, None, result))
      queue.complete()
      return

    # This with-statement causes the adapter to set _orig_pb on all
    # entities it converts from protobuf.
    # TODO: Does this interact properly with the cache?
    with conn.adapter:
      # Start running all the sub-queries.
      todo = []  # List of (subit, dsquery) tuples.
      for subq in self.__subqueries:
        dsquery = subq._get_query(conn)
        subit = tasklets.SerialQueueFuture('_MultiQuery.run_to_queue[par]')
        subq.run_to_queue(subit, conn, options=options, dsquery=dsquery)
        todo.append((subit, dsquery))

      # Create a list of (first-entity, subquery-iterator) tuples.
      state = []  # List of _SubQueryIteratorState instances.
      for subit, dsquery in todo:
        try:
          thing = yield subit.getq()
        except EOFError:
          continue
        else:
          state.append(_SubQueryIteratorState(thing, subit, dsquery,
                                              self.__orders))

      # Now turn it into a sorted heap.  The heapq module claims that
      # calling heapify() is more efficient than calling heappush() for
      # each item.
      heapq.heapify(state)

      # Repeatedly yield the lowest entity from the state vector,
      # filtering duplicates.  This is essentially a multi-way merge
      # sort.  One would think it should be possible to filter
      # duplicates simply by dropping other entities already in the
      # state vector that are equal to the lowest entity, but because of
      # the weird sorting of repeated properties, we have to explicitly
      # keep a set of all keys, so we can remove later occurrences.
      # Note that entities will still be sorted correctly, within the
      # constraints given by the sort order.
      keys_seen = set()
      while state and limit > 0:
        item = heapq.heappop(state)
        batch = item.batch
        index = item.index
        entity = item.entity
        key = entity._key
        if key not in keys_seen:
          keys_seen.add(key)
          if offset > 0:
            offset -= 1
          else:
            limit -= 1
            if keys_only:
              queue.putq((batch, index, key))
            else:
              queue.putq((batch, index, entity))
        subit = item.iterator
        try:
          batch, index, entity = yield subit.getq()
        except EOFError:
          pass
        else:
          item.batch = batch
          item.index = index
          item.entity = entity
          heapq.heappush(state, item)
      queue.complete()

  # Datastore API using the default context.

  def iter(self, **q_options):
    return QueryIterator(self, **q_options)

  __iter__ = iter

  # TODO: Add fetch() etc.?


# Helper functions to convert between orders and orderings.  An order
# is a datastore_query.Order instance.  An ordering is a
# (property_name, direction) tuple.

def _order_to_ordering(order):
  pb = order._to_pb()
  return pb.property(), pb.direction()  # TODO: What about UTF-8?


def _orders_to_orderings(orders):
  if orders is None:
    return []
  if isinstance(orders, datastore_query.PropertyOrder):
    return [_order_to_ordering(orders)]
  if isinstance(orders, datastore_query.CompositeOrder):
    # TODO: What about UTF-8?
    return [(pb.property(), pb.direction()) for pb in orders._to_pbs()]
  raise ValueError('Bad order: %r' % (orders,))


def _ordering_to_order(ordering):
  name, direction = ordering
  return datastore_query.PropertyOrder(name, direction)


def _orderings_to_orders(orderings):
  orders = [_ordering_to_order(o) for o in orderings]
  if not orders:
    return None
  if len(orders) == 1:
    return orders[0]
  return datastore_query.CompositeOrder(orders)
