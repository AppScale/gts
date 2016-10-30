""" Constants useful for Backup & Recovery operations. """

# Location where we place the tar of the snapshot.
BACKUP_DIR_LOCATION = "/opt/appscale/backups"

# Location where we place the source code tars.
APP_BACKUP_DIR_LOCATION = "{0}/apps".format(BACKUP_DIR_LOCATION)

# Location where deployed app source code resides in an AppScale deployment.
APP_DIR_LOCATION = "/opt/appscale/apps"

# A suffix appended to an existing backup tar (for rollback purposes).
BACKUP_ROLLBACK_SUFFIX = "_last_successful"

# Cassandra tarred backup file location.
CASSANDRA_BACKUP_FILE_LOCATION = "{0}/cassandra_backup.tar.gz".format(
  BACKUP_DIR_LOCATION)

# Cassandra data directories.
CASSANDRA_DATA_SUBDIRS = ["Keyspace1", "system",
  # TODO Is the rest needed?
  # "commitlog", "saved_caches",
  # "system_traces"
]

# Default port for the backup/recovery web server.
DEFAULT_PORT = 8423

# HTTP Codes.
HTTP_OK = 200

# The percentage of disk fullness that is considered reasonable.
PADDING_PERCENTAGE = 0.9

# Number of times to retry stopping a service.
SERVICE_STOP_RETRIES = 10


class StorageTypes(object):
  """ A class containing the supported types of storage infrastructures
  for backups. """
  GCS = 'gcs'
  LOCAL_FS = ''

  def get_storage_types(self):
    """ Accessor for getting all the supported storage types. """
    return [self.LOCAL_FS, self.GCS]
