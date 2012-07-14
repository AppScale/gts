#!/usr/bin/python
# Author: Navraj Chohan
# See LICENSE file

import threading
import sys
import string, cgi
import socket
import os
import types
import imp
import appscale_logger
from dbconstants import *

app_datastore_logger = appscale_logger.getLogger("appscale_datastore")

DATASTORE_DIR= "%s/AppDB" % APPSCALE_HOME

class DatastoreFactory:

  @classmethod
  def getDatastore(cls, d_type):
    """ Returns a reference for the datastore 
   
    Args: 
      d_type: The name of the datastore (ex: cassandra)
    """

    datastore = None
    mod_path = DATASTORE_DIR + "/" + d_type + "/" + d_type + "_interface.py"

    if os.path.exists(mod_path):
      sys.path.append(DATASTORE_DIR + "/" + d_type)
      d_mod = imp.load_source(d_type+"_interface.py", mod_path)
      datastore = d_mod.DatastoreProxy(app_datastore_logger)
    else:
      app_datastore_logger.error("Fail to use datastore: %s. Please \
                                  check the datastore type." % d_type)
      raise Exception("Fail to use datastore: %s" % d_type)

    return datastore

  @classmethod
  def valid_datastores(cls):
    dblist = os.listdir(DATASTORE_DIR)
    return dblist
