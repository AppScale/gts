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
           'CorrelationFilter',
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
           'apply_query',
           'inject_results',
          ]

import base64
import pickle
import collections

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


def _make_key_value_map(entity, property_names):
  """Extracts key values from the given entity.

  Args:
    entity: The entity_pb.EntityProto to extract values from.
    property_names: The names of the properties from which to extract values.

  Returns:
    A dict mapping property names to a lists of key values.
  """
  value_map = dict((name, []) for name in property_names)


  for prop in entity.property_list():
    if prop.name() in value_map:
      value_map[prop.name()].append(
          datastore_types.PropertyValueToKeyValue(prop.value()))


  if datastore_types.KEY_SPECIAL_PROPERTY in value_map:
    value_map[datastore_types.KEY_SPECIAL_PROPERTY] = [
        datastore_types.ReferenceToKeyValue(entity.key())]

  return value_map


class _PropertyComponent(_BaseComponent):
  """A component that operates on a specific set of properties."""

  def _get_prop_names(self):
    """Returns a set of property names used by the filter."""
    raise NotImplementedError


class FilterPredicate(_PropertyComponent):
  """An abstract base class for all query filters.

  All sub-classes must be immutable as these are often stored without creating a
  defensive copy.
  """

  def __call__(self, entity):
    """Applies the filter predicate to the given entity.

    Args:
      entity: the datastore_pb.EntityProto to test.

    Returns:
      True if the given entity matches the filter, False otherwise.
    """
    return self._apply(_make_key_value_map(entity, self._get_prop_names()))

  def _apply(self, key_value_map):
    """Apply the given component to the comparable value map.

    A filter matches a list of values if at least one value in the list
    matches the filter, for example:
      'prop: [1, 2]' matches both 'prop = 1' and 'prop = 2' but not 'prop = 3'

    Note: the values are actually represented as tuples whose first item
    encodes the type; see datastore_types.PropertyValueToKeyValue().

    Args:
      key_value_map: A dict mapping property names to a list of
        comparable values.

    Return:
      A boolean indicating if the given map matches the filter.
    """
    raise NotImplementedError

  def _prune(self, key_value_map):
    """Removes values from the given map that do not match the filter.

    When doing a scan in the datastore, only index values that match the filters
    are seen. When multiple values that point to the same entity are seen, the
    entity only appears where the first value is found. This function removes
    all values that don't match the query so that the first value in the map
    is the same one the datastore would see first.

    Args:
      key_value_map: the comparable value map from which to remove
        values. Does not need to contain values for all filtered properties.

    Returns:
      A value that evaluates to False if every value in a single list was
      completely removed. This effectively applies the filter but is less
      efficient than _apply().
    """
    raise NotImplementedError

  def _to_pb(self):
    """Internal only function to generate a pb."""
    raise NotImplementedError(
        'This filter only supports in memory operations (%r)' % self)

  def _to_pbs(self):
    """Internal only function to generate a list of pbs."""
    return [self._to_pb()]


class _SinglePropertyFilter(FilterPredicate):
  """Base class for a filter that operates on a single property."""

  def _get_prop_name(self):
    """Returns the name of the property being filtered."""
    raise NotImplementedError

  def _apply_to_value(self, value):
    """Apply the filter to the given value.

    Args:
      value: The comparable value to check.

    Returns:
      A boolean indicating if the given value matches the filter.
    """
    raise NotImplementedError

  def _get_prop_names(self):
    return set([self._get_prop_name()])

  def _apply(self, value_map):
    for other_value in value_map[self._get_prop_name()]:
      if self._apply_to_value(other_value):
        return True
    return False

  def _prune(self, value_map):




    if self._get_prop_name() not in value_map:
      return True
    values = [value for value in value_map[self._get_prop_name()]
              if self._apply_to_value(value)]
    value_map[self._get_prop_name()] = values
    return bool(values)


class PropertyFilter(_SinglePropertyFilter):
  """An immutable filter predicate that constrains a single property."""

  _OPERATORS = {
      '<': datastore_pb.Query_Filter.LESS_THAN,
      '<=': datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL,
      '>': datastore_pb.Query_Filter.GREATER_THAN,
      '>=': datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL,
      '=': datastore_pb.Query_Filter.EQUAL,
      }

  _OPERATORS_INVERSE = dict((value, key)
                            for key, value in _OPERATORS.iteritems())

  _OPERATORS_TO_PYTHON_OPERATOR = {
      datastore_pb.Query_Filter.LESS_THAN: '<',
      datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL: '<=',
      datastore_pb.Query_Filter.GREATER_THAN: '>',
      datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL: '>=',
      datastore_pb.Query_Filter.EQUAL: '==',
      }

  _INEQUALITY_OPERATORS = frozenset(['<', '<=', '>', '>='])

  _INEQUALITY_OPERATORS_ENUM = frozenset([
      datastore_pb.Query_Filter.LESS_THAN,
      datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL,
      datastore_pb.Query_Filter.GREATER_THAN,
      datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL,
      ])

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
    self._filter = datastore_pb.Query_Filter()
    self._filter.set_op(self._OPERATORS[op])
    self._filter.add_property().CopyFrom(value)

  @property
  def op(self):
    raw_op = self._filter.op()
    return self._OPERATORS_INVERSE.get(raw_op, str(raw_op))

  @property
  def value(self):

    return self._filter.property(0)

  def __repr__(self):
    prop = self.value
    name = prop.name()
    value = datastore_types.FromPropertyPb(prop)
    return '%s(%r, <%r, %r>)' % (self.__class__.__name__, self.op, name, value)

  def _get_prop_name(self):
    return self._filter.property(0).name()

  def _apply_to_value(self, value):
    if not hasattr(self, '_cmp_value'):
      self._cmp_value = datastore_types.PropertyValueToKeyValue(
          self._filter.property(0).value())
      self._condition = ('value %s self._cmp_value' %
                         self._OPERATORS_TO_PYTHON_OPERATOR[self._filter.op()])
    return eval(self._condition)

  def _has_inequality(self):
    """Returns True if the filter predicate contains inequalities filters."""
    return self._filter.op() in self._INEQUALITY_OPERATORS_ENUM

  @classmethod
  def _from_pb(cls, filter_pb):

    self = cls.__new__(cls)
    self._filter = filter_pb
    return self

  def _to_pb(self):
    """Returns the internal only pb representation."""
    return self._filter

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of datastore_query.PropertyFilter is unsupported.')

  def __eq__(self, other):


    if self.__class__ is not other.__class__:
      if other.__class__ is _PropertyRangeFilter:
        return [self._filter] == other._to_pbs()
      return NotImplemented
    return self._filter == other._filter


class _PropertyRangeFilter(_SinglePropertyFilter):
  """A filter predicate that represents a range of values.

  Since we allow multi-valued properties there is a large difference between
  "x > 0 AND x < 1" and "0 < x < 1." An entity with x = [-1, 2] will match the
  first but not the second.

  Since the datastore only allows a single inequality filter, multiple
  in-equality filters are merged into a single range filter in the
  datastore (unlike equality filters). This class is used by
  datastore_query.CompositeFilter to implement the same logic.
  """

  _start_key_value = None
  _end_key_value = None

  @datastore_rpc._positional(1)
  def __init__(self, start=None, start_incl=True, end=None, end_incl=True):
    """Constructs a range filter using start and end properties.

    Args:
      start: A entity_pb.Property to use as a lower bound or None to indicate
        no lower bound.
      start_incl: A boolean that indicates if the lower bound is inclusive.
      end: A entity_pb.Property to use as an upper bound or None to indicate
        no upper bound.
      end_incl: A boolean that indicates if the upper bound is inclusive.
    """
    if start is not None and not isinstance(start, entity_pb.Property):
      raise datastore_errors.BadArgumentError(
          'start argument should be entity_pb.Property (%r)' % (start,))
    if end is not None and not isinstance(end, entity_pb.Property):
      raise datastore_errors.BadArgumentError(
          'start argument should be entity_pb.Property (%r)' % (end,))
    if start and end and start.name() != end.name():
      raise datastore_errors.BadArgumentError(
          'start and end arguments must be on the same property (%s != %s)' %
          (start.name(), end.name()))
    if not start and not end:
      raise datastore_errors.BadArgumentError(
          'Unbounded ranges are not supported.')

    super(_PropertyRangeFilter, self).__init__()
    self._start = start
    self._start_incl = start_incl
    self._end = end
    self._end_incl = end_incl

  @classmethod
  def from_property_filter(cls, prop_filter):
    op = prop_filter._filter.op()
    if op == datastore_pb.Query_Filter.GREATER_THAN:
      return cls(start=prop_filter._filter.property(0), start_incl=False)
    elif op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
      return cls(start=prop_filter._filter.property(0))
    elif op == datastore_pb.Query_Filter.LESS_THAN:
      return cls(end=prop_filter._filter.property(0), end_incl=False)
    elif op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
      return cls(end=prop_filter._filter.property(0))
    else:
      raise datastore_errors.BadArgumentError(
          'Unsupported operator (%s)' % (op,))

  def intersect(self, other):
    """Returns a filter representing the intersection of self and other."""
    if isinstance(other, PropertyFilter):
      other = self.from_property_filter(other)
    elif not isinstance(other, _PropertyRangeFilter):
      raise datastore_errors.BadArgumentError(
          'other argument should be a _PropertyRangeFilter (%r)' % (other,))

    if other._get_prop_name() != self._get_prop_name():
      raise datastore_errors.BadArgumentError(
          'other argument must be on the same property (%s != %s)' %
          (other._get_prop_name(), self._get_prop_name()))

    start_source = None
    if other._start:
      if self._start:
        result = cmp(self._get_start_key_value(), other._get_start_key_value())
        if result == 0:
          result = cmp(other._start_incl, self._start_incl)
        if result > 0:
          start_source = self
        elif result < 0:
          start_source = other
      else:
        start_source = other
    elif self._start:
      start_source = self

    end_source = None
    if other._end:
      if self._end:
        result = cmp(self._get_end_key_value(), other._get_end_key_value())
        if result == 0:
          result = cmp(self._end_incl, other._end_incl)
        if result < 0:
          end_source = self
        elif result > 0:
          end_source = other
      else:
        end_source = other
    elif self._end:
      end_source = self

    if start_source:
      if end_source in (start_source, None):
        return start_source

      result = _PropertyRangeFilter(start=start_source._start,
                                    start_incl=start_source._start_incl,
                                    end=end_source._end,
                                    end_incl=end_source._end_incl)

      result._start_key_value = start_source._start_key_value
      result._end_key_value = end_source._end_key_value
      return result
    else:
      return end_source or self

  def _get_start_key_value(self):
    if self._start_key_value is None:
      self._start_key_value = datastore_types.PropertyValueToKeyValue(
          self._start.value())
    return self._start_key_value

  def _get_end_key_value(self):
    if self._end_key_value is None:
      self._end_key_value = datastore_types.PropertyValueToKeyValue(
          self._end.value())
    return self._end_key_value

  def _apply_to_value(self, value):
    """Apply the filter to the given value.

    Args:
      value: The comparable value to check.

    Returns:
      A boolean indicating if the given value matches the filter.
    """
    if self._start:
      result = cmp(self._get_start_key_value(), value)
      if result > 0 or (result == 0 and not self._start_incl):
        return False

    if self._end:
      result = cmp(self._get_end_key_value(), value)
      if result < 0 or (result == 0 and not self._end_incl):
        return False

    return True

  def _get_prop_name(self):
    if self._start:
      return self._start.name()
    if self._end:
      return self._end.name()
    assert False

  def _to_pbs(self):
    pbs = []
    if self._start:
      if self._start_incl:
        op = datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL
      else:
        op = datastore_pb.Query_Filter.GREATER_THAN
      pb = datastore_pb.Query_Filter()
      pb.set_op(op)
      pb.add_property().CopyFrom(self._start)
      pbs.append(pb)

    if self._end:
      if self._end_incl:
        op = datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL
      else:
        op = datastore_pb.Query_Filter.LESS_THAN
      pb = datastore_pb.Query_Filter()
      pb.set_op(op)
      pb.add_property().CopyFrom(self._end)
      pbs.append(pb)

    return pbs

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of %r is unsupported.' % self)

  def __eq__(self, other):


    if self.__class__ is not other.__class__:
      return NotImplemented
    return (self._start == other._start and
            self._end == other._end and
            (self._start_incl == other._start_incl or self._start is None) and
            (self._end_incl == other._end_incl or self._end is None))


class _PropertyExistsFilter(FilterPredicate):
  """A FilterPredicate that matches entities containing specific properties.

  Only works as an in-memory filter. Used internally to filter out entities
  that don't have all properties in a given Order.
  """

  def __init__(self, names):
    super(_PropertyExistsFilter, self).__init__()
    self._names = frozenset(names)

  def _apply(self, value_map):
    for name in self._names:
      if not value_map.get(name):
        return False
    return True

  def _get_prop_names(self):
    return self._names

  def _prune(self, _):

    raise NotImplementedError

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of %r is unsupported.' % self)


class CorrelationFilter(FilterPredicate):
  """A filter that isolates correlated values and applies a sub-filter on them.

  This filter assumes that every property used by the sub-filter should be
  grouped before being passed to the sub-filter. The default grouping puts
  each value in its own group. Consider:
    e = {a: [1, 2], b: [2, 1, 3], c: 4}

  A correlation filter with a sub-filter that operates on (a, b) will be tested
  against the following 3 sets of values:
    {a: 1, b: 2}
    {a: 2, b: 1}
    {b: 3}

  In this case CorrelationFilter('a = 2 AND b = 2') won't match this entity but
  CorrelationFilter('a = 2 AND b = 1') will. To apply an uncorrelated filter on
  c, the filter must be applied in parallel to the correlation filter. For
  example:
    CompositeFilter(AND, [CorrelationFilter('a = 2 AND b = 1'), 'c = 3'])

  If 'c = 3' was included in the correlation filter, c would be grouped as well.
  This would result in the following values:
    {a: 1, b: 2, c: 3}
    {a: 2, b: 1}
    {b: 3}

  If any set of correlated values match the sub-filter then the entity matches
  the correlation filter.
  """

  def __init__(self, subfilter):
    """Constructor.

    Args:
      subfilter: A FilterPredicate to apply to the correlated values
    """
    self._subfilter = subfilter

  @property
  def subfilter(self):
    return self._subfilter

  def __repr__(self):
    return '%s(%r)' % (self.__class__.__name__, self.subfilter)

  def _apply(self, value_map):


    base_map = dict((prop, []) for prop in self._get_prop_names())


    value_maps = []
    for prop in base_map:

      grouped = self._group_values(prop, value_map[prop])

      while len(value_maps) < len(grouped):
        value_maps.append(base_map.copy())

      for value, map in zip(grouped, value_maps):
        map[prop] = value

    return self._apply_correlated(value_maps)

  def _apply_correlated(self, value_maps):
    """Applies sub-filter to the correlated value maps.

    The default implementation matches when any value_map in value_maps
    matches the sub-filter.

    Args:
      value_maps: A list of correlated value_maps.
    Returns:
      True if any the entity matches the correlation filter.
    """

    for map in value_maps:
      if self._subfilter._apply(map):
        return True
    return False

  def _group_values(self, prop, values):
    """A function that groups the given values.

    Override this function to introduce custom grouping logic. The default
    implementation assumes each value belongs in its own group.

    Args:
      prop: The name of the property who's values are being grouped.
      values: A list of opaque values.

   Returns:
      A list of lists of grouped values.
    """
    return [[value] for value in values]

  def _get_prop_names(self):
    return self._subfilter._get_prop_names()


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
      raise datastore_errors.BadArgumentError('unknown operator (%s)' % (op,))
    if not filters or not isinstance(filters, (list, tuple)):
      raise datastore_errors.BadArgumentError(
          'filters argument should be a non-empty list (%r)' % (filters,))

    super(CompositeFilter, self).__init__()
    self._op = op
    flattened = []


    for f in filters:
      if isinstance(f, CompositeFilter) and f._op == self._op:


        flattened.extend(f._filters)
      elif isinstance(f, FilterPredicate):
        flattened.append(f)
      else:
        raise datastore_errors.BadArgumentError(
            'filters argument must be a list of FilterPredicates, found (%r)' %
            (f,))


    if op == self.AND:
      filters = flattened
      flattened = []
      ineq_map = {}

      for f in filters:
        if (isinstance(f, _PropertyRangeFilter) or
            (isinstance(f, PropertyFilter) and f._has_inequality())):
          name = f._get_prop_name()
          index = ineq_map.get(name)
          if index is not None:
            range_filter = flattened[index]
            flattened[index] = range_filter.intersect(f)
          else:
            if isinstance(f, PropertyFilter):
              range_filter = _PropertyRangeFilter.from_property_filter(f)
            else:
              range_filter = f
            ineq_map[name] = len(flattened)
            flattened.append(range_filter)
        else:
          flattened.append(f)

    self._filters = tuple(flattened)

  @property
  def op(self):
    return self._op

  @property
  def filters(self):
    return self._filters

  def __repr__(self):
    op = self.op
    if op == self.AND:
      op = 'AND'
    else:
      op = str(op)
    return '%s(%s, %r)' % (self.__class__.__name__, op, list(self.filters))

  def _get_prop_names(self):
    names = set()
    for f in self._filters:
      names |= f._get_prop_names()
    return names

  def _apply(self, value_map):
    if self._op == self.AND:
      for f in self._filters:
        if not f._apply(value_map):
          return False
      return True
    raise NotImplementedError

  def _prune(self, value_map):



    if self._op == self.AND:











      matches = collections.defaultdict(set)
      for f in self._filters:
        props = f._get_prop_names()
        local_value_map = dict((k, v) for k, v in value_map.iteritems()
                               if k in props)

        if not f._prune(local_value_map):
          return False


        for (prop, values) in local_value_map.iteritems():
          matches[prop].update(values)


      for prop, value_set in matches.iteritems():

        value_map[prop] = sorted(value_set)
      return True
    raise NotImplementedError

  def _to_pbs(self):
    """Returns the internal only pb representation."""



    pbs = []
    for f in self._filters:
      pbs.extend(f._to_pbs())
    return pbs

  def __eq__(self, other):
    if self.__class__ is other.__class__:
      return super(CompositeFilter, self).__eq__(other)


    if len(self._filters) == 1:
      result = self._filters[0].__eq__(other)
      if result is NotImplemented and hasattr(other, '__eq__'):
        return other.__eq__(self._filters[0])
      return result
    return NotImplemented


class _IgnoreFilter(_SinglePropertyFilter):
  """A filter that removes all entities with the given keys."""

  def __init__(self, key_value_set):
    super(_IgnoreFilter, self).__init__()
    self._keys = key_value_set

  def _get_prop_name(self):
    return datastore_types.KEY_SPECIAL_PROPERTY

  def _apply_to_value(self, value):
    return value not in self._keys


class _DedupingFilter(_IgnoreFilter):
  """A filter that removes duplicate keys."""

  def __init__(self, key_value_set=None):
    super(_DedupingFilter, self).__init__(key_value_set or set())

  def _apply_to_value(self, value):
    if super(_DedupingFilter, self)._apply_to_value(value):
      self._keys.add(value)
      return True
    return False


class Order(_PropertyComponent):
  """A base class that represents a sort order on a query.

  All sub-classes must be immutable as these are often stored without creating a
  defensive copying.

  This class can be used as either the cmp or key arg in sorted() or
  list.sort(). To provide a stable ordering a trailing key ascending order is
  always used.
  """

  def reversed(self):
    """Constructs an order representing the reverse of the current order.

    Returns:
      A new order representing the reverse direction.
    """
    raise NotImplementedError

  def _key(self, lhs_value_map):
    """Creates a key for the given value map."""
    raise NotImplementedError

  def _cmp(self, lhs_value_map, rhs_value_map):
    """Compares the given value maps."""
    raise NotImplementedError

  def _to_pb(self):
    """Internal only function to generate a filter pb."""
    raise NotImplementedError

  def key_for_filter(self, filter_predicate):
    if filter_predicate:
      return lambda x: self.key(x, filter_predicate)
    return self.key

  def cmp_for_filter(self, filter_predicate):
    if filter_predicate:
      return lambda x, y: self.cmp(x, y, filter_predicate)
    return self.cmp

  def key(self, entity, filter_predicate=None):
    """Constructs a "key" value for the given entity based on the current order.

    This function can be used as the key argument for list.sort() and sorted().

    Args:
      entity: The entity_pb.EntityProto to convert
      filter_predicate: A FilterPredicate used to prune values before comparing
        entities or None.

    Returns:
      A key value that identifies the position of the entity when sorted by
      the current order.
    """
    names = self._get_prop_names()
    names.add(datastore_types.KEY_SPECIAL_PROPERTY)
    if filter_predicate is not None:
      names |= filter_predicate._get_prop_names()

    value_map = _make_key_value_map(entity, names)
    if filter_predicate is not None:
      filter_predicate._prune(value_map)
    return (self._key(value_map),
            value_map[datastore_types.KEY_SPECIAL_PROPERTY])

  def cmp(self, lhs, rhs, filter_predicate=None):
    """Compares the given values taking into account any filters.

    This function can be used as the cmp argument for list.sort() and sorted().

    This function is slightly more efficient that Order.key when comparing two
    entities, however it is much less efficient when sorting a list of entities.

    Args:
      lhs: An entity_pb.EntityProto
      rhs: An entity_pb.EntityProto
      filter_predicate: A FilterPredicate used to prune values before comparing
        entities or None.

    Returns:
      An integer <, = or > 0 representing the operator that goes in between lhs
      and rhs that to create a true statement.

    """
    names = self._get_prop_names()
    if filter_predicate is not None:
      names |= filter_predicate._get_prop_names()

    lhs_value_map = _make_key_value_map(lhs, names)
    rhs_value_map = _make_key_value_map(rhs, names)
    if filter_predicate is not None:
      filter_predicate._prune(lhs_value_map)
      filter_predicate._prune(rhs_value_map)
    result = self._cmp(lhs_value_map, rhs_value_map)
    if result:
      return result




    lhs_key = (lhs_value_map.get(datastore_types.KEY_SPECIAL_PROPERTY) or
               datastore_types.ReferenceToKeyValue(lhs.key()))
    rhs_key = (rhs_value_map.get(datastore_types.KEY_SPECIAL_PROPERTY) or
               datastore_types.ReferenceToKeyValue(rhs.key()))

    return cmp(lhs_key, rhs_key)


class _ReverseOrder(_BaseComponent):
  """Reverses the comparison for the given object."""

  def __init__(self, obj):
    """Constructor for _ReverseOrder.

    Args:
      obj: Any comparable and hashable object.
    """
    super(_ReverseOrder, self).__init__()
    self._obj = obj

  def __hash__(self):
    return hash(self._obj)

  def __cmp__(self, other):
    assert self.__class__ == other.__class__, (
        'A datastore_query._ReverseOrder object can only be compared to '
        'an object of the same type.')
    return -cmp(self._obj, other._obj)


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

  @property
  def prop(self):
    return self.__order.property()

  @property
  def direction(self):
    return self.__order.direction()

  def __repr__(self):
    name = self.prop
    direction = self.direction
    extra = ''
    if direction == self.DESCENDING:
      extra = ', DESCENDING'
    name = repr(name).encode('utf-8')[1:-1]
    return '%s(<%s>%s)' % (self.__class__.__name__, name, extra)

  def reversed(self):
    if self.__order.direction() == self.ASCENDING:
      return PropertyOrder(self.__order.property().decode('utf-8'),
                           self.DESCENDING)
    else:
      return PropertyOrder(self.__order.property().decode('utf-8'),
                           self.ASCENDING)

  def _get_prop_names(self):
    return set([self.__order.property()])

  def _key(self, lhs_value_map):
    lhs_values = lhs_value_map[self.__order.property()]
    if not lhs_values:
      raise datastore_errors.BadArgumentError(
          'Missing value for property (%s)' % self.__order.property())

    if self.__order.direction() == self.ASCENDING:
      return min(lhs_values)
    else:
      return _ReverseOrder(max(lhs_values))

  def _cmp(self, lhs_value_map, rhs_value_map):
    lhs_values = lhs_value_map[self.__order.property()]
    rhs_values = rhs_value_map[self.__order.property()]

    if not lhs_values:
      raise datastore_errors.BadArgumentError(
          'LHS missing value for property (%s)' % self.__order.property())

    if not rhs_values:
      raise datastore_errors.BadArgumentError(
          'RHS missing value for property (%s)' % self.__order.property())

    if self.__order.direction() == self.ASCENDING:
      return cmp(min(lhs_values), min(rhs_values))
    else:
      return cmp(max(rhs_values), max(lhs_values))

  @classmethod
  def _from_pb(cls, order_pb):

    self = cls.__new__(cls)
    self.__order = order_pb
    return self

  def _to_pb(self):
    """Returns the internal only pb representation."""
    return self.__order

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of datastore_query.PropertyOrder is unsupported.')


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
    if not isinstance(orders, (list, tuple)):
      raise datastore_errors.BadArgumentError(
          'orders argument should be list or tuple (%r)' % (orders,))

    super(CompositeOrder, self).__init__()
    flattened = []
    for order in orders:
      if isinstance(order, CompositeOrder):
        flattened.extend(order._orders)
      elif isinstance(order, Order):
        flattened.append(order)
      else:
        raise datastore_errors.BadArgumentError(
            'orders argument should only contain Order (%r)' % (order,))
    self._orders = tuple(flattened)

  @property
  def orders(self):
    return self._orders

  def __repr__(self):
    return '%s(%r)' % (self.__class__.__name__, list(self.orders))

  def reversed(self):
    return CompositeOrder([order.reversed() for order in self._orders])

  def _get_prop_names(self):
    names = set()
    for order in self._orders:
      names |= order._get_prop_names()
    return names

  def _key(self, lhs_value_map):
    result = []
    for order in self._orders:
      result.append(order._key(lhs_value_map))
    return tuple(result)

  def _cmp(self, lhs_value_map, rhs_value_map):
    for order in self._orders:
      result = order._cmp(lhs_value_map, rhs_value_map)
      if result != 0:
        return result
    return 0

  def size(self):
    """Returns the number of sub-orders the instance contains."""
    return len(self._orders)

  def _to_pbs(self):
    """Returns an ordered list of internal only pb representations."""
    return [order._to_pb() for order in self._orders]

  def __eq__(self, other):
    if self.__class__ is other.__class__:
      return super(CompositeOrder, self).__eq__(other)


    if len(self._orders) == 1:
      result = self._orders[0].__eq__(other)
      if result is NotImplemented and hasattr(other, '__eq__'):
        return other.__eq__(self._orders[0])
      return result

    return NotImplemented


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

  def __repr__(self):
    arg = self.to_websafe_string()
    if arg:
      arg = '<%s>' % arg
    return '%s(%s)' % (self.__class__.__name__, arg)

  def reversed(self):
    """Creates a cursor for use in a query with a reversed sort order."""
    for pos in self.__compiled_cursor.position_list():
      if pos.has_start_key():
        raise datastore_errors.BadRequestError('Cursor cannot be reversed.')

    rev_pb = datastore_pb.CompiledCursor()
    rev_pb.CopyFrom(self.__compiled_cursor)
    for pos in rev_pb.position_list():
      pos.set_start_inclusive(not pos.start_inclusive())
    return Cursor(_cursor_pb=rev_pb)

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
          'Invalid cursor (%r). Details: %s' % (cursor, e))
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


class _QueryKeyFilter(_BaseComponent):
  """A class that implements the key filters available on a Query."""

  @datastore_rpc._positional(1)
  def __init__(self, app=None, namespace=None, kind=None, ancestor=None):
    """Constructs a _QueryKeyFilter.

    If app/namespace and ancestor are not defined, the app/namespace set in the
    environment is used.

    Args:
      app: a string representing the required app id or None.
      namespace: a string representing the required namespace or None.
      kind: a string representing the required kind or None.
      ancestor: a entity_pb.Reference representing the required ancestor or
        None.

    Raises:
      datastore_erros.BadArgumentError if app and ancestor.app() do not match or
        an unexpected type is passed in for any argument.
    """
    if kind is not None:
      datastore_types.ValidateString(
          kind, 'kind', datastore_errors.BadArgumentError)

    if ancestor is not None:
      if not isinstance(ancestor, entity_pb.Reference):
        raise datastore_errors.BadArgumentError(
            'ancestor argument should be entity_pb.Reference (%r)' %
            (ancestor,))
      if app is None:
        app = ancestor.app()
      elif app != ancestor.app():
        raise datastore_errors.BadArgumentError(
            'ancestor argument should match app ("%r" != "%r")' %
            (ancestor.app(), app))

      if namespace is None:
        namespace = ancestor.name_space()
      elif namespace != ancestor.name_space():
        raise datastore_errors.BadArgumentError(
            'ancestor argument should match namespace ("%r" != "%r")' %
            (ancestor.name_space(), namespace))

      pb = entity_pb.Reference()
      pb.CopyFrom(ancestor)
      ancestor = pb
      self.__ancestor = ancestor
      self.__path = ancestor.path().element_list()
    else:
      self.__ancestor = None
      self.__path = None

    super(_QueryKeyFilter, self).__init__()
    self.__app = datastore_types.ResolveAppId(app).encode('utf-8')
    self.__namespace = (
        datastore_types.ResolveNamespace(namespace).encode('utf-8'))
    self.__kind = kind and kind.encode('utf-8')

  @property
  def app(self):
    return self.__app

  @property
  def namespace(self):
    return self.__namespace

  @property
  def kind(self):
    return self.__kind

  @property
  def ancestor(self):

    return self.__ancestor

  def __call__(self, entity_or_reference):
    """Apply the filter.

    Accepts either an entity or a reference to avoid the need to extract keys
    from entities when we have a list of entities (which is a common case).

    Args:
      entity_or_reference: Either an entity_pb.EntityProto or
        entity_pb.Reference.
    """
    if isinstance(entity_or_reference, entity_pb.Reference):
      key = entity_or_reference
    elif isinstance(entity_or_reference, entity_pb.EntityProto):
      key = entity_or_reference.key()
    else:
      raise datastore_errors.BadArgumentError(
          'entity_or_reference argument must be an entity_pb.EntityProto ' +
          'or entity_pb.Reference (%r)' % (entity_or_reference))
    return (key.app() == self.__app and
            key.name_space() == self.__namespace and
            (not self.__kind or
             key.path().element_list()[-1].type() == self.__kind) and
            (not self.__path or
             key.path().element_list()[0:len(self.__path)] == self.__path))

  def _to_pb(self):
    pb = datastore_pb.Query()

    pb.set_app(self.__app)
    datastore_types.SetNamespace(pb, self.__namespace)
    if self.__kind is not None:
      pb.set_kind(self.__kind)
    if self.__ancestor:
      ancestor = pb.mutable_ancestor()
      ancestor.CopyFrom(self.__ancestor)

    return pb


class _BaseQuery(_BaseComponent):
  """A base class for query implementations."""

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
    raise NotImplementedError

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of %r is unsupported.' % self)


class Query(_BaseQuery):
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
      ancestor: Optional ancestor to query, an entity_pb.Reference.
      filter_predicate: Optional FilterPredicate by which to restrict the query.
      order: Optional Order in which to return results.

    Raises:
      datastore_errors.BadArgumentError if any argument is invalid.
    """
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

    self._key_filter = _QueryKeyFilter(app=app, namespace=namespace, kind=kind,
                                       ancestor=ancestor)
    self._order = order
    self._filter_predicate = filter_predicate

  @property
  def app(self):
    return self._key_filter.app

  @property
  def namespace(self):
    return self._key_filter.namespace

  @property
  def kind(self):
    return self._key_filter.kind

  @property
  def ancestor(self):
    return self._key_filter.ancestor

  @property
  def filter_predicate(self):
    return self._filter_predicate

  @property
  def order(self):
    return self._order

  def __repr__(self):
    args = []
    args.append('app=%r' % self.app)
    ns = self.namespace
    if ns:
      args.append('namespace=%r' % ns)
    kind = self.kind
    if kind is not None:
      args.append('kind=%r' % kind)
    ancestor = self.ancestor
    if ancestor is not None:
      websafe = base64.urlsafe_b64encode(ancestor.Encode())
      args.append('ancestor=<%s>' % websafe)
    filter_predicate = self.filter_predicate
    if filter_predicate is not None:
      args.append('filter_predicate=%r' % filter_predicate)
    order = self.order
    if order is not None:
      args.append('order=%r' % order)
    return '%s(%s)' % (self.__class__.__name__, ', '.join(args))

  def run_async(self, conn, query_options=None):
    if not isinstance(conn, datastore_rpc.BaseConnection):
      raise datastore_errors.BadArgumentError(
          'conn should be a datastore_rpc.BaseConnection (%r)' % (conn,))

    if not QueryOptions.is_configuration(query_options):


      query_options = QueryOptions(config=query_options)

    start_cursor = query_options.start_cursor
    if not start_cursor and query_options.produce_cursors:
      start_cursor = Cursor()

    batch0 = Batch(query_options, self, conn, start_cursor=start_cursor)
    req = self._to_pb(conn, query_options)
    return batch0._make_query_result_rpc_call('RunQuery', query_options, req)

  @classmethod
  def _from_pb(cls, query_pb):
    filter_predicate = None
    if query_pb.filter_size() > 0:
      filter_predicate = CompositeFilter(
          CompositeFilter.AND,
          [PropertyFilter._from_pb(filter_pb)
           for filter_pb in query_pb.filter_list()])

    order = None
    if query_pb.order_size() > 0:
      order = CompositeOrder([PropertyOrder._from_pb(order_pb)
                              for order_pb in query_pb.order_list()])

    ancestor = query_pb.has_ancestor() and query_pb.ancestor() or None
    kind = query_pb.has_kind() and query_pb.kind().decode('utf-8') or None
    return Query(app=query_pb.app().decode('utf-8'),
                 namespace=query_pb.name_space().decode('utf-8'),
                 kind=kind,
                 ancestor=ancestor,
                 filter_predicate=filter_predicate,
                 order=order)

  def _to_pb(self, conn, query_options):
    """Returns the internal only pb representation."""
    pb = self._key_filter._to_pb()


    if self._filter_predicate:
      for f in self._filter_predicate._to_pbs():
        pb.add_filter().CopyFrom(f)


    if self._order:
      for order in self._order._to_pbs():
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


    if ((query_options.hint == QueryOptions.ORDER_FIRST and pb.order_size()) or
        (query_options.hint == QueryOptions.ANCESTOR_FIRST and
         pb.has_ancestor()) or
        (query_options.hint == QueryOptions.FILTER_FIRST and
         pb.filter_size() > 0)):
      pb.set_hint(query_options.hint)


    conn._set_request_read_policy(pb, query_options)
    conn._set_request_transaction(pb)

    return pb


def apply_query(query, entities):
  """Performs the given query on a set of in-memory entities.

  This function can perform queries impossible in the datastore (e.g a query
  with multiple inequality filters on different properties) because all
  operations are done in memory. For queries that can also be executed on the
  the datastore, the results produced by this function may not use the same
  implicit ordering as the datastore. To ensure compatibility, explicit
  ordering must be used (e.g. 'ORDER BY ineq_prop, ..., __key__').

  Order by __key__ should always be used when a consistent result is desired
  (unless there is a sort order on another globally unique property).

  Args:
    query: a datastore_query.Query to apply
    entities: a list of entity_pb.EntityProto on which to apply the query.

  Returns:
    A list of entity_pb.EntityProto contain the results of the query.
  """
  if not isinstance(query, Query):
    raise datastore_errors.BadArgumentError(
        "query argument must be a datastore_query.Query (%r)" % (query,))

  if not isinstance(entities, list):
    raise datastore_errors.BadArgumentError(
        "entities argument must be a list (%r)" % (entities,))

  filtered_entities = filter(query._key_filter, entities)

  if not query._order:




    if query._filter_predicate:
      return filter(query._filter_predicate, filtered_entities)
    return filtered_entities





  names = query._order._get_prop_names()
  if query._filter_predicate:
    names |= query._filter_predicate._get_prop_names()


  exists_filter = _PropertyExistsFilter(names)

  value_maps = []
  for entity in filtered_entities:
    value_map = _make_key_value_map(entity, names)



    if exists_filter._apply(value_map) and (
        not query._filter_predicate or
        query._filter_predicate._prune(value_map)):
      value_map['__entity__'] = entity
      value_maps.append(value_map)

  value_maps.sort(query._order._cmp)
  return [value_map['__entity__'] for value_map in value_maps]


class _AugmentedQuery(_BaseQuery):
  """A query that combines a datastore query with in-memory filters/results."""

  @datastore_rpc._positional(2)
  def __init__(self, query, in_memory_results=None, in_memory_filter=None,
               max_filtered_count=None):
    """Constructor for _AugmentedQuery.

    Do not call directly. Use the utility functions instead (e.g.
    datastore_query.inject_results)

    Args:
      query: A datastore_query.Query object to augment.
      in_memory_results: a list of pre- sorted and filtered result to add to the
        stream of datastore results or None .
      in_memory_filter: a set of in-memory filters to apply to the datastore
        results or None.
      max_filtered_count: the maximum number of datastore entities that will be
        filtered out by in_memory_filter if known.
    """
    if not isinstance(query, Query):
      raise datastore_errors.BadArgumentError(
          'query argument should be datastore_query.Query (%r)' % (query,))
    if (in_memory_filter is not None and
        not isinstance(in_memory_filter, FilterPredicate)):
      raise datastore_errors.BadArgumentError(
          'in_memory_filter argument should be ' +
          'datastore_query.FilterPredicate (%r)' % (in_memory_filter,))
    if (in_memory_results is not None and
        not isinstance(in_memory_results, list)):
      raise datastore_errors.BadArgumentError(
          'in_memory_results argument should be a list of' +
          'datastore_pv.EntityProto (%r)' % (in_memory_results,))
    datastore_types.ValidateInteger(max_filtered_count,
                                    'max_filtered_count',
                                    empty_ok=True,
                                    zero_ok=True)
    self._query = query
    self._max_filtered_count = max_filtered_count
    self._in_memory_filter = in_memory_filter
    self._in_memory_results = in_memory_results

  def run_async(self, conn, query_options=None):
    if not isinstance(conn, datastore_rpc.BaseConnection):
      raise datastore_errors.BadArgumentError(
          'conn should be a datastore_rpc.BaseConnection (%r)' % (conn,))

    if not QueryOptions.is_configuration(query_options):


      query_options = QueryOptions(config=query_options)

    if self._query._order:


      changes = {'keys_only': False}
    else:
      changes = {}

    if self._in_memory_filter or self._in_memory_results:



      in_memory_offset = query_options.offset
      in_memory_limit = query_options.limit

      if in_memory_limit is not None:
        if self._in_memory_filter is None:

          changes['limit'] = in_memory_limit
        elif self._max_filtered_count is not None:


          changes['limit'] = in_memory_limit + self._max_filtered_count
        else:

          changes['limit'] = None

      if in_memory_offset:

        changes['offset'] = None
        if changes.get('limit', None) is not None:
          changes['limit'] += in_memory_offset
      else:
        in_memory_offset = None
    else:
      in_memory_offset = None
      in_memory_limit = None

    req = self._query._to_pb(
        conn, QueryOptions(config=query_options, **changes))

    start_cursor = query_options.start_cursor
    if not start_cursor and query_options.produce_cursors:
      start_cursor = Cursor()

    batch0 = _AugmentedBatch(query_options, self, conn,
                            in_memory_offset=in_memory_offset,
                            in_memory_limit=in_memory_limit,
                            start_cursor=start_cursor)
    return batch0._make_query_result_rpc_call('RunQuery', query_options, req)


@datastore_rpc._positional(1)
def inject_results(query, updated_entities=None, deleted_keys=None):
  """Creates a query object that will inject changes into results.

  Args:
    query: The datastore_query.Query to augment
    updated_entities: A list of entity_pb.EntityProto's that have been updated
      and should take priority over any values returned by query.
    deleted_keys: A list of entity_pb.Reference's for entities that have been
      deleted and should be removed from query results.

  Returns:
    A datastore_query.AugmentedQuery if in memory filtering is requred,
  query otherwise.
  """
  if not isinstance(query, Query):
    raise datastore_errors.BadArgumentError(
        'query argument should be datastore_query.Query (%r)' % (query,))

  overriden_keys = set()

  if deleted_keys is not None:
    if not isinstance(deleted_keys, list):
      raise datastore_errors.BadArgumentError(
          'deleted_keys argument must be a list (%r)' % (deleted_keys,))
    deleted_keys = filter(query._key_filter, deleted_keys)
    for key in deleted_keys:
      overriden_keys.add(datastore_types.ReferenceToKeyValue(key))

  if updated_entities is not None:
    if not isinstance(updated_entities, list):
      raise datastore_errors.BadArgumentError(
          'updated_entities argument must be a list (%r)' % (updated_entities,))


    updated_entities = filter(query._key_filter, updated_entities)
    for entity in updated_entities:
      overriden_keys.add(datastore_types.ReferenceToKeyValue(entity.key()))

    updated_entities = apply_query(query, updated_entities)
  else:
    updated_entities = []

  if not overriden_keys:
    return query

  return _AugmentedQuery(query,
                         in_memory_filter=_IgnoreFilter(overriden_keys),
                         in_memory_results=updated_entities,
                         max_filtered_count=len(overriden_keys))


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

  @datastore_rpc._positional(4)
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
    self._conn = conn
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
    return self._skipped_results

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
    if not -self._skipped_results <= index <= len(self.__results):
      raise datastore_errors.BadArgumentError(
          'index argument must be in the inclusive range [%d, %d]' %
          (-self._skipped_results, len(self.__results)))

    if index == len(self.__results):
      return self.__end_cursor
    elif index == -self._skipped_results:
      return self.__start_cursor
    else:
      return self.__start_cursor.advance(index + self._skipped_results,
                                         self.__query, self._conn)

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

    fetch_options, next_batch = self._make_next_batch(fetch_options)
    req = self._to_pb(fetch_options)

    config = self.__query_options.merge(fetch_options)
    return next_batch._make_query_result_rpc_call(
        'Next', config, req)

  def _to_pb(self, fetch_options=None):
    req = datastore_pb.NextRequest()

    if FetchOptions.produce_cursors(fetch_options,
                                    self.__query_options,
                                    self._conn.config):
      req.set_compile(True)

    count = FetchOptions.batch_size(fetch_options,
                                    self.__query_options,
                                    self._conn.config)
    if count is not None:
      req.set_count(count)

    if fetch_options is not None and fetch_options.offset:
      req.set_offset(fetch_options.offset)

    req.mutable_cursor().CopyFrom(self.__datastore_cursor)
    self.__datastore_cursor = None
    return req

  def _extend(self, next_batch):
    """Combines the current batch with the next one. Called by batcher."""
    self.__datastore_cursor = next_batch.__datastore_cursor
    next_batch.__datastore_cursor = None
    self.__more_results = next_batch.__more_results
    self.__results.extend(next_batch.__results)
    self.__end_cursor = next_batch.__end_cursor
    self._skipped_results += next_batch._skipped_results

  def _make_query_result_rpc_call(self, name, config, req):
    """Makes either a RunQuery or Next call that will modify the instance.

    Args:
      name: A string, the name of the call to invoke.
      config: The datastore_rpc.Configuration to use for the call.
      req: The request to send with the call.

    Returns:
      A UserRPC object that can be used to fetch the result of the RPC.
    """
    return self._conn.make_rpc_call(config, name, req,
                                    datastore_pb.QueryResult(),
                                    self.__query_result_hook)

  def __query_result_hook(self, rpc):
    """Internal method used as get_result_hook for RunQuery/Next operation."""
    try:
      self._conn.check_rpc_success(rpc)
    except datastore_errors.NeedIndexError, exc:

      if isinstance(rpc.request, datastore_pb.Query):
        yaml = datastore_index.IndexYamlForQuery(
            *datastore_index.CompositeIndexForQuery(rpc.request)[1:-1])
        raise datastore_errors.NeedIndexError(
            str(exc) + '\nThe suggested index for this query is:\n' + yaml)
      raise
    query_result = rpc.response
    if query_result.has_compiled_query():
      self._compiled_query = query_result.compiled_query

    self.__keys_only = query_result.keys_only()
    self.__end_cursor = Cursor._from_query_result(query_result)
    self._skipped_results = query_result.skipped_results()

    if query_result.more_results():
      self.__datastore_cursor = query_result.cursor()
      self.__more_results = True
    else:
      self._end()

    self.__results = self._process_results(query_result.result_list())
    return self

  def _end(self):
    """Changes the internal state so that no more batches can be produced."""
    self.__datastore_cursor = None
    self.__more_results = False

  def _make_next_batch(self, fetch_options):
    """Creates the object to store the next batch.

    Args:
      fetch_options: The datastore_query.FetchOptions passed in by the user or
        None.

    Returns:
      A tuple containing the fetch options that should be used internally and
      the object that should be used to contain the next batch.
    """
    return fetch_options, Batch(self.__query_options, self.__query, self._conn,
                                start_cursor=self.__end_cursor,
                                _compiled_query=self._compiled_query)

  def _process_results(self, results):
    """Converts the datastore results into results returned to the user.

    Args:
      results: A list of entity_pb.EntityProto's returned by the datastore

    Returns:
      A list of results that should be returned to the user.
    """
    return [self._conn.adapter.pb_to_query_result(result, self.__keys_only)
            for result in results]

  def __getstate__(self):
    raise pickle.PicklingError(
        'Pickling of datastore_query.Batch is unsupported.')


class _AugmentedBatch(Batch):
  """A batch produced by a datastore_query._AugmentedQuery."""

  @datastore_rpc._positional(4)
  def __init__(self, query_options, augmented_query, conn,
               in_memory_offset=None, in_memory_limit=None,
               start_cursor=Cursor(), _compiled_query=None,
               next_index=0):
    """A Constructor for datastore_query._AugmentedBatch.

    Constructed by datastore_query._AugmentedQuery. Should not be called
    directly.
    """
    super(_AugmentedBatch, self).__init__(query_options, augmented_query._query,
                                          conn,
                                          start_cursor=start_cursor,
                                          _compiled_query=_compiled_query)
    self.__augmented_query = augmented_query
    self.__in_memory_offset = in_memory_offset
    self.__in_memory_limit = in_memory_limit
    self.__next_index = next_index

  @property
  def query(self):
    """The query the current batch came from."""
    return self.__augmented_query

  def cursor(self, index):
    raise NotImplementedError

  def _extend(self, next_batch):
    super(_AugmentedBatch, self)._extend(next_batch)
    self.__in_memory_limit = next_batch.__in_memory_limit
    self.__in_memory_offset = next_batch.__in_memory_offset
    self.__next_index = next_batch.__next_index

  def _process_results(self, results):

    in_memory_filter = self.__augmented_query._in_memory_filter
    if in_memory_filter:
      results = filter(in_memory_filter, results)


    in_memory_results = self.__augmented_query._in_memory_results
    if in_memory_results and self.__next_index < len(in_memory_results):

      original_query = super(_AugmentedBatch, self).query
      if original_query._order:

        if results:
          next_result = in_memory_results[self.__next_index]
          next_key = original_query._order.key(next_result)
          i = 0
          while i < len(results):
            result = results[i]
            result_key = original_query._order.key(result)
            while next_key <= result_key:
              results.insert(i, next_result)
              i += 1
              self.__next_index += 1
              if self.__next_index >= len(in_memory_results):
                break
              next_result = in_memory_results[self.__next_index]
              next_key = original_query._order.key(next_result)
            i += 1
      elif results or not super(_AugmentedBatch, self).more_results:

        results = in_memory_results + results
        self.__next_index = len(in_memory_results)


    if self.__in_memory_offset:
      assert not self._skipped_results
      offset = min(self.__in_memory_offset, len(results))
      if offset:
        self._skipped_results += offset
        self.__in_memory_offset -= offset
        results = results[offset:]

    if self.__in_memory_limit is not None:
      results = results[:self.__in_memory_limit]
      self.__in_memory_limit -= len(results)
      if self.__in_memory_limit <= 0:
        self._end()

    return super(_AugmentedBatch, self)._process_results(results)

  def _make_next_batch(self, fetch_options):
    in_memory_offset = FetchOptions.offset(fetch_options)
    if in_memory_offset and (self.__augmented_query._in_memory_filter or
                             self.__augmented_query._in_memory_results):
      fetch_options = FetchOptions(offset=0)
    else:
      in_memory_offset = None
    return (fetch_options,
            _AugmentedBatch(self.query_options, self.__augmented_query,
                            self._conn,
                            in_memory_offset=in_memory_offset,
                            in_memory_limit=self.__in_memory_limit,
                            start_cursor=self.end_cursor,
                            _compiled_query=self._compiled_query,
                            next_index=self.__next_index))


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


  ASYNC_ONLY = None
  AT_LEAST_OFFSET = 0
  AT_LEAST_ONE = object()

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
    return self.next_batch(self.AT_LEAST_ONE)

  def next_batch(self, min_batch_size):
    """Get the next batch.

    The batch returned by this function cannot be used to fetch the next batch
    (through Batch.next_batch()). Instead this function will always return None.
    To retrieve the next batch use .next() or .next_batch(N).

    This function may return a batch larger than min_to_fetch, but will never
    return smaller unless there are no more results.

    Special values can be used for min_batch_size:
      ASYNC_ONLY - Do not perform any synchrounous fetches from the datastore
        even if the this produces a batch with no results.
      AT_LEAST_OFFSET - Only pull enough results to satifiy the offset.
      AT_LEAST_ONE - Pull batches until at least one result is returned.

    Args:
      min_batch_size: The minimum number of results to retrieve or one of
        (ASYNC_ONLY, AT_LEAST_OFFSET, AT_LEAST_ONE)

    Returns:
      The next Batch of results.
    """
    if min_batch_size in (Batcher.ASYNC_ONLY, Batcher.AT_LEAST_OFFSET,
                          Batcher.AT_LEAST_ONE):
      exact = False
    else:
      exact = True
      datastore_types.ValidateInteger(min_batch_size,
                                      'min_batch_size',
                                      datastore_errors.BadArgumentError)
    if not self.__next_batch:
      raise StopIteration


    batch = self.__next_batch.get_result()
    self.__next_batch = None
    self.__skipped_results += batch.skipped_results

    if min_batch_size is not Batcher.ASYNC_ONLY:
      if min_batch_size is Batcher.AT_LEAST_ONE:
        min_batch_size = 1

      needed_results = min_batch_size - len(batch.results)
      while (batch.more_results and
             (self.__skipped_results < self.__initial_offset or
              needed_results > 0)):
        if batch.query_options.batch_size:

          batch_size = max(batch.query_options.batch_size, needed_results)
        elif exact:
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
    while (not self.__current_batch or
        self.__current_pos >= len(self.__current_batch.results)):

      next_batch = self.__batcher.next()
      if not next_batch:


        raise StopIteration

      self.__current_pos = 0
      self.__current_batch = next_batch

    result = self.__current_batch.results[self.__current_pos]
    self.__current_pos += 1
    return result

  def __iter__(self):
    return self
