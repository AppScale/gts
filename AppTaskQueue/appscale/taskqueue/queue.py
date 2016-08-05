import re
import sys

from task import InvalidTaskInfo
from unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.taskqueue.taskqueue import MAX_QUEUE_NAME_LENGTH

# A regex rule for validating queue names.
QUEUE_NAME_PATTERN = r'^[a-zA-Z0-9-]{1,%s}$' % MAX_QUEUE_NAME_LENGTH

# A compiled regex rule for validating queue names.
QUEUE_NAME_RE = re.compile(QUEUE_NAME_PATTERN)

# A regex rule for validating push queue rate.
RATE_REGEX = re.compile(r'^(0|[0-9]+(\.[0-9]*)?/[smhd])')

# A regex rule for validating push queue age limit.
AGE_LIMIT_REGEX = re.compile(r'^([0-9]+(\.[0-9]*(e-?[0-9]+))?[smhd])')

# The default rate for push queues.
DEFAULT_RATE = '5/s'

# The default number of task retries for a queue.
DEFAULT_RETRY_LIMIT = 0

# The queue default time limit for retrying a failed push task.
DEFAULT_AGE_LIMIT = None

# The default minimum number of seconds to wait before retrying push tasks.
DEFAULT_MIN_BACKOFF = .1

# The default maximum number of seconds to wait before retrying push tasks.
DEFAULT_MAX_BACKOFF = 3600.0

# The default maxiumum number of times to double the interval between retries.
DEFAULT_MAX_DOUBLINGS = 16

# Validation rules for queue parameters.
QUEUE_ATTRIBUTE_RULES = {
  'name': lambda name: QUEUE_NAME_RE.match(name),
  'mode': lambda mode: mode in (QueueTypes.PUSH, QueueTypes.PULL),
  'rate': lambda rate: RATE_REGEX.match(rate),
  'task_retry_limit': lambda limit: limit >= 0,
  'task_age_limit': lambda limit: (limit is None or
                                   AGE_LIMIT_REGEX.match(limit)),
  'min_backoff_seconds': lambda seconds: seconds >= 0,
  'max_backoff_seconds': lambda seconds: seconds >= 0,
  'max_doublings': lambda doublings: doublings >= 0
}


class InvalidQueueConfiguration(Exception):
  pass


class QueueTypes(object):
  PUSH = 'push'
  PULL = 'pull'


class Queue(object):
  """ Represents a queue created by an App Engine application. """

  # Attributes that may not be defined.
  OPTIONAL_ATTRS = ['rate', 'task_age_limit', 'min_backoff_seconds',
                    'max_backoff_seconds', 'max_doublings']

  def __init__(self, queue_info):
    """ Create a Queue object.

    Args:
      queue_info: A dictionary containing queue info.
    """
    if 'name' not in queue_info:
      raise InvalidQueueConfiguration(
        'Queue requires a name: {}'.format(queue_info))

    self.name = queue_info['name']

    self.mode = QueueTypes.PUSH
    if 'mode' in queue_info:
      self.mode = queue_info['mode']

    if self.mode == QueueTypes.PUSH:
      self.rate = DEFAULT_RATE
      if 'rate' in queue_info:
        self.rate = queue_info['rate']

    self.task_retry_limit = DEFAULT_RETRY_LIMIT
    if 'retry_parameters' in queue_info:
      retry_params = queue_info['retry_parameters']
      if 'task_retry_limit' in retry_params:
        self.task_retry_limit = retry_params['task_retry_limit']

    if self.mode == QueueTypes.PUSH:
      self.task_age_limit = DEFAULT_AGE_LIMIT
      self.min_backoff_seconds = DEFAULT_MIN_BACKOFF
      self.max_backoff_seconds = DEFAULT_MAX_BACKOFF
      self.max_doublings = DEFAULT_MAX_DOUBLINGS
      if 'retry_parameters' in queue_info:
        retry_params = queue_info['retry_parameters']
        if 'task_age_limit' in retry_params:
          self.task_age_limit = retry_params['task_age_limit']
        if 'min_backoff_seconds' in retry_params:
          self.min_backoff_seconds = retry_params['min_backoff_seconds']
        if 'max_backoff_seconds' in retry_params:
          self.max_backoff_seconds = retry_params['max_backoff_seconds']
        if 'max_doublings' in retry_params:
          self.max_doublings = retry_params['max_doublings']

    self.validate_config()

  def validate_config(self):
    """ Ensures all of the Queue's attributes are valid.

    Raises:
      InvalidQueueConfiguration if there is an invalid attribute.
    """
    for attribute, rule in QUEUE_ATTRIBUTE_RULES.iteritems():
      try:
        value = getattr(self, attribute)
      except AttributeError:
        continue

      if not rule(value):
        message = 'Invalid queue configuration for {queue}.{param}: {value}'\
          .format(queue=self.name, param=attribute, value=value)
        raise InvalidQueueConfiguration(message)

  def __eq__(self, other):
    """ Checks whether or not this Queue is equivalent to another.

    Returns:
      A boolean indicating whether or not the two Queues are equal.
    """
    if not isinstance(other, self.__class__):
      return False

    if self.name != other.name or self.mode != other.mode:
      return False

    for attribute in self.OPTIONAL_ATTRS:
      if hasattr(self, attribute):
        if not hasattr(other, attribute):
          return False
        if getattr(self, attribute) != getattr(other, attribute):
          return False
      else:
        if hasattr(other, attribute):
          return False

    return True

  def __repr__(self):
    """ Generates a string representation of the queue.

    Returns:
      A string representing the Queue.
    """
    attributes = {'mode': self.mode,
                  'task_retry_limit': self.task_retry_limit}
    for attribute in self.OPTIONAL_ATTRS:
      if hasattr(self, attribute):
        attributes[attribute] = getattr(self, attribute)

    attr_str = ', '.join('{}={}'.format(attr, val)
                         for attr, val in attributes.iteritems())
    return '<Queue {}: {}>'.format(self.name, attr_str)
