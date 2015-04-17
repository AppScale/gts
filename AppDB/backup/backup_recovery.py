""" Class for handling serialized backup/recovery requests. """
import logging
import os
import sys
import uuid

import backup_exceptions

class BackupService():
  """ Backup service class. """
  def __init__(self):
    """ Constructor function for the backup service. """
    pass

  def unknown_request(self, req_type):
    """ Handles unknown request types.

    Args:
      req_type: The request type.
    Raises:
      NotImplementedError: The unknown type is not implemented.
    """
    raise NotImplementedError(
      "Unprotocol buffer type.known request of operation {0}".format(req_type))

  def remote_request(self, app_data):
    """ Handles remote requests with serialized json.

    Args:
      app_data: A str. Serialized json request.
    Returns:
      A str. Serialized json.
    """
    pass
 
