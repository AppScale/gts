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
















"""Base handler class for all mapreduce handlers.
"""



import logging
try:
  import json as simplejson
except ImportError:
  import simplejson

import google
try:
  from appengine_pipeline.src import pipeline
except ImportError:
  pipeline = None
from google.appengine.ext import webapp
from google.appengine.ext.mapreduce import errors


class Error(Exception):
  """Base-class for exceptions in this module."""


class BadRequestPathError(Error):
  """The request path for the handler is invalid."""


class BaseHandler(webapp.RequestHandler):
  """Base class for all mapreduce handlers."""

  def base_path(self):
    """Base path for all mapreduce-related urls."""
    path = self.request.path
    return path[:path.rfind("/")]


class TaskQueueHandler(BaseHandler):
  """Base class for handlers intended to be run only from the task queue.

  Sub-classes should implement the 'handle' method.
  """

  def post(self):
    if "X-AppEngine-QueueName" not in self.request.headers:
      logging.error(self.request.headers)
      logging.error("Task queue handler received non-task queue request")
      self.response.set_status(
          403, message="Task queue handler received non-task queue request")
      return
    self._setup()
    self.handle()

  def _setup(self):
    """Called before handle method to set up handler."""
    pass

  def handle(self):
    """To be implemented by subclasses."""
    raise NotImplementedError()

  def task_retry_count(self):
    """Number of times this task has been retried."""
    return int(self.request.headers.get("X-AppEngine-TaskRetryCount", 0))


class JsonHandler(BaseHandler):
  """Base class for JSON handlers for user interface.

  Sub-classes should implement the 'handle' method. They should put their
  response data in the 'self.json_response' dictionary. Any exceptions raised
  by the sub-class implementation will be sent in a JSON response with the
  name of the error_class and the error_message.
  """

  def __init__(self, *args):
    """Initializer."""
    super(BaseHandler, self).__init__(*args)
    self.json_response = {}

  def base_path(self):
    """Base path for all mapreduce-related urls.

    JSON handlers are mapped to /base_path/command/command_name thus they
    require special treatment.
    """
    path = self.request.path
    base_path = path[:path.rfind("/")]
    if not base_path.endswith("/command"):
      raise BadRequestPathError(
          "Json handlers should have /command path prefix")
    return base_path[:base_path.rfind("/")]

  def _handle_wrapper(self):
    if self.request.headers.get("X-Requested-With") != "XMLHttpRequest":
      logging.error(self.request.headers)
      logging.error("Got JSON request with no X-Requested-With header")
      self.response.set_status(
          403, message="Got JSON request with no X-Requested-With header")
      return

    self.json_response.clear()
    try:
      self.handle()
    except errors.MissingYamlError:
      logging.debug("Could not find 'mapreduce.yaml' file.")
      self.json_response.clear()
      self.json_response["error_class"] = "Notice"
      self.json_response["error_message"] = "Could not find 'mapreduce.yaml'"
    except Exception, e:
      logging.exception("Error in JsonHandler, returning exception.")

      self.json_response.clear()
      self.json_response["error_class"] = e.__class__.__name__
      self.json_response["error_message"] = str(e)

    self.response.headers["Content-Type"] = "text/javascript"
    try:
      output = simplejson.dumps(self.json_response)
    except:
      logging.exception("Could not serialize to JSON")
      self.response.set_status(500, message="Could not serialize to JSON")
      return
    else:
      self.response.out.write(output)

  def handle(self):
    """To be implemented by sub-classes."""
    raise NotImplementedError()


class PostJsonHandler(JsonHandler):
  """JSON handler that accepts POST requests."""

  def post(self):
    self._handle_wrapper()


class GetJsonHandler(JsonHandler):
  """JSON handler that accepts GET posts."""

  def get(self):
    self._handle_wrapper()



_DEFAULT_BASE_PATH = "/_ah/mapreduce"
_DEFAULT_PIPELINE_BASE_PATH = _DEFAULT_BASE_PATH + "/pipeline"


if pipeline:
  class PipelineBase(pipeline.Pipeline):
    """Base class for all pipelines within mapreduce framework.

    Rewrites base path to use pipeline library bundled with mapreduce.
    """

    def start(self, **kwargs):
      if "base_path" not in kwargs:
        kwargs["base_path"] = _DEFAULT_PIPELINE_BASE_PATH
      return pipeline.Pipeline.start(self, **kwargs)
else:
  PipelineBase = None
