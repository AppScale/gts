""" Backup & Recovery helper functions. """

import logging
import os
import statvfs
import sys
import tarfile
from os.path import getsize

import backup_recovery_constants
import backup_exceptions
from backup_recovery_constants import BACKUP_DIR_LOCATION
from backup_recovery_constants import BACKUP_ROLLBACK_SUFFIX

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
from constants import APPSCALE_DATA_DIR

def delete_local_backup_file(local_file):
  """ Removes the local backup file.

  Args:
    local_file: A str, the path to the backup file to delete.
  """
  if not remove(local_file):
    logging.warning("No local backup file '{0}' to delete. "
      "Skipping...".format(local_file))

def delete_secondary_backup(base_path):
  """ Deletes the secondary backup if it exists, upon successful backup.

  Args:
    base_path: A str, the full path of the backup file without the secondary
      suffix.
  """
  if not remove("{0}{1}".format(base_path, BACKUP_ROLLBACK_SUFFIX)):
    logging.warning("No secondary backup to remove. Skipping...")

def does_file_exist(path):
  """ Checks if the given file is in the local filesystem.

  Args:
    path: A str, the path to the file.
  Returns:
    True on success, False otherwise.
  """
  return os.path.isfile(path)

def enough_disk_space(service):
  """ Checks if there's enough available disk space for a new backup.

  Returns:
    True on success, False otherwise.
  """
  available_space = get_available_disk_space()
  logging.debug("Available space: {0}".format(available_space))

  backup_size = get_backup_size(service)
  logging.debug("Backup size: {0}".format(backup_size))

  if backup_size > available_space * \
    backup_recovery_constants.PADDING_PERCENTAGE:
    logging.warning("Not enough space for a backup.")
    return False
  return True

def get_available_disk_space():
  """ Returns the amount of available disk space under /opt/appscale.

  Returns:
    An int, the available disk space in bytes.
  """
  stat_struct = os.statvfs(os.path.dirname(BACKUP_DIR_LOCATION))
  return stat_struct[statvfs.F_BAVAIL] * stat_struct[statvfs.F_BSIZE]

def get_backup_size(service):
  """ Sums up the size of the snapshot files that consist the backup for the
  given service.

  Args:
    service: A str, the service for which we'll calculate the backup size.
  Returns:
    An int, the total size of the files consisting the backup in bytes.
  """
  backup_files = get_snapshot_paths(service)
  total_size = sum(getsize(file) for file in backup_files)
  return total_size

def get_snapshot_paths(service):
  """ Returns a list of file names holding critical data for the given service.

  Args:
    service: A str, the service for which we're getting the data files.
    Currently there is support for Cassandra and Zookeeper.
  Returns:
    A list of full paths.
  """
  if service == 'cassandra':
    look_for = 'snapshots'
  else:
    return []

  file_list = []
  data_dir = "{0}{1}".format(APPSCALE_DATA_DIR, service)
  for full_path, _, file in os.walk(data_dir):
    if look_for in full_path:
      file_list.append(full_path)
  logging.debug("List of data paths for '{0}': {1}".format(
    service, file_list))
  return file_list

def move_secondary_backup(base_path):
  """ Moves the secondary backup back in place, if it exists, upon an un
  successful backup attempt.

  Args:
    base_path: A str, the final full path of the backup file after this move.
  """
  source = "{0}{1}".format(base_path, BACKUP_ROLLBACK_SUFFIX)
  target = base_path
  if not rename(source, target):
    logging.warning("No secondary backup to restore. Skipping...")

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

def remove_dir(path):
  """ Deletes the given directory from the filesystem.

  Args:
    path: A str, the path of the directory to delete.
  Returns:
    True on success, False otherwise.
  """
  try:
    os.rmdir(path)
  except OSError:
    logging.error("OSError while deleting '{0}'".
      format(path))
    return False
  return True

def tar_backup_files(file_paths, target):
  """ Tars all snapshot files for a given snapshot name.

  Args:
    file_paths: A list of files to tar up.
    target: A str, the full path to the tar file to be created.
  Returns:
    The path to the tar file, None otherwise.
  """
  backup_file_location = target

  # Rename previous backup, if it exists.
  if not rename(backup_file_location, "{0}{1}".
      format(backup_file_location, BACKUP_ROLLBACK_SUFFIX)):
    logging.warning("'{0}' not found. Skipping file rename...".
      format(backup_file_location))

  # Tar up the backup files.
  tar = tarfile.open(backup_file_location, "w:gz")
  for name in file_paths:
    tar.add(name)
  tar.close()

  return backup_file_location

def untar_backup_files(source):
  """ Restores a previous backup into the Cassandra directory structure
  from a tar ball.

  Args:
    source: A str, the path to the backup tar.
  Raises:
    BRException: On untar issues.
  """
  logging.info("Untarring backup file '{0}'...".format(source))
  try:
    tar = tarfile.open(source, "r:gz")
    tar.extractall(path="/")
    tar.close()
  except tarfile.TarError, tar_error:
    logging.exception(tar_error)
    raise backup_exceptions.BRException(
      "Exception while untarring backup file '{0}'.".format(source))
  logging.info("Done untarring '{0}'.".format(source))
