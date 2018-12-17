""" Constants and helper functions for the RabbitMQ broker. """

# The port required to connect to RabbitMQ
RABBITMQ_PORT = 5672

def get_connection_string():
  """ Generates a connection string.

  Returns:
    A string representing the location of RabbitMQ.
  """
  return 'amqp://guest:guest@localhost:{}//'.format(RABBITMQ_PORT)
