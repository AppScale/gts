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
from appscale.datastore.fdb.cache import NSCache
from appscale.datastore.fdb.codecs import (
  decode_element, decode_path, decode_str, decode_value, encode_ancestor_range,
  encode_path, encode_value)
from appscale.datastore.fdb.sdk import ListCursor
from appscale.datastore.fdb.utils import (
  fdb, get_scatter_val, MAX_FDB_TX_DURATION, KVIterator, SCATTER_PROP)
from appscale.datastore.dbconstants import BadRequest, InternalError
from appscale.datastore.index_manager import IndexInaccessible
from appscale.datastore.utils import _FindIndexToUse

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import datastore_pb, entity_pb
from google.appengine.datastore.datastore_pb import Query_Filter, Query_Order

logger = logging.getLogger(__name__)

INDEX_DIR = u'indexes'

KEY_PROP = u'__key__'

START_FILTERS = (Query_Filter.GREATER_THAN_OR_EQUAL, Query_Filter.GREATER_THAN)
STOP_FILTERS = (Query_Filter.LESS_THAN_OR_EQUAL, Query_Filter.LESS_THAN)


class FilterProperty(object):
  __slots__ = [u'name', u'filters']

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


def get_fdb_key_selector(op, encoded_value):
  """ Like Python's slice notation, FDB range queries include the start and
      exclude the stop. Therefore, the stop selector must point to the first
      key that will be excluded from the results. """
  if op == Query_Filter.GREATER_THAN_OR_EQUAL:
    return fdb.KeySelector.first_greater_or_equal(encoded_value)
  elif op == Query_Filter.GREATER_THAN:
    return fdb.KeySelector.first_greater_than(encoded_value + b'\xff')
  elif op == Query_Filter.LESS_THAN_OR_EQUAL:
    return fdb.KeySelector.first_greater_or_equal(encoded_value + b'\xff')
  elif op == Query_Filter.LESS_THAN:
    return fdb.KeySelector.first_greater_than(encoded_value)
  else:
    raise BadRequest(u'Unsupported filter operator')


class IndexEntry(object):
  __SLOTS__ = [u'project_id', u'namespace', u'path', u'commit_vs',
               u'deleted_vs']

  def __init__(self, project_id, namespace, path, commit_vs, deleted_vs):
    self.project_id = project_id
    self.namespace = namespace
    self.path = path
    self.commit_vs = commit_vs
    if deleted_vs is None:
      deleted_vs = fdb.tuple.Versionstamp()

    self.deleted_vs = deleted_vs

  @property
  def key(self):
    key = entity_pb.Reference()
    key.set_app(self.project_id)
    key.set_name_space(self.namespace)
    key.mutable_path().MergeFrom(decode_path(self.path))
    return key

  @property
  def group(self):
    group = entity_pb.Path()
    group.add_element().MergeFrom(decode_element(self.path[:2]))
    return group

  def __repr__(self):
    return u'IndexEntry(%r, %r, %r, %r, %r)' % (
      self.project_id, self.namespace, self.path, self.commit_vs,
      self.deleted_vs)

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
  __SLOTS__ = [u'prop_name', u'value']

  def __init__(self, project_id, namespace, path, prop_name, value, commit_vs,
               deleted_vs):
    super(PropertyEntry, self).__init__(
      project_id, namespace, path, commit_vs, deleted_vs)
    self.prop_name = prop_name
    self.value = value

  def __repr__(self):
    return u'PropertyEntry(%r, %r, %r, %r, %r, %r, %r)' % (
      self.project_id, self.namespace, self.path, self.prop_name, self.value,
      self.commit_vs, self.deleted_vs)

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
  __SLOTS__ = [u'properties']

  def __init__(self, project_id, namespace, path, properties, commit_vs,
               deleted_vs):
    super(CompositeEntry, self).__init__(
      project_id, namespace, path, commit_vs, deleted_vs)
    self.properties = properties

  def __repr__(self):
    return u'CompositeEntry(%r, %r, %r, %r, %r, %r)' % (
      self.project_id, self.namespace, self.path, self.properties,
      self.commit_vs, self.deleted_vs)

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
  def __init__(self, tr, tornado_fdb, index, key_slice, fetch_limit, reverse,
               read_vs=None, snapshot=False):
    self.index = index
    self._kv_iterator = KVIterator(
      tr, tornado_fdb, key_slice, fetch_limit, reverse, snapshot=snapshot)
    self._read_vs = read_vs
    self._done = False

  @property
  def prop_names(self):
    return self.index.prop_names

  @property
  def start_key(self):
    return self._kv_iterator.slice.start.key

  @gen.coroutine
  def next_page(self):
    if self._done:
      raise gen.Return(([], False))

    kvs, more_results = yield self._kv_iterator.next_page()
    usable_entries = []
    for kv in kvs:
      entry = self.index.decode(kv)
      if not self._usable(entry):
        self._kv_iterator.increase_limit()
        more_results = not self._kv_iterator.done_with_range
        continue

      usable_entries.append(entry)

    if not more_results:
      self._done = True

    raise gen.Return((usable_entries, more_results))

  def _usable(self, entry):
    if self._read_vs and entry.deleted_vs:
      return entry.commit_vs < self._read_vs < entry.deleted_vs
    elif self._read_vs:
      return entry.commit_vs < self._read_vs
    else:
      return True


class MergeJoinIterator(object):
  def __init__(self, tr, tornado_fdb, filter_props, indexes, fetch_limit,
               read_vs=None, ancestor_path=None, snapshot=False):
    self.indexes = indexes
    self._filter_props = filter_props
    self._read_vs = read_vs
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

    result = None
    for i, (index, key_slice, prop_name, value) in enumerate(self.indexes):
      usable_entry = None
      # TODO: Keep cache of ranges to reduce unnecessary lookups.
      index_exhausted = False
      while True:
        kvs, count, more = yield self._tornado_fdb.get_range(
          self._tr, key_slice, 0, fdb.StreamingMode.small, 1,
          snapshot=self._snapshot)
        if not count:
          index_exhausted = True
          break

        key_slice = slice(fdb.KeySelector.first_greater_than(kvs[-1].key),
                          key_slice.stop)
        for kv in kvs:
          entry = index.decode(kv)
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

        result = CompositeEntry(
          usable_entry.project_id, usable_entry.namespace,
          self._candidate_path, properties, usable_entry.commit_vs,
          usable_entry.deleted_vs)
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

    results = [result] if result is not None else []
    self._fetched += len(results)
    if self._fetched == self._fetch_limit:
      self._done = True

    raise gen.Return((results, not self._done))

  def _usable(self, entry):
    if self._read_vs and entry.deleted_vs:
      return entry.commit_vs < self._read_vs < entry.deleted_vs
    elif self._read_vs:
      return entry.commit_vs < self._read_vs
    else:
      return True


class Index(object):
  """ The base class for different datastore index types. """
  __SLOTS__ = [u'directory']

  def __init__(self, directory):
    self.directory = directory

  @property
  def project_id(self):
    return self.directory.get_path()[2]

  @property
  def namespace(self):
    return self.directory.get_path()[4]

  @property
  def prop_names(self):
    return tuple()

  def pack_method(self, versionstamp):
    if versionstamp.is_complete():
      return self.directory.pack
    else:
      return self.directory.pack_with_versionstamp

  def encode_path(self, path):
    raise NotImplementedError()

  def get_slice(self, filter_props, ancestor_path=tuple(), start_cursor=None,
                end_cursor=None, reverse=False):
    subspace = self.directory
    start = None
    stop = None
    if ancestor_path:
      start, stop = encode_ancestor_range(subspace, ancestor_path)

    for filter_prop in filter_props:
      if filter_prop.name != KEY_PROP:
        raise BadRequest(u'Unexpected filter: {}'.format(filter_prop.name))

      if filter_prop.equality:
        encoded_path = self.encode_path(filter_prop.filters[0][1])
        subspace = subspace.subspace((encoded_path,))
        continue

      for op, value in filter_prop.filters:
        encoded_path = self.encode_path(value)
        if op in START_FILTERS:
          start = get_fdb_key_selector(op, subspace.pack((encoded_path,)))
        elif op in STOP_FILTERS:
          stop = get_fdb_key_selector(op, subspace.pack((encoded_path,)))
        else:
          raise BadRequest(u'Unexpected filter operation: {}'.format(op))

    if start_cursor is not None:
      encoded_path = self.encode_path(start_cursor.key().path())
      if not reverse:
        start = get_fdb_key_selector(Query_Filter.GREATER_THAN,
                                     subspace.pack((encoded_path,)))
      else:
        stop = get_fdb_key_selector(Query_Filter.LESS_THAN,
                                    subspace.pack((encoded_path,)))

    if end_cursor is not None:
      encoded_path = self.encode_path(start_cursor.key().path())
      if not reverse:
        stop = get_fdb_key_selector(Query_Filter.LESS_THAN_OR_EQUAL,
                                    subspace.pack((encoded_path,)))
      else:
        start = get_fdb_key_selector(Query_Filter.GREATER_THAN_OR_EQUAL,
                                     subspace.pack((encoded_path,)))

    selector = fdb.KeySelector.first_greater_or_equal
    start = start or selector(subspace.range().start)
    stop = stop or selector(subspace.range().stop)
    return slice(start, stop)


class KindlessIndex(Index):
  """
  A KindlessIndex handles the encoding and decoding details for kind index
  entries. These are just paths that point to entity keys.

  The FDB directory for a kindless index looks like
  (<project-dir>, 'indexes', <namespace>, 'kindless').

  Within this directory, keys are encoded as (<path-tuple>, <commit-vs>).

  The <path-tuple> is an encoded tuple containing the entity path.

  The <commit-vs> is a 10-byte versionstamp that specifies the commit version
  of the transaction that wrote the index entry.
  """
  DIR_NAME = u'kindless'

  def __repr__(self):
    return u'KindlessIndex(%r)' % self.directory

  def encode_path(self, path):
    if not isinstance(path, tuple):
      path = encode_path(path)

    return path

  def encode(self, path, commit_vs):
    return self.pack_method(commit_vs)((path, commit_vs))

  def decode(self, kv):
    path, commit_vs = self.directory.unpack(kv.key)
    deleted_vs = None
    if kv.value:
      deleted_vs = fdb.tuple.Versionstamp(kv.value)

    return IndexEntry(self.project_id, self.namespace, path, commit_vs,
                      deleted_vs)


class KindIndex(Index):
  """
  A KindIndex handles the encoding and decoding details for kind index entries.
  These are paths grouped by kind that point to entity keys.

  The FDB directory for a kind index looks like
  (<project-dir>, 'indexes', <namespace>, 'kind', <kind>).

  Within this directory, keys are encoded as
  (<kindless-path-tuple>, <commit-vs>).

  The <kindless-path-tuple> is an encoded tuple containing the entity path
  with the kind missing from the last path element. This is omitted since the
  directory path contains this.

  The <commit-vs> is a 10-byte versionstamp that specifies the commit version
  of the transaction that wrote the index entry.
  """
  DIR_NAME = u'kind'

  @property
  def kind(self):
    return self.directory.get_path()[-1]

  def __repr__(self):
    return u'KindIndex(%r)' % self.directory

  def encode_path(self, path):
    if not isinstance(path, tuple):
      path = encode_path(path)

    kindless_path = path[:-2] + path[-1:]
    return kindless_path

  def encode(self, path, commit_vs):
    return self.pack_method(commit_vs)((self.encode_path(path), commit_vs))

  def decode(self, kv):
    kindless_path, commit_vs = self.directory.unpack(kv.key)
    path = kindless_path[:-1] + (self.kind,) + kindless_path[-1:]
    deleted_vs = None
    if kv.value:
      deleted_vs = fdb.tuple.Versionstamp(kv.value)

    return IndexEntry(self.project_id, self.namespace, path, commit_vs,
                      deleted_vs)


class SinglePropIndex(Index):
  """
  A SinglePropIndex handles the encoding and decoding details for single-prop
  index entries. These are property values for a particular kind that point to
  entity keys.

  The FDB directory for a single-prop index looks like
  (<project-dir>, 'indexes', <namespace>, 'single-property', <kind>,
   <prop-name>).

  Within this directory, keys are encoded as
  (<encoded-value>, <kindless-path-tuple>, <commit-vs>).

  The <encoded-value> is a tuple in the form of
  (<encoded-type>, <encoded-value). See the codecs module for details about
  how different datastore value types are encoded.

  The <kindless-path-tuple> is an encoded tuple containing the entity path
  with the kind missing from the last path element. This is omitted since the
  directory path contains this.

  The <commit-vs> is a 10-byte versionstamp that specifies the commit version
  of the transaction that wrote the index entry.
  """
  DIR_NAME = u'single-property'

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

  def encode_path(self, path):
    if not isinstance(path, tuple):
      path = encode_path(path)

    kindless_path = path[:-2] + path[-1:]
    return kindless_path

  def encode(self, value, path, commit_vs):
    return self.pack_method(commit_vs)(
      (encode_value(value), self.encode_path(path), commit_vs))

  def decode(self, kv):
    encoded_value, kindless_path, commit_vs = self.directory.unpack(kv.key)
    value = decode_value(encoded_value)
    path = kindless_path[:-1] + (self.kind,) + kindless_path[-1:]
    deleted_vs = None
    if kv.value:
      deleted_vs = fdb.tuple.Versionstamp(kv.value)

    return PropertyEntry(self.project_id, self.namespace, path, self.prop_name,
                         value, commit_vs, deleted_vs)

  def get_slice(self, filter_props, ancestor_path=tuple(), start_cursor=None,
                end_cursor=None, reverse=False):
    subspace = self.directory
    start = None
    stop = None
    if ancestor_path:
      # Apply property equality first if it exists.
      if filter_props and filter_props[0].name == self.prop_name:
        if not filter_props[0].equality:
          raise BadRequest(u'Invalid index for ancestor query')

        value = filter_props[0].filters[0][1]
        subspace = subspace.subspace((encode_value(value),))
        filter_props = filter_props[1:]

      start, stop = encode_ancestor_range(subspace, ancestor_path)

    for filter_prop in filter_props:
      if filter_prop.name == self.prop_name:
        encoder = encode_value
      elif filter_prop.name == KEY_PROP:
        encoder = self.encode_path
      else:
        raise BadRequest(u'Unexpected filter: {}'.format(filter_prop.name))

      if filter_prop.equality:
        encoded_value = encoder(filter_prop.filters[0][1])
        subspace = subspace.subspace((encoded_value,))
        continue

      for op, value in filter_prop.filters:
        encoded_value = encoder(value)
        if op in START_FILTERS:
          start = get_fdb_key_selector(op, subspace.pack((encoded_value,)))
        elif op in STOP_FILTERS:
          stop = get_fdb_key_selector(op, subspace.pack((encoded_value,)))
        else:
          raise BadRequest(u'Unexpected filter operation: {}'.format(op))

    if start_cursor is not None:
      if not reverse and start is not None:
        unpacked_key = self.directory.unpack(start.key)
      elif reverse and stop is not None:
        unpacked_key = self.directory.unpack(stop.key)
      else:
        unpacked_key = self.directory.unpack(subspace.rawPrefix)

      cursor_prop = next((prop for prop in start_cursor.property_list()
                         if prop.name() == self.prop_name), None)
      if cursor_prop is None:
        encoded_value = unpacked_key[0]
      else:
        encoded_value = encode_value(cursor_prop.value())

      encoded_path = self.encode_path(start_cursor.key().path())
      encoded_cursor = (encoded_value, encoded_path)
      if not reverse:
        start = get_fdb_key_selector(Query_Filter.GREATER_THAN,
                                     self.directory.pack(encoded_cursor))
      else:
        stop = get_fdb_key_selector(Query_Filter.LESS_THAN,
                                    self.directory.pack(encoded_cursor))

    if end_cursor is not None:
      if not reverse and stop is not None:
        unpacked_key = self.directory.unpack(stop.key)
      elif reverse and start is not None:
        unpacked_key = self.directory.unpack(start.key)
      else:
        unpacked_key = self.directory.unpack(subspace.rawPrefix)

      cursor_prop = next((prop for prop in end_cursor.property_list()
                         if prop.name() == self.prop_name), None)
      if cursor_prop is None:
        encoded_value = unpacked_key[0]
      else:
        encoded_value = encode_value(cursor_prop.value())

      encoded_path = self.encode_path(end_cursor.key().path())
      encoded_cursor = (encoded_value, encoded_path)
      if not reverse:
        stop = get_fdb_key_selector(Query_Filter.LESS_THAN_OR_EQUAL,
                                    self.directory.pack(encoded_cursor))
      else:
        start = get_fdb_key_selector(Query_Filter.GREATER_THAN_OR_EQUAL,
                                     self.directory.pack(encoded_cursor))

    selector = fdb.KeySelector.first_greater_or_equal
    start = start or selector(subspace.range().start)
    stop = stop or selector(subspace.range().stop)
    return slice(start, stop)


class CompositeIndex(Index):
  """
  A CompositeIndex handles the encoding and decoding details for composite
  index entries.

  The FDB directory for a composite index looks like
  (<project-dir>, 'indexes', <namespace>, 'composite', <index-id>).

  Within this directory, keys are encoded as
  (<ancestor-fragment (optional)>, <encoded-values>, <remaining-path-tuple>,
   <commit-vs>).

  If the index definition requires an ancestor, the <ancestor-fragment>
  contains an encoded tuple specifying the full or partial path of the entity's
  ancestor. The number of entries written for ancestor composite indexes is
  equal to the number of ancestor path elements. For example, an entity with
  three path elements would be encoded with the following two entries:
  (('Kind1', 'key1'), <encoded-values>, ('Kind2', 'key2', 'key3'), <commit-vs>)
  (('Kind1', 'key1, 'Kind2', 'key2'), <encoded-values>, ('key3',), <commit-vs>)

  The <encoded-values> portion is a nested tuple in the form of
  (<encoded-value1>, <encoded-value2>, ...). The number of values depends on
  the index definition. Each <encoded-value> is a tuple in the form of
  (<encoded-type>, <encoded-value). See the codecs module for details about how
  different datastore value types are encoded.

  The <remaining-path-tuple> is an encoded tuple containing the portion of the
  entity path that isn't specified by the <ancestor-fragment>. If the index
  definition does not require an ancestor, this is equivalent to the
  <kindless-path> portion of a kind or single-prop index.

  The <commit-vs> is a 10-byte versionstamp that specifies the commit version
  of the transaction that wrote the index entry.
  """
  __SLOTS__ = [u'kind', u'ancestor', u'order_info']

  DIR_NAME = u'composite'

  def __init__(self, directory, kind, ancestor, order_info):
    super(CompositeIndex, self).__init__(directory)
    self.kind = kind
    self.ancestor = ancestor
    self.order_info = order_info

  @property
  def id(self):
    return int(self.directory.get_path()[6])

  @property
  def prop_names(self):
    return tuple(prop_name for prop_name, _ in self.order_info)

  def __repr__(self):
    return u'CompositeIndex(%r, %r, %r, %r)' % (
      self.directory, self.kind, self.ancestor, self.order_info)

  def encode_path(self, path):
    if not isinstance(path, tuple):
      path = encode_path(path)

    kindless_path = path[:-2] + path[-1:]
    return kindless_path

  def encode(self, prop_list, path, commit_vs):
    encoded_values_by_prop = []
    for index_prop_name, direction in self.order_info:
      reverse = direction == Query_Order.DESCENDING
      encoded_values_by_prop.append(
        tuple(encode_value(prop.value(), reverse) for prop in prop_list
              if prop.name() == index_prop_name))

    pack = self.pack_method(commit_vs)
    encoded_value_combos = itertools.product(*encoded_values_by_prop)
    if not self.ancestor:
      return tuple(pack(values + (self.encode_path(path),) + (commit_vs,))
                   for values in encoded_value_combos)

    keys = []
    for index in range(2, len(path), 2):
      ancestor_path = path[:index]
      remaining_path = self.encode_path(path[index:])
      keys.extend(
        [pack((ancestor_path,) + values + (remaining_path,) + (commit_vs,))
         for values in encoded_value_combos])

    return tuple(keys)

  def decode(self, kv):
    unpacked_key = self.directory.unpack(kv.key)
    if self.ancestor:
      kindless_path = unpacked_key[0] + unpacked_key[-2]
      values = unpacked_key[1:-2]
    else:
      kindless_path = unpacked_key[-2]
      values = unpacked_key[:-2]

    properties = []
    for index, prop_name in enumerate(self.prop_names):
      properties.append((prop_name, decode_value(values[index])))

    path = kindless_path[:-1] + (self.kind,) + kindless_path[-1:]
    commit_vs = unpacked_key[-1]
    deleted_vs = None
    if kv.value:
      deleted_vs = fdb.tuple.Versionstamp(kv.value)

    return CompositeEntry(self.project_id, self.namespace, path, properties,
                          commit_vs, deleted_vs)

  def get_slice(self, filter_props, ancestor_path=tuple(), start_cursor=None,
                end_cursor=None, reverse=False):
    subspace = self.directory
    if ancestor_path:
      subspace = subspace.subspace((ancestor_path,))

    start = None
    stop = None

    ordered_filter_props = []
    for prop_name in self.prop_names + (KEY_PROP,):
      try:
        filter_prop = next(filter_prop for filter_prop in filter_props
                           if filter_prop.name == prop_name)
        ordered_filter_props.append(filter_prop)
      except StopIteration:
        continue

    for filter_prop in ordered_filter_props:
      index_direction = next(
        (direction for name, direction in self.order_info
         if name == filter_prop.name), Query_Order.ASCENDING)
      reverse = index_direction == Query_Order.DESCENDING
      if filter_prop.name in self.prop_names:
        encoder = lambda val: encode_value(val, reverse)
      elif filter_prop.name == KEY_PROP:
        encoder = self.encode_path
      else:
        raise BadRequest(u'Unexpected filter: {}'.format(filter_prop.name))

      if filter_prop.equality:
        encoded_value = encoder(filter_prop.filters[0][1])
        subspace = subspace.subspace((encoded_value,))
        continue

      for op, value in filter_prop.filters:
        if filter_prop.name == KEY_PROP:
          encoded_value = self.encode_path(value)
        else:
          encoded_value = encoder(value)

        selector = get_fdb_key_selector(op, subspace.pack((encoded_value,)))
        if ((op in START_FILTERS and not reverse) or
            (op in STOP_FILTERS and reverse)):
          start = selector
        elif ((op in STOP_FILTERS and not reverse) or
              (op in START_FILTERS and reverse)):
          stop = selector
        else:
          raise BadRequest(u'Unexpected filter operation: {}'.format(op))

    if start_cursor is not None:
      if not reverse and start is not None:
        unpacked_key = self.directory.unpack(start.key)
      elif reverse and stop is not None:
        unpacked_key = self.directory.unpack(stop.key)
      else:
        unpacked_key = self.directory.unpack(subspace.rawPrefix)

      if self.ancestor:
        unpacked_values = unpacked_key[1:]
      else:
        unpacked_values = unpacked_key[:]

      full_path = encode_path(start_cursor.key().path())
      remaining_path = self.encode_path(full_path[len(ancestor_path):])
      encoded_values = []
      for i, (prop_name, index_direction) in enumerate(self.order_info):
        cursor_prop = next((prop for prop in start_cursor.property_list()
                            if prop.name() == prop_name), None)
        if cursor_prop is None:
          encoded_value = unpacked_values[i]
        else:
          reverse_encode = index_direction == Query_Order.DESCENDING
          encoded_value = encode_value(cursor_prop.value(), reverse_encode)

        encoded_values.append(encoded_value)

      if self.ancestor:
        encoded_cursor = ((ancestor_path,) + tuple(encoded_values) +
                          (remaining_path,))
      else:
        encoded_cursor = (tuple(encoded_values) + (remaining_path,))

      if not reverse:
        start = get_fdb_key_selector(Query_Filter.GREATER_THAN,
                                     self.directory.pack(encoded_cursor))
      else:
        stop = get_fdb_key_selector(Query_Filter.LESS_THAN,
                                    self.directory.pack(encoded_cursor))

    if end_cursor is not None:
      if not reverse and stop is not None:
        unpacked_key = self.directory.unpack(stop.key)
      elif reverse and start is not None:
        unpacked_key = self.directory.unpack(start.key)
      else:
        unpacked_key = self.directory.unpack(subspace.rawPrefix)

      if self.ancestor:
        unpacked_values = unpacked_key[1:]
      else:
        unpacked_values = unpacked_key[:]

      full_path = encode_path(end_cursor.key().path())
      remaining_path = self.encode_path(full_path[len(ancestor_path):])
      encoded_values = []
      for i, (prop_name, index_direction) in enumerate(self.order_info):
        cursor_prop = next((prop for prop in end_cursor.property_list()
                            if prop.name() == prop_name), None)
        if cursor_prop is None:
          encoded_value = unpacked_values[i]
        else:
          reverse_encode = index_direction == Query_Order.DESCENDING
          encoded_value = encode_value(cursor_prop.value(), reverse_encode)

        encoded_values.append(encoded_value)

      if self.ancestor:
        encoded_cursor = ((ancestor_path,) + tuple(encoded_values) +
                          (remaining_path,))
      else:
        encoded_cursor = (tuple(encoded_values) + (remaining_path,))

      if not reverse:
        stop = get_fdb_key_selector(Query_Filter.LESS_THAN_OR_EQUAL,
                                    self.directory.pack(encoded_cursor))
      else:
        start = get_fdb_key_selector(Query_Filter.GREATER_THAN_OR_EQUAL,
                                     self.directory.pack(encoded_cursor))

    selector = fdb.KeySelector.first_greater_or_equal
    start = start or selector(subspace.range().start)
    stop = stop or selector(subspace.range().stop)
    return slice(start, stop)


class IndexManager(object):
  """
  The IndexManager is the main interface that clients can use to interact with
  the index layer. It makes use of KindlessIndex, KindIndex, SinglePropIndex,
  and CompositeIndex namespace directories to handle the encoding and decoding
  details when satisfying requests. When a client requests data, the
  IndexManager encapsulates index data in an IndexEntry object.
  """
  _MAX_RESULTS = 300

  def __init__(self, db, tornado_fdb, data_manager, project_cache):
    self.composite_index_manager = None
    self._db = db
    self._tornado_fdb = tornado_fdb
    self._data_manager = data_manager
    self._project_cache = project_cache
    self._kindless_index_cache = NSCache(
      self._tornado_fdb, self._project_cache, KindlessIndex)
    self._kind_index_cache = NSCache(
      self._tornado_fdb, self._project_cache, KindIndex)
    self._single_prop_index_cache = NSCache(
      self._tornado_fdb, self._project_cache, SinglePropIndex)
    self._composite_index_cache = NSCache(
      self._tornado_fdb, self._project_cache, CompositeIndex)

  @gen.coroutine
  def put_entries(self, tr, old_entity, old_vs, new_entity):
    if old_entity is not None:
      keys = yield self._get_index_keys(tr, old_entity, old_vs)
      for key in keys:
        tr.set_versionstamped_value(key, b'\x00' * 14)

    if new_entity is not None:
      keys = yield self._get_index_keys(tr, new_entity)
      for key in keys:
        tr.set_versionstamped_key(key, b'')

  @gen.coroutine
  def hard_delete_entries(self, tr, old_entity, old_vs):
    keys = self._get_index_keys(tr, old_entity, old_vs)
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
  def get_iterator(self, tr, query, read_vs=None):
    project_id = decode_str(query.app())
    namespace = decode_str(query.name_space())
    filter_props = group_filters(query)
    ancestor_path = tuple()
    if query.has_ancestor():
      ancestor_path = encode_path(query.ancestor().path())

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
        index = yield self._single_prop_index_cache.get(
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
                          fetch_limit, read_vs, ancestor_path, snapshot=True))

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
                          fetch_limit, read_vs, ancestor_path, snapshot=True))

    desired_slice = index.get_slice(filter_props, ancestor_path, start_cursor,
                                    end_cursor, reverse)

    iterator = IndexIterator(tr, self._tornado_fdb, index, desired_slice,
                             fetch_limit, reverse, read_vs, snapshot=True)

    raise gen.Return(iterator)

  @gen.coroutine
  def _get_index_keys(self, tr, entity, commit_vs=None):
    if commit_vs is None:
      commit_vs = fdb.tuple.Versionstamp()

    project_id = decode_str(entity.key().app())
    namespace = decode_str(entity.key().name_space())
    path = encode_path(entity.key().path())
    kind = path[-2]

    kindless_index = yield self._kindless_index_cache.get(
      tr, project_id, namespace)
    kind_index = yield self._kind_index_cache.get(
      tr, project_id, namespace, kind)
    composite_indexes = yield self._get_indexes(
      tr, project_id, namespace, kind)

    all_keys = [kindless_index.encode(path, commit_vs),
                kind_index.encode(path, commit_vs)]
    entity_prop_names = []
    for prop in entity.property_list():
      prop_name = decode_str(prop.name())
      entity_prop_names.append(prop_name)
      index = yield self._single_prop_index_cache.get(
        tr, project_id, namespace, kind, prop_name)
      all_keys.append(index.encode(prop.value(), path, commit_vs))

    scatter_val = get_scatter_val(path)
    if scatter_val is not None:
      index = yield self._single_prop_index_cache.get(
        tr, project_id, namespace, kind, SCATTER_PROP)
      all_keys.append(index.encode(scatter_val, path, commit_vs))

    for index in composite_indexes:
      if not all(index_prop_name in entity_prop_names
                 for index_prop_name in index.prop_names):
        continue

      all_keys.extend(index.encode(entity.property_list(), path, commit_vs))

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

      kindless_index = yield self._kindless_index_cache.get(
        tr, project_id, namespace)
      raise gen.Return(kindless_index)

    kind = decode_str(query.kind())
    if all(prop_name == KEY_PROP for prop_name in prop_names):
      kind_index = yield self._kind_index_cache.get(
        tr, project_id, namespace, kind)
      raise gen.Return(kind_index)

    if sum(prop_name != KEY_PROP for prop_name in prop_names) == 1:
      prop_name = next(prop_name for prop_name in prop_names
                       if prop_name != KEY_PROP)
      ordered_prop = prop_name in [order_name for order_name, _ in order_info]
      if not query.has_ancestor() or not ordered_prop:
        single_prop_index = yield self._single_prop_index_cache.get(
          tr, project_id, namespace, decode_str(query.kind()), prop_name)
        raise gen.Return(single_prop_index)

    index_pb = _FindIndexToUse(query, self._get_indexes_pb(project_id))
    if index_pb is not None:
      index_order_info = tuple(
        (decode_str(prop.name()), prop.direction())
        for prop in index_pb.definition().property_list())
      composite_index = yield self._composite_index_cache.get(
        tr, project_id, namespace, index_pb.id(), kind=kind,
        ancestor=index_pb.definition().ancestor(), order_info=index_order_info)
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

      composite_index = yield self._composite_index_cache.get(
        tr, project_id, namespace, index.id, kind=index.kind,
        ancestor=index.ancestor, order_info=order_info)
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
  def update_composite_index(self, project_id, index_pb, cursor=(None, None)):
    start_ns, start_key = cursor
    kind = decode_str(index_pb.definition().entity_type())
    ancestor = index_pb.definition().ancestor()
    order_info = ((prop.name(), prop.direction())
                  for prop in index_pb.definition().property_list())

    tr = self._db.create_transaction()
    project_dir = yield self._project_cache.get(tr, project_id)
    # TODO: Make async.
    indexes_dir = project_dir.create_or_open(tr, (INDEX_DIR,))
    deadline = monotonic.monotonic() + MAX_FDB_TX_DURATION / 2
    for namespace in indexes_dir.list(tr):
      if start_ns is not None and namespace < start_ns:
        continue

      u_index_id = six.text_type(index_pb.id())
      # TODO: Make async.
      composite_index_dir = indexes_dir.create_or_open(
        tr, (namespace, CompositeIndex.DIR_NAME, u_index_id))
      composite_index = CompositeIndex(composite_index_dir, kind, ancestor,
                                       order_info)
      logger.info(u'Backfilling {}'.format(composite_index))
      try:
        # TODO: Make async.
        kind_index_dir = indexes_dir.open(
          tr, (namespace, KindIndex.DIR_NAME, kind))
      except ValueError:
        logger.info(u'No entities exist for {}'.format(composite_index))
        continue

      kind_index = KindIndex(kind_index_dir)
      remaining_range = kind_index_dir.range()
      if start_key is not None:
        remaining_range = slice(
          fdb.KeySelector.first_greater_than(start_key), remaining_range.stop)
        start_key = None

      kv_iterator = KVIterator(tr, self._tornado_fdb, remaining_range)
      while True:
        kvs, more_results = yield kv_iterator.next_page()
        entries = [kind_index.decode(kv) for kv in kvs]
        entity_results = yield [self._data_manager.get_entry(self, tr, entry)
                                for entry in entries]
        for index, kv in enumerate(kvs):
          entity = entity_pb.EntityProto(entity_results[index].encoded_entity)
          entry = entries[index]
          keys = composite_index.encode(
            entity.property_list(), entry.path, entry.commit_vs)
          for key in keys:
            deleted_val = (entry.deleted_vs.to_bytes()
                           if entry.deleted_vs.is_complete() else b'')
            tr[key] = deleted_val

        if not more_results:
          logger.info(u'Finished backfilling {}'.format(composite_index))
          break

        if monotonic.monotonic() > deadline:
          try:
            yield self._tornado_fdb.commit(tr)
            cursor = (namespace, kvs[-1].key)
          except fdb.FDBError as fdb_error:
            logger.warning(u'Error while updating index: {}'.format(fdb_error))
            tr.on_error(fdb_error).wait()

          yield self.update_composite_index(project_id, index_pb, cursor)
          return
