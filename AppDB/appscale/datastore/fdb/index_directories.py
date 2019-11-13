import itertools
import sys

import six

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.dbconstants import BadRequest, InternalError
from appscale.datastore.fdb.codecs import (
  decode_value, encode_value, encode_versionstamp_index, Path)
from appscale.datastore.fdb.utils import (
  DS_ROOT, fdb, format_prop_val, VERSIONSTAMP_SIZE)

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import datastore_pb, entity_pb
from google.appengine.datastore.datastore_pb import Query_Filter, Query_Order

first_gt_or_equal = fdb.KeySelector.first_greater_or_equal

KEY_PROP = u'__key__'


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
  def kind(self):
    return self.path[-2]

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

    def add_prop(prop_name, multiple, value):
      prop = entity.add_property()
      prop.set_name(prop_name)
      prop.set_meaning(entity_pb.Property.INDEX_VALUE)
      prop.set_multiple(multiple)
      prop.mutable_value().MergeFrom(value)

    for prop_name, value in self.properties:
      if isinstance(value, list):
        for multiple_val in value:
          add_prop(prop_name, True, multiple_val)
      else:
        add_prop(prop_name, False, value)

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

  def type_range(self, type_name):
    """ Returns a slice that encompasses all values for a property type. """
    if type_name == u'NULL':
      start = six.int2byte(codecs.NULL_CODE)
      stop = six.int2byte(codecs.NULL_CODE + 1)
    elif type_name == u'INT64':
      start = six.int2byte(codecs.MIN_INT64_CODE)
      stop = six.int2byte(codecs.MAX_INT64_CODE + 1)
    elif type_name == u'BOOLEAN':
      start = six.int2byte(codecs.FALSE_CODE)
      stop = six.int2byte(codecs.TRUE_CODE + 1)
    elif type_name == u'STRING':
      start = six.int2byte(codecs.BYTES_CODE)
      stop = six.int2byte(codecs.BYTES_CODE + 1)
    elif type_name == u'DOUBLE':
      start = six.int2byte(codecs.DOUBLE_CODE)
      stop = six.int2byte(codecs.DOUBLE_CODE + 1)
    elif type_name == u'POINT':
      start = six.int2byte(codecs.POINT_CODE)
      stop = six.int2byte(codecs.POINT_CODE + 1)
    elif type_name == u'USER':
      start = six.int2byte(codecs.USER_CODE)
      stop = six.int2byte(codecs.USER_CODE + 1)
    elif type_name == u'REFERENCE':
      start = six.int2byte(codecs.REFERENCE_CODE)
      stop = six.int2byte(codecs.REFERENCE_CODE + 1)
    else:
      raise InternalError(u'Unknown type name')

    return slice(self.directory.rawPrefix + start,
                 self.directory.rawPrefix + stop)


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
