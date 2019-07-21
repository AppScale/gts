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
"""Per job config for map jobs."""
from google.appengine.ext.mapreduce import hooks
from google.appengine.ext.mapreduce import input_readers
from google.appengine.ext.mapreduce import output_writers
from google.appengine.ext.mapreduce import parameters
from google.appengine.ext.mapreduce import util
from google.appengine.ext.mapreduce.api.map_job import input_reader
from google.appengine.ext.mapreduce.api.map_job import mapper as mapper_module





_Option = parameters._Option



_API_VERSION = 1


class JobConfig(parameters._Config):
  """Configurations for a map job.

  Names started with _ are reserved for internal use.

  To create an instance:
  all option names can be used as keys to __init__.
  If an option is required, the key must be provided.
  If an option isn't required and no value is given, the default value
  will be used.
  """

  job_name = _Option(basestring, required=True)




  job_id = _Option(basestring, default_factory=util._get_descending_key)


  mapper = _Option(mapper_module.Mapper, required=True)





  input_reader_cls = _Option(input_reader.InputReader, required=True)


  input_reader_params = _Option(dict, default_factory=lambda: {})


  output_writer_cls = _Option(output_writers.OutputWriter,
                              can_be_none=True)


  output_writer_params = _Option(dict, default_factory=lambda: {})




  shard_count = _Option(int,
                        default_factory=lambda: parameters.config.SHARD_COUNT)


  user_params = _Option(dict, default_factory=lambda: {})


  queue_name = _Option(
      basestring, default_factory=lambda: parameters.config.QUEUE_NAME)


  shard_max_attempts = _Option(
      int, default_factory=lambda: parameters.config.SHARD_MAX_ATTEMPTS)



  done_callback_url = _Option(basestring, can_be_none=True)


  _force_writes = _Option(bool, default_factory=lambda: False)

  _base_path = _Option(basestring,
                       default_factory=lambda: parameters.config.BASE_PATH)

  _task_max_attempts = _Option(
      int, default_factory=lambda: parameters.config.TASK_MAX_ATTEMPTS)

  _task_max_data_processing_attempts = _Option(
      int, default_factory=(
          lambda: parameters.config.TASK_MAX_DATA_PROCESSING_ATTEMPTS))

  _hooks_cls = _Option(hooks.Hooks, can_be_none=True)

  _app = _Option(basestring, can_be_none=True)

  _api_version = _Option(int, default_factory=lambda: _API_VERSION)



  def _get_mapper_params(self):
    """Converts self to model.MapperSpec.params."""
    return {"input_reader": self.input_reader_params,
            "output_writer": self.output_writer_params}

  def _get_mapper_spec(self):
    """Converts self to model.MapperSpec."""

    from google.appengine.ext.mapreduce import model

    return model.MapperSpec(
        handler_spec=util._obj_to_path(self.mapper),
        input_reader_spec=util._obj_to_path(self.input_reader_cls),
        params=self._get_mapper_params(),
        shard_count=self.shard_count,
        output_writer_spec=util._obj_to_path(self.output_writer_cls))

  def _get_mr_params(self):
    """Converts self to model.MapreduceSpec.params."""
    return {"force_writes": self._force_writes,
            "done_callback": self.done_callback_url,
            "user_params": self.user_params,
            "shard_max_attempts": self.shard_max_attempts,
            "task_max_attempts": self._task_max_attempts,
            "task_max_data_processing_attempts":
                self._task_max_data_processing_attempts,
            "queue_name": self.queue_name,
            "base_path": self._base_path,
            "app_id": self._app,
            "api_version": self._api_version}






  @classmethod
  def _get_default_mr_params(cls):
    """Gets default values for old API."""
    cfg = cls(_lenient=True)
    mr_params = cfg._get_mr_params()
    mr_params["api_version"] = 0
    return mr_params

  @classmethod
  def _to_map_job_config(cls,
                         mr_spec,


                         queue_name):
    """Converts model.MapreduceSpec back to JobConfig.

    This method allows our internal methods to use JobConfig directly.
    This method also allows us to expose JobConfig as an API during execution,
    despite that it is not saved into datastore.

    Args:
      mr_spec: model.MapreduceSpec.
      queue_name: queue name.

    Returns:
      The JobConfig object for this job.
    """
    mapper_spec = mr_spec.mapper

    api_version = mr_spec.params.get("api_version", 0)
    old_api = api_version == 0





    return cls(_lenient=old_api,
               job_name=mr_spec.name,
               job_id=mr_spec.mapreduce_id,

               mapper=util.for_name(mapper_spec.handler_spec),
               input_reader_cls=mapper_spec.input_reader_class(),
               input_reader_params=input_readers._get_params(mapper_spec),
               output_writer_cls=mapper_spec.output_writer_class(),
               output_writer_params=output_writers._get_params(mapper_spec),
               shard_count=mapper_spec.shard_count,
               queue_name=queue_name,
               user_params=mr_spec.params.get("user_params"),
               shard_max_attempts=mr_spec.params.get("shard_max_attempts"),
               done_callback_url=mr_spec.params.get("done_callback"),
               _force_writes=mr_spec.params.get("force_writes"),
               _base_path=mr_spec.params["base_path"],
               _task_max_attempts=mr_spec.params.get("task_max_attempts"),
               _task_max_data_processing_attempts=(
                   mr_spec.params.get("task_max_data_processing_attempts")),
               _hooks_cls=util.for_name(mr_spec.hooks_class_name),
               _app=mr_spec.params.get("app_id"),
               _api_version=api_version)
