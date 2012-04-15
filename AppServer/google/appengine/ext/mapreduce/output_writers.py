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
















"""Output writers for MapReduce."""

from __future__ import with_statement


__all__ = [
    "BlobstoreOutputWriter",
    "BlobstoreOutputWriterBase",
    "BlobstoreRecordsOutputWriter",
    "COUNTER_IO_WRITE_BYTES",
    "COUNTER_IO_WRITE_MSEC",
    "OutputWriter",
    "RecordsPool",
    ]

import gc
import string
import time

from google.appengine.api import files
from google.appengine.api.files import records
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import operation



COUNTER_IO_WRITE_BYTES = "io-write-bytes"


COUNTER_IO_WRITE_MSEC = "io-write-msec"


class OutputWriter(model.JsonMixin):
  """Abstract base class for output writers.

  Output writers process all mapper handler output, which is not
  the operation.

  OutputWriter's lifecycle is the following:
    0) validate called to validate mapper specification.
    1) init_job is called to initialize any job-level state.
    2) create() is called, which should create a new instance of output
       writer for a given shard
    3) from_json()/to_json() are used to persist writer's state across
       multiple slices.
    4) write() method is called to write data.
    5) finalize() is called when shard processing is done.
    5) finalize_job() is called when job is completed.
  """

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper specification.

    Args:
      mapper_spec: an instance of model.MapperSpec to validate.
    """
    raise NotImplementedError("validate() not implemented in %s" % cls)

  @classmethod
  def init_job(cls, mapreduce_state):
    """Initialize job-level writer state.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job. State can be modified during initialization.
    """
    raise NotImplementedError("init_job() not implemented in %s" % cls)

  @classmethod
  def finalize_job(cls, mapreduce_state):
    """Finalize job-level writer state.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job. State can be modified during finalization.
    """
    raise NotImplementedError("finalize_job() not implemented in %s" % cls)

  @classmethod
  def from_json(cls, state):
    """Creates an instance of the OutputWriter for the given json state.

    Args:
      state: The OutputWriter state as a dict-like object.

    Returns:
      An instance of the OutputWriter configured using the values of json.
    """
    raise NotImplementedError("from_json() not implemented in %s" % cls)

  def to_json(self):
    """Returns writer state to serialize in json.

    Returns:
      A json-izable version of the OutputWriter state.
    """
    raise NotImplementedError("to_json() not implemented in %s" %
                              self.__class__)

  @classmethod
  def create(cls, mapreduce_state, shard_number):
    """Create new writer for a shard.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job. State can be modified.
      shard_number: shard number as integer.
    """
    raise NotImplementedError("create() not implemented in %s" % cls)

  def write(self, data, ctx):
    """Write data.

    Args:
      data: actual data yielded from handler. Type is writer-specific.
      ctx: an instance of context.Context.
    """
    raise NotImplementedError("write() not implemented in %s" %
                              self.__class__)

  def finalize(self, ctx, shard_number):
    """Finalize writer shard-level state.

    Args:
      ctx: an instance of context.Context.
      shard_number: shard number as integer.
    """
    raise NotImplementedError("finalize() not implemented in %s" %
                              self.__class__)

  @classmethod
  def get_filenames(cls, mapreduce_state):
    """Obtain output filenames from mapreduce state.

    Args:
      mapreduce_state: an instance of model.MapreduceState

    Returns:
      list of filenames this writer writes to or None if writer
      doesn't write to a file.
    """
    raise NotImplementedError("get_filenames() not implemented in %s" %
                              self.__class__)


_FILES_API_FLUSH_SIZE = 128*1024


_FILES_API_MAX_SIZE = 1000*1024


class _FilePool(object):
  """Pool of file append operations."""

  def __init__(self, flush_size_chars=_FILES_API_FLUSH_SIZE, ctx=None):
    """Constructor.

    Args:
      flush_size_chars: buffer flush size in bytes as int. Internal buffer
        will be flushed once this size is reached.
      ctx: mapreduce context as context.Context. Can be null.
    """
    self._flush_size = flush_size_chars
    self._append_buffer = {}
    self._size = 0
    self._ctx = ctx

  def __append(self, filename, data):
    """Append data to the filename's buffer without checks and flushes."""
    self._append_buffer[filename] = (
        self._append_buffer.get(filename, "") + data)
    self._size += len(data)

  def append(self, filename, data):
    """Append data to a file.

    Args:
      filename: the name of the file as string.
      data: data as string.
    """
    if self._size + len(data) > self._flush_size:
      self.flush()

    if len(data) > _FILES_API_MAX_SIZE:
      raise errors.Error(
          "Can't write more than %s bytes in one request: "
          "risk of writes interleaving." % self._flush_size)
    else:
      self.__append(filename, data)

    if self._size > self._flush_size:
      self.flush()

  def flush(self):
    """Flush pool contents."""
    start_time = time.time()
    for filename, data in self._append_buffer.iteritems():
      with files.open(filename, "a") as f:
        if len(data) > self._flush_size:
          raise "Bad data: " + str(len(data))
        if self._ctx:
          operation.counters.Increment(
              COUNTER_IO_WRITE_BYTES, len(data))(self._ctx)
        f.write(data)
    if self._ctx:
      operation.counters.Increment(
          COUNTER_IO_WRITE_MSEC,
          int((time.time() - start_time) * 1000))(self._ctx)
    self._append_buffer = {}
    self._size = 0


class _StringWriter(object):
  """Simple writer for records api that writes to a string buffer."""

  def __init__(self):
    self._buffer = ""

  def to_string(self):
    """Convert writer buffer to string."""
    return self._buffer

  def write(self, data):
    """Write data.

    Args:
      data: data to append to the buffer as string.
    """
    self._buffer += data


class RecordsPool(object):
  """Pool of append operations for records files."""


  _RECORD_OVERHEAD_BYTES = 10

  def __init__(self, filename,
               flush_size_chars=_FILES_API_FLUSH_SIZE,
               ctx=None,
               exclusive=False):
    """Constructor.

    Args:
      filename: file name to write data to as string.
      flush_size_chars: buffer flush threshold as int.
      ctx: mapreduce context as context.Context.
      exclusive: a boolean flag indicating if the pool has an exclusive
        access to the file. If it is True, then it's possible to write
        bigger chunks of data.
    """
    self._flush_size = flush_size_chars
    self._buffer = []
    self._size = 0
    self._filename = filename
    self._ctx = ctx
    self._exclusive = exclusive

  def append(self, data):
    """Append data to a file."""
    data_length = len(data)
    if self._size + data_length > self._flush_size:
      self.flush()

    if not self._exclusive and data_length > _FILES_API_MAX_SIZE:
      raise errors.Error(
          "Too big input %s (%s)."  % (data_length, _FILES_API_MAX_SIZE))
    else:
      self._buffer.append(data)
      self._size += data_length

    if self._size > self._flush_size:
      self.flush()

  def flush(self):
    """Flush pool contents."""

    buf = _StringWriter()
    with records.RecordsWriter(buf) as w:
      for record in self._buffer:
        w.write(record)

    str_buf = buf.to_string()
    if not self._exclusive and len(str_buf) > _FILES_API_MAX_SIZE:

      raise errors.Error(
          "Buffer too big. Can't write more than %s bytes in one request: "
          "risk of writes interleaving. Got: %s" %
          (_FILES_API_MAX_SIZE, len(str_buf)))


    start_time = time.time()
    with files.open(self._filename, "a", exclusive_lock=self._exclusive) as f:
      f.write(str_buf)
      if self._ctx:
        operation.counters.Increment(
            COUNTER_IO_WRITE_BYTES, len(str_buf))(self._ctx)
    if self._ctx:
      operation.counters.Increment(
          COUNTER_IO_WRITE_MSEC,
          int((time.time() - start_time) * 1000))(self._ctx)


    self._buffer = []
    self._size = 0
    gc.collect()

  def __enter__(self):
    return self

  def __exit__(self, atype, value, traceback):
    self.flush()


def _get_output_sharding(
    mapreduce_state=None,
    mapper_spec=None):
  """Get output sharding parameter value from mapreduce state or mapper spec.

  At least one of the parameters should not be None.

  Args:
    mapreduce_state: mapreduce state as model.MapreduceState.
    mapper_spec: mapper specification as model.MapperSpec
  """
  if mapper_spec:
    return string.lower(mapper_spec.params.get(
        BlobstoreOutputWriterBase.OUTPUT_SHARDING_PARAM,
        BlobstoreOutputWriterBase.OUTPUT_SHARDING_NONE))
  if mapreduce_state:
    mapper_spec = mapreduce_state.mapreduce_spec.mapper
    return _get_output_sharding(mapper_spec=mapper_spec)
  raise errors.Error("Neither mapreduce_state nor mapper_spec specified.")


class BlobstoreOutputWriterBase(OutputWriter):
  """Base class for all blobstore output writers."""


  OUTPUT_SHARDING_PARAM = "output_sharding"


  OUTPUT_SHARDING_NONE = "none"


  OUTPUT_SHARDING_INPUT_SHARDS = "input"

  class _State(object):
    """Writer state. Stored in MapreduceState.

    State list all files which were created for the job.
    """
    def __init__(self, filenames):
      self.filenames = filenames

    def to_json(self):
      return {"filenames": self.filenames}

    @classmethod
    def from_json(cls, json):
      return cls(json["filenames"])

  def __init__(self, filename):
    self._filename = filename

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper specification.

    Args:
      mapper_spec: an instance of model.MapperSpec to validate.
    """
    if mapper_spec.output_writer_class() != cls:
      raise errors.BadWriterParamsError("Output writer class mismatch")

    output_sharding = _get_output_sharding(mapper_spec=mapper_spec)
    if (output_sharding != cls.OUTPUT_SHARDING_NONE and
        output_sharding != cls.OUTPUT_SHARDING_INPUT_SHARDS):
      raise errors.BadWriterParamsError(
          "Invalid output_sharding value: %s" % output_sharding)

  @classmethod
  def init_job(cls, mapreduce_state):
    """Initialize job-level writer state.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job.
    """
    output_sharding = _get_output_sharding(mapreduce_state=mapreduce_state)
    mapper_spec = mapreduce_state.mapreduce_spec.mapper
    mime_type = mapper_spec.params.get("mime_type", "application/octet-stream")

    number_of_files = 1
    if output_sharding == cls.OUTPUT_SHARDING_INPUT_SHARDS:
      mapper_spec = mapreduce_state.mapreduce_spec.mapper
      number_of_files = mapper_spec.shard_count

    filenames = []
    for i in range(number_of_files):
      blob_file_name = (mapreduce_state.mapreduce_spec.name +
                        "-" + mapreduce_state.mapreduce_spec.mapreduce_id +
                        "-output")
      if number_of_files > 1:
        blob_file_name += "-" + str(i)
      filenames.append(files.blobstore.create(
          mime_type=mime_type,
          _blobinfo_uploaded_filename=blob_file_name))

    mapreduce_state.writer_state = cls._State(filenames).to_json()

  @classmethod
  def finalize_job(cls, mapreduce_state):
    """Finalize job-level writer state.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job.
    """
    state = cls._State.from_json(
        mapreduce_state.writer_state)

    output_sharding = _get_output_sharding(mapreduce_state=mapreduce_state)

    finalized_filenames = []
    for filename in state.filenames:
      if output_sharding != cls.OUTPUT_SHARDING_INPUT_SHARDS:
        files.finalize(filename)
      finalized_filenames.append(
          files.blobstore.get_file_name(
              files.blobstore.get_blob_key(filename)))

    state.filenames = finalized_filenames
    mapreduce_state.writer_state = state.to_json()

  @classmethod
  def from_json(cls, state):
    """Creates an instance of the OutputWriter for the given json state.

    Args:
      state: The OutputWriter state as a dict-like object.

    Returns:
      An instance of the OutputWriter configured using the values of json.
    """
    return cls(state["filename"])

  def to_json(self):
    """Returns writer state to serialize in json.

    Returns:
      A json-izable version of the OutputWriter state.
    """
    return {"filename": self._filename}

  @classmethod
  def create(cls, mapreduce_state, shard_number):
    """Create new writer for a shard.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job.
      shard_number: shard number as integer.
    """
    file_index = 0
    output_sharding = _get_output_sharding(mapreduce_state=mapreduce_state)
    if output_sharding == cls.OUTPUT_SHARDING_INPUT_SHARDS:
      file_index = shard_number

    state = cls._State.from_json(
        mapreduce_state.writer_state)
    return cls(state.filenames[file_index])

  def finalize(self, ctx, shard_number):
    """Finalize writer shard-level state.

    Args:
      ctx: an instance of context.Context.
      shard_number: shard number as integer.
    """
    mapreduce_spec = ctx.mapreduce_spec
    output_sharding = _get_output_sharding(mapper_spec=mapreduce_spec.mapper)
    if output_sharding == self.OUTPUT_SHARDING_INPUT_SHARDS:



      files.finalize(self._filename)

  @classmethod
  def get_filenames(cls, mapreduce_state):
    """Obtain output filenames from mapreduce state.

    Args:
      mapreduce_state: an instance of model.MapreduceState

    Returns:
      list of filenames this writer writes to.
    """
    state = cls._State.from_json(
        mapreduce_state.writer_state)
    return state.filenames


class BlobstoreOutputWriter(BlobstoreOutputWriterBase):
  """An implementation of OutputWriter which outputs data into blobstore."""

  def write(self, data, ctx):
    """Write data.

    Args:
      data: actual data yielded from handler. Type is writer-specific.
      ctx: an instance of context.Context.
    """
    if ctx.get_pool("file_pool") is None:
      ctx.register_pool("file_pool", _FilePool(ctx=ctx))
    ctx.get_pool("file_pool").append(self._filename, str(data))


class BlobstoreRecordsOutputWriter(BlobstoreOutputWriterBase):
  """An OutputWriter which outputs data into records format."""

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper specification.

    Args:
      mapper_spec: an instance of model.MapperSpec to validate.
    """
    if cls.OUTPUT_SHARDING_PARAM in mapper_spec.params:
      raise errors.BadWriterParamsError(
          "output_sharding should not be specified for %s" % cls.__name__)
    mapper_spec.params[cls.OUTPUT_SHARDING_PARAM] = (
        cls.OUTPUT_SHARDING_INPUT_SHARDS)
    super(BlobstoreRecordsOutputWriter, cls).validate(mapper_spec)

  def write(self, data, ctx):
    """Write data.

    Args:
      data: actual data yielded from handler. Type is writer-specific.
      ctx: an instance of context.Context.
    """
    if ctx.get_pool("records_pool") is None:
      ctx.register_pool("records_pool",


                        RecordsPool(self._filename, ctx=ctx, exclusive=True))
    ctx.get_pool("records_pool").append(str(data))
