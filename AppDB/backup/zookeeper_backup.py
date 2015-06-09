""" Zookeeper data backup. """

import json
import logging
import os
import sys
import tarfile
import subprocess
from subprocess import CalledProcessError

import backup_exceptions
import gcs_helper
from backup_recovery_constants import StorageTypes

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../zkappscale/"))
import start_zookeeper
import shut_down_zookeeper

# Location where we place the tar of the backup.
BACKUP_DIR_LOCATION = "/opt/appscale/backups"

# File location of where the latest backup goes.
BACKUP_FILE_LOCATION = "{0}/zookeeper_backup.tar.gz".format(BACKUP_DIR_LOCATION)

# Zookeeper data directories.
ZOOKEEPER_DATA_SUBDIRS = ["version-2"]

def get_zookeeper_snapshot_file_names():
  """ Yields all file names which should be tar'ed up.

  Returns:
    A list of files.
  """
  file_list = []
  data_dir = "{0}{1}".format(constants.APPSCALE_DATA_DIR, "zookeeper")
  for full_path, _, _ in os.walk(data_dir):
    if 'opt' in full_path:
      file_list.append(full_path)

  logging.debug("List of snapshot paths: {0}".format(file_list))
  return file_list

def tar_backup_files(file_paths):
  """ Tars all snapshot files for a given snapshot name.

  Args:
    file_paths: A list of files to tar up.
  Returns:
    The path to the tar file, None otherwise.
  """

  # Create backups dir if not there.
  try:
    subprocess.call(["mkdir", "-p", BACKUP_DIR_LOCATION])
  except CalledProcessError as error:
    logging.error("Error while creating dir '{0}'. Error: {1}".
      format(BACKUP_DIR_LOCATION, str(error)))
    return None

  backup_file_location = BACKUP_FILE_LOCATION

  # Delete previous backup.
  try:
    subprocess.call(["rm", "-f", backup_file_location])
  except CalledProcessError as error:
    logging.error("Error while deleting previous backup '{0}'. Error: {1}".
      format(backup_file_location, str(error)))

  tar = tarfile.open(backup_file_location, "w:gz")
  for name in file_paths:
    tar.add(name)
  tar.close()

  return backup_file_location

def backup_data(storage, path=''):
  """ Backup Zookeeper directories/files.

  Args:
    storage: A str, one of the StorageTypes class members.
    path: A str, the name of the backup file to be created.
  Returns:
    The path to the backup file on success, None otherwise.
  """
  logging.info("Starting new zk backup.")

  # TODO: Tar up zookeeper data.
  files = get_zookeeper_snapshot_file_names()
  if not files:
    logging.error("No Zookeeper files were found to tar up. Aborting backup...")
    return None

  tar_file = tar_backup_files(files)
  if not tar_file:
    logging.error('Error while tarring up snapshot files. Aborting backup...')
    remove_local_backup_file(tar_file)
    return None

  if storage == StorageTypes.LOCAL_FS:
    logging.info("Done with local zk backup!")
    return tar_file
  elif storage == StorageTypes.GCS:
    return_value = path
    # Upload to GCS.
    if not gcs_helper.upload_to_bucket(path, tar_file):
      logging.error("Upload to GCS failed. Aborting backup...")
      return_value = None
    else:
      logging.info("Done with zk backup!")

    # Remove local backup file.
    remove_local_backup_file(tar_file)
    return return_value
  else:
    logging.error("Storage '{0}' not supported.")
    remove_local_backup_file()
    return None

def shutdown_zookeeper():
  """ Top level function for bringing down Zookeeper.

  Returns:
    True on success, False otherwise.
  """
  if not shut_down_zookeeper.run():
    return False
  return True

def remove_old_data():
  """ Removes previous node data from the Zookeeper deployment. """
  for directory in ZOOKEEPER_DATA_SUBDIRS:
    data_dir = "{0}{1}/{2}".format(constants.APPSCALE_DATA_DIR, "zookeeper",
      directory)
    logging.warn("Removing data from {0}".format(data_dir))
    try:
      # TODO
      logging.info("Done removing data!")
    except CalledProcessError as error:
      logging.error("Error while removing old data from zk. Overwriting... "
        "Error: {0}".format(str(error)))

def untar_backup_files():
  """ Restores a previous backup into the Cassandra directory structure
  from a tar ball. 

  Raises:
    BRException: On untar issues.
  """
  logging.info("Untarring Cassandra backup files...")
  try:
    tar = tarfile.open(BACKUP_FILE_LOCATION, "r:gz")
    tar.extractall(path="/")
    tar.close()
  except tarfile.TarError, tar_error:
    logging.exception(tar_error)
    raise backup_exceptions.BRException(
      "Exception while untarring Zookeeper backup files.")
  logging.info("Done untarring Zookeeper backup files.")

def restore_snapshots():
  """ Restore snapshot into correct directories.

  Returns:
    True on success, False otherwise.
  """
  logging.info("Restoring zk snapshot.")
  for directory in ZOOKEEPER_DATA_SUBDIRS:
    data_dir = "{0}{1}/{2}/".format(constants.APPSCALE_DATA_DIR, "zookeeper",
      directory)
    logging.debug("Restoring in dir {0}".format(data_dir))
    for path, _, filenames in os.walk(data_dir):
      for filename in filenames:
        logging.debug("Restoring: {0}".format(filename))
        if not filename:
          logging.warn("skipping...")
          continue
        full_path = "{0}/{1}".format(path, filename)
        new_full_path = "{0}/../../{1}".format(path, filename)
        logging.debug("{0} -> {1}".format(full_path, new_full_path))
        # Move the files up into the data directory.
        try:
          subprocess.call(['cp', full_path, new_full_path])
        except CalledProcessError as error:
          logging.error("Error while moving Zookeeper snapshot in place. "
            "Error: {0}".format(str(error)))
          return False
  logging.info("Done restoring zk snapshot!")
  return True

def remove_local_backup_file(local_file=BACKUP_FILE_LOCATION):
  """ Removes the local backup file.

  Args:
    local_file: A str, the path to the backup file to delete.
  """
  try:
    subprocess.call(['rm', '-rf', local_file])
  except CalledProcessError as error:
    logging.error("Error while removing local backup file '{0}'. Error: {1}".\
      format(local_file, str(error)))

def restore_data(storage, path=''):
  """ Restores the Zookeeper snapshot.

  Args:
    storage: A str, one of the StorageTypes class members.
    path: A str, the name of the backup file to restore from.
  """
  if storage == StorageTypes.GCS:
    # Download backup file and store locally with a fixed name.
    if not gcs_helper.download_from_bucket(path, BACKUP_FILE_LOCATION):
      logging.error("Download from GCS failed. Aborting recovery...")
      return False

  # TODO Make sure there's a snapshot to rollback to if restore fails.
  # Not pressing for fresh deployments.

  if not shut_down_zookeeper.run():
    logging.error("Unable to shut down Zookeeper. Aborting restore...")
    return False

  remove_old_data()
  try:
    untar_backup_files()
  except backup_exceptions.BRException as br_exception:
    logging.exception("Exception while restoring zk snapshots. Need to "
      "rollback... Exception: {0}".format(str(br_exception)))
  restore_snapshots()

  # Start Zookeeper.
  start_zookeeper.run()

  # Local cleanup.
  if storage == StorageTypes.GCS:
    remove_local_backup_file()

  logging.info("Done with restore.")
  return True

if "__main__" == __name__:
  logging.getLogger().setLevel(logging.INFO)

  backup_data(storage='', path='')
  # restore_data(storage='', path='')
