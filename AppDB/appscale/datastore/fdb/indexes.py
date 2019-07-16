"""
This module stores and queries entity indexes. The IndexManager is the main
interface that clients can use to interact with the index layer. See its
documentation for implementation details.
"""
from __future__ import division

import itertools
import logging
import monotonic
import sys

import six
from tornado import gen

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.fdb.codecs import (
  decode_str, decode_value, encode_value, encode_versionstamp_index, Path)
from appscale.datastore.fdb.sdk import ListCursor
from appscale.datastore.fdb.utils import (
  format_prop_val, DS_ROOT, fdb, get_scatter_val, MAX_FDB_TX_DURATION,
  ResultIterator, SCATTER_PROP, VERSIONSTAMP_SIZE)
from appscale.datastore.dbconstants import BadRequest, InternalError
from appscale.datastore.index_manager import IndexInaccessible
from appscale.datastore.utils import _FindIndexToUse

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import datastore_pb, entity_pb
from google.appengine.datastore.datastore_pb import Query_Filter, Query_Order

logger = logging.getLogger(__name__)

KEY_PROP = u'__key__'

first_gt_or_equal = fdb.KeySelector.first_greater_or_equal


class FilterProperty(object):
  """ Encapsulates details for a FilterProperty that came from a query. """
  __slots__ = ['name', 'filters']

  def __init__(self, prop_name, filters):
    self.name = prop_name
    self.filters = filters

  @property
  def equality(self):
    return all(op == Query_Filter.EQUAL for op, _ in self.filters)

  def __repr__(self):
    return u'FilterProperty(%r, %r)' % (self.name, self.filters)


def group_filters(query):
  filter_props = []
  for query_filter in query.filter_list():
    if query_filter.property_size() != 1:
      raise BadRequest(u'Each filter must have exactly one property')

    prop = query_filter.property(0)
    prop_name = decode_str(prop.name())
    filter_info = (query_filter.op(), prop.value())
    if filter_props and filter_props[-1].name == prop_name:
      filter_props[-1].filters.append(filter_info)
    else:
      filter_props.append(FilterProperty(prop_name, [filter_info]))

  # Since the filter list can come in any order, put inequality filters last.
  inequality_index = None
  for index, filter_prop in enumerate(filter_props):
    if not filter_prop.equality:
      inequality_index = index
      break

  if inequality_index is not None:
    inequality_prop = filter_props.pop(inequality_index)
    filter_props.append(inequality_prop)

  # Put key filters last.
  key_index = None
  for index, filter_prop in enumerate(filter_props):
    if filter_prop.name == KEY_PROP:
      key_index = index
      break

  if key_index is not None:
    key_prop = filter_props.pop(key_index)
    filter_props.append(key_prop)

  for filter_prop in filter_props[:-1]:
    if filter_prop.name == KEY_PROP:
      raise BadRequest(
        u'Only the last filter property can be on {}'.format(KEY_PROP))

    if not filter_prop.equality:
      raise BadRequest(u'All but the last property must be equality filters')

  return tuple(filter_props)


def get_order_info(query):
  filter_props = group_filters(query)

  # Orders on equality filters can be ignored.
  equality_props = [prop.name for prop in filter_props if prop.equality]
  relevant_orders = [order for order in query.order_list()
                     if order.property() not in equality_props]

  order_info = []
  for filter_prop in filter_props:
    if filter_prop.equality:
      continue

    direction = next(
      (order.direction() for order in relevant_orders
       if order.property() == filter_prop.name), Query_Order.ASCENDING)
    order_info.append((filter_prop.name, direction))

  filter_prop_names = [prop.name for prop in filter_props]
  order_info.extend(
    [(decode_str(order.property()), order.direction())
     for order in relevant_orders
     if order.property() not in filter_prop_names])

  return tuple(order_info)


def get_scan_direction(query, index):
  order_info = get_order_info(query)
  if not order_info:
    return Query_Order.ASCENDING

  first_property, first_direction = order_info[0]
  if first_property == KEY_PROP or isinstance(index, SinglePropIndex):
    return first_direction

  index_direction = next(direction for prop_name, direction in index.order_info
                         if prop_name == first_property)
  if index_direction == first_direction:
    return Query_Order.ASCENDING
  else:
    return Query_Order.DESCENDING


class IndexEntry(object):
  """ Encapsulates details for an index entry. """
  __slots__ = ['project_id', 'namespace', 'path', 'commit_versionstamp',
               'deleted_versionstamp']

  def __init__(self, project_id, namespace, path, commit_versionstamp,
               deleted_versionstamp):
    self.project_id = project_id
    self.namespace = namespace
    self.path = path
    self.commit_versionstamp = commit_versionstamp
    self.deleted_versionstamp = deleted_versionstamp

  @property
  def key(self):
    key = entity_pb.Reference()
    key.set_app(self.project_id)
    key.set_name_space(self.namespace)
    key.mutable_path().MergeFrom(Path.decode(self.path))
    return key

  @property
  def group(self):
    group = entity_pb.Path()
    group.add_element().MergeFrom(Path.decode_element(self.path[:2]))
    return group

  def __repr__(self):
    return u'IndexEntry(%r, %r, %r, %r, %r)' % (
      self.project_id, self.namespace, self.path, self.commit_versionstamp,
      self.deleted_versionstamp)

  def key_result(self):
    entity = entity_pb.EntityProto()
    entity.mutable_key().MergeFrom(self.key)
    entity.mutable_entity_group()
    return entity

  def cursor_result(self, ordered_props):
    compiled_cursor = datastore_pb.CompiledCursor()
    position = compiled_cursor.add_position()
    position.mutable_key().MergeFrom(self.key)
    position.set_start_inclusive(False)
    return compiled_cursor


class PropertyEntry(IndexEntry):
  """ Encapsulates details for a single-property index entry. """
  __slots__ = ['prop_name', 'value']

  def __init__(self, project_id, namespace, path, prop_name, value,
               commit_versionstamp, deleted_versionstamp):
    super(PropertyEntry, self).__init__(
      project_id, namespace, path, commit_versionstamp, deleted_versionstamp)
    self.prop_name = prop_name
    self.value = value

  def __repr__(self):
    return u'PropertyEntry(%r, %r, %r, %r, %r, %r, %r)' % (
      self.project_id, self.namespace, self.path, self.prop_name, self.value,
      self.commit_versionstamp, self.deleted_versionstamp)

  def __str__(self):
    return u'PropertyEntry(%s, %r, %s, %s, %s, %r, %r)' % (
      self.project_id, self.namespace, self.path, self.prop_name,
      format_prop_val(self.value), self.commit_versionstamp,
      self.deleted_versionstamp)

  def prop_result(self):
    entity = entity_pb.EntityProto()
    entity.mutable_key().MergeFrom(self.key)
    entity.mutable_entity_group().MergeFrom(self.group)
    prop = entity.add_property()
    prop.set_name(self.prop_name)
    prop.set_meaning(entity_pb.Property.INDEX_VALUE)
    prop.set_multiple(False)
    prop.mutable_value().MergeFrom(self.value)
    return entity

  def cursor_result(self, ordered_props):
    compiled_cursor = datastore_pb.CompiledCursor()
    position = compiled_cursor.add_position()
    position.mutable_key().MergeFrom(self.key)
    position.set_start_inclusive(False)
    if self.prop_name in ordered_props:
      index_value = position.add_indexvalue()
      index_value.set_property(self.prop_name)
      index_value.mutable_value().MergeFrom(self.value)

    return compiled_cursor


class CompositeEntry(IndexEntry):
  """ Encapsulates details for a composite index entry. """
  __slots__ = ['properties']

  def __init__(self, project_id, namespace, path, properties,
               commit_versionstamp, deleted_versionstamp):
    super(CompositeEntry, self).__init__(
      project_id, namespace, path, commit_versionstamp, deleted_versionstamp)
    self.properties = properties

  def __repr__(self):
    return u'CompositeEntry(%r, %r, %r, %r, %r, %r)' % (
      self.project_id, self.namespace, self.path, self.properties,
      self.commit_versionstamp, self.deleted_versionstamp)

  def prop_result(self):
    entity = entity_pb.EntityProto()
    entity.mutable_key().MergeFrom(self.key)
    entity.mutable_entity_group().MergeFrom(self.group)
    for prop_name, value in self.properties:
      prop = entity.add_property()
      prop.set_name(prop_name)
      prop.set_meaning(entity_pb.Property.INDEX_VALUE)
      # TODO: Check if this is sometimes True.
      prop.set_multiple(False)
      prop.mutable_value().MergeFrom(value)

    return entity

  def cursor_result(self, ordered_props):
    compiled_cursor = datastore_pb.CompiledCursor()
    position = compiled_cursor.add_position()
    position.mutable_key().MergeFrom(self.key)
    position.set_start_inclusive(False)
    for prop_name, value in self.properties:
      if prop_name not in ordered_props:
        continue

      index_value = position.add_indexvalue()
      index_value.set_property(prop_name)
      index_value.mutable_value().MergeFrom(value)

    return compiled_cursor


class IndexIterator(object):
  """
  Returns pages of index entry results. It ignores Key-Values that do not apply
  to the given read_versionstamp. It converts usable Key-Values to IndexEntry
  objects.
  """
  def __init__(self, tr, tornado_fdb, index, key_slice, fetch_limit, reverse,
               read_versionstamp=None, snapshot=False):
    self.index = index
    self._result_iterator = ResultIterator(
      tr, tornado_fdb, key_slice, fetch_limit, reverse, snapshot=snapshot)
    self._read_versionstamp = read_versionstamp
    self._done = False

  @property
  def prop_names(self):
    return self.index.prop_names

  @property
  def start_key(self):
    return self._result_iterator.slice.start.key

  @gen.coroutine
  def next_page(self):
    if self._done:
      raise gen.Return(([], False))

    results, more_results = yield self._result_iterator.next_page()
    usable_entries = []
    for result in results:
      entry = self.index.decode(result)
      if not self._usable(entry):
        self._result_iterator.increase_limit()
        more_results = not self._result_iterator.done_with_range
        continue

      usable_entries.append(entry)

    if not more_results:
      self._done = True

    raise gen.Return((usable_entries, more_results))

  def _usable(self, entry):
    if self._read_versionstamp and entry.deleted_versionstamp:
      return (entry.commit_versionstamp < self._read_versionstamp <
              entry.deleted_versionstamp)
    elif self._read_versionstamp:
      return entry.commit_versionstamp < self._read_versionstamp
    else:
      return entry.deleted_versionstamp is None


class MergeJoinIterator(object):
  """
  Returns pages of index entry results from multiple ranges. It ignores
  Key-Values that do not apply to the given read_versionstamp. It converts
  usable Key-Values to IndexEntry objects.
  """
  def __init__(self, tr, tornado_fdb, filter_props, indexes, fetch_limit,
               read_versionstamp=None, ancestor_path=None, snapshot=False):
    self.indexes = indexes
    self._filter_props = filter_props
    self._read_versionstamp = read_versionstamp
    self._tr = tr
    self._tornado_fdb = tornado_fdb
    self._fetch_limit = fetch_limit
    self._fetched = 0
    self._snapshot = snapshot
    self._done = False
    self._candidate_path = None
    self._candidate_entries = []
    self._ancestor_path = ancestor_path

  @property
  def prop_names(self):
    prop_names = set()
    for index, _, _, _ in self.indexes:
      prop_names.update(index.prop_names)

    return tuple(prop_names)

  @gen.coroutine
  def next_page(self):
    if self._done:
      raise gen.Return(([], False))

    composite_entry = None
    for i, (index, key_slice, prop_name, value) in enumerate(self.indexes):
      usable_entry = None
      # TODO: Keep cache of ranges to reduce unnecessary lookups.
      index_exhausted = False
      while True:
        results, count, more = yield self._tornado_fdb.get_range(
          self._tr, key_slice, 0, fdb.StreamingMode.small, 1,
          snapshot=self._snapshot)
        if not count:
          index_exhausted = True
          break

        key_slice = slice(fdb.KeySelector.first_greater_than(results[-1].key),
                          key_slice.stop)
        for result in results:
          entry = index.decode(result)
          if self._usable(entry):
            usable_entry = entry
            break

        if usable_entry is not None:
          break

      if index_exhausted:
        self._done = True
        break

      if usable_entry.path == self._candidate_path:
        self._candidate_entries.append(usable_entry)
      else:
        self._candidate_path = usable_entry.path
        self._candidate_entries = [usable_entry]

      next_index_op = Query_Filter.GREATER_THAN_OR_EQUAL
      if len(self._candidate_entries) == len(self.indexes):
        properties = []
        for partial_entry in self._candidate_entries:
          if isinstance(partial_entry, PropertyEntry):
            properties.append((partial_entry.prop_name, partial_entry.value))
          else:
            for property in partial_entry.properties:
              if property not in properties:
                properties.append(property)

        composite_entry = CompositeEntry(
          usable_entry.project_id, usable_entry.namespace,
          self._candidate_path, properties, usable_entry.commit_versionstamp,
          usable_entry.deleted_versionstamp)
        self._candidate_entries = []
        next_index_op = Query_Filter.GREATER_THAN

      next_index_i = (i + 1) % len(self.indexes)
      next_index, next_slice, next_prop_name, next_value =\
        self.indexes[next_index_i]

      # TODO: This probably doesn't work for all cases.
      last_prop = None
      if isinstance(next_index, CompositeIndex):
        last_prop = next_index.prop_names[-1]

      tmp_filter_props = []
      for filter_prop in self._filter_props:
        if (filter_prop.name in (next_prop_name, last_prop, KEY_PROP) or
            filter_prop.name not in next_index.prop_names):
          continue
        else:
          tmp_filter_props.append(filter_prop)

      tmp_filter_props.append(
        FilterProperty(next_prop_name, [(Query_Filter.EQUAL, next_value)]))

      if last_prop is not None:
        val = next(value for prop_name, value in usable_entry.properties
                   if prop_name == last_prop)
        tmp_filter_props.append(
          FilterProperty(last_prop, [(Query_Filter.EQUAL, val)]))

      tmp_filter_props.append(
        FilterProperty(KEY_PROP, [(next_index_op, usable_entry.path)]))

      new_slice = next_index.get_slice(tmp_filter_props,
                                       ancestor_path=self._ancestor_path)
      self.indexes[next_index_i][1] = new_slice

    entries = [composite_entry] if composite_entry is not None else []
    self._fetched += len(entries)
    if self._fetched == self._fetch_limit:
      self._done = True

    raise gen.Return((entries, not self._done))

  def _usable(self, entry):
    if self._read_versionstamp and entry.deleted_versionstamp:
      return (entry.commit_versionstamp < self._read_versionstamp <
              entry.deleted_versionstamp)
    elif self._read_versionstamp:
      return entry.commit_versionstamp < self._read_versionstamp
    else:
      return entry.deleted_versionstamp is None


class IndexSlice(object):
  """ Encapsulates details about an index range in a way that's mutable. """
  __slots__ = ['_directory_prefix', '_order_info', '_ancestor', '_start_parts',
               '_stop_parts']

  def __init__(self, directory_prefix, order_info, ancestor=False):
    self._directory_prefix = directory_prefix
    self._order_info = order_info
    self._ancestor = ancestor

    self._start_parts = [self._directory_prefix]
    self._stop_parts = [self._directory_prefix, b'\xFF']

  @property
  def start(self):
    return first_gt_or_equal(b''.join(self._start_parts))

  @property
  def stop(self):
    return first_gt_or_equal(b''.join(self._stop_parts))

  @property
  def _expected_parts(self):
    total = 1  # directory prefix
    if self._ancestor:
      total += 1

    total += len(self._order_info)
    total += 1  # path
    total += 1  # commit versionstamp
    return total

  def set_ancestor(self, ancestor_path):
    if not ancestor_path:
      return

    index = 1 if self._ancestor else -2
    if self._ancestor:
      self._set_start(index, Path.pack(ancestor_path))
      self._set_stop(index, Path.pack(ancestor_path))
      self._set_stop(index + 1, b'\xFF')
    else:
      prefix = Path.pack(ancestor_path, omit_terminator=True)
      self._set_start(index, prefix)
      self._set_stop(index, prefix + b'\xFF')

  def apply_prop_filter(self, prop_name, op, value):
    index, direction = self._prop_details(prop_name)
    prop_reverse = direction == Query_Order.DESCENDING
    encoded_value = encode_value(value, prop_reverse)
    if op == Query_Filter.EQUAL:
      self._set_start(index, encoded_value)
      self._set_stop(index, encoded_value)
      self._set_stop(index + 1, b'\xFF')
      return

    if (op == Query_Filter.GREATER_THAN_OR_EQUAL and not prop_reverse or
        op == Query_Filter.LESS_THAN_OR_EQUAL and prop_reverse):
      self._set_start(index, encoded_value)
    elif (op == Query_Filter.GREATER_THAN and not prop_reverse or
          op == Query_Filter.LESS_THAN and prop_reverse):
      self._set_start(index, encoded_value + b'\xFF')
    elif (op == Query_Filter.LESS_THAN_OR_EQUAL and not prop_reverse or
          op == Query_Filter.GREATER_THAN_OR_EQUAL and prop_reverse):
      self._set_stop(index, encoded_value)
      self._set_stop(index + 1, b'\xFF')
    elif (op == Query_Filter.LESS_THAN and not prop_reverse or
          op == Query_Filter.GREATER_THAN and prop_reverse):
      self._set_stop(index, encoded_value)
    else:
      raise BadRequest(u'Unexpected filter operation')

  def apply_path_filter(self, op, path, ancestor_path=()):
    if not isinstance(path, tuple):
      path = Path.flatten(path)

    remaining_path = path[len(ancestor_path):] if self._ancestor else path
    if not remaining_path:
      raise InternalError(u'Path filter must be within ancestor')

    start = Path.pack(remaining_path, omit_terminator=True)
    # Since the commit versionstamp could potentially start with 0xFF, this
    # selection scans up to the next possible path value.
    stop = start + six.int2byte(Path.MIN_ID_MARKER)
    index = -2
    if op == Query_Filter.EQUAL:
      self._set_start(index, start)
      self._set_stop(index, stop)
      self._set_stop(index + 1, b'\xFF')
      return

    if op == Query_Filter.GREATER_THAN_OR_EQUAL:
      self._set_start(index, start)
    elif op == Query_Filter.GREATER_THAN:
      self._set_start(index, stop)
    elif op == Query_Filter.LESS_THAN_OR_EQUAL:
      self._set_stop(index, stop)
    elif op == Query_Filter.LESS_THAN:
      self._set_stop(index, start)
    else:
      raise BadRequest(u'Unexpected filter operation')

  def apply_cursor(self, op, cursor, ancestor_path):
    if op in (Query_Filter.GREATER_THAN_OR_EQUAL, Query_Filter.GREATER_THAN):
      existing_parts = self._start_parts
    else:
      existing_parts = self._stop_parts

    for prop_name, direction in self._order_info:
      cursor_prop = next((prop for prop in cursor.property_list()
                          if prop.name() == prop_name), None)
      if cursor_prop is not None:
        index = self._prop_details(prop_name)[0]
        encoded_value = encode_value(cursor_prop.value(),
                                     direction == Query_Order.DESCENDING)
        self._update_parts(existing_parts, index, encoded_value)

    self.apply_path_filter(op, cursor.key().path(), ancestor_path)

  def _prop_details(self, prop_name):
    prop_index = next(
      (index for index, (name, direction) in enumerate(self._order_info)
       if name == prop_name), None)
    if prop_index is None:
      raise InternalError(u'{} is not in index'.format(prop_name))

    index = prop_index + 1  # Account for directory prefix.
    if self._ancestor:
      index += 1

    return index, self._order_info[prop_index][1]

  def _update_parts(self, parts, index, new_value):
    if index < 0:
      index = self._expected_parts + index

    # Ensure fields are set in order.
    if len(parts) < index:
      raise BadRequest(u'Invalid filter combination')

    if len(parts) == index:
      parts.append(new_value)
      return

    if new_value == parts[index]:
      return

    # If this field has already been set, ensure the new range is smaller.
    candidate = parts[:index] + [new_value]
    if parts is self._start_parts:
      if b''.join(candidate) < b''.join(parts):
        raise BadRequest(u'Invalid filter combination')

      self._start_parts = candidate
    elif parts is self._stop_parts:
      if b''.join(candidate) > b''.join(parts):
        raise BadRequest(u'Invalid filter combination')

      self._stop_parts = candidate

  def _set_start(self, index, new_value):
    return self._update_parts(self._start_parts, index, new_value)

  def _set_stop(self, index, new_value):
    return self._update_parts(self._stop_parts, index, new_value)


class Index(object):
  """ The base class for different datastore index types. """
  __slots__ = ['directory']

  def __init__(self, directory):
    self.directory = directory

  @property
  def project_id(self):
    return self.directory.get_path()[len(DS_ROOT)]

  @property
  def versionstamp_slice(self):
    """ The portion of keys that contain the commit versionstamp. """
    return slice(-VERSIONSTAMP_SIZE, None)

  @property
  def prop_names(self):
    return NotImplementedError()

  def get_slice(self, filter_props, ancestor_path=tuple(), start_cursor=None,
                end_cursor=None, reverse_scan=False):
    has_ancestor_field = getattr(self, 'ancestor', False)
    order_info = getattr(
      self, 'order_info', tuple((prop_name, Query_Order.ASCENDING)
                                for prop_name in self.prop_names))
    index_slice = IndexSlice(
      self.directory.rawPrefix, order_info, ancestor=has_ancestor_field)

    # First, apply the ancestor filter if it comes first in the index.
    if has_ancestor_field:
      index_slice.set_ancestor(ancestor_path)

    # Second, apply property filters in the index's definition order.
    ordered_filter_props = []
    for prop_name in self.prop_names:
      filter_prop = next((filter_prop for filter_prop in filter_props
                          if filter_prop.name == prop_name), None)
      if filter_prop is not None:
        ordered_filter_props.append(filter_prop)

    for filter_prop in ordered_filter_props:
      for op, value in filter_prop.filters:
        index_slice.apply_prop_filter(filter_prop.name, op, value)

    # Third, apply the ancestor filter if it hasn't been applied yet.
    if not has_ancestor_field:
      index_slice.set_ancestor(ancestor_path)

    # Fourth, apply key property filters.
    key_filter_props = [filter_prop for filter_prop in filter_props
                        if filter_prop.name == KEY_PROP]
    for filter_prop in key_filter_props:
      for op, path in filter_prop.filters:
        index_slice.apply_path_filter(op, path, ancestor_path)

    # Finally, apply cursors.
    if start_cursor is not None:
      op = (Query_Filter.LESS_THAN if reverse_scan
            else Query_Filter.GREATER_THAN)
      index_slice.apply_cursor(op, start_cursor, ancestor_path)

    if end_cursor is not None:
      op = (Query_Filter.GREATER_THAN_OR_EQUAL if reverse_scan
            else Query_Filter.LESS_THAN_OR_EQUAL)
      index_slice.apply_cursor(op, end_cursor, ancestor_path)

    return slice(index_slice.start, index_slice.stop)


class KindlessIndex(Index):
  """
  A KindlessIndex handles the encoding and decoding details for kind index
  entries. These are paths that point to entity keys.

  The FDB directory for a kindless index looks like
  (<project-dir>, 'kindless-indexes', <namespace>).

  Within this directory, keys are encoded as <path> + <commit-versionstamp>.

  The <path> contains the entity path. See codecs.Path for encoding details.

  The <commit-versionstamp> is a 10-byte versionstamp that specifies the commit
  version of the transaction that wrote the index entry.
  """
  DIR_NAME = u'kindless-indexes'

  @property
  def prop_names(self):
    return ()

  @property
  def namespace(self):
    return self.directory.get_path()[-1]

  def __repr__(self):
    return u'KindlessIndex(%r)' % self.directory

  @classmethod
  def directory_path(cls, project_id, namespace):
    return project_id, cls.DIR_NAME, namespace

  def encode_key(self, path, commit_versionstamp):
    key = b''.join([self.directory.rawPrefix, Path.pack(path),
                    commit_versionstamp or b'\x00' * VERSIONSTAMP_SIZE])
    if not commit_versionstamp:
      key += encode_versionstamp_index(len(key) - VERSIONSTAMP_SIZE)

    return key

  def decode(self, kv):
    path = Path.unpack(kv.key, len(self.directory.rawPrefix))[0]
    commit_versionstamp = kv.key[self.versionstamp_slice]
    deleted_versionstamp = kv.value or None
    return IndexEntry(self.project_id, self.namespace, path,
                      commit_versionstamp, deleted_versionstamp)


class KindIndex(Index):
  """
  A KindIndex handles the encoding and decoding details for kind index entries.
  These are paths grouped by kind that point to entity keys.

  The FDB directory for a kind index looks like
  (<project-dir>, 'kind-indexes', <namespace>, <kind>).

  Within this directory, keys are encoded as <path> + <commit-versionstamp>.

  The <path> contains the entity path. See codecs.Path for encoding details.

  The <commit-versionstamp> is a 10-byte versionstamp that specifies the commit
  version of the transaction that wrote the index entry.
  """
  DIR_NAME = u'kind-indexes'

  @property
  def namespace(self):
    return self.directory.get_path()[-2]

  @property
  def kind(self):
    return self.directory.get_path()[-1]

  def __repr__(self):
    return u'KindIndex(%r)' % self.directory

  @classmethod
  def directory_path(cls, project_id, namespace, kind):
    return project_id, cls.DIR_NAME, namespace, kind

  @classmethod
  def section_path(cls, project_id):
    return project_id, cls.DIR_NAME

  @property
  def prop_names(self):
    return ()

  def encode_key(self, path, commit_versionstamp):
    key = b''.join([self.directory.rawPrefix, Path.pack(path),
                    commit_versionstamp or b'\x00' * VERSIONSTAMP_SIZE])
    if not commit_versionstamp:
      key += encode_versionstamp_index(len(key) - VERSIONSTAMP_SIZE)

    return key

  def decode(self, kv):
    path = Path.unpack(kv.key, len(self.directory.rawPrefix))[0]
    commit_versionstamp = kv.key[self.versionstamp_slice]
    deleted_versionstamp = kv.value or None
    return IndexEntry(self.project_id, self.namespace, path,
                      commit_versionstamp, deleted_versionstamp)


class SinglePropIndex(Index):
  """
  A SinglePropIndex handles the encoding and decoding details for single-prop
  index entries. These are property values for a particular kind that point to
  entity keys.

  The FDB directory for a single-prop index looks like
  (<project-dir>, 'single-property-indexes', <namespace>, <kind>, <prop-name>).

  Within this directory, keys are encoded as
  (<value>, <path>, <commit-versionstamp>).

  The <value> contains a property value. See the codecs module for encoding
  details.

  The <path> contains the entity path. See codecs.Path for encoding details.

  The <commit-versionstamp> is a 10-byte versionstamp that specifies the commit
  version of the transaction that wrote the index entry.
  """
  DIR_NAME = u'single-property-indexes'

  @property
  def namespace(self):
    return self.directory.get_path()[-3]

  @property
  def kind(self):
    return self.directory.get_path()[-2]

  @property
  def prop_name(self):
    return self.directory.get_path()[-1]

  @property
  def prop_names(self):
    return (self.directory.get_path()[-1],)

  def __repr__(self):
    return u'SinglePropIndex(%r)' % self.directory

  @classmethod
  def directory_path(cls, project_id, namespace, kind, prop_name):
    return project_id, cls.DIR_NAME, namespace, kind, prop_name

  def encode_key(self, value, path, commit_versionstamp):
    key = b''.join([self.directory.rawPrefix, encode_value(value),
                    Path.pack(path),
                    commit_versionstamp or b'\x00' * VERSIONSTAMP_SIZE])
    if not commit_versionstamp:
      key += encode_versionstamp_index(len(key) - VERSIONSTAMP_SIZE)

    return key

  def decode(self, kv):
    value, pos = decode_value(kv.key, len(self.directory.rawPrefix))
    path = Path.unpack(kv.key, pos)[0]
    commit_versionstamp = kv.key[self.versionstamp_slice]
    deleted_versionstamp = kv.value or None
    return PropertyEntry(self.project_id, self.namespace, path, self.prop_name,
                         value, commit_versionstamp, deleted_versionstamp)


class CompositeIndex(Index):
  """
  A CompositeIndex handles the encoding and decoding details for composite
  index entries.

  The FDB directory for a composite index looks like
  (<project-dir>, 'composite-indexes', <index-id>, <namespace>).

  Within this directory, keys are encoded as
  (<ancestor-fragment (optional)>, <encoded-value(s)>, <remaining-path>,
   <commit-versionstamp>).

  If the index definition requires an ancestor, the <ancestor-fragment>
  contains an encoded tuple specifying the full or partial path of the entity's
  ancestor. The number of entries written for ancestor composite indexes is
  equal to the number of ancestor path elements. For example, an entity with
  three path elements would be encoded with the following two entries:
  (('Kind1', 'key1'), <encoded-values>, ('Kind2', 'key2', 'key3'), <commit-vs>)
  (('Kind1', 'key1, 'Kind2', 'key2'), <encoded-values>, ('key3',), <commit-vs>)

  The <encoded-value(s)> portion contains the property values as defined by the
  index. See the codecs module for encoding details.

  The <remaining-path> is an encoded tuple containing the portion of the entity
  path that isn't specified by the <ancestor-fragment>. If the index definition
  does not require an ancestor, this contains the full path.

  The <commit-versionstamp> is a 10-byte versionstamp that specifies the commit
  version of the transaction that wrote the index entry.
  """
  __slots__ = ['kind', 'ancestor', 'order_info']

  DIR_NAME = u'composite-indexes'

  def __init__(self, directory, kind, ancestor, order_info):
    super(CompositeIndex, self).__init__(directory)
    self.kind = kind
    self.ancestor = ancestor
    self.order_info = order_info

  @property
  def id(self):
    return int(self.directory.get_path()[-2])

  @property
  def namespace(self):
    return self.directory.get_path()[-1]

  @property
  def prop_names(self):
    return tuple(prop_name for prop_name, _ in self.order_info)

  def __repr__(self):
    return u'CompositeIndex(%r, %r, %r, %r)' % (
      self.directory, self.kind, self.ancestor, self.order_info)

  @classmethod
  def directory_path(cls, project_id, index_id, namespace):
    return project_id, cls.DIR_NAME, six.text_type(index_id), namespace

  def encode_key(self, ancestor_path, encoded_values, remaining_path,
                 commit_versionstamp):
    ancestor_path = Path.pack(ancestor_path) if ancestor_path else b''
    remaining_path = Path.pack(remaining_path)
    key = b''.join(
      (self.directory.rawPrefix, ancestor_path) + tuple(encoded_values) +
      (remaining_path, commit_versionstamp or b'\x00' * VERSIONSTAMP_SIZE))
    if not commit_versionstamp:
      key += encode_versionstamp_index(len(key) - VERSIONSTAMP_SIZE)

    return key

  def encode_keys(self, prop_list, path, commit_versionstamp):
    encoded_values_by_prop = []
    for index_prop_name, direction in self.order_info:
      reverse = direction == Query_Order.DESCENDING
      encoded_values_by_prop.append(
        tuple(encode_value(prop.value(), reverse) for prop in prop_list
              if prop.name() == index_prop_name))

    encoded_value_combos = itertools.product(*encoded_values_by_prop)
    if not self.ancestor:
      return tuple(self.encode_key((), values, path, commit_versionstamp)
                   for values in encoded_value_combos)

    keys = []
    for index in range(2, len(path), 2):
      ancestor_path = path[:index]
      remaining_path = path[index:]
      keys.extend(
        [self.encode_key(ancestor_path, values, remaining_path,
                         commit_versionstamp)
        for values in encoded_value_combos])

    return tuple(keys)

  def decode(self, kv):
    pos = len(self.directory.rawPrefix)
    properties = []
    if self.ancestor:
      ancestor_path, pos = Path.unpack(kv.key, pos)
    else:
      ancestor_path = ()

    for prop_name, direction in self.order_info:
      value, pos = decode_value(kv.key, pos,
                                direction == Query_Order.DESCENDING)
      properties.append((prop_name, value))

    remaining_path = Path.unpack(kv.key, pos)[0]
    path = ancestor_path + remaining_path
    commit_versionstamp = kv.key[self.versionstamp_slice]
    deleted_versionstamp = kv.value or None
    return CompositeEntry(self.project_id, self.namespace, path, properties,
                          commit_versionstamp, deleted_versionstamp)


class IndexManager(object):
  """
  The IndexManager is the main interface that clients can use to interact with
  the index layer. It makes use of KindlessIndex, KindIndex, SinglePropIndex,
  and CompositeIndex namespace directories to handle the encoding and decoding
  details when satisfying requests. When a client requests data, the
  IndexManager encapsulates index data in an IndexEntry object.
  """
  _MAX_RESULTS = 300

  def __init__(self, db, tornado_fdb, data_manager, directory_cache):
    self.composite_index_manager = None
    self._db = db
    self._tornado_fdb = tornado_fdb
    self._data_manager = data_manager
    self._directory_cache = directory_cache

  @gen.coroutine
  def put_entries(self, tr, old_version_entry, new_entity):
    if old_version_entry.has_entity:
      keys = yield self._get_index_keys(
        tr, old_version_entry.decoded, old_version_entry.commit_versionstamp)
      for key in keys:
        # Set deleted versionstamp.
        tr.set_versionstamped_value(
          key, b'\x00' * VERSIONSTAMP_SIZE + encode_versionstamp_index(0))

    if new_entity is not None:
      keys = yield self._get_index_keys(tr, new_entity)
      for key in keys:
        tr.set_versionstamped_key(key, b'')

  @gen.coroutine
  def hard_delete_entries(self, tr, version_entry):
    if not version_entry.has_entity:
      return

    keys = yield self._get_index_keys(
      tr, version_entry.decoded, version_entry.commit_versionstamp)
    for key in keys:
      del tr[key]

  def rpc_limit(self, query):
    check_more_results = False
    limit = None
    if query.has_limit():
      limit = query.limit()

    if query.has_count() and (limit is None or limit > query.count()):
      check_more_results = True
      limit = query.count()

    if limit is None or limit > self._MAX_RESULTS:
      check_more_results = True
      limit = self._MAX_RESULTS

    if query.has_offset():
      limit += query.offset()

    return limit, check_more_results

  def include_data(self, query):
    if query.keys_only() and query.property_name_list():
      raise BadRequest(
        u'A keys-only query cannot include a property name list')

    if query.keys_only():
      return False

    if not query.property_name_list():
      return True

    return False

  @gen.coroutine
  def get_iterator(self, tr, query, read_versionstamp=None):
    project_id = decode_str(query.app())
    namespace = decode_str(query.name_space())
    filter_props = group_filters(query)
    ancestor_path = tuple()
    if query.has_ancestor():
      ancestor_path = Path.flatten(query.ancestor().path())

    start_cursor = None
    if query.has_compiled_cursor():
      start_cursor = ListCursor(query)._GetLastResult()

    end_cursor = None
    if query.has_end_compiled_cursor():
      end_compiled = query.end_compiled_cursor()
      end_cursor = ListCursor(query)._DecodeCompiledCursor(end_compiled)[0]

    rpc_limit, check_more_results = self.rpc_limit(query)
    fetch_limit = rpc_limit
    if check_more_results:
      fetch_limit += 1

    index = yield self._get_perfect_index(tr, query)
    reverse = get_scan_direction(query, index) == Query_Order.DESCENDING

    if index is None:
      if not all(prop.equality for prop in filter_props):
        raise BadRequest(u'Query not supported')

      indexes = []
      equality_props = [filter_prop for filter_prop in filter_props
                        if filter_prop.name == KEY_PROP]
      if len(equality_props) > 1:
        raise BadRequest(u'Only one equality key filter is supported')

      equality_prop = next(iter(equality_props), None)
      other_props = [filter_prop for filter_prop in filter_props
                     if filter_prop.name != KEY_PROP]
      for filter_prop in other_props:
        index = yield self._single_prop_index(
          tr, project_id, namespace, decode_str(query.kind()),
          filter_prop.name)
        for op, value in filter_prop.filters:
          tmp_filter_prop = FilterProperty(filter_prop.name, [(op, value)])
          if equality_prop is not None:
            tmp_filter_props = (tmp_filter_prop, equality_prop)
          else:
            tmp_filter_props = (tmp_filter_prop,)

          slice = index.get_slice(tmp_filter_props, ancestor_path,
                                  start_cursor, end_cursor)
          indexes.append([index, slice, filter_prop.name, value])

      raise gen.Return(
        MergeJoinIterator(tr, self._tornado_fdb, filter_props, indexes,
                          fetch_limit, read_versionstamp, ancestor_path,
                          snapshot=True))

    equality_prop = next(
      (filter_prop for filter_prop in filter_props if filter_prop.equality),
      None)
    if equality_prop is not None and len(equality_prop.filters) > 1:
      indexes = []
      for op, value in equality_prop.filters:
        tmp_filter_props = []
        for filter_prop in filter_props:
          if filter_prop.name == equality_prop.name:
            tmp_filter_props.append(
              FilterProperty(filter_prop.name, [(op, value)]))
          else:
            tmp_filter_props.append(filter_prop)

        desired_slice = index.get_slice(
          tmp_filter_props, ancestor_path, start_cursor, end_cursor, reverse)
        indexes.append([index, desired_slice, equality_prop.name, value])

      raise gen.Return(
        MergeJoinIterator(tr, self._tornado_fdb, filter_props, indexes,
                          fetch_limit, read_versionstamp, ancestor_path,
                          snapshot=True))

    desired_slice = index.get_slice(filter_props, ancestor_path, start_cursor,
                                    end_cursor, reverse)

    iterator = IndexIterator(tr, self._tornado_fdb, index, desired_slice,
                             fetch_limit, reverse, read_versionstamp,
                             snapshot=True)

    raise gen.Return(iterator)

  @gen.coroutine
  def _get_index_keys(self, tr, entity, commit_versionstamp=None):
    project_id = decode_str(entity.key().app())
    namespace = decode_str(entity.key().name_space())
    path = Path.flatten(entity.key().path())
    kind = path[-2]

    kindless_index = yield self._kindless_index(tr, project_id, namespace)
    kind_index = yield self._kind_index(tr, project_id, namespace, kind)
    composite_indexes = yield self._get_indexes(
      tr, project_id, namespace, kind)

    all_keys = [kindless_index.encode_key(path, commit_versionstamp),
                kind_index.encode_key(path, commit_versionstamp)]
    entity_prop_names = []
    for prop in entity.property_list():
      prop_name = decode_str(prop.name())
      entity_prop_names.append(prop_name)
      index = yield self._single_prop_index(
        tr, project_id, namespace, kind, prop_name)
      all_keys.append(
        index.encode_key(prop.value(), path, commit_versionstamp))

    scatter_val = get_scatter_val(path)
    if scatter_val is not None:
      index = yield self._single_prop_index(
        tr, project_id, namespace, kind, SCATTER_PROP)
      all_keys.append(index.encode_key(scatter_val, path, commit_versionstamp))

    for index in composite_indexes:
      if not all(index_prop_name in entity_prop_names
                 for index_prop_name in index.prop_names):
        continue

      all_keys.extend(
        index.encode_keys(entity.property_list(), path, commit_versionstamp))

    raise gen.Return(all_keys)

  @gen.coroutine
  def _get_perfect_index(self, tr, query):
    project_id = decode_str(query.app())
    namespace = decode_str(query.name_space())
    filter_props = group_filters(query)
    order_info = get_order_info(query)

    prop_names = [filter_prop.name for filter_prop in filter_props]
    prop_names.extend([prop_name for prop_name, _ in order_info
                       if prop_name not in prop_names])
    prop_names.extend([decode_str(prop_name)
                       for prop_name in query.property_name_list()
                       if prop_name not in prop_names])

    if not query.has_kind():
      if not all(prop_name == KEY_PROP for prop_name in prop_names):
        raise BadRequest(u'kind must be specified when filtering or ordering '
                         u'properties other than __key__')

      kindless_index = yield self._kindless_index(tr, project_id, namespace)
      raise gen.Return(kindless_index)

    kind = decode_str(query.kind())
    if all(prop_name == KEY_PROP for prop_name in prop_names):
      kind_index = yield self._kind_index(tr, project_id, namespace, kind)
      raise gen.Return(kind_index)

    if sum(prop_name != KEY_PROP for prop_name in prop_names) == 1:
      prop_name = next(prop_name for prop_name in prop_names
                       if prop_name != KEY_PROP)
      ordered_prop = prop_name in [order_name for order_name, _ in order_info]
      if not query.has_ancestor() or not ordered_prop:
        single_prop_index = yield self._single_prop_index(
          tr, project_id, namespace, decode_str(query.kind()), prop_name)
        raise gen.Return(single_prop_index)

    index_pb = _FindIndexToUse(query, self._get_indexes_pb(project_id))
    if index_pb is not None:
      composite_index = yield self._composite_index(
        tr, project_id, index_pb.id(), namespace)
      raise gen.Return(composite_index)

  @gen.coroutine
  def _get_indexes(self, tr, project_id, namespace, kind):
    try:
      project_index_manager = self.composite_index_manager.projects[project_id]
    except KeyError:
      raise BadRequest(u'project_id: {} not found'.format(project_id))

    relevant_indexes = [index for index in project_index_manager.indexes
                        if index.kind == kind]
    fdb_indexes = []
    for index in relevant_indexes:
      order_info = []
      for prop in index.properties:
        direction = (Query_Order.DESCENDING if prop.direction == 'desc'
                     else Query_Order.ASCENDING)
        order_info.append((prop.name, direction))

      composite_index = yield self._composite_index(
        tr, project_id, index.id, namespace)
      fdb_indexes.append(composite_index)

    raise gen.Return(fdb_indexes)

  def _get_indexes_pb(self, project_id):
    try:
      project_index_manager = self.composite_index_manager.projects[project_id]
    except KeyError:
      raise BadRequest(u'project_id: {} not found'.format(project_id))

    try:
      indexes = project_index_manager.indexes_pb
    except IndexInaccessible:
      raise InternalError(u'ZooKeeper is not accessible')

    return indexes

  @gen.coroutine
  def _kindless_index(self, tr, project_id, namespace):
    path = KindlessIndex.directory_path(project_id, namespace)
    directory = yield self._directory_cache.get(tr, path)
    raise gen.Return(KindlessIndex(directory))

  @gen.coroutine
  def _kind_index(self, tr, project_id, namespace, kind):
    path = KindIndex.directory_path(project_id, namespace, kind)
    directory = yield self._directory_cache.get(tr, path)
    raise gen.Return(KindIndex(directory))

  @gen.coroutine
  def _single_prop_index(self, tr, project_id, namespace, kind, prop_name):
    path = SinglePropIndex.directory_path(
      project_id, namespace, kind, prop_name)
    directory = yield self._directory_cache.get(tr, path)
    raise gen.Return(SinglePropIndex(directory))

  @gen.coroutine
  def _composite_index(self, tr, project_id, index_id, namespace):
    path = CompositeIndex.directory_path(project_id, index_id, namespace)
    directory = yield self._directory_cache.get(tr, path)
    kind, ancestor, order_info = self._index_details(project_id, index_id)
    raise gen.Return(CompositeIndex(directory, kind, ancestor, order_info))

  def _index_details(self, project_id, index_id):
    project_indexes = self.composite_index_manager.projects[project_id].indexes
    index_def = next((ds_index for ds_index in project_indexes
                      if ds_index.id == index_id), None)
    if index_def is None:
      raise InternalError(u'Unable to retrieve index details')

    order_info = tuple(
      (decode_str(prop.name), prop.to_pb().direction())
      for prop in index_def.properties)
    return index_def.kind, index_def.ancestor, order_info

  @gen.coroutine
  def _indexes_for_kind(self, tr, project_id, kind):
    section_path = KindIndex.section_path(project_id)
    section_dir = yield self._directory_cache.get(tr, section_path)
    # TODO: This can be made async.
    indexes = []
    namespaces = section_dir.list(tr)
    for namespace in namespaces:
      ns_dir = section_dir.open(tr, (namespace,))
      try:
        kind_dir = ns_dir.open(tr, (kind,))
      except ValueError:
        continue

      indexes.append(KindIndex(kind_dir))

    raise gen.Return(indexes)

  @gen.coroutine
  def update_composite_index(self, project_id, index_pb, cursor=(None, None)):
    start_ns, start_key = cursor
    project_id = decode_str(project_id)
    kind = decode_str(index_pb.definition().entity_type())
    tr = self._db.create_transaction()
    deadline = monotonic.monotonic() + MAX_FDB_TX_DURATION - 1
    kind_indexes = yield self._indexes_for_kind(tr, project_id, kind)
    for kind_index in kind_indexes:
      if start_ns is not None and kind_index.namespace < start_ns:
        continue

      composite_path = CompositeIndex.directory_path(
        project_id, index_pb.id(), kind_index.namespace)
      composite_dir = yield self._directory_cache.get(tr, composite_path)
      order_info = tuple(
        (decode_str(prop.name()), prop.direction())
        for prop in index_pb.definition().property_list())
      composite_index = CompositeIndex(
        composite_dir, kind, index_pb.definition().ancestor(), order_info)

      logger.info(u'Backfilling {}'.format(composite_index))
      remaining_range = kind_index.directory.range()
      if start_key is not None:
        remaining_range = slice(
          fdb.KeySelector.first_greater_than(start_key), remaining_range.stop)
        start_key = None

      result_iterator = ResultIterator(tr, self._tornado_fdb, remaining_range)
      while True:
        results, more_results = yield result_iterator.next_page()
        index_entries = [kind_index.decode(result) for result in results]
        version_entries = yield [self._data_manager.get_entry(self, tr, entry)
                                 for entry in index_entries]
        for index_entry, version_entry in zip(index_entries, version_entries):
          new_keys = composite_index.encode_keys(
            version_entry.decoded.property_list(), version_entry.path,
            version_entry.commit_versionstamp)
          for new_key in new_keys:
            tr[new_key] = index_entry.deleted_versionstamp or b''

        if not more_results:
          logger.info(u'Finished backfilling {}'.format(composite_index))
          break

        if monotonic.monotonic() > deadline:
          try:
            yield self._tornado_fdb.commit(tr)
            cursor = (kind_index.namespace, results[-1].key)
          except fdb.FDBError as fdb_error:
            logger.warning(u'Error while updating index: {}'.format(fdb_error))
            tr.on_error(fdb_error).wait()

          yield self.update_composite_index(project_id, index_pb, cursor)
          return

    yield self._tornado_fdb.commit(tr)
