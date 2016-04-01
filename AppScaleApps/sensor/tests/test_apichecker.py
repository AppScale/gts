#!/usr/bin/env python
""" Testing for high level API checker. """
import json
import os
import sys
import unittest

from flexmock import flexmock

# Include these paths to get webapp2.
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer/lib/webob-1.2.3"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer/lib/webapp2-2.5.2/"))
import webapp2

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import apichecker

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.api import urlfetch

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from common import constants
from common import util
import settings

class FakeRunner:
  def __init__(self, uuid):
    self.uuid = uuid
  def run(self):
    return {'fake':'value'}
  def cleanup(self):
    return

class TestApiChecker(unittest.TestCase):
  def test_get_result(self):
    flexmock(apichecker).should_receive('get_runner_constructor').and_return(FakeRunner)
    uuid = 'myuuid'

    expected = {constants.ApiTags.DATA: {uuid: {"Memcache": {'fake':'value'}}},
      constants.ApiTags.USER_ID: settings.USER_ID,
      constants.ApiTags.APP_ID: settings.APP_ID,
      constants.ApiTags.API_KEY: settings.API_KEY}
    self.assertEquals(json.dumps(expected), apichecker.get_result('Memcache', uuid))

    expected = {constants.ApiTags.DATA: {uuid: {"DB": {'fake':'value'}}},
      constants.ApiTags.USER_ID: settings.USER_ID,
      constants.ApiTags.APP_ID: settings.APP_ID,
      constants.ApiTags.API_KEY: settings.API_KEY}
    self.assertEquals(json.dumps(expected), apichecker.get_result('DB', uuid))

    expected = {constants.ApiTags.DATA: {uuid: {"Urlfetch": {'fake':'value'}}},
      constants.ApiTags.USER_ID: settings.USER_ID,
      constants.ApiTags.APP_ID: settings.APP_ID,
      constants.ApiTags.API_KEY: settings.API_KEY}
    self.assertEquals(json.dumps(expected), apichecker.get_result('Urlfetch', uuid))
