import base64
import datetime
import random
import re
import string
import sys

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from .constants import FULL_QUEUE_NAME_RE
from .protocols import taskqueue_service_pb2

sys.path.append(APPSCALE_PYTHON_APPSERVER)

MAX_TAG_LENGTH = 500

MAX_TASK_NAME_LENGTH = 500

# A regex rule for validating task names.
TASK_NAME_PATTERN = r'^[a-zA-Z0-9_-]{1,%s}$' % MAX_TASK_NAME_LENGTH

# A compiled regex rule for validating task names.
TASK_NAME_RE = re.compile(TASK_NAME_PATTERN)

# Validation rules for queue parameters.
QUEUE_ATTRIBUTE_RULES = {
  'id': lambda name: TASK_NAME_RE.match(name),
  'queueName': lambda name: FULL_QUEUE_NAME_RE.match(name),
  'tag': lambda tag: tag is None or len(tag) <= MAX_TAG_LENGTH
}

# All possible fields to include in a task's JSON representation.
TASK_FIELDS = ('kind', 'queueName', 'id', 'enqueueTimestamp', 'leaseTimestamp',
               'payloadBase64', 'retry_count', 'tag')


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
      encoded_payload = task_info['payloadBase64']

      # Google's REST API adds missing padding.
      missing_padding = 4 - (len(encoded_payload) % 4)
      encoded_payload += '=' * missing_padding

      # This decode/encode step is performed in order to match Google's
      # behavior in cases where the given payload does not have the correct
      # padding. It can be removed if we start storing the payload as binary
      # blobs. The conversion from unicode string to byte string is needed
      # because urlsafe_b64decode chokes on some invalid base64 that Google
      # accepts.
      payload = base64.urlsafe_b64decode(encoded_payload.encode('utf8'))
      self.payloadBase64 = base64.urlsafe_b64encode(payload)

    if 'id' in task_info and task_info['id']:
      self.id = task_info['id']
    else:
      self.id = ''.join(random.choice(string.ascii_lowercase)
                        for _ in range(20))

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
    for attribute, rule in QUEUE_ATTRIBUTE_RULES.items():
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
      InvalidTaskInfo if ETA information is not set.
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
      max_retries: An integer specifying the queue's task retry limit.
    Returns:
      A boolean indicating whether or not the task has expired.
    """
    if self.retry_count < max_retries:
      return False

    if self.leaseTimestamp >= datetime.datetime.utcnow():
      return False

    return True

  def __repr__(self):
    """ Generates a string representation of the task.

    Returns:
      A string representing the task.
    """
    attributes = {'id': self.id}
    if hasattr(self, 'queueName'):
      attributes['queue'] = self.queueName

    values = ', '.join(['='.join([attr, val])
                        for attr, val in attributes.items()])
    return '<Task: {}>'.format(values)

  def json_safe_dict(self, fields=TASK_FIELDS):
    """ Generate a JSON-safe dictionary representation of the task.

    Args:
      fields: A list of fields to include in the response.
    Returns:
      A JSON-safe dictionary representing the task.
    """
    task = {}

    if 'kind' in fields:
      task['kind'] = 'taskqueues#task'

    if 'id' in fields:
      task['id'] = self.id

    if 'retry_count' in fields:
      task['retry_count'] = self.retry_count

    # Timestamps are represented as microseconds since the epoch.
    epoch = datetime.datetime.utcfromtimestamp(0)
    for attribute in self.OPTIONAL_ATTRS:
      if attribute not in fields or not hasattr(self, attribute):
        continue

      value = getattr(self, attribute)
      if isinstance(value, datetime.datetime):
        # All numbers are represented as strings in the GCP ecosystem for
        # Javascript compatibility reasons. We convert to string so that
        # the response can be successfully parsed by Google API clients.
        value = str(int((value - epoch).total_seconds() * 1000000))
      task[attribute] = value
      if attribute == 'payloadBase64':
        task[attribute] = task[attribute].decode('utf-8')

    return task

  def encode_lease_pb(self):
    """ Encode this task as a protocol buffer response.

    Returns:
      A TaskQueueQueryAndOwnTasksResponse.Task object.
    """
    task_pb = \
      taskqueue_service_pb2.TaskQueueQueryAndOwnTasksResponse().task.add()
    task_pb.task_name = self.id.encode('utf-8')
    epoch = datetime.datetime.utcfromtimestamp(0)
    task_pb.eta_usec = int((self.get_eta() - epoch).total_seconds() * 1000000)
    task_pb.retry_count = self.retry_count
    task_pb.body = base64.urlsafe_b64decode(self.payloadBase64)
    try:
      task_pb.tag = self.tag.encode('utf-8')
    except AttributeError:
      pass
    return task_pb
