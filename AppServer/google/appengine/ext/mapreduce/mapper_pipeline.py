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


__all__ = [
    "MapperPipeline",
    ]

import google

from google.appengine.api import files
from google.appengine.ext.mapreduce import control
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import parameters
from google.appengine.ext.mapreduce import pipeline_base





class MapperPipeline(pipeline_base._OutputSlotsMixin,
                     pipeline_base.PipelineBase):
  """Pipeline wrapper for mapper job.

  Args:
    job_name: mapper job name as string
    handler_spec: mapper handler specification as string.
    input_reader_spec: input reader specification as string.
    output_writer_spec: output writer specification as string.
    params: mapper parameters for input reader and output writer as dict.
    shards: number of shards in the job as int.

  Returns:
    default: the list of filenames produced by the mapper if there was any
      output and the map was completed successfully.
    result_status: one of model.MapreduceState._RESULTS.
    job_id: mr id that can be used to query model.MapreduceState. Available
      immediately after run returns.
  """
  async = True



  output_names = [


      "job_id",

      "counters"] + pipeline_base._OutputSlotsMixin.output_names

  def run(self,
          job_name,
          handler_spec,
          input_reader_spec,
          output_writer_spec=None,
          params=None,
          shards=None):
    """Start a mapreduce job.

    Args:
      job_name: mapreduce name. Only for display purpose.
      handler_spec: fully qualified name to your map function/class.
      input_reader_spec: fully qualified name to input reader class.
      output_writer_spec: fully qualified name to output writer class.
      params: a dictionary of parameters for input reader and output writer
        initialization.
      shards: number of shards. This provides a guide to mapreduce. The real
        number of shards is determined by how input are splited.
    """
    if shards is None:
      shards = parameters.config.SHARD_COUNT

    mapreduce_id = control.start_map(
        job_name,
        handler_spec,
        input_reader_spec,
        params or {},
        mapreduce_parameters={
            "done_callback": self.get_callback_url(),
            "done_callback_method": "GET",
            "pipeline_id": self.pipeline_id,
        },
        shard_count=shards,
        output_writer_spec=output_writer_spec,
        )
    self.fill(self.outputs.job_id, mapreduce_id)
    self.set_status(console_url="%s/detail?job_id=%s" % (
        (parameters.config.BASE_PATH, mapreduce_id)))

  def callback(self):
    """Callback after this async pipeline finishes."""
    mapreduce_id = self.outputs.job_id.value
    mapreduce_state = model.MapreduceState.get_by_job_id(mapreduce_id)
    mapper_spec = mapreduce_state.mapreduce_spec.mapper
    outputs = []
    output_writer_class = mapper_spec.output_writer_class()
    if (output_writer_class and
        mapreduce_state.result_status == model.MapreduceState.RESULT_SUCCESS):
      outputs = output_writer_class.get_filenames(mapreduce_state)

    self.fill(self.outputs.result_status, mapreduce_state.result_status)
    self.fill(self.outputs.counters, mapreduce_state.counters_map.to_dict())
    self.complete(outputs)


class _CleanupPipeline(pipeline_base.PipelineBase):
  """A pipeline to do a cleanup for mapreduce jobs.

  Args:
    filename_or_list: list of files or file lists to delete.
  """

  def delete_file_or_list(self, filename_or_list):
    if isinstance(filename_or_list, list):
      for filename in filename_or_list:
        self.delete_file_or_list(filename)
    else:
      filename = filename_or_list
      for _ in range(10):
        try:
          files.delete(filename)
          break
        except:
          pass

  def run(self, temp_files):
    self.delete_file_or_list(temp_files)
