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















"""Mapreduce shuffler implementation."""

from __future__ import with_statement




__all__ = [
    "ShufflePipeline",
    ]



import gc
import heapq
import logging
import time
import zlib

from appengine_pipeline.src import pipeline
from appengine_pipeline.src.pipeline import common as pipeline_common
from google.appengine.api import files
from google.appengine.api.files import file_service_pb
from google.appengine.ext import db
from google.appengine.ext.mapreduce import context
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import mapper_pipeline
from google.appengine.ext.mapreduce import operation
from google.appengine.ext.mapreduce import output_writers
from google.appengine.ext.mapreduce import pipeline_base
from google.appengine.ext.mapreduce import records





class _OutputFile(db.Model):
  """Entity to store output filenames of pipelines.

  These entities are always children of key returned by get_root_key().
  """

  @classmethod
  def kind(cls):
    """Returns entity kind."""
    return "_GAE_MR_OutputFile"

  @classmethod
  def get_root_key(cls, job_id):
    """Get root key to store output files.

    Args:
      job_id: pipeline's job id.

    Returns:
      root key for a given job id to store output file entities.
    """
    return db.Key.from_path(cls.kind(), job_id)


def _compare_keys(key_record1, key_record2):
  """Compare two (key, records) protos by key."""
  return cmp(key_record1[0], key_record2[0])


class _BatchRecordsReader(input_readers.RecordsReader):
  """Records reader that reads in big batches."""

  BATCH_SIZE = 1024*1024 * 3

  def __iter__(self):

    records = []
    size = 0
    for record in input_readers.RecordsReader.__iter__(self):
      records.append(record)
      size += len(record)
      if size > self.BATCH_SIZE:
        yield records
        size = 0
        records = []
        gc.collect()
    if records:
      yield records
      records = []
      gc.collect()



def _sort_records_map(records):
  """Map function sorting records.

  Converts records to KeyValue protos, sorts them by key and writes them
  into new blobstore file. Creates _OutputFile entity to record resulting
  file name.

  Args:
    records: list of records which are serialized KeyValue protos.
  """
  ctx = context.get()
  l = len(records)
  key_records = [None] * l

  logging.debug("Parsing")
  for i in range(l):
    proto = file_service_pb.KeyValue()
    proto.ParseFromString(records[i])
    key_records[i] = (proto.key(), records[i])

  logging.debug("Sorting")
  key_records.sort(cmp=_compare_keys)

  logging.debug("Writing")
  blob_file_name = (ctx.mapreduce_spec.name + "-" +
                    ctx.mapreduce_id + "-output")
  output_path = files.blobstore.create(
      _blobinfo_uploaded_filename=blob_file_name)
  with output_writers.RecordsPool(output_path, ctx=ctx) as pool:
    for key_record in key_records:
      pool.append(key_record[1])

  logging.debug("Finalizing")
  files.finalize(output_path)
  output_path = files.blobstore.get_file_name(
      files.blobstore.get_blob_key(output_path))

  entity = _OutputFile(key_name=output_path,
                       parent=_OutputFile.get_root_key(ctx.mapreduce_id))
  entity.put()


class _SortChunksPipeline(pipeline_base.PipelineBase):
  """A pipeline to sort multiple key-value files.

  Args:
    job_name: root job name.
    filenames: list of filenames to sort.

  Returns:
    The list of lists of sorted filenames. Each list corresponds to one
    input file. Each filenames contains a chunk of sorted data.
  """

  def run(self, job_name, filenames):
    sort_mappers = []
    for i in range(len(filenames)):
      filename = filenames[i]
      sort_mapper = yield mapper_pipeline.MapperPipeline(
          "%s-shuffle-sort-%s" % (job_name, str(i)),
          __name__ + "._sort_records_map",
          __name__ + "._BatchRecordsReader",
          None,
          {
              "files": [filename],
              "processing_rate": 1000000,
          },
          shards=1)
      sort_mappers.append(sort_mapper)
    with pipeline.After(*sort_mappers):
      job_ids = yield pipeline_common.Append(*[mapper.job_id for mapper in
                                               sort_mappers])
      result = yield _CollectOutputFiles(job_ids)
      with pipeline.After(result):
        yield _CleanupOutputFiles(job_ids)
      yield pipeline_common.Return(result)


class _CollectOutputFiles(pipeline_base.PipelineBase):
  """Collect output file names from _OutputFile entities for given jobs.

  Args:
    job_ids: list of job ids to load filenames.

  Returns:
    list of lists of filenames produced by specified job ids.
  """

  def run(self, job_ids):
    result = []
    for job_id in job_ids:
      entities = _OutputFile.all().ancestor(_OutputFile.get_root_key(job_id))
      result.append([entity.key().name() for entity in entities])
    return result


class _CleanupOutputFiles(pipeline_base.PipelineBase):
  """Cleanup _OutputFile entities for given job ids.

  Args:
    job_ids: list of job ids.
  """

  def run(self, job_ids):
    for job_id in job_ids:
      db.delete(_OutputFile.all().ancestor(_OutputFile.get_root_key(job_id)))


class _MergingReader(input_readers.InputReader):
  """Reader which merge-reads multiple sorted KeyValue files.

  Reads list of lists of filenames. Each filename list constitutes one shard
  and is merged together.

  Yields (key, values) tuple. If none of the max_values_count and
  max_values_size parameters are not specified, then there will be a single key.
  Otherwise multiple (key, values) pairs for the same key will be created,
  according to restrictions.
  """

  expand_parameters = True

  FILES_PARAM = "files"
  MAX_VALUES_COUNT_PARAM = "max_values_count"
  MAX_VALUES_SIZE_PARAM = "max_values_size"

  def __init__(self,
               offsets,
               max_values_count,
               max_values_size):
    """Constructor.

    Args:
      offsets: offsets for each input file to start from as list of ints.
      max_values_count: maximum number of values to yield for a single value at
        a time. Ignored if -1.
      max_values_size: maximum total size of yielded values.  Ignored if -1
    """
    self._offsets = offsets
    self._max_values_count = max_values_count
    self._max_values_size = max_values_size

  def __iter__(self):
    """Iterate over records in input files.

    self._offsets is always correctly updated so that stopping iterations
    doesn't skip records and doesn't read the same record twice.

    Raises:
      Exception: when Files list and offsets do not match.

    Yields:
      The result.
    """
    ctx = context.get()
    mapper_spec = ctx.mapreduce_spec.mapper
    shard_number = ctx._shard_state.shard_number
    filenames = mapper_spec.params[self.FILES_PARAM][shard_number]

    if len(filenames) != len(self._offsets):
      raise Exception("Files list and offsets do not match.")


    readers = []


    for (i, filename) in enumerate(filenames):
      offset = self._offsets[i]
      reader = records.RecordsReader(files.BufferedFile(filename))
      reader.seek(offset)
      readers.append((None, None, i, reader))





    current_result = None
    current_count = 0
    current_size = 0
    while readers:
      (key, value, index, reader) = readers[0]

      if key is not None:
        current_count += 1
        current_size += len(value)

        should_yield = False
        if current_result:
          if key != current_result[0]:

            should_yield = True
          elif (self._max_values_count != -1 and
                current_count >= self._max_values_count):

            current_result[2] = True
            should_yield = True
          elif (self._max_values_size != -1 and
                current_size >= self._max_values_size):

            current_result[2] = True
            should_yield = True

        if should_yield:

          yield current_result
        if not current_result or should_yield:
          current_result = [key, [], False]
          current_count = 0
          current_size = 0
        current_result[1].append(value)


      try:
        self._offsets[index] = reader.tell()
        start_time = time.time()
        binary_record = reader.read()

        if context.get():
          operation.counters.Increment(
              input_readers.COUNTER_IO_READ_BYTES,
              len(binary_record))(context.get())
          operation.counters.Increment(
              input_readers.COUNTER_IO_READ_MSEC,
              int((time.time() - start_time) * 1000))(context.get())
        proto = file_service_pb.KeyValue()
        proto.ParseFromString(binary_record)

        heapq.heapreplace(readers,
                          (proto.key(), proto.value(), index, reader))
      except EOFError:
        heapq.heappop(readers)


    if current_result:
      yield current_result

  @classmethod
  def from_json(cls, json):
    """Restore reader from json state."""
    return cls(json["offsets"],
               json["max_values_count"],
               json["max_values_size"])

  def to_json(self):
    """Serialize reader state to json."""
    return {"offsets": self._offsets,
            "max_values_count": self._max_values_count,
            "max_values_size": self._max_values_size}

  @classmethod
  def split_input(cls, mapper_spec):
    """Split input into multiple shards."""
    filelists = mapper_spec.params[cls.FILES_PARAM]
    max_values_count = mapper_spec.params.get(cls.MAX_VALUES_COUNT_PARAM, -1)
    max_values_size = mapper_spec.params.get(cls.MAX_VALUES_SIZE_PARAM, -1)
    return [cls([0] * len(files), max_values_count, max_values_size)
            for files in filelists]

  @classmethod
  def validate(cls, mapper_spec):
    """Validate reader parameters in mapper_spec."""
    if mapper_spec.input_reader_class() != cls:
      raise errors.BadReaderParamsError("Input reader class mismatch")
    params = mapper_spec.params
    if cls.FILES_PARAM not in params:
      raise errors.BadReaderParamsError("Missing files parameter.")


class _HashingBlobstoreOutputWriter(output_writers.BlobstoreOutputWriterBase):
  """An OutputWriter which outputs data into blobstore in key-value format.

  The output is tailored towards shuffler needs. It shards key/values using
  key hash modulo number of output files.
  """


  def __init__(self, filenames):
    """Constructor.

    Args:
      filenames: list of filenames that this writer outputs to.
    """
    self._filenames = filenames

  @classmethod
  def validate(cls, mapper_spec):
    """Validates mapper specification.

    Args:
      mapper_spec: an instance of model.MapperSpec to validate.
    Raises:
      BadWriterParamsError: when Output writer class mismatch.
    """
    if mapper_spec.output_writer_class() != cls:
      raise errors.BadWriterParamsError("Output writer class mismatch")

  @classmethod
  def init_job(cls, mapreduce_state):
    """Initialize job-level writer state.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
      job. State can be modified during initialization.
    """
    shards = mapreduce_state.mapreduce_spec.mapper.shard_count

    filenames = []
    for i in range(shards):
      blob_file_name = (mapreduce_state.mapreduce_spec.name +
                        "-" + mapreduce_state.mapreduce_spec.mapreduce_id +
                        "-output-" + str(i))
      filenames.append(
          files.blobstore.create(
              _blobinfo_uploaded_filename=blob_file_name))
    mapreduce_state.writer_state = {"filenames": filenames}

  @classmethod
  def finalize_job(cls, mapreduce_state):
    """Finalize job-level writer state.

    Args:
      mapreduce_state: an instance of model.MapreduceState describing current
        job. State can be modified during finalization.
    """
    finalized_filenames = []
    for filename in mapreduce_state.writer_state["filenames"]:
      files.finalize(filename)
      finalized_filenames.append(
          files.blobstore.get_file_name(
              files.blobstore.get_blob_key(filename)))
    mapreduce_state.writer_state = {"filenames": finalized_filenames}

  @classmethod
  def from_json(cls, json):
    """Creates an instance of the OutputWriter for the given json state.

    Args:
      json: The OutputWriter state as a dict-like object.

    Returns:
      An instance of the OutputWriter configured using the values of json.
    """
    return cls(json["filenames"])

  def to_json(self):
    """Returns writer state to serialize in json.

    Returns:
      A json-izable version of the OutputWriter state.
    """
    return {"filenames": self._filenames}

  @classmethod
  def create(cls, mr_spec, shard_number, shard_attempt, _writer_state=None):
    """Inherit docs."""
    return cls(_writer_state["filenames"])

  @classmethod
  def get_filenames(cls, mapreduce_state):
    """See parent class."""
    if mapreduce_state.writer_state:
      return mapreduce_state.writer_state["filenames"]
    return []

  def finalize(self, ctx, shard_state):
    pass

  def write(self, data):
    """Write data.

    Args:
      data: actual data yielded from handler. Type is writer-specific.
    """
    ctx = context.get()
    if len(data) != 2:
      logging.error("Got bad tuple of length %d (2-tuple expected): %s",
                    len(data), data)

    try:
      key = str(data[0])
      value = str(data[1])
    except TypeError:
      logging.error("Expecting a tuple, but got %s: %s",
                    data.__class__.__name__, data)

    # AppScale: Use a deterministic hash function.
    file_index = zlib.adler32(key) % len(self._filenames)

    pool_name = "kv_pool%d" % file_index
    filename = self._filenames[file_index]

    if ctx.get_pool(pool_name) is None:
      ctx.register_pool(pool_name,
                        output_writers.RecordsPool(filename=filename, ctx=ctx))
    proto = file_service_pb.KeyValue()
    proto.set_key(key)
    proto.set_value(value)
    ctx.get_pool(pool_name).append(proto.Encode())


class _ShardOutputs(pipeline_base.PipelineBase):
  """Shards the ouputs.

  Takes a flat list of filenames, returns a list of lists, each with
  one member each.
  """

  def run(self, filenames):
    result = []
    for name in filenames:
      result.append([name])
    return result


def _merge_map(key, values, partial):
  """A map function used in merge phase.

  Stores (key, values) into KeyValues proto and yields its serialization.

  Args:
    key: values key.
    values: values themselves.
    partial: True if more values for this key will follow. False otherwise.

  Yields:
    The proto.
  """
  proto = file_service_pb.KeyValues()
  proto.set_key(key)
  proto.value_list().extend(values)
  proto.set_partial(partial)
  yield proto.Encode()


class _MergePipeline(pipeline_base.PipelineBase):
  """Pipeline to merge sorted chunks.

  This pipeline merges together individually sorted chunks of each shard.

  Args:
    filenames: list of lists of filenames. Each list will correspond to a single
      shard. Each file in the list should have keys sorted and should contain
      records with KeyValue serialized entity.

  Yields:
    The list of filenames, where each filename is fully merged and will contain
    records with KeyValues serialized entity.
  """


  _MAX_VALUES_COUNT = 100000

  _MAX_VALUES_SIZE = 1000000

  def run(self, job_name, filenames):
    yield mapper_pipeline.MapperPipeline(
        job_name + "-shuffle-merge",
        __name__ + "._merge_map",
        __name__ + "._MergingReader",
        output_writer_spec=
        output_writers.__name__ + ".BlobstoreRecordsOutputWriter",
        params={
            _MergingReader.FILES_PARAM: filenames,
            _MergingReader.MAX_VALUES_COUNT_PARAM: self._MAX_VALUES_COUNT,
            _MergingReader.MAX_VALUES_SIZE_PARAM: self._MAX_VALUES_SIZE,
        },
        shards=len(filenames))


def _hashing_map(binary_record):
  """A map function used in hash phase.

  Reads KeyValue from binary record.

  Args:
    binary_record: The binary record.

  Yields:
    The (key, value).
  """
  proto = file_service_pb.KeyValue()
  proto.ParseFromString(binary_record)
  yield (proto.key(), proto.value())


class _HashPipeline(pipeline_base.PipelineBase):
  """A pipeline to read mapper output and hash by key.

  Args:
    job_name: root mapreduce job name.
    bucket_name: The name of your Google Cloud Storage bucket.
    filenames: filenames of mapper output. Should be of records format
      with serialized KeyValue proto.
    shards: Optional. Number of output shards to generate. Defaults
      to the number of input files.

  Yields:
    The list of filenames. Each file is of records formad with serialized
    KeyValue proto. For each proto its output file is decided based on key
    hash. Thus all equal keys would end up in the same file.
  """

  def run(self, job_name, bucket_name, filenames, shards=None):
    if shards is None:
      shards = len(filenames)
    yield mapper_pipeline.MapperPipeline(
        job_name + "-shuffle-hash",
        __name__ + "._hashing_map",
        input_readers.__name__ + "._GoogleCloudStorageRecordInputReader",
        output_writer_spec=__name__ + "._HashingBlobstoreOutputWriter",
        params={
            "input_reader": {
                "bucket_name": bucket_name,
                "objects": filenames,
            },
        },
        shards=shards)


def _strip_bucket_name(bucket_name, filenames):
  """Strips out the GCS bucket name from each filename if present.

  Args:
    bucket_name: The name of the Google Cloud Storage bucket in which the
      filenames reside.
    filenames: list of file names that may or may not contain the
      bucket_name.

  Returns:
    filenames: without the GCS bucket name (if present).
  """
  strip_out = "/%s/" % bucket_name
  filenames_only = []
  for filename in filenames:
    if filename.startswith(strip_out):
      filenames_only.append(filename[len(strip_out):])
    else:
      filenames_only.append(filename)
  return filenames_only


class ShufflePipeline(pipeline_base.PipelineBase):
  """A pipeline to shuffle multiple key-value files.

  Args:
    job_name: The descriptive name of the overall job.
    mapper_params: parameters to use for mapper phase.
    filenames: list of file names to sort. Files have to be of records format
      defined by Files API and contain serialized file_service_pb.KeyValue
      protocol messages. The filenames may or may not contain the
      GCS bucket name in their path.
    shards: Optional. Number of output shards to generate. Defaults
      to the number of input files.

  Returns:
    default: a list of filenames as string. Resulting files contain
      serialized file_service_pb.KeyValues protocol messages with
      all values collated to a single key. When there is no output,
      an empty list from shuffle service or a list of empty files from
      in memory shuffler.
  """

  def run(self, job_name, mapper_params, filenames, shards=None):
    bucket_name = mapper_params["bucket_name"]
    filenames_only = _strip_bucket_name(bucket_name, filenames)
    hashed_files = yield _HashPipeline(job_name, bucket_name,
                                       filenames_only, shards=shards)
    sorted_files = yield _SortChunksPipeline(job_name, hashed_files)
    temp_files = [hashed_files, sorted_files]

    merged_files = yield _MergePipeline(job_name, sorted_files)

    with pipeline.After(merged_files):
      all_temp_files = yield pipeline_common.Extend(*temp_files)
      yield mapper_pipeline._CleanupPipeline(all_temp_files)

    yield pipeline_common.Return(merged_files)
