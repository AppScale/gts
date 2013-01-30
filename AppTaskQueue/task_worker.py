""" Implements a the task queue worker and routing. """
from celery import Celery

from tq_config import TaskQueueConfig

config = TaskQueueConfig(TaskQueueConfig.RABBITMQ, app_id, )

celery = Celery('tasks', broker=config.get_broker_string(), backend='amqp')

@celery.task
def execute_task(url, args):
  pass

