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
















"""Base handler class for all mapreduce handlers."""





import httplib
import logging
import json
import webapp2

import google

try:
  from google.appengine.ext.mapreduce import pipeline_base
except ImportError:
  pipeline_base = None
from google.appengine.ext.mapreduce import errors
from google.appengine.ext.mapreduce import model
from google.appengine.ext.mapreduce import parameters
from google.appengine.ext.mapreduce import util


class Error(Exception):
  """Base-class for exceptions in this module."""


class BadRequestPathError(Error):
  """The request path for the handler is invalid."""


class BaseHandler(webapp2.RequestHandler):
  """Base class for all mapreduce handlers.

  In Python27 runtime, webapp2 will automatically replace webapp.
  """

  def base_path(self):
    """Base path for all mapreduce-related urls."""
    path = self.request.path
    return path[:path.rfind("/")]


class TaskQueueHandler(BaseHandler):
  """Base class for handlers intended to be run only from the task queue.

  Sub-classes should implement
  1. the 'handle' method for all POST request.
  2. '_preprocess' method for decoding or validations before handle.
  3. '_drop_gracefully' method if _preprocess fails and the task has to
     be dropped.
  """

  def __init__(self, *args, **kwargs):





    self._preprocess_success = False
    super(TaskQueueHandler, self).__init__(*args, **kwargs)

  def initialize(self, request, response):
    """Initialize.

    1. call webapp init.
    2. check request is indeed from taskqueue.
    3. check the task has not been retried too many times.
    4. run handler specific processing logic.
    5. run error handling logic if precessing failed.

    Args:
      request: a webapp.Request instance.
      response: a webapp.Response instance.
    """
    super(TaskQueueHandler, self).initialize(request, response)


    if "X-AppEngine-QueueName" not in self.request.headers:
      logging.error(self.request.headers)
      logging.error("Task queue handler received non-task queue request")
      self.response.set_status(
          403, message="Task queue handler received non-task queue request")
      return


    if self.task_retry_count() > parameters._MAX_TASK_RETRIES:
      logging.error(
          "Task %s has been retried %s times. Dropping it permanently.",
          self.request.headers["X-AppEngine-TaskName"], self.task_retry_count())
      return

    try:
      self._preprocess()
      self._preprocess_success = True

    except:



      self._preprocess_success = False
      mr_id = self.request.headers.get(util._MR_ID_TASK_HEADER, None)
      if mr_id is None:
        raise
      logging.error(
          "Preprocess task %s failed. Dropping it permanently.",
          self.request.headers["X-AppEngine-TaskName"])
      self._drop_gracefully()

  def post(self):
    if self._preprocess_success:
      self.handle()

  def handle(self):
    """To be implemented by subclasses."""
    raise NotImplementedError()

  def _preprocess(self):
    """Preprocess.

    This method is called after webapp initialization code has been run
    successfully. It can thus access self.request, self.response and so on.
    """
    pass

  def _drop_gracefully(self):
    """Drop task gracefully.

    When preprocess failed, this method is called before the task is dropped.
    """
    pass

  def task_retry_count(self):
    """Number of times this task has been retried."""
    return int(self.request.headers.get("X-AppEngine-TaskExecutionCount", 0))

  def retry_task(self):
    """Ask taskqueue to retry this task.

    Even though raising an exception can cause a task retry, it
    will flood logs with highly visible ERROR logs. Handlers should uses
    this method to perform controlled task retries. Only raise exceptions
    for those deserve ERROR log entries.
    """
    self.response.set_status(httplib.SERVICE_UNAVAILABLE, "Retry task")
    self.response.clear()


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
      output = json.dumps(self.json_response, cls=model.JsonEncoder)
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


class HugeTaskHandler(TaskQueueHandler):
  """Base handler for processing HugeTasks."""

  class _RequestWrapper(object):
    def __init__(self, request):
      self._request = request
      self._params = model.HugeTask.decode_payload(request)

    def get(self, name, default=""):
      return self._params.get(name, default)

    def set(self, name, value):
      self._params[name] = value

    def __getattr__(self, name):
      return getattr(self._request, name)

  def __init__(self, *args, **kwargs):
    super(HugeTaskHandler, self).__init__(*args, **kwargs)

  def _preprocess(self):
    self.request = self._RequestWrapper(self.request)


if pipeline_base:

  PipelineBase = pipeline_base.PipelineBase
else:
  PipelineBase = None
