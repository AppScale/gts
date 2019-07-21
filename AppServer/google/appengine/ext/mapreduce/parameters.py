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
"""Parameters to control Mapreduce."""

__all__ = ["CONFIG_NAMESPACE",
           "config"]

from google.appengine.api import lib_config

CONFIG_NAMESPACE = "mapreduce"


class _ConfigDefaults(object):
  """Default configs.

  Do not change parameters whose names begin with _.

  SHARD_MAX_ATTEMPTS: Max attempts to execute a shard before giving up.

  TASK_MAX_ATTEMPTS: Max attempts to execute a task before dropping it. Task
    is any taskqueue task created by MR framework. A task is dropped
    when its X-AppEngine-TaskExecutionCount is bigger than this number.
    Dropping a task will cause abort on the entire MR job.

  TASK_MAX_DATA_PROCESSING_ATTEMPTS:
    Max times to execute a task when previous task attempts failed during
    data processing stage. An MR work task has three major stages:
    initial setup, data processing, and final checkpoint.
    Setup stage should be allowed to be retried more times than data processing
    stage: setup failures are caused by unavailable GAE services while
    data processing failures are mostly due to user function error out on
    certain input data. Thus, set TASK_MAX_ATTEMPTS higher than this parameter.

  QUEUE_NAME: Default queue for MR.

  SHARD_COUNT: Default shard count.

  PROCESSING_RATE_PER_SEC: Default rate of processed entities per second.

  BASE_PATH : Base path of mapreduce and pipeline handlers.
  """

  SHARD_MAX_ATTEMPTS = 4


  TASK_MAX_ATTEMPTS = 31

  TASK_MAX_DATA_PROCESSING_ATTEMPTS = 11

  QUEUE_NAME = "default"

  SHARD_COUNT = 8


  PROCESSING_RATE_PER_SEC = 1000000


  BASE_PATH = "/_ah/mapreduce"




  _SLICE_DURATION_SEC = 15


  _LEASE_GRACE_PERIOD = 1


  _REQUEST_EVENTUAL_TIMEOUT = 10 * 60 + 30


  _CONTROLLER_PERIOD_SEC = 2


config = lib_config.register(CONFIG_NAMESPACE, _ConfigDefaults.__dict__)





_DEFAULT_PIPELINE_BASE_PATH = config.BASE_PATH + "/pipeline"

_GCS_URLFETCH_TIMEOUT_SEC = 30
