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
"""Base pipelines."""

import google

from appengine_pipeline.src import pipeline

from google.appengine.ext.mapreduce import parameters




class PipelineBase(pipeline.Pipeline):
  """Base class for all pipelines within mapreduce framework.

  Rewrites base path to use pipeline library bundled with mapreduce.
  """

  def start(self, **kwargs):
    if "base_path" not in kwargs:
      kwargs["base_path"] = parameters._DEFAULT_PIPELINE_BASE_PATH
    return pipeline.Pipeline.start(self, **kwargs)


class _OutputSlotsMixin(object):
  """Defines common output slots for all MR user facing pipelines.

  result_status: one of model.MapreduceState._RESULTS. When a MR pipeline
    finishes, user should check this for the status of the MR job.
  """

  output_names = ["result_status"]
