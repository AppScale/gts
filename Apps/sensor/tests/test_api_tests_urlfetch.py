#!/usr/bin/env python
""" Testing for Memcache API checker. """

import os
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from api_tests import urlfetch
from common import constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.api import urlfetch as google_urlfetch

class FakeGoodResponse:
  def __init__(self):
    self.status_code = constants.HTTP_OK

class FakeBadResponse:
  def __init__(self):
    self.status_code = constants.HTTP_NOTFOUND

class TestUrlfetch(unittest.TestCase):
  def test_fetch(self):
    mock = flexmock(google_urlfetch)
    
    # Test execution without exceptions.
    mock.should_receive("fetch").and_return(FakeGoodResponse())
    results = urlfetch.fetch("fake_url")
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), 0)

    # Test with exceptions being thrown up.
    mock.should_receive("fetch").and_raise(Exception("test exception"))
    results = urlfetch.fetch("fake_url")
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)

    # Test execution without exceptions but 404 returned
    mock.should_receive("fetch").and_return(FakeBadResponse())
    results = urlfetch.fetch("fake_url")
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)
