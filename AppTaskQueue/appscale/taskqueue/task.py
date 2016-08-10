import datetime
import json
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
  'tag': lambda tag: len(tag) <= MAX_TAG_LENGTH
}


class InvalidTaskInfo(Exception):
  pass


class Task(object):
  """ Represents a task created by an App Engine application. """

  # Attributes that may not be defined.
  OPTIONAL_ATTRS = ['queueName', 'enqueueTimestamp', 'leaseTimestamp', 'tag']

  def __init__(self, task_info):
    """ Create a Task object.

    Args:
      task_info: A dictionary containing task info.
    """
    self.retry_count = 0

    if 'payloadBase64' in task_info:
      self.payload = task_info['payloadBase64']

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
      if isinstance(task_info['leaseTimestamp'], datetime.datetime):
        self.leaseTimestamp = task_info['leaseTimestamp']
      else:
        self.leaseTimestamp = datetime.datetime.utcfromtimestamp(
          int(task_info['leaseTimestamp']) / 1000000.0)

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

  def __repr__(self):
    """ Generates a string representation of the task.

    Returns:
      A string representing the task.
    """
    attributes = {'id': self.id,
                  'payload': self.payload}
    attr_str = ', '.join('{}={}'.format(attr, val)
                         for attr, val in attributes.iteritems())
    return '<Task: {}>'.format(attr_str)

  def to_json(self):
    """ Generate a JSON representation of the task.

    Returns:
      A string in JSON format representing the task.
    """
    task = {
      'kind': 'taskqueues#task',
      'id': self.id,
      'payloadBase64': self.payload,
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
    return json.dumps(task)
