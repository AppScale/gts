import datetime
import logging
import random
import struct
import sys
import time
from collections import defaultdict

import six
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.locks import Lock as AsyncLock

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.fdb.codecs import decode_str
from appscale.datastore.fdb.polling_lock import PollingLock
from appscale.datastore.fdb.utils import fdb, ResultIterator

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api import datastore
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


def fill_stat_entities(project_id, stats_by_ns_kind_isroot,
                       entity_bytes_by_prop, timestamp):
  stats_by_ns_kind = defaultdict(lambda: defaultdict(StatsSummary))
  for namespace, kinds in six.iteritems(stats_by_ns_kind_isroot):
    for kind, (root, non_root) in six.iteritems(kinds):
      stats_by_ns_kind[namespace][kind] += root + non_root

  stats_by_namespace = {}
  for namespace, kinds in six.iteritems(stats_by_ns_kind):
    stats_by_namespace[namespace] = sum(six.itervalues(kinds), StatsSummary())

  stats_by_kind = defaultdict(StatsSummary)
  for namespace, kinds in six.iteritems(stats_by_ns_kind):
    for kind, stats in six.iteritems(kinds):
      stats_by_kind[kind] += stats

  entities = []

  # TODO: Cover and test all stat entity types.
  total_stats = sum(six.itervalues(stats_by_namespace), StatsSummary())
  entity = datastore.Entity(
    '__Stat_Total__', _app=project_id, name='total_entity_usage')
  entity['bytes'] = total_stats.total_bytes
  entity['count'] = total_stats.entity_count
  entity['timestamp'] = timestamp

  entity['entity_bytes'] = total_stats.entity_bytes
  entity['builtin_index_bytes'] = total_stats.builtin_bytes
  entity['builtin_index_count'] = total_stats.builtin_count
  entity['composite_index_bytes'] = total_stats.composite_bytes
  entity['composite_index_count'] = total_stats.composite_count
  entities.append(entity)

  for namespace, stats in six.iteritems(stats_by_namespace):
    if namespace:
      entity = datastore.Entity('__Stat_Namespace__', _app=project_id,
                                name=namespace)
    else:
      entity = datastore.Entity('__Stat_Namespace__', _app=project_id, id=1)

    entity['bytes'] = stats.total_bytes
    entity['count'] = stats.entity_count
    entity['timestamp'] = timestamp

    entity['subject_namespace'] = namespace
    entity['entity_bytes'] = stats.entity_bytes
    entity['builtin_index_bytes'] = stats.builtin_bytes
    entity['builtin_index_count'] = stats.builtin_count
    entity['composite_index_bytes'] = stats.composite_bytes
    entity['composite_index_count'] = stats.composite_count
    entities.append(entity)

  for kind, stats in six.iteritems(stats_by_kind):
    entity = datastore.Entity('__Stat_Kind__', _app=project_id, name=kind)
    entity['bytes'] = stats.total_bytes
    entity['count'] = stats.entity_count
    entity['timestamp'] = timestamp

    entity['builtin_index_bytes'] = stats.builtin_bytes
    entity['builtin_index_count'] = stats.builtin_count
    entity['composite_index_bytes'] = stats.composite_bytes
    entity['composite_index_count'] = stats.composite_count
    entities.append(entity)

  stats_by_kind_root = defaultdict(StatsSummary)
  stats_by_kind_nonroot = defaultdict(StatsSummary)
  for namespace, kinds in six.iteritems(stats_by_ns_kind_isroot):
    for kind, (root, non_root) in six.iteritems(kinds):
      stats_by_kind_root[kind] += root
      stats_by_kind_nonroot[kind] += non_root

  for kind, stats in six.iteritems(stats_by_kind_root):
    entity = datastore.Entity('__Stat_Kind_IsRootEntity__', _app=project_id,
                              name=kind)
    entity['bytes'] = stats.total_bytes
    entity['count'] = stats.entity_count
    entity['timestamp'] = timestamp

    entity['kind_name'] = kind
    entity['entity_bytes'] = stats.entity_bytes
    entities.append(entity)

  for kind, stats in six.iteritems(stats_by_kind_nonroot):
    entity = datastore.Entity('__Stat_Kind_NotRootEntity__', _app=project_id,
                              name=kind)
    entity['bytes'] = stats.total_bytes
    entity['count'] = stats.entity_count
    entity['timestamp'] = timestamp

    entity['kind_name'] = kind
    entity['entity_bytes'] = stats.entity_bytes
    entities.append(entity)

  # entity_bytes, builtin_index_bytes, builtin_index_count
  stats_by_prop_type = defaultdict(lambda: [0, 0, 0])
  for namespace, kinds in six.iteritems(entity_bytes_by_prop):
    for kind, prop_names in six.iteritems(kinds):
      for prop_name, prop_types in six.iteritems(prop_names):
        for prop_type, byte_count in six.iteritems(prop_types):
          stats_by_prop_type[prop_type][0] += byte_count

  for prop_name, prop_types in six.iteritems(total_stats.prop_bytes):
    for prop_type, byte_count in six.iteritems(prop_types):
      stats_by_prop_type[prop_type][1] += byte_count

  for prop_name, prop_types in six.iteritems(total_stats.prop_count):
    for prop_type, count in six.iteritems(prop_types):
      stats_by_prop_type[prop_type][2] += count

  for prop_type, (entity_bytes, builtin_bytes, builtin_count) in \
       six.iteritems(stats_by_prop_type):
    entity = datastore.Entity('__Stat_PropertyType__', _app=project_id,
                              name=StatsPropTypes.NAMES[prop_type])
    entity['bytes'] = entity_bytes + builtin_bytes
    entity['count'] = builtin_count
    entity['timestamp'] = timestamp

    entity['property_type'] = StatsPropTypes.NAMES[prop_type]
    entity['entity_bytes'] = entity_bytes
    entity['builtin_index_bytes'] = builtin_bytes
    entity['builtin_index_count'] = builtin_count
    entities.append(entity)

  # entity_bytes, builtin_index_bytes, builtin_index_count
  stats_by_kind_prop_type = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
  for namespace, kinds in six.iteritems(entity_bytes_by_prop):
    for kind, prop_names in six.iteritems(kinds):
      for prop_name, prop_types in six.iteritems(prop_names):
        for prop_type, byte_count in six.iteritems(prop_types):
          stats_by_kind_prop_type[kind][prop_type][0] += byte_count

  for kind, stats in six.iteritems(stats_by_kind):
    for prop_name, prop_types in six.iteritems(stats.prop_bytes):
      for prop_type, byte_count in six.iteritems(prop_types):
        stats_by_kind_prop_type[kind][prop_type][1] += byte_count

    for prop_name, prop_types in six.iteritems(stats.prop_count):
      for prop_type, count in six.iteritems(prop_types):
        stats_by_kind_prop_type[kind][prop_type][2] += count

  for kind, prop_types in six.iteritems(stats_by_kind_prop_type):
    for prop_type, (entity_bytes, builtin_bytes, builtin_count) \
        in six.iteritems(prop_types):
      type_name = StatsPropTypes.NAMES[prop_type]
      entity = datastore.Entity('__Stat_PropertyType_Kind__', _app=project_id,
                                name=u'_'.join([type_name, kind]))
      entity['bytes'] = entity_bytes + builtin_bytes
      entity['count'] = builtin_count
      entity['timestamp'] = timestamp

      entity['kind_name'] = kind
      entity['entity_bytes'] = entity_bytes

      entity['property_type'] = type_name
      entity['builtin_index_bytes'] = builtin_bytes
      entity['builtin_index_count'] = builtin_count
      entities.append(entity)

  # entity_bytes, builtin_index_bytes, builtin_index_count
  stats_by_kind_prop_name = defaultdict(lambda: defaultdict(lambda: [0, 0, 0]))
  for namespace, kinds in six.iteritems(entity_bytes_by_prop):
    for kind, prop_names in six.iteritems(kinds):
      for prop_name, prop_types in six.iteritems(prop_names):
        stats_by_kind_prop_name[kind][prop_name][0] += \
          sum(six.itervalues(prop_types))

  for kind, stats in six.iteritems(stats_by_kind):
    for prop_name, prop_types in six.iteritems(stats.prop_bytes):
      stats_by_kind_prop_name[kind][prop_name][1] += \
        sum(six.itervalues(prop_types))

    for prop_name, prop_types in six.iteritems(stats.prop_count):
      stats_by_kind_prop_name[kind][prop_name][2] += \
        sum(six.itervalues(prop_types))

  for kind, prop_types in six.iteritems(stats_by_kind_prop_name):
    for prop_name, (entity_bytes, builtin_bytes, builtin_count) \
        in six.iteritems(prop_types):
      entity = datastore.Entity('__Stat_PropertyType_Kind__', _app=project_id,
                                name=u'_'.join([prop_name, kind]))
      entity['bytes'] = entity_bytes + builtin_bytes
      entity['count'] = builtin_count
      entity['timestamp'] = timestamp

      entity['kind_name'] = kind
      entity['entity_bytes'] = entity_bytes

      entity['property_name'] = prop_name
      entity['builtin_index_bytes'] = builtin_bytes
      entity['builtin_index_count'] = builtin_count
      entities.append(entity)

  for namespace, kinds in six.iteritems(stats_by_ns_kind):
    for kind, stats in six.iteritems(kinds):
      entity = datastore.Entity(
        '__Stat_Ns_Kind__', _app=project_id, name=kind, namespace=namespace)
      entity['bytes'] = stats.total_bytes
      entity['count'] = stats.entity_count
      entity['timestamp'] = timestamp

      entity['kind_name'] = kind
      entity['entity_bytes'] = stats.entity_bytes

      entity['builtin_index_bytes'] = stats.builtin_bytes
      entity['builtin_index_count'] = stats.builtin_count
      entity['composite_index_bytes'] = stats.composite_bytes
      entity['composite_index_count'] = stats.composite_count
      entities.append(entity)

  return entities


class ProjectStatsDir(object):
  """
  A ProjectStatsDir handles the encoding and decoding details for a project's
  stats entries.

  The directory path looks like (<project-dir>, 'stats').
  """
  DIR_NAME = u'stats'

  def __init__(self, directory):
    self.directory = directory

  def encode_entity_count(self, namespace, kind, is_root, count):
    key = self.directory.pack((u'entities', namespace, kind, is_root, u'count'))
    return key, self._encode_delta(count)

  def encode_entity_bytes(self, namespace, kind, is_root, byte_count):
    key = self.directory.pack((u'entities', namespace, kind, is_root, u'bytes'))
    return key, self._encode_delta(byte_count)

  def encode_kindless_count(self, namespace, kind, is_root, count):
    key = self.directory.pack((u'kindless', namespace, kind, is_root, u'count'))
    return key, self._encode_delta(count)

  def encode_kindless_bytes(self, namespace, kind, is_root, byte_count):
    key = self.directory.pack((u'kindless', namespace, kind, is_root, u'bytes'))
    return key, self._encode_delta(byte_count)

  def encode_kind_count(self, namespace, kind, is_root, count):
    key = self.directory.pack((u'kind', namespace, kind, is_root, u'count'))
    return key, self._encode_delta(count)

  def encode_kind_bytes(self, namespace, kind, is_root, byte_count):
    key = self.directory.pack((u'kind', namespace, kind, is_root, u'bytes'))
    return key, self._encode_delta(byte_count)

  def encode_prop_type_count(self, namespace, kind, is_root, prop_name,
                             prop_type, count):
    key = self.directory.pack((u'prop-type', namespace, kind, is_root,
                               prop_name, prop_type, u'count'))
    return key, self._encode_delta(count)

  def encode_prop_type_bytes(self, namespace, kind, is_root, prop_name,
                             prop_type, byte_count):
    key = self.directory.pack((u'prop-type', namespace, kind, is_root,
                               prop_name, prop_type, u'bytes'))
    return key, self._encode_delta(byte_count)

  def encode_composite_count(self, namespace, kind, is_root, count):
    key = self.directory.pack((u'composite', namespace, kind, is_root, u'count'))
    return key, self._encode_delta(count)

  def encode_composite_bytes(self, namespace, kind, is_root, byte_count):
    key = self.directory.pack((u'composite', namespace, kind, is_root, u'bytes'))
    return key, self._encode_delta(byte_count)

  def encode_entity_bytes_by_prop(self, namespace, kind, prop_name, prop_type,
                                  byte_count):
    key = self.directory.pack((u'entity-bytes-by-prop', namespace, kind,
                               prop_name, prop_type))
    return key, self._encode_delta(byte_count)

  def encode_last_versionstamp(self):
    return self.directory.pack((u'last-versionstamp',)), b'\x00' * 14

  def encode_last_timestamp(self):
    key = self.directory.pack((u'last-timestamp',))
    value = fdb.tuple.pack((int(time.time()),))
    return key, value

  def decode(self, kvs):
    # By namespace/kind/[root, nonroot]
    stats_by_ns_kind_isroot = defaultdict(
      lambda: defaultdict(lambda: [StatsSummary(), StatsSummary()]))

    # By namespace/kind/prop_name/prop_type
    entity_bytes_by_prop = defaultdict(
      lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(int))))
    last_timestamp = None
    for kv in kvs:
      path = self.directory.unpack(kv.key)
      section = path[0]
      if section == u'last-versionstamp':
        continue

      if section == u'last-timestamp':
        last_timestamp = datetime.datetime.utcfromtimestamp(
          fdb.tuple.unpack(kv.value)[0])
        continue

      namespace = path[1]
      kind = path[2]
      value = struct.unpack('<q', kv.value)[0]

      if section == u'entity-bytes-by-prop':
        prop_name = path[3]
        prop_type = path[4]
        entity_bytes_by_prop[namespace][kind][prop_name][prop_type] = value
        continue

      is_root = path[3]
      stats_type = path[-1]
      stats = stats_by_ns_kind_isroot[namespace][kind][0 if is_root else 1]
      if section == u'entities' and stats_type == u'count':
        stats.entity_count = value
      elif section == u'entities' and stats_type == u'bytes':
        stats.entity_bytes = value
      elif section == u'kindless' and stats_type == u'count':
        stats.kindless_count = value
      elif section == u'kindless' and stats_type == u'bytes':
        stats.kindless_bytes = value
      elif section == u'kind' and stats_type == u'count':
        stats.kind_count = value
      elif section == u'kind' and stats_type == u'bytes':
        stats.kind_bytes = value
      elif section == u'prop-type':
        prop_name = path[4]
        prop_type = path[5]
        if stats_type == u'count':
          stats.prop_count[prop_name][prop_type] = value
        elif stats_type == u'bytes':
          stats.prop_bytes[prop_name][prop_type] = value
        else:
          raise Exception(u'Unknown stats field')
      elif section == u'composite' and stats_type == u'count':
        stats.composite_count = value
      elif section == u'composite' and stats_type == u'bytes':
        stats.composite_bytes = value
      else:
        raise Exception(u'Unknown stats field')

    return stats_by_ns_kind_isroot, entity_bytes_by_prop, last_timestamp

  @classmethod
  def directory_path(cls, project_id):
    return project_id, cls.DIR_NAME

  @staticmethod
  def _encode_delta(delta):
    return struct.pack('<q', delta)


class StatsSummary(object):
  __slots__ = ['entity_count', 'entity_bytes',
               'kindless_count', 'kindless_bytes',
               'kind_count', 'kind_bytes',
               'prop_count', 'prop_bytes',
               'composite_count', 'composite_bytes']

  def __init__(self):
    self.entity_count = 0
    self.entity_bytes = 0

    self.kindless_count = 0
    self.kindless_bytes = 0

    self.kind_count = 0
    self.kind_bytes = 0

    # By prop_name/prop_type
    self.prop_count = defaultdict(lambda: defaultdict(int))
    self.prop_bytes = defaultdict(lambda: defaultdict(int))

    self.composite_count = 0
    self.composite_bytes = 0

  def bytes_for_prop_name(self, prop_name):
    return sum(six.itervalues(self.prop_bytes[prop_name]))

  @property
  def total_prop_bytes(self):
    return sum(self.bytes_for_prop_name(prop) for prop in self.prop_bytes)

  @property
  def builtin_bytes(self):
    return self.kindless_bytes + self.kind_bytes + self.total_prop_bytes

  def count_for_prop_name(self, prop_name):
    return sum(six.itervalues(self.prop_count[prop_name]))

  @property
  def total_prop_count(self):
    return sum(self.count_for_prop_name(prop) for prop in self.prop_count)

  @property
  def builtin_count(self):
    return self.kindless_count + self.kind_count + self.total_prop_count

  @property
  def total_bytes(self):
    return self.entity_bytes + self.builtin_bytes + self.composite_bytes

  def __repr__(self):
    return (u'StatsSummary({!r}, {!r}, {!r}, {!r}, {!r}, {!r}, {!r}, {!r}, '
            u'{!r}, {!r})'.format(
      self.entity_count, self.entity_bytes,
      self.kindless_count, self.kindless_bytes,
      self.kind_count, self.kind_bytes,
      {prop_name: dict(prop_types)
       for prop_name, prop_types in six.iteritems(self.prop_count)},
      {prop_name: dict(prop_types)
       for prop_name, prop_types in six.iteritems(self.prop_bytes)},
      self.composite_count,
      self.composite_bytes))

  def add_kindless_keys(self, keys):
    self.kindless_count += len(keys)
    self.kindless_bytes += sum(len(key) for key in keys)

  def add_kind_keys(self, keys):
    self.kind_count += len(keys)
    self.kind_bytes += sum(len(key) for key in keys)

  def add_prop_key(self, prop_pb, key):
    prop_name = decode_str(prop_pb.name())
    prop_type = stats_prop_type(prop_pb)
    self.prop_count[prop_name][prop_type] += 1
    self.prop_bytes[prop_name][prop_type] += len(key)

  def add_composite_keys(self, keys):
    self.composite_count += len(keys)
    self.composite_bytes += sum(len(key) for key in keys)

  @classmethod
  def from_entity(cls, encoded_entity):
    stats = cls()
    stats.entity_count += 1
    stats.entity_bytes += len(encoded_entity)
    return stats

  def __sub__(self, other):
    self.entity_count -= other.entity_count
    self.entity_bytes -= other.entity_bytes
    self.kindless_count -= other.kindless_count
    self.kindless_bytes -= other.kindless_bytes
    self.kind_count -= other.kind_count
    self.kind_bytes -= other.kind_bytes
    for prop_name, prop_types in six.iteritems(other.prop_count):
      for prop_type, count in six.iteritems(prop_types):
        self.prop_count[prop_name][prop_type] -= count

    for prop_name, prop_types in six.iteritems(other.prop_bytes):
      for prop_type, byte_count in six.iteritems(prop_types):
        self.prop_bytes[prop_name][prop_type] -= byte_count

    self.composite_count -= other.composite_count
    self.composite_bytes -= other.composite_bytes
    return self

  def __add__(self, other):
    self.entity_count += other.entity_count
    self.entity_bytes += other.entity_bytes
    self.kindless_count += other.kindless_count
    self.kindless_bytes += other.kindless_bytes
    self.kind_count += other.kind_count
    self.kind_bytes += other.kind_bytes
    for prop_name, prop_types in six.iteritems(other.prop_count):
      for prop_type, count in six.iteritems(prop_types):
        self.prop_count[prop_name][prop_type] += count

    for prop_name, prop_types in six.iteritems(other.prop_bytes):
      for prop_type, byte_count in six.iteritems(prop_types):
        self.prop_bytes[prop_name][prop_type] += byte_count

    self.composite_count += other.composite_count
    self.composite_bytes += other.composite_bytes
    return self

  def iter_encode(self, stats_dir, namespace, kind, is_root):
    if self.entity_count:
      yield stats_dir.encode_entity_count(
        namespace, kind, is_root, self.entity_count)

    if self.entity_bytes:
      yield stats_dir.encode_entity_bytes(
        namespace, kind, is_root, self.entity_bytes)

    if self.kindless_count:
      yield stats_dir.encode_kindless_count(
        namespace, kind, is_root, self.kindless_count)

    if self.kindless_bytes:
      yield stats_dir.encode_kindless_bytes(
        namespace, kind, is_root, self.kindless_bytes)

    if self.kind_count:
      yield stats_dir.encode_kind_count(
        namespace, kind, is_root, self.kind_count)

    if self.kind_bytes:
      yield stats_dir.encode_kind_bytes(
        namespace, kind, is_root, self.kind_bytes)

    for prop_name, prop_types in six.iteritems(self.prop_count):
      for prop_type, count in six.iteritems(prop_types):
        if count:
          yield stats_dir.encode_prop_type_count(
            namespace, kind, is_root, prop_name, prop_type, count)

    for prop_name, prop_types in six.iteritems(self.prop_bytes):
      for prop_type, byte_count in six.iteritems(prop_types):
        if byte_count:
          yield stats_dir.encode_prop_type_bytes(
            namespace, kind, is_root, prop_name, prop_type, byte_count)

    if self.composite_count:
      yield stats_dir.encode_composite_count(
        namespace, kind, is_root, self.composite_count)

    if self.composite_bytes:
      yield stats_dir.encode_composite_bytes(
        namespace, kind, is_root, self.composite_bytes)


class StatsBuffer(object):
  AVG_FLUSH_INTERVAL = 60

  SUMMARY_INTERVAL = 300

  _LOCK_KEY = u'stats-lock'

  def __init__(self, db, tornado_fdb, directory_cache, ds_access):
    self._db = db
    self._tornado_fdb = tornado_fdb
    self._directory_cache = directory_cache
    self._buffer_lock = AsyncLock()
    self._ds_access = ds_access

    summary_lock_key = self._directory_cache.root_dir.pack((self._LOCK_KEY,))
    self._summary_lock = PollingLock(
      self._db, self._tornado_fdb, summary_lock_key)

    # By project
    self._last_summarized = {}

    # By project/namespace/kind
    self._stats_root = defaultdict(
      lambda: defaultdict(lambda: defaultdict(StatsSummary)))
    self._stats_nonroot = defaultdict(
      lambda: defaultdict(lambda: defaultdict(StatsSummary)))

    # By project/namespace/kind/prop_name/prop_type
    self._entity_bytes_by_prop = defaultdict(
      lambda: defaultdict(lambda: defaultdict(lambda: defaultdict(
        lambda: defaultdict(int)))))

  def start(self):
    self._summary_lock.start()
    IOLoop.current().spawn_callback(self._periodic_flush)
    IOLoop.current().spawn_callback(self._periodic_summary)

  @gen.coroutine
  def apply_diffs(self, stat_diffs):
    with (yield self._buffer_lock.acquire()):
      for project_id, namespace, path, stats_diff in stat_diffs:
        kind = path[-2]
        if len(path) == 2:
          self._stats_root[project_id][namespace][kind] += stats_diff
        else:
          self._stats_nonroot[project_id][namespace][kind] += stats_diff

        for prop_name, prop_types in six.iteritems(stats_diff.prop_bytes):
          for prop_type in prop_types:
            self._entity_bytes_by_prop[project_id][namespace][kind]\
              [prop_name][prop_type] += stats_diff.entity_bytes

  @gen.coroutine
  def _periodic_flush(self):
    while True:
      try:
        yield gen.sleep(random.random() * self.AVG_FLUSH_INTERVAL)
        yield self._flush()
      except Exception:
        # TODO: Exponential backoff here.
        logger.exception(u'Unexpected error while flushing stats')
        yield gen.sleep(random.random() * 2)
        continue

  @gen.coroutine
  def _flush(self):
    if not self._stats_root and not self._stats_nonroot:
      return

    with (yield self._buffer_lock.acquire()):
      tr = self._db.create_transaction()
      yield self._flush_stats(tr, self._stats_root, is_root=True)
      yield self._flush_stats(tr, self._stats_nonroot, is_root=False)
      yield self._flush_bytes_by_prop(tr)
      yield self._tornado_fdb.commit(tr)
      logger.debug(u'Finished flushing stats')
      self._stats_root.clear()
      self._stats_nonroot.clear()

  @gen.coroutine
  def _flush_stats(self, tr, stats_by_project_ns_kind, is_root):
    for project_id, namespaces in six.iteritems(stats_by_project_ns_kind):
      stats_dir = yield self._project_stats_dir(tr, project_id)
      for namespace, kinds in six.iteritems(namespaces):
        for kind, stats in six.iteritems(kinds):
          for key, value in stats.iter_encode(stats_dir, namespace, kind, is_root):
            tr.add(key, value)

      vs_key, vs_value = stats_dir.encode_last_versionstamp()
      tr.set_versionstamped_value(vs_key, vs_value)
      ts_key, ts_value = stats_dir.encode_last_timestamp()
      tr[ts_key] = ts_value

  @gen.coroutine
  def _flush_bytes_by_prop(self, tr):
    for project_id, namespaces in six.iteritems(self._entity_bytes_by_prop):
      stats_dir = yield self._project_stats_dir(tr, project_id)
      for namespace, kinds in six.iteritems(namespaces):
        for kind, prop_names in six.iteritems(kinds):
          for prop_name, prop_types in six.iteritems(prop_names):
            for prop_type, byte_count in six.iteritems(prop_types):
              key, value = stats_dir.encode_entity_bytes_by_prop(
                namespace, kind, prop_name, prop_type, byte_count)
              tr.add(key, value)

  @gen.coroutine
  def _periodic_summary(self):
    while True:
      try:
        yield self._summary_lock.acquire()
        tr = self._db.create_transaction()
        last_summarized = {}

        # TODO: This can be made async.
        project_ids = self._directory_cache.root_dir.list(tr)

        for project_id in project_ids:
          stats_dir = yield self._project_stats_dir(tr, project_id)
          last_vs_key = stats_dir.encode_last_versionstamp()[0]
          last_versionstamp = yield self._tornado_fdb.get(tr, last_vs_key)
          if (not last_versionstamp.present() or
              last_versionstamp.value == self._last_summarized.get(project_id)):
            continue

          last_summarized[project_id] = last_versionstamp.value
          results = yield ResultIterator(
            tr, self._tornado_fdb, stats_dir.directory.range(),
            snapshot=True).list()
          stats, entity_bytes_by_prop, last_timestamp = \
            stats_dir.decode(results)
          entities = fill_stat_entities(
            project_id, stats, entity_bytes_by_prop, last_timestamp)
          yield [self._ds_access._upsert(tr, entity.ToPb())
                 for entity in entities]

        yield self._tornado_fdb.commit(tr)
        self._last_summarized = last_summarized
        logger.debug(u'Finished summarizing stats')
        yield gen.sleep(self.SUMMARY_INTERVAL)
      except Exception:
        logger.exception(u'Unexpected error while summarizing stats')
        yield gen.sleep(random.random() * 20)

  @gen.coroutine
  def _project_stats_dir(self, tr, project_id):
    path = ProjectStatsDir.directory_path(project_id)
    directory = yield self._directory_cache.get(tr, path)
    raise gen.Return(ProjectStatsDir(directory))
