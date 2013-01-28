""" A task worker. """

from celery import Celery
from tq_config = import TaskQueueConfig


class Worker():
  """ A celery taskqueue worker. """
  def __init__(self, broker):
    """ Worker constructor. 
    
    Args:
      broker: A TaskQueueConfig broker enum.
    """
    config = TaskQueueConfig(broker)
    celery = Celery('tasks', broker=config.get_broker_string())

