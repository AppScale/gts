""" Cassandra data backup. """

import logging
import os
import subprocess
import sys
from subprocess import CalledProcessError

import backup_exceptions
import backup_recovery_helper
import gcs_helper

from backup_recovery_constants import CASSANDRA_BACKUP_FILE_LOCATION
from backup_recovery_constants import CASSANDRA_DATA_SUBDIRS
from backup_recovery_constants import StorageTypes

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import dbconstants

from cassandra import start_cassandra
from cassandra import shut_down_cassandra
from cassandra.cassandra_interface import NODE_TOOL
from cassandra.cassandra_interface import KEYSPACE

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib"))
from constants import APPSCALE_DATA_DIR

logging.getLogger().setLevel(logging.INFO)

def clear_old_snapshots():
  """ Remove any old snapshots to minimize disk space usage locally. """
  logging.info('Removing old Cassandra snapshots...')
  try:
    subprocess.check_call([NODE_TOOL, 'clearsnapshot'])
  except CalledProcessError as error:
    logging.error('Error while deleting old Cassandra snapshots. Error: {0}'.\
      format(str(error)))

def create_snapshot(snapshot_name=''):
  """ Perform local Cassandra backup by taking a new snapshot.

  Args:
    snapshot_name: A str, optional. A fixed name for the snapshot to create.
  Returns:
    True on success, False otherwise.
  """
  logging.info('Creating new Cassandra snapshots...')
  try:
    subprocess.check_call([NODE_TOOL, 'snapshot'])
  except CalledProcessError as error:
    logging.error('Error while creating new Cassandra snapshots. Error: {0}'.\
      format(str(error)))
    return False
  return True

def refresh_data():
  """ Performs a refresh of the data in Cassandra. """
  for column_family in dbconstants.INITIAL_TABLES:
    try:
      subprocess.check_call([NODE_TOOL, 'refresh', KEYSPACE, column_family])
    except CalledProcessError as error:
      logging.error('Error while refreshing Cassandra data. Error: {0}'.\
        format(error))

def remove_old_data():
  """ Removes previous node data from the Cassandra store. """
  for directory in CASSANDRA_DATA_SUBDIRS:
    data_dir = "{0}{1}/{2}".format(APPSCALE_DATA_DIR, "cassandra",
      directory)
    logging.warning("Removing data from {0}".format(data_dir))
    try:
      subprocess.Popen('find /opt/appscale/cassandra -name "*" | '
        'grep ".db\|.txt\|.log" | grep -v snapshot | xargs rm', shell=True)
      logging.info("Done removing data!")
    except CalledProcessError as error:
      logging.error("Error while removing old data from db. Overwriting... "
        "Error: {0}".format(str(error)))

def restore_snapshots():
  """ Restore snapshot into correct directories.

  Returns:
    True on success, False otherwise.
  """
  logging.info("Restoring Cassandra snapshots.")

  for directory in CASSANDRA_DATA_SUBDIRS:
    data_dir = "{0}{1}/{2}/".format(APPSCALE_DATA_DIR, "cassandra",
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
        if not backup_recovery_helper.rename(full_path, new_full_path):
          logging.error("Error while moving Cassandra snapshot in place. "
            "Aborting restore...")
          return False

  logging.info("Done restoring Cassandra snapshots.")
  return True

def shutdown_datastore():
  """ Top level function for bringing down Cassandra.

  Returns:
    True on success, False otherwise.
  """
  logging.info("Shutting down Cassandra.")
  if not shut_down_cassandra.run():
    return False
  return True

def backup_data(storage, path=''):
  """ Backup Cassandra snapshot data directories/files.

  Args:
    storage: A str, the storage that is used for storing the backup.
    path: A str, the full backup filename path to use for cloud backup.
  Returns:
    The path to the backup file on success, None otherwise.
  """
  if storage not in StorageTypes().get_storage_types():
    logging.error("Storage '{0}' not supported.")
    return None

  logging.info("Starting new db backup.")
  clear_old_snapshots()

  if not create_snapshot():
    logging.error("Failed to create Cassandra snapshots. Aborting backup...")
    return None

  files = backup_recovery_helper.get_snapshot_paths('cassandra')
  if not files:
    logging.error("No Cassandra files were found to tar up. Aborting backup...")
    return None

  if not backup_recovery_helper.enough_disk_space('cassandra'):
    logging.error("There's not enough available space to create another db"
      "backup. Aborting...")
    return None

  tar_file = backup_recovery_helper.tar_backup_files(files,
    CASSANDRA_BACKUP_FILE_LOCATION)
  if not tar_file:
    logging.error('Error while tarring up snapshot files. Aborting backup...')
    clear_old_snapshots()
    backup_recovery_helper.delete_local_backup_file(tar_file)
    backup_recovery_helper.move_secondary_backup(tar_file)
    return None

  if storage == StorageTypes.LOCAL_FS:
    logging.info("Done with local db backup!")
    clear_old_snapshots()
    backup_recovery_helper.\
      delete_secondary_backup(CASSANDRA_BACKUP_FILE_LOCATION)
    return tar_file
  elif storage == StorageTypes.GCS:
    return_value = path
    # Upload to GCS.
    if not gcs_helper.upload_to_bucket(path, tar_file):
      logging.error("Upload to GCS failed. Aborting backup...")
      backup_recovery_helper.move_secondary_backup(tar_file)
      return_value = None
    else:
      logging.info("Done with db backup!")
      backup_recovery_helper.\
        delete_secondary_backup(CASSANDRA_BACKUP_FILE_LOCATION)

    # Remove local backup file(s).
    clear_old_snapshots()
    backup_recovery_helper.delete_local_backup_file(tar_file)
    return return_value

def restore_data(storage, path=''):
  """ Restores the Cassandra backup.

  Args:
    storage: A str, one of the StorageTypes class members.
    path: A str, the name of the backup file to restore from.
  Returns:
    True on success, False otherwise.
  """
  if storage not in StorageTypes().get_storage_types():
    logging.error("Storage '{0}' not supported.")
    return False

  logging.info("Starting new db restore.")

  if storage == StorageTypes.GCS:
    # Download backup file and store locally with a fixed name.
    if not gcs_helper.download_from_bucket(path,
        CASSANDRA_BACKUP_FILE_LOCATION):
      logging.error("Download from GCS failed. Aborting recovery...")
      return False

  # TODO Make sure there's a snapshot to rollback to if restore fails.
  # Not pressing for fresh deployments.
  # create_snapshot('rollback-snapshot')

  if not shut_down_cassandra.run():
    logging.error("Unable to shut down Cassandra. Aborting restore...")
    if storage == StorageTypes.GCS:
      backup_recovery_helper.\
        delete_local_backup_file(CASSANDRA_BACKUP_FILE_LOCATION)
    return False

  remove_old_data()
  try:
    backup_recovery_helper.untar_backup_files(CASSANDRA_BACKUP_FILE_LOCATION)
  except backup_exceptions.BRException as br_exception:
    logging.exception("Error while unpacking backup files. Exception: {0}".
      format(str(br_exception)))
    start_cassandra.run()
    if storage == StorageTypes.GCS:
      backup_recovery_helper.\
        delete_local_backup_file(CASSANDRA_BACKUP_FILE_LOCATION)
    return False
  restore_snapshots()

  # Start Cassandra and repair.
  logging.info("Starting Cassandra.")
  start_cassandra.run()
  refresh_data()

  # Local cleanup.
  clear_old_snapshots()
  if storage == StorageTypes.GCS:
    backup_recovery_helper.\
      delete_local_backup_file(CASSANDRA_BACKUP_FILE_LOCATION)

  logging.info("Done with db restore.")
  return True

if "__main__" == __name__:
  backup_data(storage='', path='')
  # restore_data(storage='', path='')
