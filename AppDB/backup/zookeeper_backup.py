""" Zookeeper data backup. """

import logging
import os
import sys
import tarfile
from subprocess import call

import backup_exceptions

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import constants

# Location where we place the tar of the backup.
BACKUP_DIR_LOCATION = "/opt/appscale/backups"

# File location of where the latest backup goes.
BACKUP_FILE_LOCATION = "{0}/zookeeper_backup.tar.gz".format(BACKUP_DIR_LOCATION)

# Zookeeper data directories.
ZOOKEEPER_DATA_SUBDIRS = ["version-2"]

def get_snapshot_file_names():
  """ Yields all file names which should be tar'ed up.

  Returns:
    A list of files.
  """
  file_list = []
  data_dir = "{0}{1}".format(constants.APPSCALE_DATA_DIR, "zookeeper")
  for full_path, _, _ in os.walk(data_dir):
    if 'opt' in full_path:
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

def backup_data(path='', force_local=False):
  """ Backup Zookeeper directories/files.
  
  Args:
    path: A str, the URL to use for cloud backup.
    force_local: Do not fetch the backup from the cloud.
  """
  logging.info("Starting new zk backup.")
  logging.info("Done with zk backup!")
  return BACKUP_FILE_LOCATION

def remove_old_data():
  """ Removes previous node data from the Zookeeper deployment. """
  for directory in ZOOKEEPER_DATA_SUBDIRS:
    data_dir = "{0}{1}/{2}".format(constants.APPSCALE_DATA_DIR, "zookeeper",
      directory)
    logging.warning("Removing data from {0}".format(data_dir))
    call(["rm", "-rf", data_dir])
  logging.warning("Done removing data!")

def restore_snapshot():
  """ Restore snapshot into correct directories. """
  logging.info("Restoring zk snapshot.")
  for directory in ZOOKEEPER_DATA_SUBDIRS:
    data_dir = "{0}{1}/{2}/".format(constants.APPSCALE_DATA_DIR, "zookeeper",
      directory)
    logging.info("Dealing with data dir {0}".format(data_dir))
    for path, _, filenames in os.walk(data_dir):
      for filename in filenames:
        logging.info("Dealing with filename {0}".format(filename))
        if not filename:
          logging.warn("skipping...")
          continue
        full_path = "{0}/{1}".format(path, filename)
        new_full_path = "{0}/../../{1}".format(path, filename)
        logging.error("Moving {0} -> {1}".format(full_path, new_full_path))
        # Move the files up into the data directory.
        call(['mv', full_path, new_full_path])
  logging.info("Done restoring zk snapshot!")

def restore_previous_backup():
  """ Restores a previous backup into the Zookeeper directory structure
  from a tar ball. 

  Raises:
    BRException: On untar issues.
  """
  logging.info("Restoring zk backup tarball...")
  try:
    tar = tarfile.open(BACKUP_FILE_LOCATION, "r:gz")
    tar.extractall(path="/")
    tar.close()
  except tarfile.TarError, tar_error:
    logging.exception(tar_error)
    raise backup_exceptions.BRException("Exception on zk restore.")
  logging.info("Done restoring zk backup tarball!")

def  remove_local_backup_file():
  """ Removed the local backup file. """
  call(['rm', '-rf', BACKUP_FILE_LOCATION])
 
def restore_data(path='', force_local=False):
  """ Restores the Cassandra snapshot. 

  Args:
    path: The URL to fetch the backup from.
    force_local: Do not fetch the backup from the cloud.
  """
  logging.info("Starting new zk restore.")
  logging.info("Done with backup!")

if "__main__" == __name__:
  backup_data(path='', force_local=True)
  restore_data(path='', force_local=True)
