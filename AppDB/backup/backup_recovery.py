""" Class for handling serialized backup/recovery requests. """
import logging
import json
import os
import sys
import threading

import backup_exceptions
import cassandra_backup

sys.path.append(os.path.join(os.path.dirname(__file__), "../cassandra/"))
import shut_down_cassandra

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
    elif request_type == "shutdown":
      return self.shutdown_datastore(request)

  def shutdown_datastore(self, request):
    """ Top level function for bringing down cassandra.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A json string to return to the client.
    """
    success = True
    reason = "success"
    try:
      self.__backup_lock.acquire()
      shut_down_cassandra.run()
    except backup_exceptions.BRException, exception:
      logging.error("Unable to shut down datastore ->\n{0}".format(
        exception)) 
      success = False
      reason = str(exception)
    finally:
      self.__backup_lock.release()
    return json.dumps({'success': success, 'reason': reason})
     
  def do_backup(self, request):
    """ Top level function for doing backups.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A json string to return to the client.
    """
    success = True
    reason = "success"
    path = request[self.GCS_PATH_NAME_TAG]
    try:
      logging.info("Acquiring lock for a backup")
      self.__backup_lock.acquire()
      logging.info("Got the lock for a backup")
      cassandra_backup.backup_data(path)
      logging.info("Successful backup!")
    except backup_exceptions.BRException, exception:
      logging.error("Unable to complete backup {0}".format(exception)) 
      success = False
      reason = str(exception)
    finally:
      self.__backup_lock.release()

    return json.dumps({'success': success, 'reason': reason})

  def do_restore(self, request):
    """ Top level function for doing restores.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A json string to return to the client.
    """
    success = True
    reason = "success"
    path = request[self.GCS_PATH_NAME_TAG]
    try:
      logging.info("Acquiring lock for a restore.")
      self.__backup_lock.acquire()
      logging.info("Got the lock for a restore")
      cassandra_backup.restore_data() 
      logging.info("Successful restore")
    except backup_exceptions.BRException, exception:
      logging.error("Unable to complete restore {0}".format(
        exception)) 
      success = False
      reason = str(exception)
    finally:
      self.__backup_lock.release()

    return json.dumps({'success': success, 'reason': reason})

if __name__ == '__main__':
  #TODO
  pass  
