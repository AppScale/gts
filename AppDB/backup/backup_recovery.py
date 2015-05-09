""" Class for handling serialized backup/recovery requests. """
import logging
import json
import os
import sys
import threading

import backup_exceptions
import cassandra_backup
import zookeeper_backup

sys.path.append(os.path.join(os.path.dirname(__file__), "../cassandra/"))
import shut_down_cassandra

sys.path.append(os.path.join(os.path.dirname(__file__), "../zkappscale/"))
import shut_down_zookeeper

class BackupService():
  """ Backup service class. """

  # The key to use to figure out the type of request sent.
  REQUEST_TYPE_TAG = "type"

  # The key to use to lookup the backup name.
  BACKUP_NAME_TAG = "backup_name"

  # Google Cloud Storage bucket tag name. 
  BUCKET_NAME_TAG = "bucket_name"

  # Google Cloud Storage object tag name.
  GCS_OBJECT_NAME_TAG = "object_name"

  def __init__(self):
    """ Constructor function for the backup service. """
    self.__cassandra_backup_lock = threading.Lock()
    self.__zookeeper_backup_lock = threading.Lock()

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
    """ Handles remote requests with serialized JSON.

    Args:
      request_data: A str, the serialized JSON request.
    Returns:
      A str, serialized JSON.
    """
    try:
      request = json.loads(request_data)
    except (TypeError, ValueError) as error:
      logging.exception(error)
      return self.bad_request("Unable to parse request. Exception: {0}".
        format(error))

    request_type = request[self.REQUEST_TYPE_TAG]
    if request_type == "cassandra_backup":
      return self.do_cassandra_backup(request)
    elif request_type == "cassandra_restore":
      return self.do_cassandra_restore(request)
    elif request_type == "cassandra_shutdown":
      return self.shutdown_datastore()
    elif request_type == "zookeeper_backup":
      return self.do_zookeeper_backup(request)
    elif request_type == "zookeeper_restore":
      return self.do_zookeeper_restore(request)
    elif request_type == "zookeeper_shutdown":
      return self.shutdown_zookeeper()

  def shutdown_datastore(self):
    """ Top level function for bringing down Cassandra.

    Returns:
      A JSON string to return to the client.
    """
    self.__cassandra_backup_lock.acquire(True)
    success = shut_down_cassandra.run()
    self.__cassandra_backup_lock.release()
    if not success:
      return self.bad_request('Monit error')
    return json.dumps({'success': True})
     
  def do_cassandra_backup(self, request):
    """ Top level function for doing Cassandra backups.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A JSON string to return to the client.
    """
    success = True
    reason = "success"
    path = request[self.GCS_OBJECT_NAME_TAG]
    try:
      logging.info("Acquiring lock for db backup.")
      self.__cassandra_backup_lock.acquire(True)
      logging.info("Got the lock for db backup.")
      cassandra_backup.backup_data(path)
      logging.info("Successful db backup!")
    except backup_exceptions.BRException, exception:
      logging.error("Unable to complete db backup: {0}".format(exception))
      success = False
      reason = str(exception)
    finally:
      self.__cassandra_backup_lock.release()

    return json.dumps({'success': success, 'reason': reason})

  def do_cassandra_restore(self, request):
    """ Top level function for doing Cassandra restores.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A JSON string to return to the client.
    """
    success = True
    reason = "success"
    path = request[self.GCS_OBJECT_NAME_TAG]
    try:
      logging.info("Acquiring lock for db restore.")
      self.__cassandra_backup_lock.acquire(True)
      logging.info("Got the lock for db restore.")
      cassandra_backup.restore_data(path)
      logging.info("Successful db restore!")
    except backup_exceptions.BRException, exception:
      logging.error("Unable to complete db restore: {0}".format(exception))
      success = False
      reason = str(exception)
    finally:
      self.__cassandra_backup_lock.release()

    return json.dumps({'success': success, 'reason': reason})

  def shutdown_zookeeper(self):
    """ Top level function for bringing down Zookeeper.

    Returns:
      A JSON string to return to the client.
    """
    self.__zookeeper_backup_lock.acquire(True)
    success = shut_down_zookeeper.run()
    self.__zookeeper_backup_lock.release()
    if not success:
      return self.bad_request('Monit error')
    return json.dumps({'success': True})

  def do_zookeeper_backup(self, request):
    """ Top level function for doing Zookeeper backups.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A JSON string to return to the client.
    """
    success = True
    reason = "success"
    path = request[self.GCS_OBJECT_NAME_TAG]
    try:
      logging.info("Acquiring lock for zk backup.")
      self.__zookeeper_backup_lock.acquire(True)
      logging.info("Got the lock for zk backup.")
      zookeeper_backup.backup_data(path)
      logging.info("Successful zk backup!")
    except backup_exceptions.BRException, exception:
      logging.error("Unable to complete zk backup: {0}".format(exception))
      success = False
      reason = str(exception)
    finally:
      self.__zookeeper_backup_lock.release()
      logging.info("Released lock for zk backup.")

    return json.dumps({'success': success, 'reason': reason})

  def do_zookeeper_restore(self, request):
    """ Top level function for doing Zookeeper restores.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A JSON string to return to the client.
    """
    success = True
    reason = "success"
    path = request[self.GCS_OBJECT_NAME_TAG]
    try:
      logging.info("Acquiring lock for zk restore.")
      self.__zookeeper_backup_lock.acquire(True)
      logging.info("Got the lock for zk restore.")
      zookeeper_backup.restore_data(path)
      logging.info("Successful zk restore!")
    except backup_exceptions.BRException, exception:
      logging.error("Unable to complete zk restore: {0}".format(exception))
      success = False
      reason = str(exception)
    finally:
      self.__zookeeper_backup_lock.release()
      logging.info("Released lock for zk restore.")

    return json.dumps({'success': success, 'reason': reason})
