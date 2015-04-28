#!/usr/bin/env python

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

class TestHelper(unittest.TestCase):
  """ A set of test cases for Hermes top level functions. """

  def test_poll(self):
    flexmock(helper).should_receive('urlfetch_async').and_return()
    flexmock(helper).should_receive('create_request').and_return()
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
