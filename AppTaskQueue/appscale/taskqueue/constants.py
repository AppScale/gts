import re


class InvalidQueueConfiguration(Exception):
  """ Indicates an invalid queue configuration. """
  pass

class InvalidTarget(Exception):
  """ Indicates an invalid target. """
  pass

def non_negative_int(value):
  """ Checks if a value is greater than 0. """
  return isinstance(value, int) and value >= 0


# A regex rule for validating push queue age limit.
AGE_LIMIT_REGEX = re.compile(r'^([0-9]+(\.[0-9]*(e-?[0-9]+))?[smhd])')

# A compiled regex rule for validating queue names.
QUEUE_NAME_RE = re.compile(r'^[a-zA-Z0-9-]{1,100}$')

# A regex rule for validating push queue rate.
RATE_REGEX = re.compile(r'^(0|[0-9]+(\.[0-9]*)?/[smhd])')

# A regex rule for validating targets, will not match instance.version.module.
TARGET_REGEX = re.compile(r'^([a-zA-Z0-9\-]+[\.]?[a-zA-Z0-9\-]*)$')

REQUIRED_PULL_QUEUE_FIELDS = ['name', 'mode']

REQUIRED_PUSH_QUEUE_FIELDS = ['name', 'rate']

SUPPORTED_PULL_QUEUE_FIELDS = {
  'mode': lambda mode: mode == 'pull',
  'name': QUEUE_NAME_RE.match,
  'retry_parameters': {
    'task_retry_limit': non_negative_int
  }
}

# The supported push queue attributes and the rules they must follow.
SUPPORTED_PUSH_QUEUE_FIELDS = {
  'mode': lambda mode: mode == 'push',
  'name': QUEUE_NAME_RE.match,
  'rate': RATE_REGEX.match,
  'target': TARGET_REGEX.match,
  'retry_parameters': {
    'task_retry_limit': non_negative_int,
    'task_age_limit': AGE_LIMIT_REGEX.match,
    'min_backoff_seconds': non_negative_int,
    'max_backoff_seconds': non_negative_int,
    'max_doublings': non_negative_int
  }
}
