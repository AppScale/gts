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




"""Generate Datastore Stats over Dev mode appserver's datastore."""









import datetime
import logging

from google.appengine.api import datastore
from google.appengine.api import datastore_types
from google.appengine.api import users
from google.appengine.ext.db import stats

DELETE_BATCH_SIZE = 100


_GLOBAL_KEY = (stats.GlobalStat, 'total_entity_usage', '')




_PROPERTY_TYPE_TO_DSS_NAME = {
    unicode: 'String',
    bool: 'Boolean',
    long: 'Integer',
    type(None): 'NULL',
    float: 'Float',
    datastore_types.Key: 'Key',
    datastore_types.Blob: 'Blob',
    datastore_types.ByteString: 'ShortBlob',
    datastore_types.Text: 'Text',
    users.User: 'User',
    datastore_types.Category: 'Category',
    datastore_types.Link: 'Link',
    datastore_types.Email: 'Email',
    datetime.datetime: 'Date/Time',
    datastore_types.GeoPt: 'GeoPt',
    datastore_types.IM: 'IM',
    datastore_types.PhoneNumber: 'PhoneNumber',
    datastore_types.PostalAddress: 'PostalAddress',
    datastore_types.Rating: 'Rating',
    datastore_types.BlobKey: 'BlobKey',
    }




class DatastoreStatsProcessor(object):
  """Generates datastore stats for an app's an datastore entities."""

  def __init__(self, _app=None):
    self.app_id = datastore_types.ResolveAppId(_app)


    self.whole_app_stats = {}



    self.namespace_stats = {}
    self.found_non_empty_namespace = False


    self.old_stat_keys = []


    self.timestamp = datetime.datetime.utcnow()

  def __ScanAllNamespaces(self):
    """Scans all the namespaces and processes each namespace."""
    namespace_query = datastore.Query('__namespace__', _app=self.app_id)

    for namespace_entity in namespace_query.Run():
      name = namespace_entity.key().name()
      if name is None:
        name = ''
      self.__ProcessNamespace(name)

  def __ProcessNamespace(self, namespace):
    """Process all the entities in a given namespace."""

    all_query = datastore.Query(namespace=namespace, _app=self.app_id)
    all_query['__key__ >='] = datastore_types.Key.from_path(
        ' ', 1L, namespace=namespace, _app=self.app_id)


    for entity in all_query.Run():
      self.found_non_empty_namespace |= (namespace != '')
      proto = entity.ToPb()
      proto_size = len(proto.SerializeToString())

      if entity.key().kind() in stats._DATASTORE_STATS_CLASSES_BY_KIND:



        stat_kind = stats._DATASTORE_STATS_CLASSES_BY_KIND[entity.key().kind()]

        self.old_stat_keys.append(entity.key())
        self.__AggregateTotal(proto_size, namespace, stat_kind)
      else:
        self.__ProcessUserEntity(proto_size, entity.key(), proto, namespace)

  def __ProcessUserEntity(self, proto_size, key, proto, namespace):
    """Increment datastore stats for a non stats record."""
    self.__AggregateTotal(proto_size, namespace, None)

    kind_name = key.kind()

    self.__Increment(self.whole_app_stats, 1,
                     (stats.KindStat, kind_name, ''),
                     proto_size, kind_name=kind_name)

    self.__Increment(self.namespace_stats, 1,
                     (stats.NamespaceKindStat, kind_name, namespace),
                     proto_size, kind_name=kind_name)



    if key.parent() is None:
      whole_app_model = stats.KindRootEntityStat
      namespace_model = stats.NamespaceKindRootEntityStat
    else:
      whole_app_model = stats.KindNonRootEntityStat
      namespace_model = stats.NamespaceKindNonRootEntityStat

    self.__Increment(self.whole_app_stats, 1,
                     (whole_app_model, kind_name, ''),
                     proto_size, kind_name=kind_name)

    self.__Increment(self.namespace_stats, 1,
                     (namespace_model, kind_name, namespace),
                     proto_size, kind_name=kind_name)

    self.__ProcessProperties(
        kind_name,
        namespace,
        (proto.property_list(), proto.raw_property_list()))

  def __ProcessProperties(self, kind_name, namespace, prop_lists):
    for prop_list in prop_lists:
      for prop in prop_list:
        try:
          value = datastore_types.FromPropertyPb(prop)
          self.__AggregateProperty(kind_name, namespace, prop, value)
        except (AssertionError, AttributeError, TypeError, ValueError), e:
          logging.error('Cannot process property %r, exception %s' %
                        (prop, e))

  def __AggregateProperty(self, kind_name, namespace, prop, value):
    property_name = prop.name()
    property_type = _PROPERTY_TYPE_TO_DSS_NAME[type(value)]
    size = len(prop.SerializeToString())


    self.__Increment(self.whole_app_stats, 1,
                     (stats.PropertyTypeStat, property_type, ''),
                     size, property_type=property_type)

    self.__Increment(self.namespace_stats, 1,
                     (stats.NamespacePropertyTypeStat,
                      property_type, namespace),
                     size, property_type=property_type)


    self.__Increment(self.whole_app_stats, 1,
                     (stats.KindPropertyTypeStat,
                      property_type + '_' + kind_name, ''),
                     size, property_type=property_type, kind_name=kind_name)

    self.__Increment(self.namespace_stats, 1,
                     (stats.NamespaceKindPropertyTypeStat,
                      property_type + '_' + kind_name, namespace),
                     size, property_type=property_type, kind_name=kind_name)


    self.__Increment(self.whole_app_stats, 1,
                     (stats.KindPropertyNameStat,
                      property_name + '_' + kind_name, ''),
                     size, property_name=property_name, kind_name=kind_name)

    self.__Increment(self.namespace_stats, 1,
                     (stats.NamespaceKindPropertyNameStat,
                      property_name + '_' + kind_name, namespace),
                     size, property_name=property_name, kind_name=kind_name)


    self.__Increment(self.whole_app_stats, 1,
                     (stats.KindPropertyNamePropertyTypeStat,
                      property_type + '_' + property_name + '_' + kind_name,
                      ''), size, property_type=property_type,
                     property_name=property_name, kind_name=kind_name)

    self.__Increment(self.namespace_stats, 1,
                     (stats.NamespaceKindPropertyNamePropertyTypeStat,
                      property_type + '_' + property_name + '_' + kind_name,
                      namespace),
                     size, property_type=property_type,
                     property_name=property_name, kind_name=kind_name)

  def __AggregateTotal(self, size, namespace, stat_kind):
    """Aggregate total datastore stats."""

    if stat_kind == stats.GlobalStat:
      count = 0
    else:
      count = 1


    self.__Increment(self.whole_app_stats, count, _GLOBAL_KEY, size)


    name_id = namespace
    if not name_id:
      name_id = 1

    if (stat_kind == stats.NamespaceStat) and (namespace == ''):
      count = 0


    self.__Increment(self.whole_app_stats, count,
                     (stats.NamespaceStat, name_id, ''),
                     size, subject_namespace=namespace)

    if stat_kind == stats.NamespaceGlobalStat:
      count = 0


    self.__Increment(
        self.namespace_stats, count,
        (stats.NamespaceGlobalStat, 'total_entity_usage', namespace), size)

  def __Increment(self, stats_dict, count, stat_key, size, **kwds):
    """Increment stats for a particular kind.

    Args:
        stats_dict: The dictionary where the entities are held.
          The entities are keyed by stat_key. e.g. The
          __Stat_Total__ entity will be found in stats_dict[_GLOBAL_KEY].
        count: The amount to increment the datastore stat by.
        stat_key: A tuple of (db.Model of the stat, key value, namespace).
        size: The "bytes" to increment the size by.
        kwds: Name value pairs that are set on the created entities.
    """

    if stat_key not in stats_dict:
      stat_model = stat_key[0](
          key=datastore_types.Key.from_path(stat_key[0].STORED_KIND_NAME,
                                            stat_key[1],
                                            namespace=stat_key[2],
                                            _app=self.app_id),
          _app=self.app_id)
      stats_dict[stat_key] = stat_model
      for field, value in kwds.iteritems():
        setattr(stat_model, field, value)
      stat_model.count = count
      stat_model.bytes = size
      stat_model.timestamp = self.timestamp
    else:
      stat_model = stats_dict[stat_key]
      stat_model.count += count
      stat_model.bytes += size

  def __Finalize(self):
    """Finishes processing, deletes all old stats and writes new ones."""

    for i in range(0, len(self.old_stat_keys), DELETE_BATCH_SIZE):
      datastore.Delete(self.old_stat_keys[i:i+DELETE_BATCH_SIZE])

    self.written = 0

    for stat in self.whole_app_stats.itervalues():
      if stat.count:
        stat.put()
        self.written += 1



    if self.found_non_empty_namespace:
      for stat in self.namespace_stats.itervalues():
        if stat.count:
          stat.put()
          self.written += 1

  def Run(self):
    """Scans the datastore, computes new stats and writes them."""
    self.__ScanAllNamespaces()
    self.__Finalize()
    return self

  def Report(self):
    """Produce a small report about the result."""
    stat = self.whole_app_stats.get(_GLOBAL_KEY, None)
    total_size = 0
    total_count = 0
    if stat:
      total_size = stat.bytes
      total_count = stat.count

      if not total_count:
        total_count = 1

    return ('Scanned %d entities of total %d bytes. Inserted %d new records.'
            % (total_count, total_size, self.written))
