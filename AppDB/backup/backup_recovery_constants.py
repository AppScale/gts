""" Constants useful for backup_recovery_service operations. """

# Location where we place the tar of the snapshot.
BACKUP_DIR_LOCATION = "/opt/appscale/backups"

# File location of where the latest backup goes.
BACKUP_FILE_LOCATION = "{0}/cassandra_backup.tar.gz".format(BACKUP_DIR_LOCATION)

# A suffix appended to an existing backup tar.
BACKUP_ROLLBACK_SUFFIX = "_last_successful"

# Cassandra directories to remove to get rid of data.
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

class StorageTypes(object):
  """ A class containing the supported types of storage infrastructures
  for backups. """
  GCS = 'gcs'
  LOCAL_FS = ''

  def get_storage_types(self):
    """ Accessor for getting all the supported storage types. """
    return [self.LOCAL_FS, self.GCS]
