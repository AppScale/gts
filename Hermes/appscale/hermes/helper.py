""" Helper functions for Hermes operations. """
import errno
import os

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
