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
















"""Pipelines for mapreduce library."""

from __future__ import with_statement



import google

from appengine_pipeline.src import pipeline
from appengine_pipeline.src.pipeline import common as pipeline_common
from google.appengine.api import files
from google.appengine.api.files import file_service_pb
from google.appengine.ext.mapreduce import output_writers
from google.appengine.ext.mapreduce import base_handler
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import mapper_pipeline
from google.appengine.ext.mapreduce import shuffler




MapperPipeline = mapper_pipeline.MapperPipeline

ShufflePipeline = shuffler.ShufflePipeline


class KeyValueBlobstoreOutputWriter(
    output_writers.BlobstoreRecordsOutputWriter):
  """Output writer for KeyValue records files in blobstore."""

  def write(self, data, ctx):
    if len(data) != 2:
      logging.error("Got bad tuple of length %d (2-tuple expected): %s",
                    len(data), data)

    try:
      key = str(data[0])
      value = str(data[1])
    except TypeError:
      logging.error("Expecting a tuple, but got %s: %s",
                    data.__class__.__name__, data)

    proto = file_service_pb.KeyValue()
    proto.set_key(key)
    proto.set_value(value)
    output_writers.BlobstoreRecordsOutputWriter.write(self, proto.Encode(), ctx)


class MapPipeline(base_handler.PipelineBase):
  """Runs the map stage of MapReduce.

  Iterates over input reader and outputs data into key/value format
  for shuffler consumption.

  Args:
    job_name: mapreduce job name as string.
    mapper_spec: specification of map handler function as string.
    input_reader_spec: input reader specification as string.
    params: mapper and input reader parameters as dict.
    shards: number of shards to start as int.

  Returns:
    list of filenames list sharded by hash code.
  """

  def run(self,
          job_name,
          mapper_spec,
          input_reader_spec,
          params,
          shards=None):
    yield MapperPipeline(
        job_name + "-map",
        mapper_spec,
        input_reader_spec,
        output_writer_spec= __name__ + ".KeyValueBlobstoreOutputWriter",
        params=params,
        shards=shards)


class KeyValuesReader(input_readers.RecordsReader):
  """Reader to read KeyValues records files from Files API."""

  expand_parameters = True

  def __iter__(self):
    for binary_record in input_readers.RecordsReader.__iter__(self):
      proto = file_service_pb.KeyValues()
      proto.ParseFromString(binary_record)
      yield (proto.key(), proto.value_list())


class ReducePipeline(base_handler.PipelineBase):
  """Runs the reduce stage of MapReduce.

  Merge-reads input files and runs reducer function on them.

  Args:
    job_name: mapreduce job name as string.
    reader_spec: specification of reduce function.
    output_writer_spec: specification of output write to use with reduce
      function.
    params: mapper parameters to use as dict.
    filenames: list of filenames to reduce.

  Returns:
    filenames from output writer.
  """

  def run(self,
          job_name,
          reducer_spec,
          output_writer_spec,
          params,
          filenames):
    new_params = dict(params or {})
    new_params.update({
        "files": filenames
        })
    yield mapper_pipeline.MapperPipeline(
        job_name + "-reduce",
        reducer_spec,
        __name__ + ".KeyValuesReader",
        output_writer_spec,
        new_params)



class MapreducePipeline(base_handler.PipelineBase):
  """Pipeline to execute MapReduce jobs.

  Args:
    job_name: job name as string.
    mapper_spec: specification of mapper to use.
    reader_spec: specification of reducer to use.
    input_reader_spec: specification of input reader to read data from.
    output_writer_spec: specification of output writer to save reduce output to.
    mapper_params: parameters to use for mapper phase.
    reducer_params: parameters to use for reduce phase.
    shards: number of shards to use as int.

  Returns:
    filenames from output writer.
  """

  def run(self,
          job_name,
          mapper_spec,
          reducer_spec,
          input_reader_spec,
          output_writer_spec=None,
          mapper_params=None,
          reducer_params=None,
          shards=None):
    map_pipeline = yield MapPipeline(job_name,
                                     mapper_spec,
                                     input_reader_spec,
                                     params=mapper_params,
                                     shards=shards)
    shuffler_pipeline = yield ShufflePipeline(job_name, map_pipeline)
    reducer_pipeline = yield ReducePipeline(job_name,
                                            reducer_spec,
                                            output_writer_spec,
                                            reducer_params,
                                            shuffler_pipeline)
    with pipeline.After(reducer_pipeline):
      all_temp_files = yield pipeline_common.Extend(
          map_pipeline, shuffler_pipeline)
      yield mapper_pipeline._CleanupPipeline(all_temp_files)
    yield pipeline_common.Return(reducer_pipeline)
