import re
import sys

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)


class EmptyQueue(Exception):
  """ Indicates that there are no tasks in the queue. """
  pass

class QueueNotFound(Exception):
  """ Indicates that the specified queue does not exist. """
  pass

class InvalidQueueConfiguration(Exception):
  """ Indicates an invalid queue configuration. """
  pass

class InvalidTarget(Exception):
  """ Indicates an invalid target. """
  pass

class TaskNotFound(Exception):
  """ Indicates that the specified task does not exist. """
  pass


# A regex rule for validating push queue age limit.
AGE_LIMIT_REGEX = re.compile(r'^([0-9]+(\.[0-9]*(e-?[0-9]+))?[smhd])')

# A regex rule for validating push queue rate.
RATE_REGEX = re.compile(r'^(0|[0-9]+(\.[0-9]*)?/[smhd])')

# A regex rule for validating targets, will not match instance.version.module.
TARGET_REGEX = re.compile(r'^([a-zA-Z0-9\-]+[\.]?[a-zA-Z0-9\-]*)$')

SHUTTING_DOWN_TIMEOUT = 10  # Limit time for finishing request

MAX_QUEUE_NAME_LENGTH = 100

# A regex rule for validating queue names.
FULL_QUEUE_NAME_PATTERN = r'^(projects/[a-zA-Z0-9-]+/taskqueues/)?' \
                     r'[a-zA-Z0-9-]{1,%s}$' % MAX_QUEUE_NAME_LENGTH

# A compiled regex rule for validating queue names.
FULL_QUEUE_NAME_RE = re.compile(FULL_QUEUE_NAME_PATTERN)
