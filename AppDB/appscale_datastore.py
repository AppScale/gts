#!/usr/bin/python
# Author: Navraj Chohan
# Author: Soo Hwan Park
# Author: Chris Bunch
# Author: Gaurav Kumar Mehta
# Author: NOMURA Yoshihide
# See LICENSE file
import imp
import os
import sys
import string
import socket
import threading
import types

import appscale_logger
from dbconstants import *

app_datastore_logger = appscale_logger.getLogger("appscale_datastore")

DB_ERROR = "DB_ERROR:"

ERROR_CODES = [DB_ERROR]

DATASTORE_DIR= "%s/AppDB" % APPSCALE_HOME

class DatastoreFactory:
  @classmethod
  def getDatastore(cls, d_type):
    datastore = None
    d_name= "py_" + d_type
    mod_path = DATASTORE_DIR + "/" + d_type + "/" + d_name + ".py"
    if os.path.exists(mod_path):
      sys.path.append(DATASTORE_DIR + "/" + d_type)
      d_mod = imp.load_source(d_name, mod_path)
      datastore = d_mod.DatastoreProxy(app_datastore_logger)
    else:
      app_datastore_logger.error("Fail to use datastore: %s. Please " + \
                                 "check the datastore type." % d_type)
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
