import datetime
import random
import re
import string
import sys

import queue
from unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.taskqueue.taskqueue import MAX_TAG_LENGTH
from google.appengine.api.taskqueue.taskqueue import MAX_TASK_NAME_LENGTH

# A regex rule for validating task names.
TASK_NAME_PATTERN = r'^[a-zA-Z0-9_-]{1,%s}$' % MAX_TASK_NAME_LENGTH

# A compiled regex rule for validating task names.
TASK_NAME_RE = re.compile(TASK_NAME_PATTERN)

# Validation rules for queue parameters.
QUEUE_ATTRIBUTE_RULES = {
  'id': lambda name: TASK_NAME_RE.match(name),
  'queueName': lambda name: queue.QUEUE_NAME_RE.match(name),
  'tag': lambda tag: tag is None or len(tag) <= MAX_TAG_LENGTH
}


def parse_timestamp(timestamp):
  """ Parses timestamps used for creating tasks.

  Args:
    timestamp: Either a datetime object or an integer specifying the number
      of microseconds since the epoch.
  Returns:
    A datetime object.
  """
  if isinstance(timestamp, datetime.datetime):
    return timestamp
  else:
    return datetime.datetime.utcfromtimestamp(int(timestamp) / 1000000.0)


class InvalidTaskInfo(Exception):
  pass


class Task(object):
  """ Represents a task created by an App Engine application. """

  # Attributes that may not be defined.
  OPTIONAL_ATTRS = ['queueName', 'enqueueTimestamp', 'leaseTimestamp', 'tag',
                    'payloadBase64']

  def __init__(self, task_info):
    """ Create a Task object.

    Args:
      task_info: A dictionary containing task info.
    """
    self.retry_count = 0

    if 'payloadBase64' in task_info:
      self.payloadBase64 = task_info['payloadBase64']

    self.id = ''.join(random.choice(string.ascii_lowercase) for _ in range(20))
    if 'id' in task_info:
      self.id = task_info['id']

    if 'queueName' in task_info:
      self.queueName = task_info['queueName']

    if 'tag' in task_info:
      self.tag = task_info['tag']

    if 'retry_count' in task_info:
      self.retry_count = task_info['retry_count']

    if 'leaseTimestamp' in task_info:
      self.leaseTimestamp = parse_timestamp(task_info['leaseTimestamp'])

    if 'enqueueTimestamp' in task_info:
      self.enqueueTimestamp = parse_timestamp(task_info['enqueueTimestamp'])

    self.validate_info()

  def validate_info(self):
    """ Make sure the existing attributes are valid.

    Raises:
      InvalidTaskInfo if one of the attribute fails validation.
    """
    for attribute, rule in QUEUE_ATTRIBUTE_RULES.iteritems():
      try:
        value = getattr(self, attribute)
      except AttributeError:
        continue

      if not rule(value):
        raise InvalidTaskInfo(
          'Invalid task info: {}={}'.format(attribute, value))

  def get_eta(self):
    """ Returns the ETA for a task.

    Raises:
      InvalidTaskInfo if
    """
    epoch = datetime.datetime.utcfromtimestamp(0)
    if hasattr(self, 'leaseTimestamp') and self.leaseTimestamp != epoch:
      return self.leaseTimestamp

    try:
      return self.enqueueTimestamp
    except AttributeError:
      raise InvalidTaskInfo('No ETA info for {}'.format(self))

  def expired(self, max_retries):
    """ Checks whether or not a task has expired.

    Args:
      max_retries: An integers specifying the queue's task retry limit.
    Returns:
      A boolean indicating whether or not the task has expired.
    """
    if self.retry_count <= max_retries:
      return False

    if self.leaseTimestamp >= datetime.datetime.now():
      return False

    return True

  def __repr__(self):
    """ Generates a string representation of the task.

    Returns:
      A string representing the task.
    """
    return '<Task: {}>'.format(self.id)

  def json_safe_dict(self):
    """ Generate a JSON-safe dictionary representation of the task.

    Returns:
      A JSON-safe dictionary representing the task.
    """
    task = {
      'kind': 'taskqueues#task',
      'id': self.id,
      'retry_count': self.retry_count
    }
    # Timestamps are represented as microseconds since the epoch.
    epoch = datetime.datetime.utcfromtimestamp(0)
    for attribute in self.OPTIONAL_ATTRS:
      if hasattr(self, attribute):
        value = getattr(self, attribute)
        if isinstance(value, datetime.datetime):
          value = long((value - epoch).total_seconds() * 1000000)
        task[attribute] = value

    return task
