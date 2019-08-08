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














"""Defines input readers for MapReduce."""



__all__ = [
    "AbstractDatastoreInputReader",
    "ALLOW_CHECKPOINT",
    "BadReaderParamsError",
    "BlobstoreLineInputReader",
    "BlobstoreZipInputReader",
    "BlobstoreZipLineInputReader",
    "COUNTER_IO_READ_BYTES",
    "COUNTER_IO_READ_MSEC",
    "DatastoreEntityInputReader",
    "DatastoreInputReader",
    "DatastoreKeyInputReader",
    "GoogleCloudStorageInputReader",
    "GoogleCloudStorageRecordInputReader",
    "RandomStringInputReader",
    "RawDatastoreInputReader",
    "Error",
    "InputReader",
    "LogInputReader",
    "NamespaceInputReader",
    ]




import base64
import copy
import logging
import pickle
import random
import string
import StringIO
import time
import zipfile

from google.net.proto import ProtocolBuffer
from google.appengine.ext import ndb

from google.appengine.api import datastore
from google.appengine.api import logservice
from google.appengine.api.logservice import log_service_pb
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import key_range
from google.appengine.ext.db import metadata
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import datastore_range_iterators as db_iters
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import json_util
from google.appengine.ext.mapreduce import key_ranges
from google.appengine.ext.mapreduce import kv_pb
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import namespace_range
from google.appengine.ext.mapreduce import operation
from google.appengine.ext.mapreduce import property_range
from google.appengine.ext.mapreduce import records
from google.appengine.ext.mapreduce import util



try:

  cloudstorage = None
  from google.appengine._internal import cloudstorage
  if hasattr(cloudstorage, "_STUB"):
    cloudstorage = None
except ImportError:
  pass


if cloudstorage is None:
  try:
    import cloudstorage
  except ImportError:
    pass



Error = errors.Error
BadReaderParamsError = errors.BadReaderParamsError



COUNTER_IO_READ_BYTES = "io-read-bytes"


COUNTER_IO_READ_MSEC = "io-read-msec"



ALLOW_CHECKPOINT = util.ALLOW_CHECKPOINT


class InputReader(json_util.JsonMixin):
  """Abstract base class for input readers.

  InputReaders have the following properties:
   * They are created by using the split_input method to generate a set of
     InputReaders from a MapperSpec.
   * They generate inputs to the mapper via the iterator interface.
   * After creation, they can be serialized and resumed using the JsonMixin
     interface.
   * They are cast to string for a user-readable description; it may be
     valuable to implement __str__.
  """




  expand_parameters = False


  _APP_PARAM = "_app"
  NAMESPACE_PARAM = "namespace"
  NAMESPACES_PARAM = "namespaces"

  def __iter__(self):
    return self

  def next(self):
    """Returns the next input from this input reader as a key, value pair.

    Returns:
      The next input from this input reader.
    """
    raise NotImplementedError("next() not implemented in %s" % self.__class__)

  @classmethod
  def from_json(cls, input_shard_state):
    """Creates an instance of the InputReader for the given input shard state.

    Args:
      input_shard_state: The InputReader state as a dict-like object.

    Returns:
      An instance of the InputReader configured using the values of json.
    """
    raise NotImplementedError("from_json() not implemented in %s" % cls)

  def to_json(self):
    """Returns an input shard state for the remaining inputs.

    Returns:
      A json-izable version of the remaining InputReader.
    """
    raise NotImplementedError("to_json() not implemented in %s" %
                              self.__class__)

  @classmethod
  def split_input(cls, mapper_spec):
    """Returns a list of input readers.

    This method creates a list of input readers, each for one shard.
    It attempts to split inputs among readers evenly.

    Args:
      mapper_spec: model.MapperSpec specifies the inputs and additional
        parameters to define the behavior of input readers.

    Returns:
      A list of InputReaders. None or [] when no input data can be found.
    """
    raise NotImplementedError("split_input() not implemented in %s" % cls)

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Input reader parameters are expected to be passed as "input_reader"
    subdictionary in mapper_spec.params.

    Pre 1.6.4 API mixes input reader parameters with all other parameters. Thus
    to be compatible, input reader check mapper_spec.params as well and
    issue a warning if "input_reader" subdicationary is not present.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    if mapper_spec.input_reader_class() != cls:
      raise BadReaderParamsError("Input reader class mismatch")


def _get_params(mapper_spec, allowed_keys=None, allow_old=True):
  """Obtain input reader parameters.

  Utility function for input readers implementation. Fetches parameters
  from mapreduce specification giving appropriate usage warnings.

  Args:
    mapper_spec: The MapperSpec for the job
    allowed_keys: set of all allowed keys in parameters as strings. If it is not
      None, then parameters are expected to be in a separate "input_reader"
      subdictionary of mapper_spec parameters.
    allow_old: Allow parameters to exist outside of the input_reader
      subdictionary for compatability.

  Returns:
    mapper parameters as dict

  Raises:
    BadReaderParamsError: if parameters are invalid/missing or not allowed.
  """
  if "input_reader" not in mapper_spec.params:
    message = ("Input reader's parameters should be specified in "
               "input_reader subdictionary.")
    if not allow_old or allowed_keys:
      raise errors.BadReaderParamsError(message)
    params = mapper_spec.params
    params = dict((str(n), v) for n, v in params.iteritems())
  else:
    if not isinstance(mapper_spec.params.get("input_reader"), dict):
      raise errors.BadReaderParamsError(
          "Input reader parameters should be a dictionary")
    params = mapper_spec.params.get("input_reader")
    params = dict((str(n), v) for n, v in params.iteritems())
    if allowed_keys:
      params_diff = set(params.keys()) - allowed_keys
      if params_diff:
        raise errors.BadReaderParamsError(
            "Invalid input_reader parameters: %s" % ",".join(params_diff))
  return params


class AbstractDatastoreInputReader(InputReader):
  """Abstract class for datastore input readers."""


  _BATCH_SIZE = 50


  _MAX_SHARD_COUNT = 256




  MAX_NAMESPACES_FOR_KEY_SHARD = 10


  ENTITY_KIND_PARAM = "entity_kind"
  KEYS_ONLY_PARAM = "keys_only"
  BATCH_SIZE_PARAM = "batch_size"
  KEY_RANGE_PARAM = "key_range"
  FILTERS_PARAM = "filters"
  WHOLE_EG_PARAM = "whole_eg"

  _KEY_RANGE_ITER_CLS = db_iters.AbstractKeyRangeIterator

  def __init__(self, iterator):
    """Create new DatastoreInputReader object.

    This is internal constructor. Use split_input to create readers instead.

    Args:
      iterator: an iterator that generates objects for this input reader.
    """
    self._iter = iterator

  def __iter__(self):
    """Yields whatever internal iterator yields."""
    for o in self._iter:
      yield o

  def __str__(self):
    """Returns the string representation of this InputReader."""
    return repr(self._iter)

  def to_json(self):
    """Serializes input reader to json compatible format.

    Returns:
      all the data in json-compatible map.
    """
    return self._iter.to_json()

  @classmethod
  def from_json(cls, json):
    """Create new DatastoreInputReader from json, encoded by to_json.

    Args:
      json: json representation of DatastoreInputReader.

    Returns:
      an instance of DatastoreInputReader with all data deserialized from json.
    """
    return cls(db_iters.RangeIteratorFactory.from_json(json))

  @classmethod
  def _get_query_spec(cls, mapper_spec):
    """Construct a model.QuerySpec from model.MapperSpec."""
    params = _get_params(mapper_spec)
    entity_kind = params[cls.ENTITY_KIND_PARAM]
    filters = params.get(cls.FILTERS_PARAM)
    app = params.get(cls._APP_PARAM)
    ns = params.get(cls.NAMESPACE_PARAM)

    return model.QuerySpec(
        entity_kind=cls._get_raw_entity_kind(entity_kind),
        keys_only=bool(params.get(cls.KEYS_ONLY_PARAM, False)),
        filters=filters,
        batch_size=int(params.get(cls.BATCH_SIZE_PARAM, cls._BATCH_SIZE)),
        model_class_path=entity_kind,
        app=app,
        ns=ns)

  @classmethod
  def split_input(cls, mapper_spec):
    """Inherit doc."""
    shard_count = mapper_spec.shard_count
    query_spec = cls._get_query_spec(mapper_spec)
    params = _get_params(mapper_spec)
    shard_whole_eg = params.get(cls.WHOLE_EG_PARAM, False)

    namespaces = None
    if query_spec.ns is not None:
      k_ranges = cls._to_key_ranges_by_shard(
          query_spec.app, [query_spec.ns], shard_count, query_spec,
          shard_whole_eg=shard_whole_eg)
    else:
      ns_keys = namespace_range.get_namespace_keys(
          query_spec.app, cls.MAX_NAMESPACES_FOR_KEY_SHARD+1)


      if not ns_keys:
        return


      elif len(ns_keys) <= cls.MAX_NAMESPACES_FOR_KEY_SHARD:
        namespaces = [ns_key.name() or "" for ns_key in ns_keys]
        k_ranges = cls._to_key_ranges_by_shard(
            query_spec.app, namespaces, shard_count, query_spec,
            shard_whole_eg=shard_whole_eg)

      else:
        ns_ranges = namespace_range.NamespaceRange.split(n=shard_count,
                                                         contiguous=False,
                                                         can_query=lambda: True,
                                                         _app=query_spec.app)
        k_ranges = [key_ranges.KeyRangesFactory.create_from_ns_range(ns_range)
                    for ns_range in ns_ranges]

    iters = [db_iters.RangeIteratorFactory.create_key_ranges_iterator(
        r, query_spec, cls._KEY_RANGE_ITER_CLS) for r in k_ranges]

    return [cls(i) for i in iters]

  @classmethod
  def _to_key_ranges_by_shard(cls, app, namespaces, shard_count, query_spec,
                              shard_whole_eg=False):
    """Get a list of key_ranges.KeyRanges objects, one for each shard.

    This method uses scatter index to split each namespace into pieces
    and assign those pieces to shards.

    Args:
      app: app_id in str.
      namespaces: a list of namespaces in str.
      shard_count: number of shards to split.
      query_spec: model.QuerySpec.
      shard_whole_eg: Whether to align shard ranges to entity-group boundaries.

    Returns:
      a list of key_ranges.KeyRanges objects.
    """


    key_ranges_by_ns = []
    for namespace in namespaces:
      ranges = cls._split_ns_by_scatter(
          shard_count,
          namespace,
          query_spec.entity_kind,
          app,
          shard_whole_eg=shard_whole_eg)


      random.shuffle(ranges)
      key_ranges_by_ns.append(ranges)



    ranges_by_shard = [[] for _ in range(shard_count)]
    for ranges in key_ranges_by_ns:
      for i, k_range in enumerate(ranges):
        if k_range:
          ranges_by_shard[i].append(k_range)


    key_ranges_by_shard = []
    for ranges in ranges_by_shard:
      if ranges:
        key_ranges_by_shard.append(key_ranges.KeyRangesFactory.create_from_list(
            ranges))
    return key_ranges_by_shard

  @classmethod
  def _split_ns_by_scatter(cls, shard_count, namespace, raw_entity_kind, app,
                           shard_whole_eg=False):
    """Split a namespace by scatter index into key_range.KeyRange.

    TODO: Power this with key_range.KeyRange.compute_split_points.

    Args:
      shard_count: number of shards.
      namespace: namespace name to split. str.
      raw_entity_kind: low level datastore API entity kind.
      app: app id in str.
      shard_whole_eg: Whether to align shard ranges to entity-group boundaries.

    Returns:
      A list of key_range.KeyRange objects. If there are not enough entities to
    splits into requested shards, the returned list will contain KeyRanges
    ordered lexicographically with any Nones appearing at the end.
    """
    if shard_count == 1:

      return [key_range.KeyRange(namespace=namespace, _app=app)]

    ds_query = datastore.Query(kind=raw_entity_kind,
                               namespace=namespace,
                               _app=app,
                               keys_only=True)
    ds_query.Order("__scatter__")
    oversampling_factor = 32
    random_keys = ds_query.Get(shard_count * oversampling_factor)

    if not random_keys:


      return ([key_range.KeyRange(namespace=namespace, _app=app)] +
              [None] * (shard_count - 1))

    random_keys.sort()
    if shard_whole_eg:
      random_keys = cls.align_to_entity_groups(random_keys)

    if len(random_keys) >= shard_count:

      random_keys = cls._choose_split_points(random_keys, shard_count)

    k_ranges = []

    k_ranges.append(key_range.KeyRange(
        key_start=None,
        key_end=random_keys[0],
        direction=key_range.KeyRange.ASC,
        include_start=False,
        include_end=False,
        namespace=namespace,
        _app=app))

    for i in range(0, len(random_keys) - 1):
      k_ranges.append(key_range.KeyRange(
          key_start=random_keys[i],
          key_end=random_keys[i+1],
          direction=key_range.KeyRange.ASC,
          include_start=True,
          include_end=False,
          namespace=namespace,
          _app=app))

    k_ranges.append(key_range.KeyRange(
        key_start=random_keys[-1],
        key_end=None,
        direction=key_range.KeyRange.ASC,
        include_start=True,
        include_end=False,
        namespace=namespace,
        _app=app))

    if len(k_ranges) < shard_count:

      k_ranges += [None] * (shard_count - len(k_ranges))
    return k_ranges

  @classmethod
  def _choose_split_points(cls, sorted_keys, shard_count):
    """Returns the best split points given a random set of datastore.Keys."""
    assert len(sorted_keys) >= shard_count
    index_stride = len(sorted_keys) / float(shard_count)
    return [sorted_keys[int(round(index_stride * i))]
            for i in range(1, shard_count)]

  @classmethod
  def align_to_entity_groups(cls, keys):
    """Aligns the specified keys to entity group boundaries.

    This entails converting each key to the key of its entity group and
    removing duplicates.

    Args:
      keys: The sorted list of entity keys that should be aligned. If the list
        contains Nones, they must all be at the end.

    Returns:
      The sorted list of entity group keys, with Nones truncated from the end.
    """
    result = []
    for key in keys:
      if key is None:
        break
      eg_key = key.entity_group()
      if not result or result[-1] != eg_key:
        result.append(eg_key)

    return result

  @classmethod
  def validate(cls, mapper_spec):
    """Inherit docs."""
    params = _get_params(mapper_spec)
    if cls.ENTITY_KIND_PARAM not in params:
      raise BadReaderParamsError("Missing input reader parameter 'entity_kind'")
    if cls.BATCH_SIZE_PARAM in params:
      try:
        batch_size = int(params[cls.BATCH_SIZE_PARAM])
        if batch_size < 1:
          raise BadReaderParamsError("Bad batch size: %s" % batch_size)
      except ValueError, e:
        raise BadReaderParamsError("Bad batch size: %s" % e)
    if cls.NAMESPACE_PARAM in params:
      if not isinstance(params[cls.NAMESPACE_PARAM],
                        (str, unicode, type(None))):
        raise BadReaderParamsError(
            "Expected a single namespace string")
    if cls.NAMESPACES_PARAM in params:
      raise BadReaderParamsError("Multiple namespaces are no longer supported")
    if cls.FILTERS_PARAM in params:
      filters = params[cls.FILTERS_PARAM]
      if not isinstance(filters, list):
        raise BadReaderParamsError("Expected list for filters parameter")
      for f in filters:
        if not isinstance(f, (tuple, list)):
          raise BadReaderParamsError("Filter should be a tuple or list: %s", f)
        if len(f) != 3:
          raise BadReaderParamsError("Filter should be a 3-tuple: %s", f)
        prop, op, _ = f
        if not isinstance(prop, basestring):
          raise BadReaderParamsError("Property should be string: %s", prop)
        if not isinstance(op, basestring):
          raise BadReaderParamsError("Operator should be string: %s", op)

  @classmethod
  def _get_raw_entity_kind(cls, entity_kind_or_model_classpath):
    """Returns the entity kind to use with low level datastore calls.

    Args:
      entity_kind_or_model_classpath: user specified entity kind or model
        classpath.

    Returns:
      the entity kind in str to use with low level datastore calls.
    """
    return entity_kind_or_model_classpath


class RawDatastoreInputReader(AbstractDatastoreInputReader):
  """Iterates over an entity kind and yields datastore.Entity."""

  _KEY_RANGE_ITER_CLS = db_iters.KeyRangeEntityIterator

  @classmethod
  def validate(cls, mapper_spec):
    """Inherit docs."""
    super(RawDatastoreInputReader, cls).validate(mapper_spec)
    params = _get_params(mapper_spec)
    entity_kind = params[cls.ENTITY_KIND_PARAM]
    if "." in entity_kind:
      logging.warning(
          ". detected in entity kind %s specified for reader %s."
          "Assuming entity kind contains the dot.",
          entity_kind, cls.__name__)
    if cls.FILTERS_PARAM in params:
      filters = params[cls.FILTERS_PARAM]
      for f in filters:
        if f[1] != "=":
          raise BadReaderParamsError(
              "Only equality filters are supported: %s", f)


class DatastoreInputReader(AbstractDatastoreInputReader):
  """Iterates over a Model and yields model instances.

  Supports both db.model and ndb.model.
  """

  _KEY_RANGE_ITER_CLS = db_iters.KeyRangeModelIterator

  @classmethod
  def _get_raw_entity_kind(cls, model_classpath):
    entity_type = util.for_name(model_classpath)
    if isinstance(entity_type, db.Model):
      return entity_type.kind()
    elif isinstance(entity_type, (ndb.Model, ndb.MetaModel)):

      return entity_type._get_kind()
    else:
      return util.get_short_name(model_classpath)

  @classmethod
  def validate(cls, mapper_spec):
    """Inherit docs."""
    super(DatastoreInputReader, cls).validate(mapper_spec)
    params = _get_params(mapper_spec)
    entity_kind = params[cls.ENTITY_KIND_PARAM]

    try:
      model_class = util.for_name(entity_kind)
    except ImportError, e:
      raise BadReaderParamsError("Bad entity kind: %s" % e)
    if cls.FILTERS_PARAM in params:
      filters = params[cls.FILTERS_PARAM]
      if issubclass(model_class, db.Model):
        cls._validate_filters(filters, model_class)
      else:
        cls._validate_filters_ndb(filters, model_class)
      property_range.PropertyRange(filters, entity_kind)

  @classmethod
  def _validate_filters(cls, filters, model_class):
    """Validate user supplied filters.

    Validate filters are on existing properties and filter values
    have valid semantics.

    Args:
      filters: user supplied filters. Each filter should be a list or tuple of
        format (<property_name_as_str>, <query_operator_as_str>,
        <value_of_certain_type>). Value type is up to the property's type.
      model_class: the db.Model class for the entity type to apply filters on.

    Raises:
      BadReaderParamsError: if any filter is invalid in any way.
    """
    if not filters:
      return

    properties = model_class.properties()

    for f in filters:
      prop, _, val = f
      if prop not in properties:
        raise errors.BadReaderParamsError(
            "Property %s is not defined for entity type %s",
            prop, model_class.kind())



      try:
        properties[prop].validate(val)
      except db.BadValueError, e:
        raise errors.BadReaderParamsError(e)

  @classmethod

  def _validate_filters_ndb(cls, filters, model_class):
    """Validate ndb.Model filters."""
    if not filters:
      return

    properties = model_class._properties

    for f in filters:
      prop, _, val = f
      if prop not in properties:
        raise errors.BadReaderParamsError(
            "Property %s is not defined for entity type %s",
            prop, model_class._get_kind())



      try:
        properties[prop]._do_validate(val)
      except db.BadValueError, e:
        raise errors.BadReaderParamsError(e)

  @classmethod
  def split_input(cls, mapper_spec):
    """Inherit docs."""
    shard_count = mapper_spec.shard_count
    query_spec = cls._get_query_spec(mapper_spec)

    if not property_range.should_shard_by_property_range(query_spec.filters):
      return super(DatastoreInputReader, cls).split_input(mapper_spec)

    p_range = property_range.PropertyRange(query_spec.filters,
                                           query_spec.model_class_path)
    p_ranges = p_range.split(shard_count)


    if query_spec.ns:
      ns_range = namespace_range.NamespaceRange(
          namespace_start=query_spec.ns,
          namespace_end=query_spec.ns,
          _app=query_spec.app)
      ns_ranges = [copy.copy(ns_range) for _ in p_ranges]
    else:
      ns_keys = namespace_range.get_namespace_keys(
          query_spec.app, cls.MAX_NAMESPACES_FOR_KEY_SHARD+1)
      if not ns_keys:
        return


      if len(ns_keys) <= cls.MAX_NAMESPACES_FOR_KEY_SHARD:
        ns_ranges = [namespace_range.NamespaceRange(_app=query_spec.app)
                     for _ in p_ranges]

      else:
        ns_ranges = namespace_range.NamespaceRange.split(n=shard_count,
                                                         contiguous=False,
                                                         can_query=lambda: True,
                                                         _app=query_spec.app)
        p_ranges = [copy.copy(p_range) for _ in ns_ranges]

    assert len(p_ranges) == len(ns_ranges)

    iters = [
        db_iters.RangeIteratorFactory.create_property_range_iterator(
            p, ns, query_spec) for p, ns in zip(p_ranges, ns_ranges)]
    return [cls(i) for i in iters]


class DatastoreKeyInputReader(RawDatastoreInputReader):
  """Iterate over an entity kind and yields datastore.Key."""

  _KEY_RANGE_ITER_CLS = db_iters.KeyRangeKeyIterator



DatastoreEntityInputReader = RawDatastoreInputReader




class _OldAbstractDatastoreInputReader(InputReader):
  """Abstract base class for classes that iterate over datastore entities.

  Concrete subclasses must implement _iter_key_range(self, k_range). See the
  docstring for that method for details.
  """


  _BATCH_SIZE = 50


  _MAX_SHARD_COUNT = 256


  _OVERSAMPLING_FACTOR = 32




  MAX_NAMESPACES_FOR_KEY_SHARD = 10


  ENTITY_KIND_PARAM = "entity_kind"
  KEYS_ONLY_PARAM = "keys_only"
  BATCH_SIZE_PARAM = "batch_size"
  KEY_RANGE_PARAM = "key_range"
  NAMESPACE_RANGE_PARAM = "namespace_range"
  CURRENT_KEY_RANGE_PARAM = "current_key_range"
  FILTERS_PARAM = "filters"





  def __init__(self,
               entity_kind,
               key_ranges=None,
               ns_range=None,
               batch_size=_BATCH_SIZE,
               current_key_range=None,
               filters=None):
    """Create new AbstractDatastoreInputReader object.

    This is internal constructor. Use split_query in a concrete class instead.

    Args:
      entity_kind: entity kind as string.
      key_ranges: a sequence of key_range.KeyRange instances to process. Only
          one of key_ranges or ns_range can be non-None.
      ns_range: a namespace_range.NamespaceRange to process. Only one of
          key_ranges or ns_range can be non-None.
      batch_size: size of read batch as int.
      current_key_range: the current key_range.KeyRange being processed.
      filters: optional list of filters to apply to the query. Each filter is
        a tuple: (<property_name_as_str>, <query_operation_as_str>, <value>).
        User filters are applied first.
    """
    assert key_ranges is not None or ns_range is not None, (
        "must specify one of 'key_ranges' or 'ns_range'")
    assert key_ranges is None or ns_range is None, (
        "can't specify both 'key_ranges ' and 'ns_range'")

    self._entity_kind = entity_kind


    self._key_ranges = key_ranges and list(reversed(key_ranges))

    self._ns_range = ns_range
    self._batch_size = int(batch_size)
    self._current_key_range = current_key_range
    self._filters = filters

  @classmethod
  def _get_raw_entity_kind(cls, entity_kind):
    if "." in entity_kind:
      logging.warning(
          ". detected in entity kind %s specified for reader %s."
          "Assuming entity kind contains the dot.",
          entity_kind, cls.__name__)
    return entity_kind

  def __iter__(self):
    """Iterates over the given KeyRanges or NamespaceRange.

    This method iterates over the given KeyRanges or NamespaceRange and sets
    the self._current_key_range to the KeyRange currently being processed. It
    then delegates to the _iter_key_range method to yield that actual
    results.

    Yields:
      Forwards the objects yielded by the subclasses concrete _iter_key_range()
      method. The caller must consume the result yielded because self.to_json()
      will not include it.
    """
    if self._key_ranges is not None:
      for o in self._iter_key_ranges():
        yield o
    elif self._ns_range is not None:
      for o in self._iter_ns_range():
        yield o
    else:
      assert False, "self._key_ranges and self._ns_range are both None"

  def _iter_key_ranges(self):
    """Iterates over self._key_ranges, delegating to self._iter_key_range()."""
    while True:
      if self._current_key_range is None:
        if self._key_ranges:
          self._current_key_range = self._key_ranges.pop()


          continue
        else:
          break

      for key, o in self._iter_key_range(
          copy.deepcopy(self._current_key_range)):


        self._current_key_range.advance(key)
        yield o
      self._current_key_range = None

  def _iter_ns_range(self):
    """Iterates over self._ns_range, delegating to self._iter_key_range()."""
    while True:
      if self._current_key_range is None:
        query = self._ns_range.make_datastore_query()
        namespace_result = query.Get(1)
        if not namespace_result:
          break

        namespace = namespace_result[0].name() or ""
        self._current_key_range = key_range.KeyRange(
            namespace=namespace, _app=self._ns_range.app)
        yield ALLOW_CHECKPOINT

      for key, o in self._iter_key_range(
          copy.deepcopy(self._current_key_range)):


        self._current_key_range.advance(key)
        yield o

      if (self._ns_range.is_single_namespace or
          self._current_key_range.namespace == self._ns_range.namespace_end):
        break
      self._ns_range = self._ns_range.with_start_after(
          self._current_key_range.namespace)
      self._current_key_range = None

  def _iter_key_range(self, k_range):
    """Yields a db.Key and the value that should be yielded by self.__iter__().

    Args:
      k_range: The key_range.KeyRange to iterate over.

    Yields:
      A 2-tuple containing the last db.Key processed and the value that should
      be yielded by __iter__. The returned db.Key will be used to determine the
      InputReader's current position in self._current_key_range.
    """
    raise NotImplementedError("_iter_key_range() not implemented in %s" %
                              self.__class__)

  def __str__(self):
    """Returns the string representation of this InputReader."""
    if self._ns_range is None:
      return repr(self._key_ranges)
    else:
      return repr(self._ns_range)

  @classmethod
  def _choose_split_points(cls, sorted_keys, shard_count):
    """Returns the best split points given a random set of db.Keys."""
    assert len(sorted_keys) >= shard_count
    index_stride = len(sorted_keys) / float(shard_count)
    return [sorted_keys[int(round(index_stride * i))]
            for i in range(1, shard_count)]



  @classmethod
  def _split_input_from_namespace(cls, app, namespace, entity_kind,
                                  shard_count):
    """Helper for _split_input_from_params.

    If there are not enough Entities to make all of the given shards, the
    returned list of KeyRanges will include Nones. The returned list will
    contain KeyRanges ordered lexographically with any Nones appearing at the
    end.

    Args:
      app: the app.
      namespace: the namespace.
      entity_kind: entity kind as string.
      shard_count: the number of shards.

    Returns:
      KeyRange objects.
    """

    raw_entity_kind = cls._get_raw_entity_kind(entity_kind)
    if shard_count == 1:

      return [key_range.KeyRange(namespace=namespace, _app=app)]

    ds_query = datastore.Query(kind=raw_entity_kind,
                               namespace=namespace,
                               _app=app,
                               keys_only=True)
    ds_query.Order("__scatter__")
    random_keys = ds_query.Get(shard_count * cls._OVERSAMPLING_FACTOR)

    if not random_keys:


      return ([key_range.KeyRange(namespace=namespace, _app=app)] +
              [None] * (shard_count - 1))

    random_keys.sort()

    if len(random_keys) >= shard_count:

      random_keys = cls._choose_split_points(random_keys, shard_count)


    key_ranges = []

    key_ranges.append(key_range.KeyRange(
        key_start=None,
        key_end=random_keys[0],
        direction=key_range.KeyRange.ASC,
        include_start=False,
        include_end=False,
        namespace=namespace,
        _app=app))

    for i in range(0, len(random_keys) - 1):
      key_ranges.append(key_range.KeyRange(
          key_start=random_keys[i],
          key_end=random_keys[i+1],
          direction=key_range.KeyRange.ASC,
          include_start=True,
          include_end=False,
          namespace=namespace,
          _app=app))

    key_ranges.append(key_range.KeyRange(
        key_start=random_keys[-1],
        key_end=None,
        direction=key_range.KeyRange.ASC,
        include_start=True,
        include_end=False,
        namespace=namespace,
        _app=app))

    if len(key_ranges) < shard_count:

      key_ranges += [None] * (shard_count - len(key_ranges))

    return key_ranges

  @classmethod
  def _split_input_from_params(cls, app, namespaces, entity_kind_name,
                               params, shard_count):
    """Return input reader objects. Helper for split_input."""

    key_ranges = []
    for namespace in namespaces:
      key_ranges.extend(
          cls._split_input_from_namespace(app,
                                          namespace,
                                          entity_kind_name,
                                          shard_count))




    shared_ranges = [[] for _ in range(shard_count)]
    for i, k_range in enumerate(key_ranges):
      shared_ranges[i % shard_count].append(k_range)
    batch_size = int(params.get(cls.BATCH_SIZE_PARAM, cls._BATCH_SIZE))

    return [cls(entity_kind_name,
                key_ranges=key_ranges,
                ns_range=None,
                batch_size=batch_size)
            for key_ranges in shared_ranges if key_ranges]

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    if mapper_spec.input_reader_class() != cls:
      raise BadReaderParamsError("Input reader class mismatch")
    params = _get_params(mapper_spec)
    if cls.ENTITY_KIND_PARAM not in params:
      raise BadReaderParamsError("Missing mapper parameter 'entity_kind'")
    if cls.BATCH_SIZE_PARAM in params:
      try:
        batch_size = int(params[cls.BATCH_SIZE_PARAM])
        if batch_size < 1:
          raise BadReaderParamsError("Bad batch size: %s" % batch_size)
      except ValueError, e:
        raise BadReaderParamsError("Bad batch size: %s" % e)
    if cls.NAMESPACE_PARAM in params:
      if not isinstance(params[cls.NAMESPACE_PARAM],
                        (str, unicode, type(None))):
        raise BadReaderParamsError(
            "Expected a single namespace string")
    if cls.NAMESPACES_PARAM in params:
      raise BadReaderParamsError("Multiple namespaces are no longer supported")
    if cls.FILTERS_PARAM in params:
      filters = params[cls.FILTERS_PARAM]
      if not isinstance(filters, list):
        raise BadReaderParamsError("Expected list for filters parameter")
      for f in filters:
        if not isinstance(f, (tuple, list)):
          raise BadReaderParamsError("Filter should be a tuple or list: %s", f)
        if len(f) != 3:
          raise BadReaderParamsError("Filter should be a 3-tuple: %s", f)
        if not isinstance(f[0], basestring):
          raise BadReaderParamsError("First element should be string: %s", f)
        if f[1] != "=":
          raise BadReaderParamsError(
              "Only equality filters are supported: %s", f)

  @classmethod
  def split_input(cls, mapper_spec):
    """Splits query into shards without fetching query results.

    Tries as best as it can to split the whole query result set into equal
    shards. Due to difficulty of making the perfect split, resulting shards'
    sizes might differ significantly from each other.

    Args:
      mapper_spec: MapperSpec with params containing 'entity_kind'.
        May have 'namespace' in the params as a string containing a single
        namespace. If specified then the input reader will only yield values
        in the given namespace. If 'namespace' is not given then values from
        all namespaces will be yielded. May also have 'batch_size' in the params
        to specify the number of entities to process in each batch.

    Returns:
      A list of InputReader objects. If the query results are empty then the
      empty list will be returned. Otherwise, the list will always have a length
      equal to number_of_shards but may be padded with Nones if there are too
      few results for effective sharding.
    """
    params = _get_params(mapper_spec)
    entity_kind_name = params[cls.ENTITY_KIND_PARAM]
    batch_size = int(params.get(cls.BATCH_SIZE_PARAM, cls._BATCH_SIZE))
    shard_count = mapper_spec.shard_count
    namespace = params.get(cls.NAMESPACE_PARAM)
    app = params.get(cls._APP_PARAM)
    filters = params.get(cls.FILTERS_PARAM)

    if namespace is None:











      namespace_query = datastore.Query("__namespace__",
                                        keys_only=True,
                                        _app=app)
      namespace_keys = namespace_query.Get(
          limit=cls.MAX_NAMESPACES_FOR_KEY_SHARD+1)

      if len(namespace_keys) > cls.MAX_NAMESPACES_FOR_KEY_SHARD:
        ns_ranges = namespace_range.NamespaceRange.split(n=shard_count,
                                                         contiguous=True,
                                                         _app=app)
        return [cls(entity_kind_name,
                    key_ranges=None,
                    ns_range=ns_range,
                    batch_size=batch_size,
                    filters=filters)
                for ns_range in ns_ranges]
      elif not namespace_keys:
        return [cls(entity_kind_name,
                    key_ranges=None,
                    ns_range=namespace_range.NamespaceRange(_app=app),
                    batch_size=shard_count,
                    filters=filters)]
      else:
        namespaces = [namespace_key.name() or ""
                      for namespace_key in namespace_keys]
    else:
      namespaces = [namespace]

    readers = cls._split_input_from_params(
        app, namespaces, entity_kind_name, params, shard_count)
    if filters:
      for reader in readers:
        reader._filters = filters
    return readers

  def to_json(self):
    """Serializes all the data in this query range into json form.

    Returns:
      all the data in json-compatible map.
    """
    if self._key_ranges is None:
      key_ranges_json = None
    else:
      key_ranges_json = []
      for k in self._key_ranges:
        if k:
          key_ranges_json.append(k.to_json())
        else:
          key_ranges_json.append(None)

    if self._ns_range is None:
      namespace_range_json = None
    else:
      namespace_range_json = self._ns_range.to_json_object()

    if self._current_key_range is None:
      current_key_range_json = None
    else:
      current_key_range_json = self._current_key_range.to_json()

    json_dict = {self.KEY_RANGE_PARAM: key_ranges_json,
                 self.NAMESPACE_RANGE_PARAM: namespace_range_json,
                 self.CURRENT_KEY_RANGE_PARAM: current_key_range_json,
                 self.ENTITY_KIND_PARAM: self._entity_kind,
                 self.BATCH_SIZE_PARAM: self._batch_size,
                 self.FILTERS_PARAM: self._filters}
    return json_dict

  @classmethod
  def from_json(cls, json):
    """Create new DatastoreInputReader from the json, encoded by to_json.

    Args:
      json: json map representation of DatastoreInputReader.

    Returns:
      an instance of DatastoreInputReader with all data deserialized from json.
    """
    if json[cls.KEY_RANGE_PARAM] is None:

      key_ranges = None
    else:
      key_ranges = []
      for k in json[cls.KEY_RANGE_PARAM]:
        if k:
          key_ranges.append(key_range.KeyRange.from_json(k))
        else:
          key_ranges.append(None)

    if json[cls.NAMESPACE_RANGE_PARAM] is None:
      ns_range = None
    else:
      ns_range = namespace_range.NamespaceRange.from_json_object(
          json[cls.NAMESPACE_RANGE_PARAM])

    if json[cls.CURRENT_KEY_RANGE_PARAM] is None:
      current_key_range = None
    else:
      current_key_range = key_range.KeyRange.from_json(
          json[cls.CURRENT_KEY_RANGE_PARAM])

    return cls(
        json[cls.ENTITY_KIND_PARAM],
        key_ranges,
        ns_range,
        json[cls.BATCH_SIZE_PARAM],
        current_key_range,
        filters=json.get(cls.FILTERS_PARAM))


class BlobstoreLineInputReader(InputReader):
  """Input reader for a newline delimited blob in Blobstore."""


  _BLOB_BUFFER_SIZE = 64000


  _MAX_SHARD_COUNT = 256


  _MAX_BLOB_KEYS_COUNT = 246


  BLOB_KEYS_PARAM = "blob_keys"


  INITIAL_POSITION_PARAM = "initial_position"
  END_POSITION_PARAM = "end_position"
  BLOB_KEY_PARAM = "blob_key"

  def __init__(self, blob_key, start_position, end_position):
    """Initializes this instance with the given blob key and character range.

    This BlobstoreInputReader will read from the first record starting after
    strictly after start_position until the first record ending at or after
    end_position (exclusive). As an exception, if start_position is 0, then
    this InputReader starts reading at the first record.

    Args:
      blob_key: the BlobKey that this input reader is processing.
      start_position: the position to start reading at.
      end_position: a position in the last record to read.
    """
    self._blob_key = blob_key
    self._blob_reader = blobstore.BlobReader(blob_key,
                                             self._BLOB_BUFFER_SIZE,
                                             start_position)
    self._end_position = end_position
    self._has_iterated = False
    self._read_before_start = bool(start_position)

  def next(self):
    """Returns the next input from as an (offset, line) tuple."""
    self._has_iterated = True

    if self._read_before_start:
      self._blob_reader.readline()
      self._read_before_start = False
    start_position = self._blob_reader.tell()

    if start_position > self._end_position:
      raise StopIteration()

    line = self._blob_reader.readline()

    if not line:
      raise StopIteration()

    return start_position, line.rstrip("\n")

  def to_json(self):
    """Returns an json-compatible input shard spec for remaining inputs."""
    new_pos = self._blob_reader.tell()
    if self._has_iterated:
      new_pos -= 1
    return {self.BLOB_KEY_PARAM: self._blob_key,
            self.INITIAL_POSITION_PARAM: new_pos,
            self.END_POSITION_PARAM: self._end_position}

  def __str__(self):
    """Returns the string representation of this BlobstoreLineInputReader."""
    return "blobstore.BlobKey(%r):[%d, %d]" % (
        self._blob_key, self._blob_reader.tell(), self._end_position)

  @classmethod
  def from_json(cls, json):
    """Instantiates an instance of this InputReader for the given shard spec."""
    return cls(json[cls.BLOB_KEY_PARAM],
               json[cls.INITIAL_POSITION_PARAM],
               json[cls.END_POSITION_PARAM])

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    if mapper_spec.input_reader_class() != cls:
      raise BadReaderParamsError("Mapper input reader class mismatch")
    params = _get_params(mapper_spec)
    if cls.BLOB_KEYS_PARAM not in params:
      raise BadReaderParamsError("Must specify 'blob_keys' for mapper input")
    blob_keys = params[cls.BLOB_KEYS_PARAM]
    if isinstance(blob_keys, basestring):


      blob_keys = blob_keys.split(",")
    if len(blob_keys) > cls._MAX_BLOB_KEYS_COUNT:
      raise BadReaderParamsError("Too many 'blob_keys' for mapper input")
    if not blob_keys:
      raise BadReaderParamsError("No 'blob_keys' specified for mapper input")
    for blob_key in blob_keys:
      blob_info = blobstore.BlobInfo.get(blobstore.BlobKey(blob_key))
      if not blob_info:
        raise BadReaderParamsError("Could not find blobinfo for key %s" %
                                   blob_key)

  @classmethod
  def split_input(cls, mapper_spec):
    """Returns a list of shard_count input_spec_shards for input_spec.

    Args:
      mapper_spec: The mapper specification to split from. Must contain
          'blob_keys' parameter with one or more blob keys.

    Returns:
      A list of BlobstoreInputReaders corresponding to the specified shards.
    """
    params = _get_params(mapper_spec)
    blob_keys = params[cls.BLOB_KEYS_PARAM]
    if isinstance(blob_keys, basestring):


      blob_keys = blob_keys.split(",")

    blob_sizes = {}
    for blob_key in blob_keys:
      blob_info = blobstore.BlobInfo.get(blobstore.BlobKey(blob_key))
      blob_sizes[blob_key] = blob_info.size

    shard_count = min(cls._MAX_SHARD_COUNT, mapper_spec.shard_count)
    shards_per_blob = shard_count // len(blob_keys)
    if shards_per_blob == 0:
      shards_per_blob = 1

    chunks = []
    for blob_key, blob_size in blob_sizes.items():
      blob_chunk_size = blob_size // shards_per_blob
      for i in xrange(shards_per_blob - 1):
        chunks.append(BlobstoreLineInputReader.from_json(
            {cls.BLOB_KEY_PARAM: blob_key,
             cls.INITIAL_POSITION_PARAM: blob_chunk_size * i,
             cls.END_POSITION_PARAM: blob_chunk_size * (i + 1)}))
      chunks.append(BlobstoreLineInputReader.from_json(
          {cls.BLOB_KEY_PARAM: blob_key,
           cls.INITIAL_POSITION_PARAM: blob_chunk_size * (shards_per_blob - 1),
           cls.END_POSITION_PARAM: blob_size}))
    return chunks


class BlobstoreZipInputReader(InputReader):
  """Input reader for files from a zip archive stored in the Blobstore.

  Each instance of the reader will read the TOC, from the end of the zip file,
  and then only the contained files which it is responsible for.
  """


  _MAX_SHARD_COUNT = 256


  BLOB_KEY_PARAM = "blob_key"
  START_INDEX_PARAM = "start_index"
  END_INDEX_PARAM = "end_index"

  def __init__(self, blob_key, start_index, end_index,
               _reader=blobstore.BlobReader):
    """Initializes this instance with the given blob key and file range.

    This BlobstoreZipInputReader will read from the file with index start_index
    up to but not including the file with index end_index.

    Args:
      blob_key: the BlobKey that this input reader is processing.
      start_index: the index of the first file to read.
      end_index: the index of the first file that will not be read.
      _reader: a callable that returns a file-like object for reading blobs.
          Used for dependency injection.
    """
    self._blob_key = blob_key
    self._start_index = start_index
    self._end_index = end_index
    self._reader = _reader
    self._zip = None
    self._entries = None

  def next(self):
    """Returns the next input from this input reader as (ZipInfo, opener) tuple.

    Returns:
      The next input from this input reader, in the form of a 2-tuple.
      The first element of the tuple is a zipfile.ZipInfo object.
      The second element of the tuple is a zero-argument function that, when
      called, returns the complete body of the file.
    """
    if not self._zip:
      self._zip = zipfile.ZipFile(self._reader(self._blob_key))

      self._entries = self._zip.infolist()[self._start_index:self._end_index]
      self._entries.reverse()
    if not self._entries:
      raise StopIteration()
    entry = self._entries.pop()
    self._start_index += 1
    return (entry, lambda: self._read(entry))

  def _read(self, entry):
    """Read entry content.

    Args:
      entry: zip file entry as zipfile.ZipInfo.
    Returns:
      Entry content as string.
    """
    start_time = time.time()
    content = self._zip.read(entry.filename)

    ctx = context.get()
    if ctx:
      operation.counters.Increment(COUNTER_IO_READ_BYTES, len(content))(ctx)
      operation.counters.Increment(
          COUNTER_IO_READ_MSEC, int((time.time() - start_time) * 1000))(ctx)

    return content

  @classmethod
  def from_json(cls, json):
    """Creates an instance of the InputReader for the given input shard state.

    Args:
      json: The InputReader state as a dict-like object.

    Returns:
      An instance of the InputReader configured using the values of json.
    """
    return cls(json[cls.BLOB_KEY_PARAM],
               json[cls.START_INDEX_PARAM],
               json[cls.END_INDEX_PARAM])

  def to_json(self):
    """Returns an input shard state for the remaining inputs.

    Returns:
      A json-izable version of the remaining InputReader.
    """
    return {self.BLOB_KEY_PARAM: self._blob_key,
            self.START_INDEX_PARAM: self._start_index,
            self.END_INDEX_PARAM: self._end_index}

  def __str__(self):
    """Returns the string representation of this BlobstoreZipInputReader."""
    return "blobstore.BlobKey(%r):[%d, %d]" % (
        self._blob_key, self._start_index, self._end_index)

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    if mapper_spec.input_reader_class() != cls:
      raise BadReaderParamsError("Mapper input reader class mismatch")
    params = _get_params(mapper_spec)
    if cls.BLOB_KEY_PARAM not in params:
      raise BadReaderParamsError("Must specify 'blob_key' for mapper input")
    blob_key = params[cls.BLOB_KEY_PARAM]
    blob_info = blobstore.BlobInfo.get(blobstore.BlobKey(blob_key))
    if not blob_info:
      raise BadReaderParamsError("Could not find blobinfo for key %s" %
                                 blob_key)

  @classmethod
  def split_input(cls, mapper_spec, _reader=blobstore.BlobReader):
    """Returns a list of input shard states for the input spec.

    Args:
      mapper_spec: The MapperSpec for this InputReader. Must contain
          'blob_key' parameter with one blob key.
      _reader: a callable that returns a file-like object for reading blobs.
          Used for dependency injection.

    Returns:
      A list of InputReaders spanning files within the zip.
    """
    params = _get_params(mapper_spec)
    blob_key = params[cls.BLOB_KEY_PARAM]
    zip_input = zipfile.ZipFile(_reader(blob_key))
    zfiles = zip_input.infolist()
    total_size = sum(x.file_size for x in zfiles)
    num_shards = min(mapper_spec.shard_count, cls._MAX_SHARD_COUNT)
    size_per_shard = total_size // num_shards



    shard_start_indexes = [0]
    current_shard_size = 0
    for i, fileinfo in enumerate(zfiles):
      current_shard_size += fileinfo.file_size
      if current_shard_size >= size_per_shard:
        shard_start_indexes.append(i + 1)
        current_shard_size = 0

    if shard_start_indexes[-1] != len(zfiles):
      shard_start_indexes.append(len(zfiles))

    return [cls(blob_key, start_index, end_index, _reader)
            for start_index, end_index
            in zip(shard_start_indexes, shard_start_indexes[1:])]


class BlobstoreZipLineInputReader(InputReader):
  """Input reader for newline delimited files in zip archives from Blobstore.

  This has the same external interface as the BlobstoreLineInputReader, in that
  it takes a list of blobs as its input and yields lines to the reader.
  However the blobs themselves are expected to be zip archives of line delimited
  files instead of the files themselves.

  This is useful as many line delimited files gain greatly from compression.
  """


  _MAX_SHARD_COUNT = 256


  _MAX_BLOB_KEYS_COUNT = 246


  BLOB_KEYS_PARAM = "blob_keys"


  BLOB_KEY_PARAM = "blob_key"
  START_FILE_INDEX_PARAM = "start_file_index"
  END_FILE_INDEX_PARAM = "end_file_index"
  OFFSET_PARAM = "offset"

  def __init__(self, blob_key, start_file_index, end_file_index, offset,
               _reader=blobstore.BlobReader):
    """Initializes this instance with the given blob key and file range.

    This BlobstoreZipLineInputReader will read from the file with index
    start_file_index up to but not including the file with index end_file_index.
    It will return lines starting at offset within file[start_file_index]

    Args:
      blob_key: the BlobKey that this input reader is processing.
      start_file_index: the index of the first file to read within the zip.
      end_file_index: the index of the first file that will not be read.
      offset: the byte offset within blob_key.zip[start_file_index] to start
        reading. The reader will continue to the end of the file.
      _reader: a callable that returns a file-like object for reading blobs.
          Used for dependency injection.
    """
    self._blob_key = blob_key
    self._start_file_index = start_file_index
    self._end_file_index = end_file_index
    self._initial_offset = offset
    self._reader = _reader
    self._zip = None
    self._entries = None
    self._filestream = None

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    if mapper_spec.input_reader_class() != cls:
      raise BadReaderParamsError("Mapper input reader class mismatch")
    params = _get_params(mapper_spec)
    if cls.BLOB_KEYS_PARAM not in params:
      raise BadReaderParamsError("Must specify 'blob_keys' for mapper input")

    blob_keys = params[cls.BLOB_KEYS_PARAM]
    if isinstance(blob_keys, basestring):


      blob_keys = blob_keys.split(",")
    if len(blob_keys) > cls._MAX_BLOB_KEYS_COUNT:
      raise BadReaderParamsError("Too many 'blob_keys' for mapper input")
    if not blob_keys:
      raise BadReaderParamsError("No 'blob_keys' specified for mapper input")
    for blob_key in blob_keys:
      blob_info = blobstore.BlobInfo.get(blobstore.BlobKey(blob_key))
      if not blob_info:
        raise BadReaderParamsError("Could not find blobinfo for key %s" %
                                   blob_key)

  @classmethod
  def split_input(cls, mapper_spec, _reader=blobstore.BlobReader):
    """Returns a list of input readers for the input spec.

    Args:
      mapper_spec: The MapperSpec for this InputReader. Must contain
          'blob_keys' parameter with one or more blob keys.
      _reader: a callable that returns a file-like object for reading blobs.
          Used for dependency injection.

    Returns:
      A list of InputReaders spanning the subfiles within the blobs.
      There will be at least one reader per blob, but it will otherwise
      attempt to keep the expanded size even.
    """
    params = _get_params(mapper_spec)
    blob_keys = params[cls.BLOB_KEYS_PARAM]
    if isinstance(blob_keys, basestring):


      blob_keys = blob_keys.split(",")

    blob_files = {}
    total_size = 0
    for blob_key in blob_keys:
      zip_input = zipfile.ZipFile(_reader(blob_key))
      blob_files[blob_key] = zip_input.infolist()
      total_size += sum(x.file_size for x in blob_files[blob_key])

    shard_count = min(cls._MAX_SHARD_COUNT, mapper_spec.shard_count)





    size_per_shard = total_size // shard_count

    readers = []
    for blob_key in blob_keys:
      bfiles = blob_files[blob_key]
      current_shard_size = 0
      start_file_index = 0
      next_file_index = 0
      for fileinfo in bfiles:
        next_file_index += 1
        current_shard_size += fileinfo.file_size
        if current_shard_size >= size_per_shard:
          readers.append(cls(blob_key, start_file_index, next_file_index, 0,
                             _reader))
          current_shard_size = 0
          start_file_index = next_file_index
      if current_shard_size != 0:
        readers.append(cls(blob_key, start_file_index, next_file_index, 0,
                           _reader))

    return readers

  def next(self):
    """Returns the next line from this input reader as (lineinfo, line) tuple.

    Returns:
      The next input from this input reader, in the form of a 2-tuple.
      The first element of the tuple describes the source, it is itself
        a tuple (blobkey, filenumber, byteoffset).
      The second element of the tuple is the line found at that offset.
    """
    if not self._filestream:
      if not self._zip:
        self._zip = zipfile.ZipFile(self._reader(self._blob_key))

        self._entries = self._zip.infolist()[self._start_file_index:
                                             self._end_file_index]
        self._entries.reverse()
      if not self._entries:
        raise StopIteration()
      entry = self._entries.pop()
      value = self._zip.read(entry.filename)
      self._filestream = StringIO.StringIO(value)
      if self._initial_offset:
        self._filestream.seek(self._initial_offset)
        self._filestream.readline()

    start_position = self._filestream.tell()
    line = self._filestream.readline()

    if not line:

      self._filestream.close()
      self._filestream = None
      self._start_file_index += 1
      self._initial_offset = 0
      return self.next()

    return ((self._blob_key, self._start_file_index, start_position),
            line.rstrip("\n"))

  def _next_offset(self):
    """Return the offset of the next line to read."""
    if self._filestream:
      offset = self._filestream.tell()
      if offset:
        offset -= 1
    else:
      offset = self._initial_offset

    return offset

  def to_json(self):
    """Returns an input shard state for the remaining inputs.

    Returns:
      A json-izable version of the remaining InputReader.
    """

    return {self.BLOB_KEY_PARAM: self._blob_key,
            self.START_FILE_INDEX_PARAM: self._start_file_index,
            self.END_FILE_INDEX_PARAM: self._end_file_index,
            self.OFFSET_PARAM: self._next_offset()}

  @classmethod
  def from_json(cls, json, _reader=blobstore.BlobReader):
    """Creates an instance of the InputReader for the given input shard state.

    Args:
      json: The InputReader state as a dict-like object.
      _reader: For dependency injection.

    Returns:
      An instance of the InputReader configured using the values of json.
    """
    return cls(json[cls.BLOB_KEY_PARAM],
               json[cls.START_FILE_INDEX_PARAM],
               json[cls.END_FILE_INDEX_PARAM],
               json[cls.OFFSET_PARAM],
               _reader)

  def __str__(self):
    """Returns the string representation of this reader.

    Returns:
      string blobkey:[start file num, end file num]:current offset.
    """
    return "blobstore.BlobKey(%r):[%d, %d]:%d" % (
        self._blob_key, self._start_file_index, self._end_file_index,
        self._next_offset())


class RandomStringInputReader(InputReader):
  """RandomStringInputReader generates random strings as output.

  Primary usage is to populate output with testing entries.
  """


  COUNT = "count"

  STRING_LENGTH = "string_length"

  DEFAULT_STRING_LENGTH = 10

  def __init__(self, count, string_length):
    """Initialize input reader.

    Args:
      count: number of entries this shard should generate.
      string_length: the length of generated random strings.
    """
    self._count = count
    self._string_length = string_length

  def __iter__(self):
    ctx = context.get()

    while self._count:
      self._count -= 1
      start_time = time.time()
      content = "".join(random.choice(string.ascii_lowercase)
                        for _ in range(self._string_length))
      if ctx:
        operation.counters.Increment(
            COUNTER_IO_READ_MSEC, int((time.time() - start_time) * 1000))(ctx)
        operation.counters.Increment(COUNTER_IO_READ_BYTES, len(content))(ctx)
      yield content

  @classmethod
  def split_input(cls, mapper_spec):
    params = _get_params(mapper_spec)
    count = params[cls.COUNT]
    string_length = cls.DEFAULT_STRING_LENGTH
    if cls.STRING_LENGTH in params:
      string_length = params[cls.STRING_LENGTH]

    shard_count = mapper_spec.shard_count
    count_per_shard = count // shard_count

    mr_input_readers = [
        cls(count_per_shard, string_length) for _ in range(shard_count)]

    left = count - count_per_shard*shard_count
    if left > 0:
      mr_input_readers.append(cls(left, string_length))

    return mr_input_readers

  @classmethod
  def validate(cls, mapper_spec):
    if mapper_spec.input_reader_class() != cls:
      raise BadReaderParamsError("Mapper input reader class mismatch")

    params = _get_params(mapper_spec)
    if cls.COUNT not in params:
      raise BadReaderParamsError("Must specify %s" % cls.COUNT)
    if not isinstance(params[cls.COUNT], int):
      raise BadReaderParamsError("%s should be an int but is %s" %
                                 (cls.COUNT, type(params[cls.COUNT])))
    if params[cls.COUNT] <= 0:
      raise BadReaderParamsError("%s should be a positive int")
    if cls.STRING_LENGTH in params and not (
        isinstance(params[cls.STRING_LENGTH], int) and
        params[cls.STRING_LENGTH] > 0):
      raise BadReaderParamsError("%s should be a positive int but is %s" %
                                 (cls.STRING_LENGTH, params[cls.STRING_LENGTH]))
    if (not isinstance(mapper_spec.shard_count, int) or
        mapper_spec.shard_count <= 0):
      raise BadReaderParamsError(
          "shard_count should be a positive int but is %s" %
          mapper_spec.shard_count)

  @classmethod
  def from_json(cls, json):
    return cls(json[cls.COUNT], json[cls.STRING_LENGTH])

  def to_json(self):
    return {self.COUNT: self._count, self.STRING_LENGTH: self._string_length}








class NamespaceInputReader(InputReader):
  """An input reader to iterate over namespaces.

  This reader yields namespace names as string.
  It will always produce only one shard.
  """

  NAMESPACE_RANGE_PARAM = "namespace_range"
  BATCH_SIZE_PARAM = "batch_size"
  _BATCH_SIZE = 10

  def __init__(self, ns_range, batch_size=_BATCH_SIZE):
    self.ns_range = ns_range
    self._batch_size = batch_size

  def to_json(self):
    """Serializes all the data in this query range into json form.

    Returns:
      all the data in json-compatible map.
    """
    return {self.NAMESPACE_RANGE_PARAM: self.ns_range.to_json_object(),
            self.BATCH_SIZE_PARAM: self._batch_size}

  @classmethod
  def from_json(cls, json):
    """Create new DatastoreInputReader from the json, encoded by to_json.

    Args:
      json: json map representation of DatastoreInputReader.

    Returns:
      an instance of DatastoreInputReader with all data deserialized from json.
    """
    return cls(
        namespace_range.NamespaceRange.from_json_object(
            json[cls.NAMESPACE_RANGE_PARAM]),
        json[cls.BATCH_SIZE_PARAM])

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    if mapper_spec.input_reader_class() != cls:
      raise BadReaderParamsError("Input reader class mismatch")
    params = _get_params(mapper_spec)
    if cls.BATCH_SIZE_PARAM in params:
      try:
        batch_size = int(params[cls.BATCH_SIZE_PARAM])
        if batch_size < 1:
          raise BadReaderParamsError("Bad batch size: %s" % batch_size)
      except ValueError, e:
        raise BadReaderParamsError("Bad batch size: %s" % e)

  @classmethod
  def split_input(cls, mapper_spec):
    """Returns a list of input readers for the input spec.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Returns:
      A list of InputReaders.
    """
    batch_size = int(_get_params(mapper_spec).get(
        cls.BATCH_SIZE_PARAM, cls._BATCH_SIZE))
    shard_count = mapper_spec.shard_count
    namespace_ranges = namespace_range.NamespaceRange.split(shard_count,
                                                            contiguous=True)
    return [NamespaceInputReader(ns_range, batch_size)
            for ns_range in namespace_ranges]

  def __iter__(self):
    while True:
      keys = self.ns_range.make_datastore_query().Get(limit=self._batch_size)
      if not keys:
        break

      for key in keys:
        namespace = metadata.Namespace.key_to_namespace(key)
        self.ns_range = self.ns_range.with_start_after(namespace)
        yield namespace

  def __str__(self):
    return repr(self.ns_range)


class LogInputReader(InputReader):
  """Input reader for a time range of logs via the Logs Reader API.

  The number of input shards may be specified by the SHARDS_PARAM mapper
  parameter.  A starting and ending time (in seconds since the Unix epoch) are
  required to generate time ranges over which to shard the input.
  """

  START_TIME_PARAM = "start_time"
  END_TIME_PARAM = "end_time"
  MINIMUM_LOG_LEVEL_PARAM = "minimum_log_level"
  INCLUDE_INCOMPLETE_PARAM = "include_incomplete"
  INCLUDE_APP_LOGS_PARAM = "include_app_logs"
  VERSION_IDS_PARAM = "version_ids"
  MODULE_VERSIONS_PARAM = "module_versions"


  _OFFSET_PARAM = "offset"
  _PROTOTYPE_REQUEST_PARAM = "prototype_request"

  _PARAMS = frozenset([START_TIME_PARAM, END_TIME_PARAM, _OFFSET_PARAM,
                       MINIMUM_LOG_LEVEL_PARAM, INCLUDE_INCOMPLETE_PARAM,
                       INCLUDE_APP_LOGS_PARAM, VERSION_IDS_PARAM,
                       MODULE_VERSIONS_PARAM, _PROTOTYPE_REQUEST_PARAM])
  _KWARGS = frozenset([_OFFSET_PARAM, _PROTOTYPE_REQUEST_PARAM])

  def __init__(self,
               start_time=None,
               end_time=None,
               minimum_log_level=None,
               include_incomplete=False,
               include_app_logs=False,
               version_ids=None,
               module_versions=None,
               **kwargs):
    """Constructor.

    Args:
      start_time: The earliest request completion or last-update time of logs
        that should be mapped over, in seconds since the Unix epoch.
      end_time: The latest request completion or last-update time that logs
        should be mapped over, in seconds since the Unix epoch.
      minimum_log_level: An application log level which serves as a filter on
        the requests mapped over--requests with no application log at or above
        the specified level will be omitted, even if include_app_logs is False.
      include_incomplete: Whether or not to include requests that have started
        but not yet finished, as a boolean.  Defaults to False.
      include_app_logs: Whether or not to include application level logs in the
        mapped logs, as a boolean.  Defaults to False.
      version_ids: A list of version ids whose logs should be read. This can not
        be used with module_versions
      module_versions: A list of tuples containing a module and version id
        whose logs should be read. This can not be used with version_ids
      **kwargs: A dictionary of keywords associated with this input reader.
    """
    InputReader.__init__(self)



    self.__params = dict(kwargs)

    if start_time is not None:
      self.__params[self.START_TIME_PARAM] = start_time
    if end_time is not None:
      self.__params[self.END_TIME_PARAM] = end_time
    if minimum_log_level is not None:
      self.__params[self.MINIMUM_LOG_LEVEL_PARAM] = minimum_log_level
    if include_incomplete is not None:
      self.__params[self.INCLUDE_INCOMPLETE_PARAM] = include_incomplete
    if include_app_logs is not None:
      self.__params[self.INCLUDE_APP_LOGS_PARAM] = include_app_logs
    if version_ids:
      self.__params[self.VERSION_IDS_PARAM] = version_ids
    if module_versions:
      self.__params[self.MODULE_VERSIONS_PARAM] = module_versions


    if self._PROTOTYPE_REQUEST_PARAM in self.__params:
      prototype_request = log_service_pb.LogReadRequest(
          self.__params[self._PROTOTYPE_REQUEST_PARAM])
      self.__params[self._PROTOTYPE_REQUEST_PARAM] = prototype_request

  def __iter__(self):
    """Iterates over logs in a given range of time.

    Yields:
      A RequestLog containing all the information for a single request.
    """
    for log in logservice.fetch(**self.__params):
      self.__params[self._OFFSET_PARAM] = log.offset
      yield log

  @classmethod
  def from_json(cls, json):
    """Creates an instance of the InputReader for the given input shard's state.

    Args:
      json: The InputReader state as a dict-like object.

    Returns:
      An instance of the InputReader configured using the given JSON parameters.
    """

    params = dict((str(k), v) for k, v in json.iteritems()
                  if k in cls._PARAMS)




    if cls._OFFSET_PARAM in params:
      params[cls._OFFSET_PARAM] = base64.b64decode(params[cls._OFFSET_PARAM])
    return cls(**params)

  def to_json(self):
    """Returns an input shard state for the remaining inputs.

    Returns:
      A JSON serializable version of the remaining input to read.
    """

    params = dict(self.__params)
    if self._PROTOTYPE_REQUEST_PARAM in params:
      prototype_request = params[self._PROTOTYPE_REQUEST_PARAM]
      params[self._PROTOTYPE_REQUEST_PARAM] = prototype_request.Encode()
    if self._OFFSET_PARAM in params:
      params[self._OFFSET_PARAM] = base64.b64encode(params[self._OFFSET_PARAM])
    return params

  @classmethod
  def split_input(cls, mapper_spec):
    """Returns a list of input readers for the given input specification.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Returns:
      A list of InputReaders.
    """
    params = _get_params(mapper_spec)
    shard_count = mapper_spec.shard_count


    start_time = params[cls.START_TIME_PARAM]
    end_time = params[cls.END_TIME_PARAM]
    seconds_per_shard = (end_time - start_time) / shard_count


    shards = []
    for _ in xrange(shard_count - 1):
      params[cls.END_TIME_PARAM] = (params[cls.START_TIME_PARAM] +
                                    seconds_per_shard)
      shards.append(LogInputReader(**params))
      params[cls.START_TIME_PARAM] = params[cls.END_TIME_PARAM]


    params[cls.END_TIME_PARAM] = end_time
    return shards + [LogInputReader(**params)]

  @classmethod
  def validate(cls, mapper_spec):
    """Validates the mapper's specification and all necessary parameters.

    Args:
      mapper_spec: The MapperSpec to be used with this InputReader.

    Raises:
      BadReaderParamsError: If the user fails to specify both a starting time
        and an ending time, or if the starting time is later than the ending
        time.
    """
    if mapper_spec.input_reader_class() != cls:
      raise errors.BadReaderParamsError("Input reader class mismatch")

    params = _get_params(mapper_spec, allowed_keys=cls._PARAMS)
    if (cls.VERSION_IDS_PARAM not in params and
        cls.MODULE_VERSIONS_PARAM not in params):
      raise errors.BadReaderParamsError("Must specify a list of version ids or "
                                        "module/version ids for mapper input")
    if (cls.VERSION_IDS_PARAM in params and
        cls.MODULE_VERSIONS_PARAM in params):
      raise errors.BadReaderParamsError("Can not supply both version ids or "
                                        "module/version ids. Use only one.")
    if (cls.START_TIME_PARAM not in params or
        params[cls.START_TIME_PARAM] is None):
      raise errors.BadReaderParamsError("Must specify a starting time for "
                                        "mapper input")
    if cls.END_TIME_PARAM not in params or params[cls.END_TIME_PARAM] is None:
      params[cls.END_TIME_PARAM] = time.time()

    if params[cls.START_TIME_PARAM] >= params[cls.END_TIME_PARAM]:
      raise errors.BadReaderParamsError("The starting time cannot be later "
                                        "than or the same as the ending time.")

    if cls._PROTOTYPE_REQUEST_PARAM in params:
      try:
        params[cls._PROTOTYPE_REQUEST_PARAM] = log_service_pb.LogReadRequest(
            params[cls._PROTOTYPE_REQUEST_PARAM])
      except (TypeError, ProtocolBuffer.ProtocolBufferDecodeError):
        raise errors.BadReaderParamsError("The prototype request must be "
                                          "parseable as a LogReadRequest.")




    try:
      logservice.fetch(**params)
    except logservice.InvalidArgumentError, e:
      raise errors.BadReaderParamsError("One or more parameters are not valid "
                                        "inputs to logservice.fetch(): %s" % e)

  def __str__(self):
    """Returns the string representation of this LogInputReader."""
    params = []
    for key in sorted(self.__params.keys()):
      value = self.__params[key]
      if key is self._PROTOTYPE_REQUEST_PARAM:
        params.append("%s='%s'" % (key, value))
      elif key is self._OFFSET_PARAM:
        params.append("%s='%s'" % (key, value))
      else:
        params.append("%s=%s" % (key, value))

    return "LogInputReader(%s)" % ", ".join(params)


class _GoogleCloudStorageInputReader(InputReader):
  """Input reader from Google Cloud Storage using the cloudstorage library.

  This class is expected to be subclassed with a reader that understands
  user-level records.

  Required configuration in the mapper_spec.input_reader dictionary.
    BUCKET_NAME_PARAM: name of the bucket to use (with no extra delimiters or
      suffixed such as directories.
    OBJECT_NAMES_PARAM: a list of object names or prefixes. All objects must be
      in the BUCKET_NAME_PARAM bucket. If the name ends with a * it will be
      treated as prefix and all objects with matching names will be read.
      Entries should not start with a slash unless that is part of the object's
      name. An example list could be:
      ["my-1st-input-file", "directory/my-2nd-file", "some/other/dir/input-*"]
      To retrieve all files "*" will match every object in the bucket. If a file
      is listed twice or is covered by multiple prefixes it will be read twice,
      there is no deduplication.

  Optional configuration in the mapper_sec.input_reader dictionary.
    BUFFER_SIZE_PARAM: the size of the read buffer for each file handle.
    DELIMITER_PARAM: if specified, turn on the shallow splitting mode.
      The delimiter is used as a path separator to designate directory
      hierarchy. Matching of prefixes from OBJECT_NAME_PARAM
      will stop at the first directory instead of matching
      all files under the directory. This allows MR to process bucket with
      hundreds of thousands of files.
    FAIL_ON_MISSING_INPUT: if specified and True, the MR will fail if any of
      the input files are missing. Missing files will be skipped otherwise.
  """


  BUCKET_NAME_PARAM = "bucket_name"
  OBJECT_NAMES_PARAM = "objects"
  BUFFER_SIZE_PARAM = "buffer_size"
  DELIMITER_PARAM = "delimiter"
  FAIL_ON_MISSING_INPUT = "fail_on_missing_input"


  _ACCOUNT_ID_PARAM = "account_id"


  _JSON_PICKLE = "pickle"
  _JSON_FAIL_ON_MISSING_INPUT = "fail_on_missing_input"
  _STRING_MAX_FILES_LISTED = 10







  def __init__(self, filenames, index=0, buffer_size=None, _account_id=None,
               delimiter=None):
    """Initialize a GoogleCloudStorageInputReader instance.

    Args:
      filenames: A list of Google Cloud Storage filenames of the form
        '/bucket/objectname'.
      index: Index of the next filename to read.
      buffer_size: The size of the read buffer, None to use default.
      _account_id: Internal use only. See cloudstorage documentation.
      delimiter: Delimiter used as path separator. See class doc for details.
    """
    self._filenames = filenames
    self._index = index
    self._buffer_size = buffer_size
    self._account_id = _account_id
    self._delimiter = delimiter
    self._bucket = None
    self._bucket_iter = None






    self._fail_on_missing_input = None

  def _next_file(self):
    """Find next filename.

    self._filenames may need to be expanded via listbucket.

    Returns:
      None if no more file is left. Filename otherwise.
    """
    while True:
      if self._bucket_iter:
        try:
          return self._bucket_iter.next().filename
        except StopIteration:
          self._bucket_iter = None
          self._bucket = None
      if self._index >= len(self._filenames):
        return
      filename = self._filenames[self._index]
      self._index += 1
      if self._delimiter is None or not filename.endswith(self._delimiter):
        return filename
      self._bucket = cloudstorage.listbucket(filename,
                                             delimiter=self._delimiter)
      self._bucket_iter = iter(self._bucket)

  @classmethod
  def get_params(cls, mapper_spec, allowed_keys=None, allow_old=True):
    params = _get_params(mapper_spec, allowed_keys, allow_old)


    if (mapper_spec.params.get(cls.BUCKET_NAME_PARAM) is not None and
        params.get(cls.BUCKET_NAME_PARAM) is None):
      params[cls.BUCKET_NAME_PARAM] = mapper_spec.params[cls.BUCKET_NAME_PARAM]
    return params

  @classmethod
  def validate(cls, mapper_spec):
    """Validate mapper specification.

    Args:
      mapper_spec: an instance of model.MapperSpec

    Raises:
      BadReaderParamsError: if the specification is invalid for any reason such
        as missing the bucket name or providing an invalid bucket name.
    """
    reader_spec = cls.get_params(mapper_spec, allow_old=False)


    if cls.BUCKET_NAME_PARAM not in reader_spec:
      raise errors.BadReaderParamsError(
          "%s is required for Google Cloud Storage" %
          cls.BUCKET_NAME_PARAM)
    try:
      cloudstorage.validate_bucket_name(
          reader_spec[cls.BUCKET_NAME_PARAM])
    except ValueError, error:
      raise errors.BadReaderParamsError("Bad bucket name, %s" % (error))


    if cls.OBJECT_NAMES_PARAM not in reader_spec:
      raise errors.BadReaderParamsError(
          "%s is required for Google Cloud Storage" %
          cls.OBJECT_NAMES_PARAM)
    filenames = reader_spec[cls.OBJECT_NAMES_PARAM]
    if not isinstance(filenames, list):
      raise errors.BadReaderParamsError(
          "Object name list is not a list but a %s" %
          filenames.__class__.__name__)
    for filename in filenames:
      if not isinstance(filename, basestring):
        raise errors.BadReaderParamsError(
            "Object name is not a string but a %s" %
            filename.__class__.__name__)
    if cls.DELIMITER_PARAM in reader_spec:
      delimiter = reader_spec[cls.DELIMITER_PARAM]
      if not isinstance(delimiter, basestring):
        raise errors.BadReaderParamsError(
            "%s is not a string but a %s" %
            (cls.DELIMITER_PARAM, type(delimiter)))

  @classmethod
  def split_input(cls, mapper_spec):
    """Returns a list of input readers.

    An equal number of input files are assigned to each shard (+/- 1). If there
    are fewer files than shards, fewer than the requested number of shards will
    be used. Input files are currently never split (although for some formats
    could be and may be split in a future implementation).

    Args:
      mapper_spec: an instance of model.MapperSpec.

    Returns:
      A list of InputReaders. None when no input data can be found.
    """
    reader_spec = cls.get_params(mapper_spec, allow_old=False)
    bucket = reader_spec[cls.BUCKET_NAME_PARAM]
    filenames = reader_spec[cls.OBJECT_NAMES_PARAM]
    delimiter = reader_spec.get(cls.DELIMITER_PARAM)
    account_id = reader_spec.get(cls._ACCOUNT_ID_PARAM)
    buffer_size = reader_spec.get(cls.BUFFER_SIZE_PARAM)
    fail_on_missing_input = reader_spec.get(cls.FAIL_ON_MISSING_INPUT)


    all_filenames = []
    for filename in filenames:
      if filename.endswith("*"):
        all_filenames.extend(
            [file_stat.filename for file_stat in cloudstorage.listbucket(
                "/" + bucket + "/" + filename[:-1], delimiter=delimiter,
                _account_id=account_id)])
      else:
        all_filenames.append("/%s/%s" % (bucket, filename))


    readers = []
    for shard in range(0, mapper_spec.shard_count):
      shard_filenames = all_filenames[shard::mapper_spec.shard_count]
      if shard_filenames:
        reader = cls(
            shard_filenames, buffer_size=buffer_size, _account_id=account_id,
            delimiter=delimiter)
        reader._fail_on_missing_input = fail_on_missing_input
        readers.append(reader)
    return readers

  @classmethod
  def from_json(cls, state):
    obj = pickle.loads(state[cls._JSON_PICKLE])

    obj._fail_on_missing_input = state.get(
        cls._JSON_FAIL_ON_MISSING_INPUT, False)
    if obj._bucket:
      obj._bucket_iter = iter(obj._bucket)
    return obj

  def to_json(self):
    before_iter = self._bucket_iter
    self._bucket_iter = None
    try:
      return {
          self._JSON_PICKLE: pickle.dumps(self),


          self._JSON_FAIL_ON_MISSING_INPUT:
              getattr(self, "_fail_on_missing_input", False)
      }
    finally:
      self._bucket_itr = before_iter

  def next(self):
    """Returns the next input from this input reader, a block of bytes.

    Non existent files will be logged and skipped. The file might have been
    removed after input splitting.

    Returns:
      The next input from this input reader in the form of a cloudstorage
      ReadBuffer that supports a File-like interface (read, readline, seek,
      tell, and close). An error may be raised if the file can not be opened.

    Raises:
      StopIteration: The list of files has been exhausted.
    """
    options = {}
    if self._buffer_size:
      options["read_buffer_size"] = self._buffer_size
    if self._account_id:
      options["_account_id"] = self._account_id
    while True:
      filename = self._next_file()
      if filename is None:
        raise StopIteration()
      try:
        start_time = time.time()
        handle = cloudstorage.open(filename, **options)

        ctx = context.get()
        if ctx:
          operation.counters.Increment(
              COUNTER_IO_READ_MSEC, int((time.time() - start_time) * 1000))(ctx)

        return handle
      except cloudstorage.NotFoundError:
        self._on_missing_input_file(filename)

        if getattr(self, "_fail_on_missing_input", False):
          raise errors.FailJobError(
              "File missing in GCS, aborting: %s" % filename)

        logging.warning("File %s may have been removed. Skipping file.",
                        filename)

  def _on_missing_input_file(self, filename):
    """Hook which is called when an input file is missing.

    This implementation is a no-op.  Subclasses can override it to add error
    handling.  Note that this method should not raise exceptions.  Instead, use
    the FAIL_ON_MISSING_INPUT param to control that.

    Args:
      filename: The file that is missing.
    """
    pass

  def __str__(self):

    num_files = len(self._filenames)
    if num_files > self._STRING_MAX_FILES_LISTED:
      names = "%s...%s + %d not shown" % (
          ",".join(self._filenames[0:self._STRING_MAX_FILES_LISTED-1]),
          self._filenames[-1],
          num_files - self._STRING_MAX_FILES_LISTED)
    else:
      names = ",".join(self._filenames)

    if self._index > num_files:
      status = "EOF"
    else:
      status = "Next %s (%d of %d)" % (
          self._filenames[self._index],
          self._index + 1,
          num_files)
    return "CloudStorage [%s, %s]" % (status, names)


GoogleCloudStorageInputReader = _GoogleCloudStorageInputReader


class _GoogleCloudStorageRecordInputReader(_GoogleCloudStorageInputReader):
  """Read data from a Google Cloud Storage file using LevelDB format.

  See the _GoogleCloudStorageOutputWriter for additional configuration options.
  """

  def __getstate__(self):
    result = self.__dict__.copy()

    if "_record_reader" in result:


      result.pop("_record_reader")
    return result

  def next(self):
    """Returns the next input from this input reader, a record.

    Returns:
      The next input from this input reader in the form of a record read from
      an LevelDB file.

    Raises:
      StopIteration: The ordered set records has been exhausted.
    """
    while True:
      if not hasattr(self, "_cur_handle") or self._cur_handle is None:

        self._cur_handle = super(_GoogleCloudStorageRecordInputReader,
                                 self).next()
      if not hasattr(self, "_record_reader") or self._record_reader is None:
        self._record_reader = records.RecordsReader(self._cur_handle)

      try:
        start_time = time.time()
        content = self._record_reader.read()

        ctx = context.get()
        if ctx:
          operation.counters.Increment(COUNTER_IO_READ_BYTES, len(content))(ctx)
          operation.counters.Increment(
              COUNTER_IO_READ_MSEC, int((time.time() - start_time) * 1000))(ctx)
        return content

      except EOFError:
        self._cur_handle = None
        self._record_reader = None


GoogleCloudStorageRecordInputReader = _GoogleCloudStorageRecordInputReader


class _ReducerReader(_GoogleCloudStorageRecordInputReader):
  """Reader to read KeyValues records from GCS."""

  expand_parameters = True

  def __init__(self, filenames, index=0, buffer_size=None, _account_id=None,
               delimiter=None):
    super(_ReducerReader, self).__init__(filenames, index, buffer_size,
                                         _account_id, delimiter)
    self.current_key = None
    self.current_values = None

  def __iter__(self):
    ctx = context.get()
    combiner = None

    if ctx:
      combiner_spec = ctx.mapreduce_spec.mapper.params.get("combiner_spec")
      if combiner_spec:
        combiner = util.handler_for_name(combiner_spec)

    try:
      while True:
        binary_record = super(_ReducerReader, self).next()
        proto = kv_pb.KeyValues()
        proto.ParseFromString(binary_record)

        to_yield = None
        if self.current_key is not None and self.current_key != proto.key():
          to_yield = (self.current_key, self.current_values)
          self.current_key = None
          self.current_values = None

        if self.current_key is None:
          self.current_key = proto.key()
          self.current_values = []

        if combiner:
          combiner_result = combiner(
              self.current_key, proto.value_list(), self.current_values)

          if not util.is_generator(combiner_result):
            raise errors.BadCombinerOutputError(
                "Combiner %s should yield values instead of returning them "
                "(%s)" % (combiner, combiner_result))

          self.current_values = []
          for value in combiner_result:
            if isinstance(value, operation.Operation):
              value(ctx)
            else:

              self.current_values.append(value)




          if not to_yield:
            yield ALLOW_CHECKPOINT
        else:

          self.current_values.extend(proto.value_list())

        if to_yield:
          yield to_yield

          yield ALLOW_CHECKPOINT
    except StopIteration:
      pass



    if self.current_key is not None:
      to_yield = (self.current_key, self.current_values)
      self.current_key = None
      self.current_values = None
      yield to_yield

  @staticmethod
  def encode_data(data):
    """Encodes the given data, which may have include raw bytes.

    Works around limitations in JSON encoding, which cannot handle raw bytes.

    Args:
      data: the data to encode.

    Returns:
      The data encoded.
    """
    return base64.b64encode(pickle.dumps(data))

  @staticmethod
  def decode_data(data):
    """Decodes data encoded with the encode_data function."""
    return pickle.loads(base64.b64decode(data))

  def to_json(self):
    """Returns an input shard state for the remaining inputs.

    Returns:
      A json-izable version of the remaining InputReader.
    """
    result = super(_ReducerReader, self).to_json()
    result["current_key"] = self.encode_data(self.current_key)
    result["current_values"] = self.encode_data(self.current_values)
    return result

  @classmethod
  def from_json(cls, json):
    """Creates an instance of the InputReader for the given input shard state.

    Args:
      json: The InputReader state as a dict-like object.

    Returns:
      An instance of the InputReader configured using the values of json.
    """
    result = super(_ReducerReader, cls).from_json(json)
    result.current_key = _ReducerReader.decode_data(json["current_key"])
    result.current_values = _ReducerReader.decode_data(json["current_values"])
    return result
