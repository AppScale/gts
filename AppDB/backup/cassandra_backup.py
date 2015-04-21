""" Cassandra data backup. """
import os
import sys
import tarfile

from subprocess import call
from yaml import safe_load 

sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import constants

# Location of cassandra yaml configuration file.
PATH_TO_YAML = '{0}/AppDB/cassandra/cassandra/conf/cassandra.yaml'.\
  format(constants.APPSCALE_HOME)

# Full path for the nodetool binary.
NODE_TOOL = '{0}/AppDB/cassandra/cassandra/bin/nodetool'.\
  format(constants.APPSCALE_HOME)

# Location where we place the tar of the nameshot.
BACKUP_DIR_LOCATION = "/opt/appscale/backups"

def get_cassandra_config():
  """ Get the cassandra configuration from its YAML file.
  """
  cassy_yaml = open(PATH_TO_YAML)
  return safe_load(cassy_yaml)

def recursive_dir_backup(dir_path, gs_backup_path):
  """Backup a directory and all of its contents to Google Cloud Storage.

  Args:
    dir_path: Path to backup.
    gs_backup_path: The full GCS path to backup to.
  """
  #TODO do not use gsutil
  call(['gsutil', '-m', 'cp', '-R', dir_path, gs_backup_path])

def clear_old_snapshots():
  """ Remove any old snapshots to minimize diskspace usage both locally. """
  call([NODE_TOOL, 'clearsnapshot'])

def create_snapshot(name):
  """ Perform local Cassandra backup by taking a new snapshot. 

  Args:
    name: The name of the snapshot.
  `"""
  call([NODE_TOOL, 'snapshot', '-t',  name])

def get_snapshot_file_names(file_filter):
  """ Yields all file names which should be tar'ed up.

  Args:
    file_filter: The string parameter each file should contain.
  Returns:
    A list of files.
  """
  file_list = []
  data_dir = "{0}{1}".format(constants.APPSCALE_DATA_DIR, "cassandra")
  for _, dirnames, filenames in os.walk(data_dir):
    for file_name in filenames: 
      path = os.path.join("{0}{1}".format(constants.APPSCALE_DATA_DIR, 
        dirnames), file_name)
      if file_filter in path and 'snapshots' in path:
        file_list.append(path)
  return file_list

def tar_snapshot(name):
  """ Tars all snapshot files for a given snapshot name.

  Args:
    name: The name of the snapshot. 
  Returns:
    The tar file location.
  """ 
  pass

def backup_data_dirs(backup_name):
  """ Backup every Cassandra data directory recursively. 

  Args:
    backup_name: A str, the name of the backup.
  """
  files = get_snapshot_file_names(backup_name)
  return files
