#!/usr/bin/env python

import json
import os
import sys
import unittest
from flexmock import flexmock
from tornado.ioloop import IOLoop

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import helper
from hermes import poll
from hermes import shutdown
from hermes import signal_handler

class FakeResponse(object):
  def __init__(self):
    self.body = "{}"

class TestHelper(unittest.TestCase):
  """ A set of test cases for Hermes top level functions. """

  def test_poll(self):
    flexmock(helper).should_receive('get_deployment_id').and_return(None)
    poll()

    flexmock(helper).should_receive('get_deployment_id').\
      and_return('deployment_id')
    flexmock(json).should_receive('dumps').and_return("data")
    flexmock(helper).should_receive('create_request').and_return()
    flexmock(helper).should_receive('urlfetch').and_return(FakeResponse())
    flexmock(json).should_receive('loads').and_return({})
    flexmock(helper).should_receive('urlfetch_async').and_return()
    poll()

  def test_signal_handler(self):
    flexmock(IOLoop.instance()).should_receive('add_callback').and_return()\
      .times(1)
    signal_handler(15, None)

  def test_shutdown(self):
    flexmock(IOLoop.instance()).should_receive('stop').and_return().times(1)
    shutdown()

if __name__ == "__main__":
  unittest.main()
