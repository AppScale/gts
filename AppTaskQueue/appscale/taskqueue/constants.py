import re


class InvalidQueueConfiguration(Exception):
  """ Indicates an invalid queue configuration. """
  pass


# A regex rule for validating push queue age limit.
AGE_LIMIT_REGEX = re.compile(r'^([0-9]+(\.[0-9]*(e-?[0-9]+))?[smhd])')

# A compiled regex rule for validating queue names.
QUEUE_NAME_RE = re.compile(r'^[a-zA-Z0-9-]{1,100}$')

# A regex rule for validating push queue rate.
RATE_REGEX = re.compile(r'^(0|[0-9]+(\.[0-9]*)?/[smhd])')

REQUIRED_PULL_QUEUE_FIELDS = ['name', 'mode']

REQUIRED_PUSH_QUEUE_FIELDS = ['name', 'rate']

SUPPORTED_PULL_QUEUE_FIELDS = {
  'mode': lambda mode: mode == 'pull',
  'name': QUEUE_NAME_RE.match,
  'retry_parameters': {
    'task_retry_limit': lambda limit: limit >= 0
  }
}

# The supported push queue attributes and the rules they must follow.
SUPPORTED_PUSH_QUEUE_FIELDS = {
  'mode': lambda mode: mode == 'push',
  'name': QUEUE_NAME_RE.match,
  'rate': RATE_REGEX.match,
  'retry_parameters': {
    'task_retry_limit': lambda limit: limit >= 0,
    'task_age_limit': AGE_LIMIT_REGEX.match,
    'min_backoff_seconds': lambda seconds: seconds >= 0,
    'max_backoff_seconds': lambda seconds: seconds >= 0,
    'max_doublings': lambda doublings: doublings >= 0
  }
}
