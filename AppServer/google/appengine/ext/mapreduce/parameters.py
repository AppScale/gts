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

  Do not change parameters starts with _.

  SHARD_RETRY_LIMIT: How many times a shard can retry.

  QUEUE_NAME: Default queue for MR.

  SHARD_COUNT: Default shard count.

  PROCESSING_RATE_PER_SEC: Default rate of processed entities per second.

  BASE_PATH : Base path of mapreduce and pipeline handlers.

  RETRY_SLICE_ERROR_MAX_RETRIES:
    How many times to cope with a RetrySliceError before totally
  giving up and aborting the whole job. RetrySliceError is raised only
  during processing user data. Errors from MR framework are not counted.

  MAX_TASK_RETRIES: How many times to retry a task before dropping it.
  """

  SHARD_RETRY_LIMIT = 3

  QUEUE_NAME = "default"

  SHARD_COUNT = 8


  PROCESSING_RATE_PER_SEC = 1000000


  BASE_PATH = "/_ah/mapreduce"

  RETRY_SLICE_ERROR_MAX_RETRIES = 10


  MAX_TASK_RETRIES = 30




  _SLICE_DURATION_SEC = 15


  _LEASE_GRACE_PERIOD = 1


  _REQUEST_EVENTUAL_TIMEOUT = 10 * 60 + 30


  _CONTROLLER_PERIOD_SEC = 2


config = lib_config.register(CONFIG_NAMESPACE, _ConfigDefaults.__dict__)





_DEFAULT_PIPELINE_BASE_PATH = config.BASE_PATH + "/pipeline"





DEFAULT_SHARD_RETRY_LIMIT = config.SHARD_RETRY_LIMIT
DEFAULT_QUEUE_NAME = config.QUEUE_NAME
DEFAULT_SHARD_COUNT = config.SHARD_COUNT
_DEFAULT_PROCESSING_RATE_PER_SEC = config.PROCESSING_RATE_PER_SEC
_DEFAULT_BASE_PATH = config.BASE_PATH
_RETRY_SLICE_ERROR_MAX_RETRIES = config.RETRY_SLICE_ERROR_MAX_RETRIES
_MAX_TASK_RETRIES = config.MAX_TASK_RETRIES
_SLICE_DURATION_SEC = config._SLICE_DURATION_SEC
_LEASE_GRACE_PERIOD = config._LEASE_GRACE_PERIOD
_REQUEST_EVENTUAL_TIMEOUT = config._REQUEST_EVENTUAL_TIMEOUT
_CONTROLLER_PERIOD_SEC = config._CONTROLLER_PERIOD_SEC
