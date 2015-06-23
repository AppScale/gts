""" Constants useful for Backup & Recovery operations. """

# Location where we place the tar of the snapshot.
BACKUP_DIR_LOCATION = "/opt/appscale/backups"

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

# Temporary Zookeeper backup file location.
TMP_ZOOKEEPER_BACKUP = "{0}/zookeeper_backup".format(
  BACKUP_DIR_LOCATION)

# Zookeeper paths that are not considered while taking a backup.
ZK_IGNORE_PATHS = ['/appcontroller', '/deployment_id', '/zookeeper']

# Zookeeper top level path.
ZK_TOP_LEVEL = "/"

# Zookeeper tarred backup file location.
ZOOKEEPER_BACKUP_FILE_LOCATION = "{0}/zookeeper_backup.tar.gz".format(
  BACKUP_DIR_LOCATION)

# Zookeeper data directories.
ZOOKEEPER_DATA_SUBDIRS = ["version-2"]

class StorageTypes(object):
  """ A class containing the supported types of storage infrastructures
  for backups. """
  GCS = 'gcs'
  LOCAL_FS = ''

  def get_storage_types(self):
    """ Accessor for getting all the supported storage types. """
    return [self.LOCAL_FS, self.GCS]
