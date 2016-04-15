#!/usr/bin/env python
""" 
Checks different APIs and sends data to AppScale servers for analysis.
"""
from common import constants
from common import util

import importlib
import json
import logging
import os
import settings
import sys

# Include these paths to get webapp2.
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webob-1.2.3"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webapp2-2.5.2/"))
import webapp2

class AllChecker(webapp2.RequestHandler):
  """ Path for retrieving health status. """
  def get(self):
    """ GET path to do health checking on different APIs. """
    remote_api_key = self.request.get(constants.ApiTags.API_KEY)
    if remote_api_key != settings.API_KEY:
      logging.error("Request with bad API key")
      self.response.set_status(constants.HTTP_DENIED)
      self.response.write("Bad API Key")
      return
    results = {}
    uuid_tag = util.get_uuid()
    for suite_tag in constants.AllTestSuites.all_suites():
      suite_runner_constructor = get_runner_constructor(suite_tag)
      suite_runner = suite_runner_constructor(uuid_tag)
      results[suite_tag] = suite_runner.run()
      suite_runner.cleanup()
    json_result = json.dumps( 
      {constants.ApiTags.DATA: {uuid_tag:results},
       constants.ApiTags.APP_ID: settings.APP_ID,
       constants.ApiTags.USER_ID: settings.USER_ID,
       constants.ApiTags.API_KEY: settings.API_KEY})
      
    self.response.write(json_result)

def get_runner_constructor(suite_tag):
  """ Returns the function to run for the test runner.
 
  Args:
    suite_tag: A str, locates the test runner for an API.
  Returns:
    A function to run the tests.
  """
  module_name = "api_tests." + suite_tag.lower()
  module = importlib.import_module(module_name)
  suite_runner_function = getattr(module, "Test" + suite_tag)
  return suite_runner_function

def get_result(suite_tag, uuid_tag):
  """ Gets the results for a test.

  Args:
    suite_tag: A str, locates the test runner for an API.
    uuid: A str, a unique string to identify a test.
  Returns:
    A JSON result string.
  """
  suite_runner_constructor = get_runner_constructor(suite_tag)
  suite_runner = suite_runner_constructor(uuid_tag) 
  results = suite_runner.run()
  suite_runner.cleanup()
  json_result = json.dumps( 
    {constants.ApiTags.DATA: {uuid_tag: {suite_tag: results}},
     constants.ApiTags.USER_ID: settings.USER_ID,
     constants.ApiTags.APP_ID: settings.APP_ID,
     constants.ApiTags.API_KEY: settings.API_KEY})
 
  logging.debug(json_result)
  return json_result

APP = webapp2.WSGIApplication([
  (r'/health/all', AllChecker),
], debug=constants.DEBUG_MODE)
