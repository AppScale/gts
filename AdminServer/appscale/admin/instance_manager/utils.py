""" Common functions for managing AppServer instances. """

import fnmatch
import glob
import logging
import os
import shutil
import subprocess

from appscale.admin.constants import InvalidSource
from appscale.admin.instance_manager.constants import (
  CONFLICTING_JARS, LOGROTATE_CONFIG_DIR, MODIFIED_JARS, MONIT_INSTANCE_PREFIX)
from appscale.common.constants import CONFIG_DIR

logger = logging.getLogger(__name__)


def fetch_file(host, location):
  """ Copies a file from another machine.

  Args:
    host: A string specifying the IP address or hostname of the remote machine.
    location: A string specifying the path to the file.
  """
  key_file = os.path.join(CONFIG_DIR, 'ssh.key')
  remote_location = '{}:{}'.format(host, location)
  scp_cmd = ['scp', '-i', key_file,
             '-o', 'StrictHostKeyChecking no',
             remote_location, location]
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
    logger.info('Creating lib directory: {}'.format(lib_dir))
    os.mkdir(lib_dir)

  for pattern in MODIFIED_JARS:
    copy_files_matching_pattern(pattern, lib_dir)


def remove_conflicting_jars(source_path):
  """ Removes jars uploaded which may conflict with AppScale jars.

  Args:
    source_path: A string specifying the location of the source code.
  """
  lib_dir = os.path.join(find_web_inf(source_path), 'lib')
  if not os.path.isdir(lib_dir):
    logger.warn('Java source does not contain lib directory')
    return

  logger.info('Removing jars from {}'.format(lib_dir))
  for file in os.listdir(lib_dir):
    for pattern in CONFLICTING_JARS:
      if fnmatch.fnmatch(file, pattern):
        os.remove(os.path.join(lib_dir, file))


def remove_logrotate(project_id):
  """ Removes logrotate script for the given project.

  Args:
    project_id: A string, the name of the project to remove logrotate for.
  """
  app_logrotate_script = "{0}/appscale-{1}".\
    format(LOGROTATE_CONFIG_DIR, project_id)
  logger.debug("Removing script: {}".format(app_logrotate_script))

  try:
    os.remove(app_logrotate_script)
  except OSError:
    logging.error("Error while removing log rotation for application: {}".
                  format(project_id))


def setup_logrotate(app_name, log_size):
  """ Creates a logrotate script for the logs that the given application
      will create.

  Args:
    app_name: A string, the application ID.
    log_size: An integer, the size of logs that are kept per application server.
      The size should be in bytes.
  Returns:
    True on success, False otherwise.
  """
  # Write application specific logrotation script.
  app_logrotate_script = "{0}/appscale-{1}".\
    format(LOGROTATE_CONFIG_DIR, app_name)

  log_prefix = ''.join([MONIT_INSTANCE_PREFIX, app_name])

  # Application logrotate script content.
  contents = """/var/log/appscale/{log_prefix}*.log {{
  size {size}
  missingok
  rotate 7
  compress
  delaycompress
  notifempty
  copytruncate
}}
""".format(log_prefix=log_prefix, size=log_size)
  logger.debug("Logrotate file: {} - Contents:\n{}".
    format(app_logrotate_script, contents))

  with open(app_logrotate_script, 'w') as app_logrotate_fd:
    app_logrotate_fd.write(contents)

  return True
