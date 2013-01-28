""" AppScale TaskQueue configuration class. """

import os
import sys 

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import file_io

class TaskQueueConfig():
  """ Contains configuration of the TaskQueue system. """

  RABBITMQ = 0
  # Other brokers include Redis, MongoDB, Beanstalk, CouchDB, SQLAlchemy
  # Django ORM, Amazon, SQS and more. 

  def __init__(self, broker):
    """ Configuration constructor. 

    Args:
      broker: The broker to use.
    """
    self._broker = broker
    self._broker_location = self.__broker_location(broker)

  def __broker_location(self, broker):
    """ Gets the broker location connection string.
    
    Args:
      broker: The broker enum value.
    Returns:
      A broker connection string.
    Raises:
      NotImplementedError: If the broker is not implemented
    """ 
    if broker == self.RABBITMQ:
      from brokers import rabbitmq
      return rabbitmq.get_connection_string()
    else:
      raise NotImplementedError(
              "The given broker of code %d is not implemented" % broker)

  def get_broker_string(self):
    """ Gets the broker connection string.

    Returns:
      A string which tells of the location of the configured broker.
    """
    return self._broker_location
