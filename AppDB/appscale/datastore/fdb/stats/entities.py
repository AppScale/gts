"""
Each stat kind is populated from one or more stat sections (which are described
in the containers module).
Ns_Kind_CompositeIndex -> composite-indexes
Kind_CompositeIndex -> composite-indexes
Ns_Kind_IsRootEntity -> entities + builtin-indexes
Ns_Kind_NotRootEntity -> entities + builtin-indexes
Kind_IsRootEntity -> entities + builtin-indexes
Kind_NotRootEntity -> entities + builtin-indexes
Ns_PropertyType_PropertyName_Kind -> entity-properties + index-properties
Ns_PropertyName_Kind -> entity-properties + index-properties
Ns_PropertyType_Kind -> entity-properties + index-properties
PropertyType_PropertyName_Kind -> entity-properties + index-properties
Ns_PropertyType -> entity-properties + index-properties
PropertyName_Kind -> entity-properties + index-properties
PropertyType_Kind -> entity-properties + index-properties
PropertyType -> entity-properties + index-properties
Ns_Kind -> entities + builtin-indexes + composite-indexes
Kind -> entities + builtin-indexes + composite-indexes
Namespace -> entities + builtin-indexes + composite-indexes
Ns_Total -> entities + builtin-indexes + composite-indexes
Total -> entities + builtin-indexes + composite-indexes
"""
import datetime
import logging
import sys
import time
from collections import defaultdict

import six

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.fdb.stats.containers import CountBytes, StatsPropTypes

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb

# The value the datastore uses to populate the meaning field for timestammps.
GD_WHEN = 7

logger = logging.getLogger(__name__)


def fill_entity(project_id, kind, properties, name=None, id_=None,
                namespace=''):
  entity = entity_pb.EntityProto()
  key = entity.mutable_key()
  key.set_app(project_id)
  if namespace:
    key.set_name_space(namespace)

  path = key.mutable_path()
  element = path.add_element()
  element.set_type(kind)
  if name is not None:
    element.set_name(name)
  else:
    element.set_id(id_)

  group = entity.mutable_entity_group()
  group.add_element().CopyFrom(element)
  for prop_name, value in six.iteritems(properties):
    prop = entity.add_property()
    prop.set_name(prop_name)
    prop.set_multiple(False)
    value_pb = prop.mutable_value()
    if isinstance(value, datetime.datetime):
      value_pb.set_int64value(
        int(time.mktime(value.timetuple()) * 1000000 + value.microsecond))
      prop.set_meaning(GD_WHEN)
    elif isinstance(value, int):
      value_pb.set_int64value(value)
    else:
      value_pb.set_stringvalue(value.encode('utf-8'))

  return entity


def fill_entities(project_id, project_stats, timestamp):
  entities = []

  composite_stats = project_stats.composite_stats.stats
  stats_kind = u'__Stat_Ns_Kind_CompositeIndex__'
  for namespace, by_index in six.iteritems(composite_stats):
    for (index_id, kind), fields in six.iteritems(by_index):
      name = u'_'.join([kind, six.text_type(index_id)])
      props = {'index_id': index_id, 'kind_name': kind, 'timestamp': timestamp,
               'count': fields.count, 'bytes': fields.bytes}
      entities.append(fill_entity(project_id, stats_kind, props, name,
                                  namespace=namespace))

  stats_kind = u'__Stat_Kind_CompositeIndex__'
  composite_stats_by_index = defaultdict(CountBytes)
  for namespace, by_index in six.iteritems(composite_stats):
    for key, fields in six.iteritems(by_index):
      composite_stats_by_index[key] += fields

  for (index_id, kind), fields in six.iteritems(composite_stats_by_index):
    name = u'_'.join([kind, six.text_type(index_id)])
    props = {'index_id': index_id, 'kind_name': kind, 'timestamp': timestamp,
             'count': fields.count, 'bytes': fields.bytes}
    entities.append(fill_entity(project_id, stats_kind, props, name))

  entity_stats = project_stats.entity_stats
  stats_kind = u'__Stat_Ns_Kind_IsRootEntity__'
  for namespace, by_kind in six.iteritems(entity_stats.entities_root):
    for kind, entity_fields in six.iteritems(by_kind):
      builtin_fields = entity_stats.builtin_indexes_root[namespace][kind]
      props = {'kind_name': kind, 'timestamp': timestamp,
               'builtin_index_count': builtin_fields.count,
               'builtin_index_bytes': builtin_fields.bytes,
               'count': entity_fields.count,
               'entity_bytes': entity_fields.bytes,
               'bytes': entity_fields.bytes + builtin_fields.bytes}
      entities.append(fill_entity(project_id, stats_kind, props, kind,
                                  namespace=namespace))

  stats_kind = u'__Stat_Ns_Kind_NotRootEntity__'
  for namespace, by_kind in six.iteritems(entity_stats.entities_notroot):
    for kind, entity_fields in six.iteritems(by_kind):
      builtin_fields = entity_stats.builtin_indexes_notroot[namespace][kind]
      props = {'kind_name': kind, 'timestamp': timestamp,
               'builtin_index_count': builtin_fields.count,
               'builtin_index_bytes': builtin_fields.bytes,
               'count': entity_fields.count,
               'entity_bytes': entity_fields.bytes,
               'bytes': entity_fields.bytes + builtin_fields.bytes}
      entities.append(fill_entity(project_id, stats_kind, props, kind,
                                  namespace=namespace))

  stats_kind = u'__Stat_Ns_Kind__'
  entity_stats_by_ns_kind = defaultdict(lambda: defaultdict(CountBytes))
  for namespace, by_kind in six.iteritems(entity_stats.entities_root):
    for kind, fields in six.iteritems(by_kind):
      entity_stats_by_ns_kind[namespace][kind] += fields

  for namespace, by_kind in six.iteritems(entity_stats.entities_notroot):
    for kind, fields in six.iteritems(by_kind):
      entity_stats_by_ns_kind[namespace][kind] += fields

  builtin_stats_by_ns_kind = defaultdict(lambda: defaultdict(CountBytes))
  for namespace, by_kind in six.iteritems(entity_stats.builtin_indexes_root):
    for kind, fields in six.iteritems(by_kind):
      builtin_stats_by_ns_kind[namespace][kind] += fields

  for namespace, by_kind in six.iteritems(entity_stats.builtin_indexes_notroot):
    for kind, fields in six.iteritems(by_kind):
      builtin_stats_by_ns_kind[namespace][kind] += fields

  composite_stats_by_ns_kind = defaultdict(lambda: defaultdict(CountBytes))
  for namespace, by_index in six.iteritems(composite_stats):
    for (index_id, kind), fields in six.iteritems(by_index):
      composite_stats_by_ns_kind[namespace][kind] += fields

  for namespace, by_kind in six.iteritems(entity_stats_by_ns_kind):
    for kind, entity_fields in six.iteritems(by_kind):
      builtin_fields = builtin_stats_by_ns_kind[namespace][kind]
      composite_fields = composite_stats_by_ns_kind[namespace][kind]
      props = {'kind_name': kind, 'timestamp': timestamp,
               'builtin_index_count': builtin_fields.count,
               'builtin_index_bytes': builtin_fields.bytes,
               'count': entity_fields.count,
               'entity_bytes': entity_fields.bytes,
               'composite_index_count': composite_fields.count,
               'composite_index_bytes': composite_fields.bytes,
               'bytes': entity_fields.bytes + builtin_fields.bytes +
                        composite_fields.bytes}
      entities.append(fill_entity(project_id, stats_kind, props, kind,
                                  namespace=namespace))

  stats_kind = u'__Stat_Kind_IsRootEntity__'
  root_entity_stats_by_kind = defaultdict(CountBytes)
  for namespace, by_kind in six.iteritems(entity_stats.entities_root):
    for kind, fields in six.iteritems(by_kind):
      root_entity_stats_by_kind[kind] += fields

  root_builtin_stats_by_kind = defaultdict(CountBytes)
  for namespace, by_kind in six.iteritems(entity_stats.builtin_indexes_root):
    for kind, fields in six.iteritems(by_kind):
      root_builtin_stats_by_kind[kind] += fields

  for kind, entity_fields in six.iteritems(root_entity_stats_by_kind):
    builtin_fields = root_builtin_stats_by_kind[kind]
    props = {'kind_name': kind, 'timestamp': timestamp,
             'builtin_index_count': builtin_fields.count,
             'builtin_index_bytes': builtin_fields.bytes,
             'count': entity_fields.count, 'entity_bytes': entity_fields.bytes,
             'bytes': entity_fields.bytes + builtin_fields.bytes}
    entities.append(fill_entity(project_id, stats_kind, props, kind))

  stats_kind = u'__Stat_Kind_NotRootEntity__'
  notroot_entity_stats_by_kind = defaultdict(CountBytes)
  for namespace, by_kind in six.iteritems(entity_stats.entities_notroot):
    for kind, fields in six.iteritems(by_kind):
      notroot_entity_stats_by_kind[kind] += fields

  notroot_builtin_stats_by_kind = defaultdict(CountBytes)
  for namespace, by_kind in six.iteritems(entity_stats.builtin_indexes_notroot):
    for kind, fields in six.iteritems(by_kind):
      notroot_builtin_stats_by_kind[kind] += fields

  for kind, entity_fields in six.iteritems(notroot_entity_stats_by_kind):
    builtin_fields = notroot_builtin_stats_by_kind[kind]
    props = {'kind_name': kind, 'timestamp': timestamp,
             'builtin_index_count': builtin_fields.count,
             'builtin_index_bytes': builtin_fields.bytes,
             'count': entity_fields.count, 'entity_bytes': entity_fields.bytes,
             'bytes': entity_fields.bytes + builtin_fields.bytes}
    entities.append(fill_entity(project_id, stats_kind, props, kind))

  stats_kind = u'__Stat_Kind__'
  entity_stats_by_kind = defaultdict(CountBytes)
  for kind, fields in six.iteritems(root_entity_stats_by_kind):
    entity_stats_by_kind[kind] += fields

  for kind, fields in six.iteritems(notroot_entity_stats_by_kind):
    entity_stats_by_kind[kind] += fields

  builtin_stats_by_kind = defaultdict(CountBytes)
  for kind, fields in six.iteritems(root_builtin_stats_by_kind):
    builtin_stats_by_kind[kind] += fields

  for kind, fields in six.iteritems(notroot_builtin_stats_by_kind):
    builtin_stats_by_kind[kind] += fields

  composite_stats_by_kind = defaultdict(CountBytes)
  for (index_id, kind), fields in six.iteritems(composite_stats_by_index):
    composite_stats_by_kind[kind] += fields

  for kind, entity_fields in six.iteritems(entity_stats_by_kind):
    builtin_fields = builtin_stats_by_kind[kind]
    composite_fields = composite_stats_by_kind[kind]
    props = {'kind_name': kind, 'timestamp': timestamp,
             'builtin_index_count': builtin_fields.count,
             'builtin_index_bytes': builtin_fields.bytes,
             'count': entity_fields.count, 'entity_bytes': entity_fields.bytes,
             'composite_index_count': composite_fields.count,
             'composite_index_bytes': composite_fields.bytes,
             'bytes': entity_fields.bytes + builtin_fields.bytes +
                      composite_fields.bytes}
    entities.append(fill_entity(project_id, stats_kind, props, kind))

  stats_kind = u'__Stat_Namespace__'
  composite_stats_by_ns = defaultdict(CountBytes)
  for namespace, by_kind in six.iteritems(composite_stats):
    composite_stats_by_ns[namespace] += sum(six.itervalues(by_kind),
                                            CountBytes())

  entity_stats_by_ns = defaultdict(CountBytes)
  for namespace, by_kind in six.iteritems(entity_stats.entities_root):
    entity_stats_by_ns[namespace] += sum(six.itervalues(by_kind), CountBytes())

  for namespace, by_kind in six.iteritems(entity_stats.entities_notroot):
    entity_stats_by_ns[namespace] += sum(six.itervalues(by_kind), CountBytes())

  builtin_stats_by_ns = defaultdict(CountBytes)
  for namespace, by_kind in six.iteritems(entity_stats.builtin_indexes_root):
    builtin_stats_by_ns[namespace] += sum(six.itervalues(by_kind), CountBytes())

  for namespace, by_kind in six.iteritems(entity_stats.builtin_indexes_notroot):
    builtin_stats_by_ns[namespace] += sum(six.itervalues(by_kind), CountBytes())

  for namespace, entity_fields in six.iteritems(entity_stats_by_ns):
    builtin_fields = builtin_stats_by_ns[namespace]
    composite_fields = composite_stats_by_ns[namespace]
    props = {'subject_namespace': namespace, 'timestamp': timestamp,
             'builtin_index_count': builtin_fields.count,
             'builtin_index_bytes': builtin_fields.bytes,
             'count': entity_fields.count, 'entity_bytes': entity_fields.bytes,
             'composite_index_count': composite_fields.count,
             'composite_index_bytes': composite_fields.bytes,
             'bytes': entity_fields.bytes + builtin_fields.bytes +
                      composite_fields.bytes}
    if namespace:
      entities.append(fill_entity(project_id, stats_kind, props, namespace))
    else:
      entities.append(fill_entity(project_id, stats_kind, props, id_=1))

  stats_kind = u'__Stat_Ns_Total__'
  name = u'total_entity_usage'
  for namespace, entity_fields in six.iteritems(entity_stats_by_ns):
    builtin_fields = builtin_stats_by_ns[namespace]
    composite_fields = composite_stats_by_ns[namespace]
    props = {'timestamp': timestamp,
             'builtin_index_count': builtin_fields.count,
             'builtin_index_bytes': builtin_fields.bytes,
             'count': entity_fields.count, 'entity_bytes': entity_fields.bytes,
             'composite_index_count': composite_fields.count,
             'composite_index_bytes': composite_fields.bytes,
             'bytes': entity_fields.bytes + builtin_fields.bytes +
                      composite_fields.bytes}
    entities.append(fill_entity(project_id, stats_kind, props, name,
                                namespace=namespace))

  stats_kind = u'__Stat_Total__'
  name = u'total_entity_usage'
  entity_fields = sum(six.itervalues(entity_stats_by_ns), CountBytes())
  builtin_fields = sum(six.itervalues(builtin_stats_by_ns), CountBytes())
  composite_fields = sum(six.itervalues(composite_stats_by_ns), CountBytes())
  props = {'timestamp': timestamp,
           'builtin_index_count': builtin_fields.count,
           'builtin_index_bytes': builtin_fields.bytes,
           'count': entity_fields.count, 'entity_bytes': entity_fields.bytes,
           'composite_index_count': composite_fields.count,
           'composite_index_bytes': composite_fields.bytes,
           'bytes': entity_fields.bytes + builtin_fields.bytes +
                    composite_fields.bytes}
  entities.append(fill_entity(project_id, stats_kind, props, name))

  prop_stats = project_stats.property_stats
  stats_kind = u'__Stat_Ns_PropertyType_PropertyName_Kind__'
  for namespace, by_kind in six.iteritems(prop_stats.entity_stats):
    for kind, by_type in six.iteritems(by_kind):
      for prop_type, by_name in six.iteritems(by_type):
        type_name = StatsPropTypes.NAMES[prop_type]
        for prop_name, entity_fields in six.iteritems(by_name):
          name = u'_'.join([type_name, prop_name, kind])
          index_fields = prop_stats.index_stats[namespace][kind][prop_type]\
            [prop_name]
          props = {'kind_name': kind, 'timestamp': timestamp,
                   'property_type': type_name, 'property_name': prop_name,
                   'builtin_index_count': index_fields.count,
                   'builtin_index_bytes': index_fields.bytes,
                   'count': entity_fields.count,
                   'entity_bytes': entity_fields.bytes,
                   'bytes': entity_fields.bytes + index_fields.bytes}
          entities.append(fill_entity(project_id, stats_kind, props, name,
                                      namespace=namespace))

  stats_kind = u'__Stat_Ns_PropertyType_Kind__'
  for namespace, by_kind in six.iteritems(prop_stats.entity_stats):
    for kind, by_type in six.iteritems(by_kind):
      for prop_type, by_name in six.iteritems(by_type):
        type_name = StatsPropTypes.NAMES[prop_type]
        name = u'_'.join([type_name, kind])
        entity_fields = sum(six.itervalues(by_name), CountBytes())
        index_fields = sum(
          six.itervalues(prop_stats.index_stats[namespace][kind][prop_type]),
          CountBytes())
        props = {'kind_name': kind, 'timestamp': timestamp,
                 'property_type': type_name,
                 'builtin_index_count': index_fields.count,
                 'builtin_index_bytes': index_fields.bytes,
                 'count': entity_fields.count,
                 'entity_bytes': entity_fields.bytes,
                 'bytes': entity_fields.bytes + index_fields.bytes}
        entities.append(fill_entity(project_id, stats_kind, props, name,
                                    namespace=namespace))

  stats_kind = u'__Stat_Ns_PropertyName_Kind__'
  for namespace, by_kind in six.iteritems(prop_stats.entity_stats):
    for kind, by_type in six.iteritems(by_kind):
      combined_entities = defaultdict(CountBytes)
      combined_indexes = defaultdict(CountBytes)
      for prop_type, by_name in six.iteritems(by_type):
        for prop_name, fields in six.iteritems(by_name):
          combined_entities[prop_name] += fields
          combined_indexes[prop_name] += prop_stats.index_stats[namespace]\
            [kind][prop_type][prop_name]

      for prop_name, entity_fields in six.iteritems(combined_entities):
        name = u'_'.join([prop_name, kind])
        index_fields = combined_indexes[prop_name]
        props = {'kind_name': kind, 'timestamp': timestamp,
                 'property_name': prop_name,
                 'builtin_index_count': index_fields.count,
                 'builtin_index_bytes': index_fields.bytes,
                 'count': entity_fields.count,
                 'entity_bytes': entity_fields.bytes,
                 'bytes': entity_fields.bytes + index_fields.bytes}
        entities.append(fill_entity(project_id, stats_kind, props, name,
                                    namespace=namespace))

  stats_kind = u'__Stat_Ns_PropertyType__'
  for namespace, by_kind in six.iteritems(prop_stats.entity_stats):
    combined_entities = defaultdict(CountBytes)
    combined_indexes = defaultdict(CountBytes)
    for kind, by_type in six.iteritems(by_kind):
      for prop_type, by_name in six.iteritems(by_type):
        combined_entities[prop_type] += sum(
          six.itervalues(by_name), CountBytes())
        combined_indexes[prop_type] += sum(
          six.itervalues(prop_stats.index_stats[namespace][kind][prop_type]),
          CountBytes())

    for prop_type, entity_fields in six.iteritems(combined_entities):
      type_name = StatsPropTypes.NAMES[prop_type]
      index_fields = combined_indexes[prop_type]
      props = {'timestamp': timestamp, 'property_type': type_name,
               'builtin_index_count': index_fields.count,
               'builtin_index_bytes': index_fields.bytes,
               'count': entity_fields.count,
               'entity_bytes': entity_fields.bytes,
               'bytes': entity_fields.bytes + index_fields.bytes}
      entities.append(fill_entity(project_id, stats_kind, props, type_name,
                                  namespace=namespace))

  stats_kind = u'__Stat_PropertyName_Kind__'
  combined_entities = defaultdict(lambda: defaultdict(CountBytes))
  combined_indexes = defaultdict(lambda: defaultdict(CountBytes))
  for namespace, by_kind in six.iteritems(prop_stats.entity_stats):
    for kind, by_type in six.iteritems(by_kind):
      for prop_type, by_name in six.iteritems(by_type):
        for prop_name, fields in six.iteritems(by_name):
          combined_entities[prop_name][kind] += fields
          combined_indexes[prop_name][kind] += prop_stats.index_stats\
            [namespace][kind][prop_type][prop_name]

  for prop_name, by_kind in six.iteritems(combined_entities):
    for kind, entity_fields in six.iteritems(by_kind):
      index_fields = combined_indexes[prop_name][kind]
      name = u'_'.join([prop_name, kind])
      props = {'timestamp': timestamp, 'kind_name': kind,
               'property_name': prop_name,
               'builtin_index_count': index_fields.count,
               'builtin_index_bytes': index_fields.bytes,
               'count': entity_fields.count,
               'entity_bytes': entity_fields.bytes,
               'bytes': entity_fields.bytes + index_fields.bytes}
      entities.append(fill_entity(project_id, stats_kind, props, name))

  stats_kind = u'__Stat_PropertyType_Kind__'
  combined_entities = defaultdict(lambda: defaultdict(CountBytes))
  combined_indexes = defaultdict(lambda: defaultdict(CountBytes))
  for namespace, by_kind in six.iteritems(prop_stats.entity_stats):
    for kind, by_type in six.iteritems(by_kind):
      for prop_type, by_name in six.iteritems(by_type):
        combined_entities[prop_type][kind] += sum(six.itervalues(by_name),
                                                  CountBytes())
        combined_indexes[prop_type][kind] += sum(
          six.itervalues(prop_stats.index_stats[namespace][kind][prop_type]),
          CountBytes())

  for prop_type, by_kind in six.iteritems(combined_entities):
    type_name = StatsPropTypes.NAMES[prop_type]
    for kind, entity_fields in six.iteritems(by_kind):
      index_fields = combined_indexes[prop_type][kind]
      name = u'_'.join([type_name, kind])
      props = {'timestamp': timestamp, 'kind_name': kind,
               'property_type': type_name,
               'builtin_index_count': index_fields.count,
               'builtin_index_bytes': index_fields.bytes,
               'count': entity_fields.count,
               'entity_bytes': entity_fields.bytes,
               'bytes': entity_fields.bytes + index_fields.bytes}
      entities.append(fill_entity(project_id, stats_kind, props, name))

  stats_kind = u'__Stat_PropertyType_PropertyName_Kind__'
  entity_props_by_type_name_kind = defaultdict(
    lambda: defaultdict(lambda: defaultdict(CountBytes)))
  index_props_by_type_name_kind = defaultdict(
    lambda: defaultdict(lambda: defaultdict(CountBytes)))
  for namespace, by_kind in six.iteritems(prop_stats.entity_stats):
    for kind, by_type in six.iteritems(by_kind):
      for prop_type, by_name in six.iteritems(by_type):
        for prop_name, entity_fields in six.iteritems(by_name):
          entity_props_by_type_name_kind[prop_type][prop_name][kind] += \
            entity_fields
          index_props_by_type_name_kind[prop_type][prop_name][kind] += \
            prop_stats.index_stats[namespace][kind][prop_type][prop_name]

  for prop_type, by_name in six.iteritems(entity_props_by_type_name_kind):
    type_name = StatsPropTypes.NAMES[prop_type]
    for prop_name, by_kind in six.iteritems(by_name):
      for kind, entity_fields in six.iteritems(by_kind):
        index_fields = index_props_by_type_name_kind[prop_type][prop_name][kind]
        name = u'_'.join([type_name, prop_name, kind])
        props = {'timestamp': timestamp, 'kind_name': kind,
                 'property_type': type_name, 'property_name': prop_name,
                 'builtin_index_count': index_fields.count,
                 'builtin_index_bytes': index_fields.bytes,
                 'count': entity_fields.count,
                 'entity_bytes': entity_fields.bytes,
                 'bytes': entity_fields.bytes + index_fields.bytes}
        entities.append(fill_entity(project_id, stats_kind, props, name))

  stats_kind = u'__Stat_PropertyType__'
  for prop_type, by_name in six.iteritems(entity_props_by_type_name_kind):
    type_name = StatsPropTypes.NAMES[prop_type]
    entity_fields = sum(
      (sum(six.itervalues(by_kind), CountBytes())
       for by_kind in six.itervalues(by_name)), CountBytes())
    index_fields = sum(
      (sum(six.itervalues(by_kind), CountBytes())
       for by_kind in six.itervalues(index_props_by_type_name_kind[prop_type])),
      CountBytes())
    props = {'timestamp': timestamp, 'property_type': type_name,
             'builtin_index_count': index_fields.count,
             'builtin_index_bytes': index_fields.bytes,
             'count': entity_fields.count,
             'entity_bytes': entity_fields.bytes,
             'bytes': entity_fields.bytes + index_fields.bytes}
    entities.append(fill_entity(project_id, stats_kind, props, type_name))

  return entities
