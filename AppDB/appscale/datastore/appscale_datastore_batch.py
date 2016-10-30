#!/usr/bin/python
# See LICENSE file

import imp
import logging
import os
import sys

from .unpackaged import APPSCALE_LIB_DIR

sys.path.append(APPSCALE_LIB_DIR)
import constants

DATASTORE_DIR= "%s/AppDB" % constants.APPSCALE_HOME

class DatastoreFactory:

  @classmethod
  def getDatastore(cls, d_type, log_level=logging.INFO):
    """ Returns a reference for the datastore. Validates where 
        the <datastore>_interface.py is and adds that path to 
        the system path.
   
    Args: 
      d_type: The name of the datastore (ex: cassandra)
      log_level: The logging level to use.
    """
    database_env_dir = '{}/{}_env'.format(DATASTORE_DIR, d_type)
    sys.path.append(database_env_dir)

    module_name = '{}_interface'.format(d_type)
    handle, path, description = imp.find_module(module_name)

    try:
      db_module = imp.load_module(module_name, handle, path, description)
      datastore = db_module.DatastoreProxy(log_level=log_level)
    finally:
      if handle:
        handle.close()

    return datastore

  @classmethod
  def valid_datastores(cls):
    """ Returns a list of directories where the datastore code is
     
    Returns: Directory list 
    """

    dblist = os.listdir(DATASTORE_DIR)
    return dblist
