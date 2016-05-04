#!/usr/bin/python
# See LICENSE file

import imp
import os
import sys
from dbconstants import *

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import constants 

DB_ERROR = "DB_ERROR:"

ERROR_CODES = [DB_ERROR]

DATASTORE_DIR= "%s/AppDB" % constants.APPSCALE_HOME

class DatastoreFactory:
  @classmethod
  def getDatastore(cls, d_type):
    database_env_dir = '{}/{}'.format(DATASTORE_DIR, d_type)
    sys.path.append(database_env_dir)

    module_name = 'py_{}'.format(d_type)
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
    # TODO: return only directory name
    dblist = os.listdir(DATASTORE_DIR)
    return dblist

  @classmethod
  def error_codes(cls):
    return ERROR_CODES
