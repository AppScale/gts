""" Helper functions for taskqueue library. """
import datetime
import os
import string
import sys
import random

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api.taskqueue import taskqueue_service_pb

# The longest you can delay a task.
MAX_ETA = datetime.timedelta(days=30)

# The most amount of bytes a pull task can have.
MAX_PULL_TASK_SIZE_BYTES = 2 ** 20

# The most amount of bytes a push task can have.
MAX_PUSH_TASK_SIZE_BYTES = 100 * (2 ** 10)

# The length of a random string.
RAND_LENGTH_SIZE = 32

# States of tasks which have been enqueued.
class TASK_STATES:
  QUEUED = "queued"
  SUCCESS = "success" 
  FAILED = "failed"
  EXPIRED = "expired"

def _sec_to_usec(t_sec):
  """Converts a time in seconds since the epoch to usec since the epoch.

  Args:
    t_sec: Time in seconds since the unix epoch
  Returns:
    An integer containing the number of usec since the unix epoch.
  """
  return int(t_sec * 1e6)

def _usec_to_sec(t_sec):
  """Converts a time in usec since the epoch to seconds since the epoch.

  Args:
    t_sec: Time in usec since the unix epoch.
  Returns:
    A float containing the number of seconds since the unix epoch.
  """
  return t_sec / 1e6

def verify_task_queue_add_request(app_id, request, now):
  """Checks that a TaskQueueAddRequest is valid.

  Checks that a TaskQueueAddRequest specifies a valid eta and a valid queue.

  Args:
    app_id: The application identifier.
    request: The taskqueue_service_pb.TaskQueueAddRequest to validate.
    now: A datetime.datetime object containing the current time in UTC.

  Returns:
    A taskqueue_service_pb.TaskQueueServiceError indicating any problems with
    the request or taskqueue_service_pb.TaskQueueServiceError.SKIPPED if it is
    valid.
  """
  if request.eta_usec() < 0:
    return taskqueue_service_pb.TaskQueueServiceError.INVALID_ETA

  eta = datetime.datetime.utcfromtimestamp(_usec_to_sec(request.eta_usec()))
  max_eta = now + MAX_ETA
  if eta > max_eta:
    return taskqueue_service_pb.TaskQueueServiceError.INVALID_ETA

  if request.has_crontimetable() and app_id is None:
    return taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED

  if request.mode() == taskqueue_service_pb.TaskQueueMode.PULL:
    max_task_size_bytes = MAX_PULL_TASK_SIZE_BYTES
  else:
    max_task_size_bytes = MAX_PUSH_TASK_SIZE_BYTES

  if request.ByteSize() > max_task_size_bytes:
    return taskqueue_service_pb.TaskQueueServiceError.TASK_TOO_LARGE

  return taskqueue_service_pb.TaskQueueServiceError.SKIPPED

def _get_random_string():
  """ Generates a random string of RAND_LENGTH_SIZE.
  
  Returns:
    A random string.
  """
  return ''.join(random.choice(string.ascii_uppercase + string.digits) \
                    for x in range(RAND_LENGTH_SIZE))

def choose_task_name(app_name, queue_name, user_chosen=None):
  """ Creates a task name that the system can use to address
      tasks from different apps and queues.
 
  Args:
    app_name: The application name.
    queue_name: The queue 
    user_chosen: A string name the user selected for their applicaiton.
  Returns:
    A randomized string representing a task name.
  """
  if not user_chosen:
    user_chosen = _get_random_string() 
  return 'task_%s_%s_%s' % (app_name, queue_name, user_chosen)
