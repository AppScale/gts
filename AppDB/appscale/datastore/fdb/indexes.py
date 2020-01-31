"""
This module stores and queries entity indexes. The IndexManager is the main
interface that clients can use to interact with the index layer. See its
documentation for implementation details.
"""
from __future__ import division

import logging
import sys

from tornado import gen

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.fdb import codecs
from appscale.datastore.fdb.codecs import (
  decode_str, encode_versionstamp_index, Path)
from appscale.datastore.fdb.composite_indexes import CompositeIndexManager
from appscale.datastore.fdb.index_directories import (
  CompositeEntry, CompositeIndex, IndexEntry, KEY_PROP, KindIndex,
  KindlessIndex, PropertyEntry, SinglePropIndex)
from appscale.datastore.fdb.sdk import FindIndexToUse, ListCursor
from appscale.datastore.fdb.stats.containers import IndexStatsSummary
from appscale.datastore.fdb.utils import (
  fdb, get_scatter_val, ResultIterator, SCATTER_PROP, VERSIONSTAMP_SIZE)
from appscale.datastore.dbconstants import BadRequest, InternalError

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb
from google.appengine.datastore.datastore_pb import Query_Filter, Query_Order

logger = logging.getLogger(__name__)


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


class NamespaceIterator(object):
  """ Iterates over a list of namespaces in a project. """
  def __init__(self, tr, tornado_fdb, project_dir):
    self._tr = tr
    self._tornado_fdb = tornado_fdb
    self._project_dir = project_dir
    self._done = False

  @gen.coroutine
  def next_page(self):
    if self._done:
      raise gen.Return(([], False))

    # TODO: This can be made async.
    ns_dir = self._project_dir.open(self._tr, (KindIndex.DIR_NAME,))
    namespaces = ns_dir.list(self._tr)

    # Filter out namespaces that don't have at least one kind.
    kinds_by_ns = yield [KindIterator(self._tr, self._tornado_fdb,
                                      self._project_dir, namespace).next_page()
                         for namespace in namespaces]
    namespaces = [
      namespace for namespace, (kinds, _) in zip(namespaces, kinds_by_ns)
      if kinds]

    # The API uses an ID of 1 to label the default namespace.
    results = [IndexEntry(self._project_dir.get_path()[-1], u'',
                          (u'__namespace__', namespace or 1), None, None)
               for namespace in namespaces]

    self._done = True
    raise gen.Return((results, False))


class KindIterator(object):
  """ Iterates over a list of kinds in a namespace. """
  def __init__(self, tr, tornado_fdb, project_dir, namespace):
    self._tr = tr
    self._tornado_fdb = tornado_fdb
    self._project_dir = project_dir
    self._namespace = namespace
    self._done = False

  @gen.coroutine
  def next_page(self):
    if self._done:
      raise gen.Return(([], False))

    # TODO: This can be made async.
    try:
      ns_dir = self._project_dir.open(
        self._tr, (KindIndex.DIR_NAME, self._namespace))
    except ValueError:
      # If the namespace does not exist, there are no kinds there.
      raise gen.Return(([], False))

    kinds = ns_dir.list(self._tr)
    populated_kinds = [
      kind for kind, populated in zip(
        kinds, (yield [self._populated(ns_dir, kind) for kind in kinds]))
      if populated]

    results = [IndexEntry(self._project_dir.get_path()[-1], self._namespace,
                          (u'__kind__', kind), None, None)
               for kind in populated_kinds]

    self._done = True
    raise gen.Return((results, False))

  @gen.coroutine
  def _populated(self, ns_dir, kind):
    """ Checks if at least one entity exists for a given kind. """
    kind_dir = ns_dir.open(self._tr, (kind,))
    kind_index = KindIndex(kind_dir)
    # TODO: Check if the presence of stat entities should mark a kind as being
    #  populated.
    index_slice = kind_index.get_slice(())
    # This query is reversed to increase the likelihood of getting a relevant
    # (not marked for GC) entry.
    iterator = IndexIterator(self._tr, self._tornado_fdb, kind_index,
                             index_slice, fetch_limit=1, reverse=True,
                             snapshot=True)
    while True:
      results, more_results = yield iterator.next_page()
      if results:
        raise gen.Return(True)

      if not more_results:
        raise gen.Return(False)


class PropertyIterator(object):
  """ Iterates over a list of indexed property names for a kind. """
  PROPERTY_TYPES = (u'NULL', u'INT64', u'BOOLEAN', u'STRING', u'DOUBLE',
                    u'POINT', u'USER', u'REFERENCE')

  def __init__(self, tr, tornado_fdb, project_dir, namespace):
    self._tr = tr
    self._tornado_fdb = tornado_fdb
    self._project_dir = project_dir
    self._namespace = namespace
    self._done = False

  @gen.coroutine
  def next_page(self):
    if self._done:
      raise gen.Return(([], False))

    # TODO: This can be made async.
    ns_dir = self._project_dir.open(
      self._tr, (SinglePropIndex.DIR_NAME, self._namespace))
    kinds = ns_dir.list(self._tr)
    # TODO: Check if stat entities belong in kinds.
    kind_dirs = [ns_dir.open(self._tr, (kind,)) for kind in kinds]
    results = []
    for kind, kind_dir in zip(kinds, kind_dirs):
      # TODO: This can be made async.
      prop_names = kind_dir.list(self._tr)
      for prop_name in prop_names:
        prop_dir = kind_dir.open(self._tr, (prop_name,))
        index = SinglePropIndex(prop_dir)
        populated_map = yield [self._populated(index, type_name)
                               for type_name in self.PROPERTY_TYPES]
        populated_types = tuple(
          type_ for type_, populated in zip(self.PROPERTY_TYPES, populated_map)
          if populated)
        if not populated_types:
          continue

        project_id = self._project_dir.get_path()[-1]
        path = (u'__kind__', kind, u'__property__', prop_name)
        prop_values = []
        for prop_type in populated_types:
          prop_value = entity_pb.PropertyValue()
          prop_value.set_stringvalue(prop_type)
          prop_values.append(prop_value)

        # TODO: Consider giving metadata results their own entry class.
        entry = CompositeEntry(
          project_id, self._namespace, path,
          [(u'property_representation', prop_values)], None, None)
        results.append(entry)

    self._done = True
    raise gen.Return((results, False))

  @gen.coroutine
  def _populated(self, prop_index, type_name):
    """ Checks if at least one entity exists for a given type name. """
    index_slice = prop_index.type_range(type_name)
    # This query is reversed to increase the likelihood of getting a relevant
    # (not marked for GC) entry.
    iterator = IndexIterator(self._tr, self._tornado_fdb, prop_index,
                             index_slice, fetch_limit=1, reverse=True,
                             snapshot=True)
    while True:
      results, more_results = yield iterator.next_page()
      if results:
        raise gen.Return(True)

      if not more_results:
        raise gen.Return(False)


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
    self._db = db
    self._tornado_fdb = tornado_fdb
    self._data_manager = data_manager
    self._directory_cache = directory_cache
    self._composite_index_manager = CompositeIndexManager(
      self._db, self._tornado_fdb, self._data_manager, self._directory_cache)

  def start(self):
    self._composite_index_manager.start()

  @gen.coroutine
  def put_entries(self, tr, old_version_entry, new_entity):
    old_key_stats = IndexStatsSummary()
    if old_version_entry.has_entity:
      old_keys, old_key_stats = yield self._get_index_keys(
        tr, old_version_entry.decoded, old_version_entry.commit_versionstamp)
      for key in old_keys:
        # Set deleted versionstamp.
        tr.set_versionstamped_value(
          key, b'\x00' * VERSIONSTAMP_SIZE + encode_versionstamp_index(0))

    new_key_stats = IndexStatsSummary()
    if new_entity is not None:
      new_keys, new_key_stats = yield self._get_index_keys(
        tr, new_entity)
      for key in new_keys:
        tr.set_versionstamped_key(key, b'')

    raise gen.Return(new_key_stats - old_key_stats)

  @gen.coroutine
  def hard_delete_entries(self, tr, version_entry):
    if not version_entry.has_entity:
      return

    keys = (yield self._get_index_keys(tr, version_entry.decoded,
                                       version_entry.commit_versionstamp))[0]
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

    if query.has_kind() and query.kind() == u'__namespace__':
      project_dir = yield self._directory_cache.get(tr, (project_id,))
      raise gen.Return(NamespaceIterator(tr, self._tornado_fdb, project_dir))
    elif query.has_kind() and query.kind() == u'__kind__':
      project_dir = yield self._directory_cache.get(tr, (project_id,))
      raise gen.Return(KindIterator(tr, self._tornado_fdb, project_dir,
                                    namespace))
    elif query.has_kind() and query.kind() == u'__property__':
      project_dir = yield self._directory_cache.get(tr, (project_id,))
      raise gen.Return(PropertyIterator(tr, self._tornado_fdb, project_dir,
                                        namespace))

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
  def merge(self, tr, project_id, new_indexes):
    yield self._composite_index_manager.merge(tr, project_id, new_indexes)

  @gen.coroutine
  def update_composite_index(self, project_id, index):
    yield self._composite_index_manager.update_composite_index(
      project_id, index)

  @gen.coroutine
  def _get_index_keys(self, tr, entity, commit_versionstamp=None):
    has_index = commit_versionstamp is None
    project_id = decode_str(entity.key().app())
    namespace = decode_str(entity.key().name_space())
    path = Path.flatten(entity.key().path())
    kind = path[-2]

    stats = IndexStatsSummary()
    kindless_index = yield self._kindless_index(tr, project_id, namespace)
    kind_index = yield self._kind_index(tr, project_id, namespace, kind)
    composite_indexes = yield self._get_indexes(
      tr, project_id, namespace, kind)

    kindless_key = kindless_index.encode_key(path, commit_versionstamp)
    kind_key = kind_index.encode_key(path, commit_versionstamp)
    stats.add_kindless_key(kindless_key, has_index)
    stats.add_kind_key(kind_key, has_index)
    all_keys = [kindless_key, kind_key]
    entity_prop_names = []
    for prop in entity.property_list():
      prop_name = decode_str(prop.name())
      entity_prop_names.append(prop_name)
      index = yield self._single_prop_index(
        tr, project_id, namespace, kind, prop_name)
      prop_key = index.encode_key(prop.value(), path, commit_versionstamp)
      stats.add_prop_key(prop, prop_key, has_index)
      all_keys.append(prop_key)

    scatter_val = get_scatter_val(path)
    if scatter_val is not None:
      index = yield self._single_prop_index(
        tr, project_id, namespace, kind, SCATTER_PROP)
      all_keys.append(index.encode_key(scatter_val, path, commit_versionstamp))

    for index in composite_indexes:
      # If the entity does not have the relevant props for the index, skip it.
      if not all(index_prop_name in entity_prop_names
                 for index_prop_name in index.prop_names):
        continue

      composite_keys = index.encode_keys(entity.property_list(), path,
                                         commit_versionstamp)
      stats.add_composite_keys(index.id, composite_keys, has_index)
      all_keys.extend(composite_keys)

    raise gen.Return((all_keys, stats))

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

    queryable = [
      index.to_pb() for index in (
        yield self._composite_index_manager.get_definitions(tr, project_id))
      if index.ready]
    index_pb = FindIndexToUse(query, queryable)
    if index_pb is not None:
      composite_index = yield self._composite_index(
        tr, project_id, index_pb.id(), namespace)
      raise gen.Return(composite_index)

  @gen.coroutine
  def _get_indexes(self, tr, project_id, namespace, kind):
    project_indexes = yield self._composite_index_manager.get_definitions(
      tr, project_id)

    relevant_indexes = [index for index in project_indexes
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
    kind, ancestor, order_info = yield self._index_details(
      tr, project_id, index_id)
    raise gen.Return(CompositeIndex(directory, kind, ancestor, order_info))

  @gen.coroutine
  def _index_details(self, tr, project_id, index_id):
    project_indexes = yield self._composite_index_manager.get_definitions(
      tr, project_id)
    index_def = next((ds_index for ds_index in project_indexes
                      if ds_index.id == index_id), None)
    if index_def is None:
      raise InternalError(u'Unable to retrieve index details')

    order_info = tuple(
      (decode_str(prop.name), prop.to_pb().direction())
      for prop in index_def.properties)
    raise gen.Return((index_def.kind, index_def.ancestor, order_info))
