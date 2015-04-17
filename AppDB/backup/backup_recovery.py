""" Class for handling serialized backup/recovery requests. """
import logging
import json
import os
import sys
import uuid

import backup_exceptions

class BackupService():
  """ Backup service class. """

  REQUEST_TYPE_TAG = "type"

  def __init__(self):
    """ Constructor function for the backup service. """
    pass

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
    return json.dumps({'success': success})

  def do_restore(self, request):
    """ Top level function for doing restores.

    Args:
      request: A dict, the request sent by the client.
    Returns:
      A json string to return to the client.
    """
    success = True
    return json.dumps({'success': success})
