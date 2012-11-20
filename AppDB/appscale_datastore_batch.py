#!/usr/bin/python
# Programmer: Navraj Chohan <nlake44@gmail.com>
# See LICENSE file

import imp
import os
import socket
import string
import sys
import threading
import types

import appscale_logger
import dbconstants

app_datastore_logger = appscale_logger.getLogger("appscale_datastore_batch")

DATASTORE_DIR= "%s/AppDB" % dbconstants.APPSCALE_HOME

class DatastoreFactory:

  @classmethod
  def getDatastore(cls, d_type):
    """ Returns a reference for the datastore. Validates where 
        the <datastore>_interface.py is and adds that path to 
        the system path.
   
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
    """ Returns a list of directories where the datastore code is
     
    Returns: Directory list 
    """

    dblist = os.listdir(DATASTORE_DIR)
    return dblist
