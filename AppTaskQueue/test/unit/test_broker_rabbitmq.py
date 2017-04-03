#!/usr/bin/env python

import unittest

from flexmock import flexmock

from appscale.common import file_io
from appscale.taskqueue.brokers import rabbitmq


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
