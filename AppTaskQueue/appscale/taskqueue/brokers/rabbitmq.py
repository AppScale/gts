""" Constants and helper functions for the RabbitMQ broker. """

import sys

from ..unpackaged import APPSCALE_LIB_DIR

sys.path.append(APPSCALE_LIB_DIR)
import file_io

# The FS location which contains the nearest RabbitMQ server
RABBITMQ_LOCATION_FILE = '/etc/appscale/taskqueue_nodes'

# The port required to connect to RabbitMQ
RABBITMQ_PORT = 5672

def get_connection_string():
  """ Reads from the local FS to get the RabbitMQ location to
      connect to.

  Returns:
    A string representing the location of RabbitMQ.
  """
  raw_ips = file_io.read(RABBITMQ_LOCATION_FILE)
  ips = raw_ips.split('\n')
  rabbitmq_ip = ips[0]

  return 'amqp://guest:guest@' + rabbitmq_ip + ':' + \
         str(RABBITMQ_PORT) + '//'
