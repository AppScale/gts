""" Cassandra data backup. """
import os
import sys
import tarfile
import socket

from subprocess import call
from yaml import safe_load 

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import constants

# Full path for the nodetool binary.
NODE_TOOL = '{0}/AppDB/cassandra/cassandra/bin/nodetool'.\
  format(constants.APPSCALE_HOME)

# Location where we place the tar of the nameshot.
BACKUP_DIR_LOCATION = "/opt/appscale/backups"

# File location of where the latest backup goes.
BACKUP_FILE_LOCATION = "{0}/backup.tar.gz".format(BACKUP_DIR_LOCATION)

def clear_old_snapshots():
  """ Remove any old snapshots to minimize diskspace usage both locally. """
  call([NODE_TOOL, 'clearsnapshot'])

def create_snapshot(name):
  """ Perform local Cassandra backup by taking a new snapshot. 

  Args:
    name: The name of the snapshot.
  `"""
  call([NODE_TOOL, 'snapshot'])

def get_snapshot_file_names():
  """ Yields all file names which should be tar'ed up.

  Returns:
    A list of files.
  """
  file_list = []
  data_dir = "{0}{1}".format(constants.APPSCALE_DATA_DIR, "cassandra")
  for _, dirnames, filenames in os.walk(data_dir):
    for file_name in filenames: 
      path = os.path.join("{0}{1}".format(constants.APPSCALE_DATA_DIR, 
        dirnames), file_name)
      if 'snapshots' in path:
        file_list.append(path)
  return file_list

def tar_snapshot(file_paths):
  """ Tars all snapshot files for a given snapshot name.

  Args:
    file_paths: A list of files to tar up.
  """ 
  call(["rm", "-f", BACKUP_FILE_LOCATION])
  tar = tarfile.open(BACKUP_FILE_LOCATION, "w")
  for name in file_paths:
    tar.add(name)
  tar.close()

def get_backup_path(bucket_name):
  """ Returns the path to use when uploading to GCS.

  Args:
    bucket_name: A str, the bucket name.

  Returns:
    A str, the path to use when storing to GCS.
  """
  hostname = socket.gethostname()
  return "{0}/{1}/cassandra/".format(bucket_name, hostname)
 
def backup_data(backup_name):
  """ Backup Cassandra snapshot data directories/files.

  Args:
    backup_name: A str, the name of the backup.
  """
  clear_old_snapshots()
  create_snapshot()
  files = get_snapshot_file_names(backup_name)
  tar_snapshots(files) 
  return BACKUP_FILE_LOCATION
