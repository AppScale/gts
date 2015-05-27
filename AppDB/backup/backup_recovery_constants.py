""" Constants useful for backup_recovery_service operations. """

# HTTP Codes.
HTTP_OK = 200

class StorageTypes(object):
  """ A class containing the supported types of storage infrastructures
  for backups. """
  GCS = 'gcs'
  LOCAL_FS = ''

  def get_storage_types(self):
    """ Accessor for getting all the supported storage types. """
    return [self.LOCAL_FS, self.GCS]
