#!/usr/bin/python
# See LICENSE file

import imp
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import constants

DATASTORE_DIR= "%s/AppDB" % constants.APPSCALE_HOME

class DatastoreFactory:

  @classmethod
  def getDatastore(cls, d_type):
    """ Returns a reference for the datastore. Validates where 
        the <datastore>_interface.py is and adds that path to 
        the system path.
   
    Args: 
      d_type: The name of the datastore (ex: cassandra)
    """
    database_env_dir = '{}/{}_env'.format(DATASTORE_DIR, d_type)
    sys.path.append(database_env_dir)

    module_name = '{}_interface'.format(d_type)
    handle, path, description = imp.find_module(module_name)

    try:
      db_module = imp.load_module(module_name, handle, path, description)
      datastore = db_module.DatastoreProxy()
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
