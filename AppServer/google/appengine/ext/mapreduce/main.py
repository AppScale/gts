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
















"""Main module for map-reduce implementation.

This module should be specified as a handler for mapreduce URLs in app.yaml:

  handlers:
  - url: /mapreduce(/.*)?
    login: admin
    script: mapreduce/main.py
"""


import wsgiref.handlers

import google
from google.appengine.ext import webapp
from google.appengine.ext.mapreduce import handlers
from google.appengine.ext.mapreduce import status
from google.appengine.ext.webapp import util

try:
  from appengine_pipeline.src import pipeline
except ImportError:
  pipeline = None


STATIC_RE = r".*/([^/]*\.(?:css|js)|status|detail)$"


class RedirectHandler(webapp.RequestHandler):
  """Redirects the user back to the status page."""

  def get(self):
    new_path = self.request.path
    if not new_path.endswith("/"):
      new_path += "/"
    new_path += "status"
    self.redirect(new_path)


def create_handlers_map():
  """Create new handlers map.

  Returns:
    list of (regexp, handler) pairs for WSGIApplication constructor.
  """
  pipeline_handlers_map = []

  if pipeline:
    pipeline_handlers_map = pipeline.create_handlers_map(prefix=".*/pipeline")

  return pipeline_handlers_map + [

      (r".*/worker_callback", handlers.MapperWorkerCallbackHandler),
      (r".*/controller_callback", handlers.ControllerCallbackHandler),
      (r".*/kickoffjob_callback", handlers.KickOffJobHandler),
      (r".*/finalizejob_callback", handlers.FinalizeJobHandler),



      (r".*/command/start_job", handlers.StartJobHandler),
      (r".*/command/cleanup_job", handlers.CleanUpJobHandler),
      (r".*/command/abort_job", handlers.AbortJobHandler),
      (r".*/command/list_configs", status.ListConfigsHandler),
      (r".*/command/list_jobs", status.ListJobsHandler),
      (r".*/command/get_job_detail", status.GetJobDetailHandler),


      (STATIC_RE, status.ResourceHandler),


      (r".*", RedirectHandler),
      ]

def create_application():
  """Create new WSGIApplication and register all handlers.

  Returns:
    an instance of webapp.WSGIApplication with all mapreduce handlers
    registered.
  """
  return webapp.WSGIApplication(create_handlers_map(),
                                debug=True)


APP = create_application()


def main():
  util.run_wsgi_app(APP)


if __name__ == "__main__":
  main()
