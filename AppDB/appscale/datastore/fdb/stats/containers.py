"""
There are five main stats sections.
- composite-indexes: (namespace, index_id, kind, count/bytes)
- builtin-indexes: (namespace, kind, is_root, count/bytes)
- entities: (namespace, kind, is_root, count/bytes)
- entity-properties: (namespace, kind, prop_type, prop_name, count/bytes)
- index-properties: (namespace, kind, prop_type, prop_name, count/bytes)
"""
import logging
import sys
from collections import defaultdict

import six

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.fdb.codecs import decode_str
from appscale.datastore.fdb.utils import decode_delta, encode_delta

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore.entity_pb import Property as Meaning

logger = logging.getLogger(__name__)


class StatsPropTypes(object):
  STRING = 0x01
  BOOLEAN = 0x02
  INTEGER = 0x03
  NULL = 0x04
  FLOAT = 0x05
  KEY = 0x06
  BLOB = 0x07
  EMBEDDED_ENTITY = 0x08
  SHORT_BLOB = 0x09
  TEXT = 0x0A
  USER = 0x0B
  CATEGORY = 0x0C
  LINK = 0x0D
  EMAIL = 0x0E
  DATE_TIME = 0x0F
  GEO_PT = 0x10
  IM = 0x11
  PHONE_NUMBER = 0x12
  POSTAL_ADDRESS = 0x13
  RATING = 0x14
  BLOB_KEY = 0x15

  MEANING_TYPES = {
    Meaning.GD_WHEN: DATE_TIME,
    Meaning.ATOM_CATEGORY: CATEGORY,
    Meaning.ATOM_LINK: LINK,
    Meaning.GD_EMAIL: EMAIL,
    Meaning.GD_IM: IM,
    Meaning.GD_PHONENUMBER: PHONE_NUMBER,
    Meaning.GD_POSTALADDRESS: POSTAL_ADDRESS,
    Meaning.GD_RATING: RATING,
    Meaning.BLOB: BLOB,
    Meaning.ENTITY_PROTO: EMBEDDED_ENTITY,
    Meaning.BYTESTRING: SHORT_BLOB,
    Meaning.TEXT: TEXT,
    Meaning.BLOBKEY: BLOB_KEY
  }

  VALUE_TYPES = {
    'string': STRING,
    'int64': INTEGER,
    'boolean': BOOLEAN,
    'double': FLOAT,
    'reference': KEY,
    'point': GEO_PT,
    'user': USER
  }

  NAMES = {
    STRING: u'String',
    BOOLEAN: u'Boolean',
    INTEGER: u'Integer',
    NULL: u'NULL',
    FLOAT: u'Float',
    KEY: u'Key',
    BLOB: u'Blob',
    EMBEDDED_ENTITY: u'EmbeddedEntity',
    SHORT_BLOB: u'ShortBlob',
    TEXT: u'Text',
    USER: u'User',
    CATEGORY: u'Category',
    LINK: u'Link',
    EMAIL: u'Email',
    DATE_TIME: u'Date/Time',
    GEO_PT: u'GeoPt',
    IM: u'IM',
    PHONE_NUMBER: u'PhoneNumber',
    POSTAL_ADDRESS: u'PostalAddress',
    RATING: u'Rating',
    BLOB_KEY: u'BlobKey'
  }


def stats_prop_type(prop_pb):
  """ Determines the property type for a Property object.

  Args:
    prop_pb: An entity_pb.Property object.

  Returns:
    A constant from PropertyTypes.
  """
  value_type = StatsPropTypes.NULL
  for type_name, type_code in six.iteritems(StatsPropTypes.VALUE_TYPES):
    if getattr(prop_pb.value(), 'has_{}value'.format(type_name))():
      value_type = type_code
      break

  if prop_pb.has_meaning():
    value_type = StatsPropTypes.MEANING_TYPES.get(
      prop_pb.meaning(), value_type)

  return value_type


class CountBytes(object):
  __slots__ = ['count', 'bytes']

  def __init__(self, count=0, bytes_=0):
    self.count = count
    self.bytes = bytes_

  def __repr__(self):
    return u'CountBytes({!r}, {!r})'.format(self.count, self.bytes)

  def __add__(self, other):
    self.count += other.count
    self.bytes += other.bytes
    return self

  def __sub__(self, other):
    self.count -= other.count
    self.bytes -= other.bytes
    return self


def create_apply_fields(tr, stats_dir):
  def apply_fields(prefix, count_bytes):
    tr.add(stats_dir.pack(prefix + (u'count',)),
           encode_delta(count_bytes.count))
    tr.add(stats_dir.pack(prefix + (u'bytes',)),
           encode_delta(count_bytes.bytes))

  return apply_fields


def create_apply_props(entity_stats, namespace, kind):
  def apply_props(prop_list, subtract=False):
    for prop_pb in prop_list:
      prop_type = stats_prop_type(prop_pb)
      prop_name = decode_str(prop_pb.name())
      fields = entity_stats[namespace][kind][prop_type][prop_name]
      delta = CountBytes(1, len(prop_pb.Encode()))
      if subtract:
        fields -= delta
      else:
        fields += delta

  return apply_props


class IndexStatsSummary(object):
  __slots__ = ['kindless', 'kind', 'single_prop', 'composite']

  def __init__(self):
    self.kindless = CountBytes()
    self.kind = CountBytes()

    # By prop_type/prop_name
    self.single_prop = defaultdict(lambda: defaultdict(CountBytes))

    # By index ID
    self.composite = defaultdict(CountBytes)

  @property
  def builtin(self):
    return self.kindless + self.kind + sum(
      (sum(six.itervalues(by_name), CountBytes())
       for by_name in six.itervalues(self.single_prop)), CountBytes())

  def __repr__(self):
    return u'IndexStatsSummary({!r}, {!r}, {!r}, {!r})'.format(
      self.kindless, self.kind,
      {prop_name: dict(prop_types)
       for prop_name, prop_types in six.iteritems(self.single_prop)},
      dict(self.composite))

  def add_kindless_key(self, key):
    self.kindless += CountBytes(1, len(key))

  def add_kind_key(self, key):
    self.kind += CountBytes(1, len(key))

  def add_prop_key(self, prop_pb, key):
    prop_type = stats_prop_type(prop_pb)
    prop_name = decode_str(prop_pb.name())
    self.single_prop[prop_type][prop_name] += CountBytes(1, len(key))

  def add_composite_keys(self, index_id, keys):
    self.composite[index_id] += CountBytes(len(keys),
                                           sum(len(key) for key in keys))

  def __sub__(self, other):
    self.kindless -= other.kindless
    self.kind -= other.kind
    for prop_type, by_name in six.iteritems(other.single_prop):
      for prop_name, fields in six.iteritems(by_name):
        self.single_prop[prop_type][prop_name] -= fields

    for index_id, fields in six.iteritems(other.composite):
      self.composite[index_id] -= fields

    return self


class CompositeStats(object):
  __slots__ = ['stats']

  SECTION_ID = u'composite-indexes'

  def __init__(self):
    # By namespace/(index_id, kind)
    self.stats = defaultdict(lambda: defaultdict(CountBytes))

  @property
  def empty(self):
    return not self.stats

  def update(self, namespace, kind, index_stats):
    for index_id, count_bytes in six.iteritems(index_stats.composite):
      self.stats[namespace][(index_id, kind)] += count_bytes

  def update_from_kv(self, path, encoded_value):
    namespace, index_id, kind, field = path
    value = decode_delta(encoded_value)
    setattr(self.stats[namespace][(index_id, kind)], field, value)

  def apply(self, tr, stats_dir):
    apply_fields = create_apply_fields(tr, stats_dir)
    for namespace, by_index in six.iteritems(self.stats):
      for (index_id, kind), fields in six.iteritems(by_index):
        apply_fields((self.SECTION_ID, namespace, index_id, kind), fields)


class EntityStats(object):
  __slots__ = ['builtin_indexes_root', 'builtin_indexes_notroot',
               'entities_root', 'entities_notroot']

  BUILTINS_SECTION = u'builtin-indexes'

  ENTITY_SECTION = u'entities'

  def __init__(self):
    # By namespace/kind
    self.builtin_indexes_root = defaultdict(lambda: defaultdict(CountBytes))
    self.builtin_indexes_notroot = defaultdict(lambda: defaultdict(CountBytes))
    self.entities_root = defaultdict(lambda: defaultdict(CountBytes))
    self.entities_notroot = defaultdict(lambda: defaultdict(CountBytes))

  @property
  def empty(self):
    return not any((self.builtin_indexes_root, self.builtin_indexes_notroot,
                    self.entities_root, self.entities_notroot))

  def update(self, old_entry, new_entry, index_stats):
    delta = CountBytes()
    if new_entry is not None:
      delta.count += 1
      delta.bytes += len(new_entry.encoded)

    if old_entry.present:
      delta.count -= 1
      delta.bytes -= len(old_entry.encoded)

    namespace = old_entry.namespace
    kind = old_entry.kind
    if len(old_entry.path) == 2:
      self.builtin_indexes_root[namespace][kind] += index_stats.builtin
      self.entities_root[namespace][kind] += delta
    else:
      self.builtin_indexes_notroot[namespace][kind] += index_stats.builtin
      self.entities_notroot[namespace][kind] += delta

  def update_builtins_from_kv(self, path, encoded_value):
    namespace, kind, is_root, field = path
    value = decode_delta(encoded_value)
    if is_root:
      setattr(self.builtin_indexes_root[namespace][kind], field, value)
    else:
      setattr(self.builtin_indexes_notroot[namespace][kind], field, value)

  def update_entities_from_kv(self, path, encoded_value):
    namespace, kind, is_root, field = path
    value = decode_delta(encoded_value)
    if is_root:
      setattr(self.entities_root[namespace][kind], field, value)
    else:
      setattr(self.entities_notroot[namespace][kind], field, value)

  def apply(self, tr, stats_dir):
    apply_fields = create_apply_fields(tr, stats_dir)
    for namespace, by_kind in six.iteritems(self.builtin_indexes_root):
      for kind, fields in six.iteritems(by_kind):
        apply_fields((self.BUILTINS_SECTION, namespace, kind, True), fields)

    for namespace, by_kind in six.iteritems(self.builtin_indexes_notroot):
      for kind, fields in six.iteritems(by_kind):
        apply_fields((self.BUILTINS_SECTION, namespace, kind, False), fields)

    for namespace, by_kind in six.iteritems(self.entities_root):
      for kind, fields in six.iteritems(by_kind):
        apply_fields((self.ENTITY_SECTION, namespace, kind, True), fields)

    for namespace, by_kind in six.iteritems(self.entities_notroot):
      for kind, fields in six.iteritems(by_kind):
        apply_fields((self.ENTITY_SECTION, namespace, kind, False), fields)


class SinglePropStats(object):
  __slots__ = ['entity_stats', 'index_stats']

  ENTITY_SECTION = u'entity-properties'

  INDEX_SECTION = u'index-properties'

  def __init__(self):
    # By namespace/kind/prop_type/prop_name
    self.entity_stats = defaultdict(
      lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(CountBytes))))
    self.index_stats = defaultdict(
      lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(CountBytes))))

  @property
  def empty(self):
    return not any((self.entity_stats, self.index_stats))

  def update(self, old_entry, new_entry, index_stats):
    namespace = old_entry.namespace
    kind = old_entry.kind
    apply_props = create_apply_props(self.entity_stats, namespace, kind)
    if old_entry.present:
      apply_props(old_entry.decoded.property_list(), subtract=True)
      apply_props(old_entry.decoded.raw_property_list(), subtract=True)

    if new_entry is not None:
      apply_props(new_entry.decoded.property_list())
      apply_props(new_entry.decoded.raw_property_list())

    for prop_type, by_name in six.iteritems(index_stats.single_prop):
      for prop_name, fields in six.iteritems(by_name):
        self.index_stats[namespace][kind][prop_type][prop_name] += fields

  def update_entity_props_from_kv(self, path, encoded_value):
    namespace, kind, prop_type, prop_name, field = path
    value = decode_delta(encoded_value)
    setattr(self.entity_stats[namespace][kind][prop_type][prop_name],
            field, value)

  def update_index_props_from_kv(self, path, encoded_value):
    namespace, kind, prop_type, prop_name, field = path
    value = decode_delta(encoded_value)
    setattr(self.index_stats[namespace][kind][prop_type][prop_name],
            field, value)

  def apply(self, tr, stats_dir):
    apply_fields = create_apply_fields(tr, stats_dir)
    for namespace, by_kind in six.iteritems(self.entity_stats):
      for kind, by_type in six.iteritems(by_kind):
        for prop_type, by_name in six.iteritems(by_type):
          for prop_name, fields in six.iteritems(by_name):
            apply_fields((self.ENTITY_SECTION, namespace, kind, prop_type,
                          prop_name), fields)

    for namespace, by_kind in six.iteritems(self.index_stats):
      for kind, by_type in six.iteritems(by_kind):
        for prop_type, by_name in six.iteritems(by_type):
          for prop_name, fields in six.iteritems(by_name):
            apply_fields((self.INDEX_SECTION, namespace, kind, prop_type,
                          prop_name), fields)


class ProjectStats(object):
  def __init__(self):
    self.composite_stats = CompositeStats()
    self.entity_stats = EntityStats()
    self.property_stats = SinglePropStats()

  @property
  def empty(self):
    return all((self.composite_stats.empty, self.entity_stats.empty,
                self.property_stats.empty))

  def update(self, old_entry, new_entry, index_stats):
    self.composite_stats.update(old_entry.namespace, old_entry.kind,
                                index_stats)
    self.entity_stats.update(old_entry, new_entry, index_stats)
    self.property_stats.update(old_entry, new_entry, index_stats)

  def update_from_kv(self, section, path, encoded_value):
    if section == CompositeStats.SECTION_ID:
      self.composite_stats.update_from_kv(path, encoded_value)
    elif section == EntityStats.BUILTINS_SECTION:
      self.entity_stats.update_builtins_from_kv(path, encoded_value)
    elif section == EntityStats.ENTITY_SECTION:
      self.entity_stats.update_entities_from_kv(path, encoded_value)
    elif section == SinglePropStats.ENTITY_SECTION:
      self.property_stats.update_entity_props_from_kv(path, encoded_value)
    elif section == SinglePropStats.INDEX_SECTION:
      self.property_stats.update_index_props_from_kv(path, encoded_value)

  def apply(self, tr, stats_dir):
    self.composite_stats.apply(tr, stats_dir)
    self.entity_stats.apply(tr, stats_dir)
    self.property_stats.apply(tr, stats_dir)
