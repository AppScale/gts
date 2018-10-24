#!/usr/bin/env python

import unittest

from appscale.taskqueue.brokers import rabbitmq


class TestBrokerRabbitMQ(unittest.TestCase):
  """
  A set of test cases for the RabbitMQ broker.
  """
  def test_get_rabbitmq_location(self):
    expected = "amqp://guest:guest@localhost:5672//"
    self.assertEquals(rabbitmq.get_connection_string(), expected)

if __name__ == "__main__":
  unittest.main()    
