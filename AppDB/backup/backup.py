"""Script for Cassandra data backup."""
# This script is modified from https://cloud.google.com/developers/
# articles/google-cloud-storage-data-backup-for-cassandra-disaster-recovery/
# See it's license. 

from datetime import datetime
from socket import gethostbyname
from socket import gethostname
from subprocess import call
from yaml import safe_load  # Requires the PyYaml module.

hostname = gethostbyname(gethostname())  # Identify the host for backup.
gs_host_path = '%sdrdata/cassandra/%s/' % (COMPANY_ROOT, hostname)
time = str(datetime.now()).replace(' ', '_')  # Identify a particular backup.
gs_backup_path = gs_host_path + time + '/'  # New path each time script is run.

# Local path to where we will save the backup log file for this host.
PATH_TO_LOGS = '/opt/appscale/backup/dr_logs/'
call(['mkdir', '-p', PATH_TO_LOGS])  # -p creates directory if it doesn't exist
BACKUP_LOG = PATH_TO_LOGS + 'backup.log'

# Read the yaml file to capture location of many important directories.
PATH_TO_YAML = '/etc/cassandra/cassandra.yaml'  # Use path to your cassandra.yaml file if different
raw_yaml = open(PATH_TO_YAML)
cass_yaml = safe_load(raw_yaml)

# Helper functions.
def SingleFileBackup(file_path):
  """Backup a single file to root of current Google Cloud Storage backup path.

  Args:
    file_path: Local path to the file we are backing up.
  """
  call(['gsutil', 'cp', file_path, gs_backup_path])


def RecursiveDirectoryBackup(directory_path):
  """Backup a directory and all of its contents to Google Cloud Storage.

  Args:
    directory_path: Local path to directory we are backing up.
  """
  call(['gsutil', '-m', 'cp', '-R', directory_path, gs_backup_path])


# Actual backup procedures begin here.
# Remove any old snapshots to minimize diskspace usage both locally and in Google Cloud Storage.
call(['nodetool', 'clearsnapshot'])

# Backup the cassandra.yaml file.
SingleFileBackup(PATH_TO_YAML)

# Backup the log4j properties file.
PATH_TO_LOG4J = '/etc/cassandra/log4j-server.properties'  # Use path to your file if different
SingleFileBackup(PATH_TO_LOG4J)

# Backup every Cassandra data directory recursively.
dirs = cass_yaml['data_file_directories']  # creates an array of directory paths
for data_directory in dirs:
  RecursiveDirectoryBackup(data_directory)

# Backup Cassandra commit logs.
RecursiveDirectoryBackup(cass_yaml['commitlog_directory'])

# Backup Cassandra saved caches.
RecursiveDirectoryBackup(cass_yaml['saved_caches_directory'])

# Backup Cassandra system logs.
SYS_LOG = '/path/to/log'  # from log4j-server.properties file
RecursiveDirectoryBackup(SYS_LOG)

# Save details about this backup to local backup log.
with open(BACKUP_LOG, 'a') as f:
  f.write(gs_backup_path + '\n')

# Copy local log to Google Cloud Storage host path. This overwrites previous log for this host.
call(['gsutil', 'cp', BACKUP_LOG, gs_host_path])

# Perform local Cassandra backup by taking a new snapshot.
call(['nodetool', 'snapshot'])
