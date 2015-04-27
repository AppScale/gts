#!/usr/bin/env python

import os
import sys
import unittest
import tornado.httpclient
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import helper
from custom_exceptions import MissingRequestArgs

class FakeAsyncClient():
  def fetch(self):
    pass

class FakeClient():
  def fetch(self):
    pass

class FakeRequest():
  def __init__(self):
    self.url = 'http://some.url'

class FakeResponse():
  def __init__(self, request, code):
    self.request = request
    self.code = code

class TestHelper(unittest.TestCase):
  """ A set of test cases for Hermes helper functions. """

  def test_create_request(self):
    # Test with no args.
    self.assertRaises(MissingRequestArgs, helper.create_request)
    # Test GET.
    self.assertIsNotNone(helper.create_request, ['some url', 'some method'])
    # Test POST.
    self.assertIsNotNone(helper.create_request, ['some url', 'some method',
      'some data'])

  def test_urlfetch(self):
    fake_request = FakeRequest()
    fake_response = FakeResponse(fake_request, 200)
    fake_client = flexmock(tornado.httpclient.HTTPClient())

    fake_client.should_receive('fetch').and_return(fake_response)
    self.assertIsNotNone(helper.urlfetch, fake_request)

  def test_urlfetch_async(self):
    pass

  def test_get_br_service_url(self):
    pass

  def get_secret_key(self):
    pass

if __name__ == "__main__":
  unittest.main()
