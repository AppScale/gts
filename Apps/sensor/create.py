#!/usr/bin/env python

""" Creates test data and provides a REST interface. """

import json
import logging
import os
import sys

# Include these paths to get webapp2.
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webob-1.2.3"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer/lib/webapp2-2.5.2/"))
import webapp2

from base_handler import BaseHandler
from common import constants
import settings

sys.path.append(os.path.join(os.path.dirname(__file__), "../../AppServer"))
from google.appengine.api.namespace_manager import set_namespace
from google.appengine.ext import db

class TestEntityOne(db.Model):
  """ Class representing test entity 1. """
  description = db.TextProperty()
  status = db.StringProperty(default="created")
  integer = db.IntegerProperty(default=0)
  datetimeprop = db.DateTimeProperty(auto_now_add=True, auto_now=True)

class TestEntityTwo(db.Model):
  """ Class representing test entity 2. """
  description = db.TextProperty()
  status = db.StringProperty(default="created")
  integer = db.IntegerProperty(default=0)
  datetimeprop = db.DateTimeProperty(auto_now_add=True, auto_now=True)


def perform_create(namespace, amount):
  """ Triggers create mapper jobs.

  Args:
    namespace: The namespace to use.
    amount: The number of entities to create.

  Returns:
    The job or task ids.
  """
  set_namespace(namespace)
  for ii in range(0, amount):
    db.put(TestEntityOne(description="HELLO!", integer=ii, status=str(ii)))

  for ii in range(0, amount):
    db.put(TestEntityTwo(description="BYEBYE!", integer=ii, status=str(ii)))
 
  return True, ""

class Create(BaseHandler):
  """ Handler for creating test entities. """

  def post(self):
    """ POST method to create test entities. """
    remote_api_key = self.request.get(constants.ApiTags.API_KEY)
    logging.debug("API key: {0}".format(remote_api_key))
    if remote_api_key != settings.API_KEY:
      self.error_out("Request with bad API key")
      return

    name_space = self.request.get("ns")
    logging.debug("Namespace: {0}".format(name_space))
    if not name_space:
      self.error_out("No namespace provided")
      return

    amount = self.request.get("amount")
    logging.debug("# of entities: {0}".format(amount))
    if not amount:
      self.error_out("No # of entities specified")
      return

    success, reason = perform_create(name_space, int(amount))
    json_result = {"success": success, "reason": reason}
    self.response.write(json.dumps(json_result))

APP = webapp2.WSGIApplication([
  (r'/create/', Create),
], debug=constants.DEBUG_MODE)
