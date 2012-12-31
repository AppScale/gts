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
    datastore = None
    d_name= "py_" + d_type
    mod_path = DATASTORE_DIR + "/" + d_type + "/" + d_name + ".py"
    if os.path.exists(mod_path):
      sys.path.append(DATASTORE_DIR + "/" + d_type)
      d_mod = imp.load_source(d_name, mod_path)
      datastore = d_mod.DatastoreProxy()
    else:
      raise Exception("Datastore was not found in %d directory. " + \
                      "Fail to use datastore: %s" %(DATASTORE_DIR, d_type))
    return datastore

  @classmethod
  def valid_datastores(cls):
    # TODO: return only directory name
    dblist = os.listdir(DATASTORE_DIR)
    return dblist

  @classmethod
  def error_codes(cls):
    return ERROR_CODES
