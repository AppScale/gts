""" Cassandra data backup. """
import logging
import os
import sys
import tarfile

from subprocess import call

import backup_exceptions

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import constants

sys.path.append(os.path.join(os.path.dirname(__file__), "../cassandra/"))
import start_cassandra

# Full path for the nodetool binary.
NODE_TOOL = '{0}/AppDB/cassandra/cassandra/bin/nodetool'.\
  format(constants.APPSCALE_HOME)

# Location where we place the tar of the nameshot.
BACKUP_DIR_LOCATION = "/opt/appscale/backups"

# File location of where the latest backup goes.
BACKUP_FILE_LOCATION = "{0}/backup.tar.gz".format(BACKUP_DIR_LOCATION)

# Cassandra directories to remove to get rid of data.
CASSANDRA_DATA_SUBDIRS = ["commitlog", "Keyspace1", "saved_caches", "system",
  "system_traces"]

def clear_old_snapshots():
  """ Remove any old snapshots to minimize diskspace usage both locally. """
  call([NODE_TOOL, 'clearsnapshot'])

def create_snapshot():
  """ Perform local Cassandra backup by taking a new snapshot. """ 
  call([NODE_TOOL, 'snapshot'])

def get_snapshot_file_names():
  """ Yields all file names which should be tar'ed up.

  Returns:
    A list of files.
  """
  file_list = []
  data_dir = "{0}{1}".format(constants.APPSCALE_DATA_DIR, "cassandra")
  for full_path, _, _ in os.walk(data_dir):
    if 'snapshots' in full_path:
      file_list.append(full_path)
  return file_list

def tar_snapshot(file_paths):
  """ Tars all snapshot files for a given snapshot name.

  Args:
    file_paths: A list of files to tar up.
  """ 
  call(["mkdir", "-p", BACKUP_DIR_LOCATION])
  call(["rm", "-f", BACKUP_FILE_LOCATION])
  tar = tarfile.open(BACKUP_FILE_LOCATION, "w:gz")
  for name in file_paths:
    tar.add(name)
  tar.close()

def backup_data(path):
  """ Backup Cassandra snapshot data directories/files. 
  
  Args:
    path: A str, the URL to use for cloud backup.
  """
  logging.info("Starting new backup.")
  clear_old_snapshots()
  create_snapshot()
  files = get_snapshot_file_names()
  tar_snapshot(files)
  #cloudstore_snap(path)
  logging.info("Done with backup!")
  return BACKUP_FILE_LOCATION

def remove_old_data():
  """ Removes previous node data from the cassandra deployment. """
  for directory in CASSANDRA_DATA_SUBDIRS:
    data_dir = "{0}{1}/{2}".format(constants.APPSCALE_DATA_DIR, "cassandra",
      directory)
    logging.warning("Removing data from {0}".format(data_dir))
    call(["rm", "-rf", data_dir])
  logging.warning("Done removing data!")

def restore_previous_backup():
  """ Restores a previous backup into the Cassandra directory structure
  from a tar ball. """
  logging.info("Restoring backup tarball...")
  try:
    tar = tarfile.open(BACKUP_FILE_LOCATION, "r:gz")
    tar.extractall(path="/")
    tar.close()
  except tarfile.TarError, tar_error:
    logging.exception(tar_error)
    raise backup_exceptions.BRException("Exception on restore")
  logging.info("Done restoring backup tarball!")
 
def restore_data():
  """ Restores the Cassandra snapshot. """
  remove_old_data()
  # TODO fetch the tar ball from cloud storage.
  restore_previous_backup()
  start_cassandra.run()
