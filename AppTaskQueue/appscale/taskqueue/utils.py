import logging
import sys

from .unpackaged import APPSCALE_LIB_DIR

sys.path.append(APPSCALE_LIB_DIR)
from constants import LOG_FORMAT


logging.basicConfig(format=LOG_FORMAT)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


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
