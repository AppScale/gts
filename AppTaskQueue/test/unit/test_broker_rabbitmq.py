#!/usr/bin/env python

import os
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
from brokers import rabbitmq

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

class TestBrokerRabbitMQ(unittest.TestCase):
  """
  A set of test cases for the RabbitMQ broker.
  """
  def test_get_rabbitmq_location(self):
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1")
    flexmock(file_io) \
       .should_receive("write").and_return(None)
    expected = "amqp://guest:guest@192.168.0.1:5672//"
    self.assertEquals(rabbitmq.get_connection_string(), expected)

if __name__ == "__main__":
  unittest.main()    
