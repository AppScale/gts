""" Class for handling serialized backup/recovery requests. """
import logging
import json
import os
import sys
import threading
import uuid

import backup
import backup_exceptions

class BackupService():
  """ Backup service class. """

  # The key to use to figure out the type of request sent.
  REQUEST_TYPE_TAG = "type"

  # The key to use to lookup the backup name.
  BACKUP_NAME_TAG = "backup_name"

  # Google Cloud Storage bucket tag name. 
  BUCKET_NAME_TAG = "bucket_name"

  # GCS path to store.
  GCS_PATH_NAME_TAG = "path_location"

  def __init__(self):
    """ Constructor function for the backup service. """
    self.__backup_lock = threading.Lock()

  @classmethod
  def bad_request(cls, reason):
    """ Returns the default bad request json string.

    Args:
      reason: The reason the request is bad.
    Returns:
      The default message to return on a bad request.
    """
    return json.dumps({'success': False, 'reason': reason})

  def remote_request(self, request_data):
    """ Handles remote requests with serialized json.

    Args:
      request_data: A str. Serialized json request.
    Returns:
      A str. Serialized json.
    """
    try:
      request = json.loads(request_data)
    except ValueError, exception:
      logging.exception(exception)
      return self.bad_request("Caught exception: {0}".format(exception))
    else:
      logging.error("Invalid json request: {0}".format(request_data))
      return self.bad_request("Bad json formatting")

    request_type = request[self.REQUEST_TYPE_TAG]
    if request_type == "backup":
      return self.do_backup(request)
    elif request_type == "restore":
      return self.do_restore(request)

  def do_backup(self, request):
    """ Top level function for doing backups.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A json string to return to the client.
    """
    success = True
    reason = "success"
    backup_name = request[self.BACKUP_NAME_TAG]
    bucket_name = request[self.BUCKET_NAME_TAG]
    path = request[self.GCS_PATH_NAME_TAG]
    self.__backup = backup.Backup(backup_name, bucket_name, path)
    try:
      logging.info("Acquiring lock for a backup ({0}).".format(backup_name))
      self.__backup_lock.acquire()
      logging.info("Got the lock for a backup ({0}).".format(backup_name))
      self.__backup.run_backup()
      logging.info("Successful backup ({0})!".format(backup_name))
    except backup_exceptions.BackupException, exception:
      logging.error("Unable to complete backup {0} --> {1}".format(
        backup_name, exception)) 
      success = False
      reason = str(exception)
    return json.dumps({'success': success, 'reason': reason})

  def do_restore(self, request):
    """ Top level function for doing restores.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A json string to return to the client.
    """
    success = True
    return json.dumps({'success': success})
