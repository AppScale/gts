import logging
import os

from appscale.common.constants import LOG_FORMAT
from celery import Celery
from kombu import (
  Exchange,
  Queue as KombuQueue
)
from .brokers import rabbitmq


logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# The directory where Celery configuration files are stored.
CELERY_CONFIG_DIR = os.path.join('/etc', 'appscale', 'celery', 'configuration')

# The working directory for Celery workers.
CELERY_WORKER_DIR = os.path.join('/etc', 'appscale', 'celery', 'workers')


def get_celery_worker_module_name(app_id):
  """ Returns the python module name of the queue worker script.

  Args:
    app_id: The application ID.
  Returns:
    A string of the module name.
  """
  return 'app___' + app_id


def get_celery_queue_name(app_id, queue_name):
  """ Gets a usable queue name for celery to prevent collisions where
  mulitple apps have the same name for a queue.

  Args:
    app_id: The application ID.
    queue_name: String name of the queue.
  Returns:
    A string to reference the queue name in celery.
  """
  return app_id + "___" + queue_name


def get_queue_function_name(queue_name):
  """ Returns the function name of a queue which is not the queue name for
  namespacing and collision reasons.

  Args:
    queue_name: The name of a queue.
  Returns:
    The string representing the function name.
  """
  # Remove '-' because that character is not valid for a function name.
  queue_name = queue_name.replace('-', '_')
  return "queue___%s" % queue_name


def get_celery_annotation_name(app_id, queue_name):
  """ Returns the annotation name for a celery configuration of a queue
  for a given application id.

  Args:
    app_id: The application ID.
    queue_name: The application queue name.
  Returns:
    A string for the annotation tag.
  """
  module_name = get_celery_worker_module_name(app_id)
  function_name = get_queue_function_name(queue_name)
  return "%s.%s" % (module_name, function_name)


def get_celery_configuration_path(app_id):
  """ Returns the full path of the configuration used for Celery.

  Args:
    app_id: The application ID.
  Returns:
    A string of the full file name of the configuration file.
  """
  return os.path.join(CELERY_CONFIG_DIR, '{}.json'.format(app_id))


def create_celery_for_app(app, rates):
  """ Create Celery interface for a given app.

  Args:
    app: A string specifying an application ID.
    rates: A dictionary mapping queue names to their rates.
  Returns:
    A Celery application object.
  """
  module_name = get_celery_worker_module_name(app)
  celery = Celery(module_name, broker=rabbitmq.get_connection_string(),
                  backend='amqp://')

  kombu_queues = []
  annotations = []
  for queue_name, rate in rates.items():
    celery_name = get_celery_queue_name(app, queue_name)
    kombu_queue = KombuQueue(celery_name, Exchange(app),
                             routing_key=celery_name)

    kombu_queues.append(kombu_queue)
    annotation_name = get_celery_annotation_name(app, queue_name)
    annotations.append({annotation_name: {'rate_limit': rate}})

  celery.conf.CELERY_QUEUES = kombu_queues
  celery.conf.CELERY_ANNOTATIONS = annotations

  # Everytime a task is enqueued, a temporary queue is created to store
  # results into rabbitmq. This can be bad in a high enqueue environment
  # We use the following to make sure these temp queues are not created.
  # See stackoverflow.com/questions/7144025/temporary-queue-made-in-celery.
  celery.conf.CELERY_IGNORE_RESULT = True
  celery.conf.CELERY_STORE_ERRORS_EVEN_IF_IGNORED = False

  # One month expiration date because a task can be deferred that long.
  celery.conf.CELERY_AMQP_TASK_RESULT_EXPIRES = 2678400

  # Disable prefetching for celery workers. If tasks are small in duration this
  # should be set to a higher value (64-128) for increased performance. See
  # celery.readthedocs.org/en/latest/userguide/optimizing.html#worker-settings.
  celery.conf.CELERYD_PREFETCH_MULTIPLIER = 1

  return celery
