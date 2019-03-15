""" Helper functions for Hermes operations. """
import errno
import os

class JSONTags(object):
  """ A class containing all JSON tags used for Hermes functionality. """
  ALL_STATS = 'all_stats'
  BUCKET_NAME = 'bucket_name'
  BODY = 'body'
  DEPLOYMENT_ID = 'deployment_id'
  ERROR = 'error'
  OBJECT_NAME = 'object_name'
  REASON = 'reason'
  STATUS = 'status'
  STORAGE = 'storage'
  SUCCESS = 'success'
  TASK_ID = 'task_id'
  TIMESTAMP = 'timestamp'
  TYPE = 'type'
  UNREACHABLE = 'unreachable'

def ensure_directory(dir_path):
  """ Ensures that the directory exists.

  Args:
    dir_path: A str representing the directory path.
  """
  try:
    os.makedirs(dir_path)
  except OSError as os_error:
    if os_error.errno == errno.EEXIST and os.path.isdir(dir_path):
      pass
    else:
      raise
