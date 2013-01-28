#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
from task_worker import Worker

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

class TestTaskQueueConfig(unittest.TestCase):
  """
  A set of test cases for the distributed taskqueue module
  """
  def test_constructor(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

  def test_get_broker_location(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)

if __name__ == "__main__":
  unittest.main()    
