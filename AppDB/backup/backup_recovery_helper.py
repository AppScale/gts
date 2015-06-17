""" Backup & Recovery helper functions. """

import logging
import os

def does_file_exist(path):
  """ Checks if the given file is in the local filesystem.

  Args:
    path: A str, the path to the file.
  Returns:
    True on success, False otherwise.
  """
  return os.path.isfile(path)

def mkdir(path):
  """ Creates a dir with the given path.

  Args:
    path: A str, the name of the dir to create.
  Returns:
    True on success, False otherwise.
  """
  try:
    os.mkdir(path)
  except OSError:
    logging.error("OSError while creating dir '{0}'".format(path))
    return False
  return True

def rename(source, destination):
  """ Renames source file into destination.

  Args:
    source: A str, the path of the file to rename.
    destination: A str, the destination path.
  Returns:
    True on success, False otherwise.
  """
  try:
    os.rename(source, destination)
  except OSError:
    logging.error("OSError while renaming '{0}' to '{1}'".
      format(source, destination))
    return False
  return True

def remove(path):
  """ Deletes the given file from the filesystem.

  Args:
    path: A str, the path of the file to delete.
  Returns:
    True on success, False otherwise.
  """
  try:
    os.remove(path)
  except OSError:
    logging.error("OSError while deleting '{0}'".
      format(path))
    return False
  return True
