""" Common functions for managing AppServer instances. """

import fnmatch
import glob
import logging
import os
import shutil
import subprocess

from appscale.common.constants import APPSCALE_HOME
from ..constants import InvalidSource


def fetch_file(host, location):
  """ Copies a file from another machine.

  Args:
    host: A string specifying the location of the remote machine.
    location: A string specifying the path to the file.
  """
  key_file = os.path.join('/', 'etc', 'appscale', 'ssh.key')
  remote_location = '{}:{}'.format(host, location)
  scp_cmd = ['scp', '-i', key_file, remote_location, location]
  subprocess.check_call(scp_cmd)


def find_web_inf(source_path):
  """ Returns the location of a Java revision's WEB-INF directory.

  Args:
    source_path: A string specifying the location of the revision's source.
  Returns:
    A string specifying the location of the WEB-INF directory.
  Raises:
    BadConfigurationException if the directory is not found.
  """
  # Check for WEB-INF directories that contain the required appengine-web.xml.
  matches = []
  for root, dirs, files in os.walk(source_path):
    if 'appengine-web.xml' in files and root.endswith('/WEB-INF'):
      matches.append(root)

  if not matches:
    raise InvalidSource('Unable to find WEB-INF directory')

  # Use the shortest path.
  shortest_match = matches[0]
  for match in matches:
    if len(match.split(os.sep)) < len(shortest_match.split(os.sep)):
      shortest_match = match
  return shortest_match


def copy_files_matching_pattern(file_path_pattern, dest):
  """ Copies files matching the pattern to the destination directory.

  Args:
    file_path_pattern: The pattern of the files to be copied over.
    dest: The destination directory.
  """
  for file in glob.glob(file_path_pattern):
    shutil.copy(file, dest)


def copy_modified_jars(source_path):
  """ Copies AppScale SDK modifications to the lib folder.

  Args:
    source_path: A string specifying the location of the source code.
  """
  web_inf_dir = find_web_inf(source_path)
  lib_dir = os.path.join(web_inf_dir, 'lib')

  if not os.path.isdir(lib_dir):
    logging.info('Creating lib directory: {}'.format(lib_dir))
    os.mkdir(lib_dir)

  repacked_lib_dir = os.path.join(
    APPSCALE_HOME, 'AppServer_Java', 'appengine-java-sdk-repacked', 'lib')
  patterns_to_copy = [
    os.path.join(repacked_lib_dir, 'user', '*.jar'),
    os.path.join(repacked_lib_dir, 'impl', 'appscale-*.jar'),
    os.path.join('/', 'usr', 'share', 'appscale', 'ext', '*')
  ]
  for pattern in patterns_to_copy:
    copy_files_matching_pattern(pattern, lib_dir)


def remove_conflicting_jars(source_path):
  """ Removes jars uploaded which may conflict with AppScale jars.

  Args:
    source_path: A string specifying the location of the source code.
  """
  lib_dir = os.path.join(find_web_inf(source_path), 'lib')
  if not os.path.isdir(lib_dir):
    logging.warn('Java source does not contain lib directory')
    return

  logging.info('Removing jars from {}'.format(lib_dir))
  conflicting_jars_pattern = [
    'appengine-api-1.0-sdk-*.jar',
    'appengine-api-stubs-*.jar',
    'appengine-api-labs-*.jar',
    'appengine-jsr107cache-*.jar',
    'jsr107cache-*.jar',
    'appengine-mapreduce*.jar',
    'appengine-pipeline*.jar',
    'appengine-gcs-client*.jar'
  ]
  for file in os.listdir(lib_dir):
    for pattern in conflicting_jars_pattern:
      if fnmatch.fnmatch(file, pattern):
        os.remove(os.path.join(lib_dir, file))
