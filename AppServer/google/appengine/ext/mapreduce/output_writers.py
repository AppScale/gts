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


__all__ = ["OutputWriter", "BlobstoreOutputWriter"]


from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import model
from google.appengine.api import files


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


class _FilePool(object):
  """Pool of file append operations."""

  MAX_SIZE = 128*1024

  def __init__(self, max_size_chars=MAX_SIZE):
    self._max_size = max_size_chars
    self._append_buffer = {}
    self._size = 0

  def __append(self, filename, data):
    self._append_buffer[filename] = (
        self._append_buffer.get(filename, "") + data)
    self._size += len(data)

  def append(self, filename, data):
    """Append data to a file."""
    if self._size + len(data) > self._max_size:
      self.flush()

    if len(data) > self._max_size:
      raise errors.Error(
          "Can't write more than %s bytes in one request: "
          "risk of writes interleaving." % self._max_size)
    else:
      self.__append(filename, data)

    if self._size > self._max_size:
      self.flush()

  def flush(self):
    """Flush pool contents."""
    for filename, data in self._append_buffer.iteritems():
      with files.open(filename, 'a') as f:
        if len(data) > self._max_size:
          raise "Bad data: " + str(len(data))
        f.write(data)
    self._append_buffer = {}
    self._size = 0


class BlobstoreOutputWriter(OutputWriter):
  """An implementation of OutputWriter which outputs data into blobstore."""

  class _State(object):
    """Writer state. Stored in MapreduceState.

    State list all files which were created for the job.
    """
    def __init__(self, filename):
      self.filename = filename

    def to_json(self):
      return {'filename': self.filename}

    @classmethod
    def from_json(cls, json):
      return cls(json['filename'])

  def __init__(self, filename):
    self._filename = filename

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper specification.

    Args:
      mapper_spec: an instance of model.MapperSpec to validate.
    """
    pass

  @classmethod
  def init_job(cls, mapreduce_state):
    """Initialize job-level writer state.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job.
    """
    filename = files.blobstore.create()
    mapreduce_state.writer_state = BlobstoreOutputWriter._State(filename).to_json()

  @classmethod
  def finalize_job(cls, mapreduce_state):
    """Finalize job-level writer state.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job.
    """
    state = BlobstoreOutputWriter._State.from_json(
        mapreduce_state.writer_state)
    files.finalize(state.filename)
    state.filename = files.blobstore.get_file_name(
        files.blobstore.get_blob_key(state.filename))
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
    state = BlobstoreOutputWriter._State.from_json(
        mapreduce_state.writer_state)
    return cls(state.filename)

  def write(self, data, ctx):
    """Write data.

    Args:
      data: actual data yielded from handler. Type is writer-specific.
      ctx: an instance of context.Context.
    """
    if ctx.get_pool("file_pool") is None:
      ctx.register_pool("file_pool", _FilePool())
    ctx.get_pool("file_pool").append(self._filename, str(data))

  def finalize(self, ctx, shard_number):
    """Finalize writer shard-level state.

    Args:
      ctx: an instance of context.Context.
      shard_number: shard number as integer.
    """
    pass
