""" Custom Backup and Recovery exceptions. """

class BackupValidationException(Exception):
  """ An exception when backup parameters and setup is incorrect. """
  pass

class RestoreValidationException(Exception):
  """ An exception when restore parameters and setup is incorrect. """
  pass

class DeleteValidationException(Exception):
  """ An exception when backup parameters and setup is incorrect. """
  pass
