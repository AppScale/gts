""" Constants and helper functions for the RabbitMQ broker. """

import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
import file_io

# The FS location which contains the nearest RabbitMQ server
RABBITMQ_LOCATION_FILE = '/etc/appscale/rabbitmq_ip' 

# The port required to connect to RabbitMQ
RABBITMQ_PORT = 5672

def get_connection_string():
  """ Reads from the local FS to get the RabbitMQ location to 
      connect to.

  Returns:
    A string representing the location of RabbitMQ.
  """
  from brokers import rabbitmq
  rabbitmq_ip = file_io.read(RABBITMQ_LOCATION_FILE)
  return 'amqp://guest:guest@' + rabbitmq_ip + ':' + \
         str(RABBITMQ_PORT) + '//'

