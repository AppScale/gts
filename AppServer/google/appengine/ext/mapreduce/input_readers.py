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
    "ConsistentKeyReader",
    "DatastoreEntityInputReader",
    "DatastoreInputReader",
    "DatastoreKeyInputReader",
    "Error",
    "InputReader",
    "NamespaceInputReader",
    "RecordsReader",
    ]



import copy
import StringIO
import time
import zipfile

from google.appengine.api import datastore
from google.appengine.api import files
from google.appengine.api.files import records
from google.appengine.datastore import datastore_query
from google.appengine.datastore import datastore_rpc
from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext import key_range
from google.appengine.ext.db import metadata
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import namespace_range
from google.appengine.ext.mapreduce import operation
from google.appengine.ext.mapreduce import util



Error = errors.Error
BadReaderParamsError = errors.BadReaderParamsError



COUNTER_IO_READ_BYTES = "io-read-bytes"


COUNTER_IO_READ_MSEC = "io-read-msec"




ALLOW_CHECKPOINT = object()


class InputReader(model.JsonMixin):
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
    """Returns a list of input readers for the input spec.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Returns:
      A list of InputReaders.
    """
    raise NotImplementedError("split_input() not implemented in %s" % cls)

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    raise NotImplementedError("validate() not implemented in %s" % cls)





class AbstractDatastoreInputReader(InputReader):
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




  def __init__(self,
               entity_kind,
               key_ranges=None,
               ns_range=None,
               batch_size=_BATCH_SIZE,
               current_key_range=None):
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
  def _split_input_from_namespace(cls, app, namespace, entity_kind_name,
                                  shard_count):
    """Return KeyRange objects. Helper for _split_input_from_params.

    If there are not enough Entities to make all of the given shards, the
    returned list of KeyRanges will include Nones. The returned list will
    contain KeyRanges ordered lexographically with any Nones appearing at the
    end.
    """

    raw_entity_kind = util.get_short_name(entity_kind_name)

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

      key_ranges = key_ranges + [None] * (shard_count - len(key_ranges))

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
    params = mapper_spec.params
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
    params = mapper_spec.params
    entity_kind_name = params[cls.ENTITY_KIND_PARAM]
    batch_size = int(params.get(cls.BATCH_SIZE_PARAM, cls._BATCH_SIZE))
    shard_count = mapper_spec.shard_count
    namespace = params.get(cls.NAMESPACE_PARAM)
    app = params.get(cls._APP_PARAM)

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
                    batch_size=batch_size)
                for ns_range in ns_ranges]
      else:
        namespaces = [namespace_key.name() or ""
                      for namespace_key in namespace_keys]
    else:
      namespaces = [namespace]

    return cls._split_input_from_params(
        app, namespaces, entity_kind_name, params, shard_count)

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
                 self.BATCH_SIZE_PARAM: self._batch_size}
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
        current_key_range)


class DatastoreInputReader(AbstractDatastoreInputReader):
  """Represents a range in query results.

  DatastoreInputReader yields model instances from the entities in a given key
  range. Iterating over DatastoreInputReader changes its range past consumed
  entries.

  The class shouldn't be instantiated directly. Use the split_input class method
  instead.
  """

  def _iter_key_range(self, k_range):
    cursor = None
    while True:
      query = k_range.make_ascending_query(
          util.for_name(self._entity_kind))
      if cursor:
        query.with_cursor(cursor)

      results = query.fetch(limit=self._batch_size)
      if not results:
        break

      for model_instance in results:
        key = model_instance.key()
        yield key, model_instance
      cursor = query.cursor()

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    super(DatastoreInputReader, cls).validate(mapper_spec)
    params = mapper_spec.params
    keys_only = util.parse_bool(params.get(cls.KEYS_ONLY_PARAM, False))
    if keys_only:
      raise BadReaderParamsError("The keys_only parameter is obsolete. "
                                 "Use DatastoreKeyInputReader instead.")

    entity_kind_name = params[cls.ENTITY_KIND_PARAM]

    try:
      util.for_name(entity_kind_name)
    except ImportError, e:
      raise BadReaderParamsError("Bad entity kind: %s" % e)


class DatastoreKeyInputReader(AbstractDatastoreInputReader):
  """An input reader which takes a Kind and yields Keys for that kind."""

  def _iter_key_range(self, k_range):
    raw_entity_kind = util.get_short_name(self._entity_kind)
    query = k_range.make_ascending_datastore_query(
        raw_entity_kind, keys_only=True)
    for key in query.Run(
        config=datastore_query.QueryOptions(batch_size=self._batch_size)):
      yield key, key


class DatastoreEntityInputReader(AbstractDatastoreInputReader):
  """An input reader which yields low level datastore entities for a kind."""

  def _iter_key_range(self, k_range):
    raw_entity_kind = util.get_short_name(self._entity_kind)
    query = k_range.make_ascending_datastore_query(
        raw_entity_kind)
    for entity in query.Run(
        config=datastore_query.QueryOptions(batch_size=self._batch_size)):
      yield entity.key(), entity


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
    params = mapper_spec.params
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
    params = mapper_spec.params
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
    params = mapper_spec.params
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
    params = mapper_spec.params
    blob_key = params[cls.BLOB_KEY_PARAM]
    zip_input = zipfile.ZipFile(_reader(blob_key))
    files = zip_input.infolist()
    total_size = sum(x.file_size for x in files)
    num_shards = min(mapper_spec.shard_count, cls._MAX_SHARD_COUNT)
    size_per_shard = total_size // num_shards



    shard_start_indexes = [0]
    current_shard_size = 0
    for i, fileinfo in enumerate(files):
      current_shard_size += fileinfo.file_size
      if current_shard_size >= size_per_shard:
        shard_start_indexes.append(i + 1)
        current_shard_size = 0

    if shard_start_indexes[-1] != len(files):
      shard_start_indexes.append(len(files))

    return [cls(blob_key, start_index, end_index, _reader)
            for start_index, end_index
            in zip(shard_start_indexes, shard_start_indexes[1:])]


class BlobstoreZipLineInputReader(InputReader):
  """Input reader for newline delimited files in zip archives from  Blobstore.

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
    params = mapper_spec.params
    if cls.BLOB_KEYS_PARAM not in params:
      raise BadReaderParamsError("Must specify 'blob_key' for mapper input")

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
    params = mapper_spec.params
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
      files = blob_files[blob_key]
      current_shard_size = 0
      start_file_index = 0
      next_file_index = 0
      for fileinfo in files:
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


class ConsistentKeyReader(DatastoreKeyInputReader):
  """A key reader which reads consistent data from datastore.

  Datastore might have entities which were written, but not visible through
  queries for some time. Typically these entities can be only read inside
  transaction until they are 'applied'.

  This reader reads all keys even if they are not visible. It might take
  significant time to start yielding some data because it has to apply all
  modifications created before its start.
  """
  START_TIME_US_PARAM = "start_time_us"
  UNAPPLIED_LOG_FILTER = "__unapplied_log_timestamp_us__ <"
  DUMMY_KIND = "DUMMY_KIND"
  DUMMY_ID = 106275677020293L
  UNAPPLIED_QUERY_DEADLINE = 270

  def _get_unapplied_jobs_accross_namespaces(self,
                                             namespace_start,
                                             namespace_end,
                                             app):
    filters = {"__key__ >=": db.Key.from_path("__namespace__",
                                              namespace_start or 1,
                                              _app=app),
               "__key__ <=": db.Key.from_path("__namespace__",
                                              namespace_end or 1,
                                              _app=app),
               self.UNAPPLIED_LOG_FILTER: self.start_time_us}
    unapplied_query = datastore.Query(filters=filters, keys_only=True, _app=app)
    return unapplied_query.Get(
        limit=self._batch_size,
        config=datastore_rpc.Configuration(
            deadline=self.UNAPPLIED_QUERY_DEADLINE))

  def _iter_ns_range(self):
    while True:
      unapplied_jobs = self._get_unapplied_jobs_accross_namespaces(
          self._ns_range.namespace_start,
          self._ns_range.namespace_end,
          self._ns_range.app)

      if not unapplied_jobs:
        break

      self._apply_jobs(unapplied_jobs)

    for o in super(ConsistentKeyReader, self)._iter_ns_range():
      yield o

  def _iter_key_range(self, k_range):
    assert hasattr(self, "start_time_us"), "start_time_us property was not set"
    if self._ns_range is None:


      self._apply_key_range(k_range)

    for o in super(ConsistentKeyReader, self)._iter_key_range(k_range):
      yield o

  def _apply_key_range(self, k_range):
    """Apply all jobs in the given KeyRange."""





    apply_range = copy.deepcopy(k_range)
    while True:



      unapplied_query = self._make_unapplied_query(apply_range)
      unapplied_jobs = unapplied_query.Get(
          limit=self._batch_size,
          config=datastore_rpc.Configuration(
              deadline=self.UNAPPLIED_QUERY_DEADLINE))
      if not unapplied_jobs:
        break
      self._apply_jobs(unapplied_jobs)


      apply_range.advance(unapplied_jobs[-1])

  def _make_unapplied_query(self, k_range):
    """Returns a datastore.Query that finds the unapplied keys in k_range."""
    unapplied_query = k_range.make_ascending_datastore_query(
        kind=None, keys_only=True)
    unapplied_query[
        ConsistentKeyReader.UNAPPLIED_LOG_FILTER] = self.start_time_us
    return unapplied_query

  def _apply_jobs(self, unapplied_jobs):
    """Apply all jobs implied by the given keys."""

    keys_to_apply = []
    for key in unapplied_jobs:


      path = key.to_path() + [ConsistentKeyReader.DUMMY_KIND,
                              ConsistentKeyReader.DUMMY_ID]
      keys_to_apply.append(
          db.Key.from_path(_app=key.app(), namespace=key.namespace(), *path))
    db.get(keys_to_apply, config=datastore_rpc.Configuration(
        deadline=self.UNAPPLIED_QUERY_DEADLINE,
        read_policy=datastore_rpc.Configuration.APPLY_ALL_JOBS_CONSISTENCY))

  @classmethod
  def _split_input_from_namespace(cls,
                                  app,
                                  namespace,
                                  entity_kind_name,
                                  shard_count):
    key_ranges = super(ConsistentKeyReader, cls)._split_input_from_namespace(
        app, namespace, entity_kind_name, shard_count)
    assert len(key_ranges) == shard_count




    try:
      last_key_range_index = key_ranges.index(None) - 1
    except ValueError:
      last_key_range_index = shard_count - 1

    if last_key_range_index != -1:
      key_ranges[0].key_start = None
      key_ranges[0].include_start = False
      key_ranges[last_key_range_index].key_end = None
      key_ranges[last_key_range_index].include_end = False
    return key_ranges

  @classmethod
  def _split_input_from_params(cls, app, namespaces, entity_kind_name,
                               params, shard_count):
    readers = super(ConsistentKeyReader, cls)._split_input_from_params(
        app,
        namespaces,
        entity_kind_name,
        params,
        shard_count)



    if not readers:
      readers = [cls(entity_kind_name,
                     key_ranges=None,
                     ns_range=namespace_range.NamespaceRange(),
                     batch_size=shard_count)]

    return readers

  @classmethod
  def split_input(cls, mapper_spec):
    """Splits input into key ranges."""
    readers = super(ConsistentKeyReader, cls).split_input(mapper_spec)

    start_time_us = mapper_spec.params.get(
        cls.START_TIME_US_PARAM, long(time.time() * 1e6))
    for reader in readers:
      reader.start_time_us = start_time_us
    return readers

  def to_json(self):
    """Serializes all the data in this reader into json form.

    Returns:
      all the data in json-compatible map.
    """
    json_dict = super(DatastoreKeyInputReader, self).to_json()
    json_dict[self.START_TIME_US_PARAM] = self.start_time_us
    return json_dict

  @classmethod
  def from_json(cls, json):
    """Create new ConsistentKeyReader from the json, encoded by to_json.

    Args:
      json: json map representation of ConsistentKeyReader.

    Returns:
      an instance of ConsistentKeyReader with all data deserialized from json.
    """
    reader = super(ConsistentKeyReader, cls).from_json(json)
    reader.start_time_us = json[cls.START_TIME_US_PARAM]
    return reader








class NamespaceInputReader(InputReader):
  """An input reader to iterate over namespaces.

  This reader yields namespace names as string.
  It will always produce only one shard.
  """

  NAMESPACE_RANGE_PARAM = "namespace_range"
  BATCH_SIZE_PARAM = "batch_size"
  _BATCH_SIZE = 10

  def __init__(self, ns_range, batch_size = _BATCH_SIZE):
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
    params = mapper_spec.params

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
    batch_size = int(mapper_spec.params.get(cls.BATCH_SIZE_PARAM,
                                            cls._BATCH_SIZE))
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


class RecordsReader(InputReader):
  """Reader to read a list of Files API file in records format.

  The number of input shards can be specified by the SHARDS_PARAM
  mapper parameter. Input files cannot be split, so there will be at most
  one shard per file. Also the number of shards will not be reduced based on
  the number of input files, so shards in always equals shards out.
  """

  FILE_PARAM = "file"
  FILES_PARAM = "files"

  def __init__(self, filenames, position):
    """Constructor.

    Args:
      filenames: list of filenames.
      position: file position to start reading from as int.
    """
    self._filenames = filenames
    if self._filenames:
      self._reader = records.RecordsReader(
          files.BufferedFile(self._filenames[0]))
      self._reader.seek(position)
    else:
      self._reader = None

  def __iter__(self):
    """Iterate over records in file.

    Yields records as strings.
    """
    ctx = context.get()

    while self._reader:
      try:
        start_time = time.time()
        record = self._reader.read()
        if ctx:
          operation.counters.Increment(
              COUNTER_IO_READ_MSEC, int((time.time() - start_time) * 1000))(ctx)
          operation.counters.Increment(COUNTER_IO_READ_BYTES, len(record))(ctx)
        yield record
      except EOFError:
        self._filenames.pop(0)
        if not self._filenames:
          self._reader = None
        else:
          self._reader = records.RecordsReader(
              files.BufferedFile(self._filenames[0]))

  @classmethod
  def from_json(cls, json):
    """Creates an instance of the InputReader for the given input shard state.

    Args:
      json: The InputReader state as a dict-like object.

    Returns:
      An instance of the InputReader configured using the values of json.
    """
    return cls(json["filenames"], json["position"])

  def to_json(self):
    """Returns an input shard state for the remaining inputs.

    Returns:
      A json-izable version of the remaining InputReader.
    """
    result = {
        "filenames": self._filenames,
        "position": 0,
        }
    if self._reader:
      result["position"] = self._reader.tell()
    return result

  @classmethod
  def split_input(cls, mapper_spec):
    """Returns a list of input readers for the input spec.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Returns:
      A list of InputReaders.
    """
    params = mapper_spec.params
    shard_count = mapper_spec.shard_count

    if cls.FILES_PARAM in params:
      filenames = params[cls.FILES_PARAM]
      if isinstance(filenames, basestring):
        filenames = filenames.split(",")
    else:
      filenames = [params[cls.FILE_PARAM]]

    batch_list = [[] for _ in xrange(shard_count)]
    for index, filename in enumerate(filenames):

      batch_list[index % shard_count].append(filenames[index])


    batch_list.sort(reverse=True, key=lambda x: len(x))
    return [RecordsReader(batch, 0) for batch in batch_list]

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper spec and all mapper parameters.

    Args:
      mapper_spec: The MapperSpec for this InputReader.

    Raises:
      BadReaderParamsError: required parameters are missing or invalid.
    """
    if mapper_spec.input_reader_class() != cls:
      raise errors.BadReaderParamsError("Input reader class mismatch")
    params = mapper_spec.params
    if (cls.FILES_PARAM not in params and
        cls.FILE_PARAM not in params):
      raise BadReaderParamsError(
          "Must specify '%s' or '%s' parameter for mapper input" %
          (cls.FILES_PARAM, cls.FILE_PARAM))

  def __str__(self):
    position = 0
    if self._reader:
      position = self._reader.tell()
    return "%s:%s" % (self._filenames, position)
