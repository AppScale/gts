#!/usr/bin/python
# See LICENSE file

import appscale.datastore
import importlib
import logging
import os
import pkgutil


class DatastoreFactory:

  @classmethod
  def getDatastore(cls, d_type, log_level=logging.INFO):
    """ Returns a reference for the datastore.
   
    Args: 
      d_type: The name of the datastore (ex: cassandra)
      log_level: The logging level to use.
    """
    db_module = importlib.import_module(
      'appscale.datastore.{0}_env.{0}_interface'.format(d_type))
    return db_module.DatastoreProxy(log_level=log_level)

  @classmethod
  def valid_datastores(cls):
    """ Returns a list of directories where the datastore code is
     
    Returns: Directory list 
    """
    datastore_package_dir = os.path.dirname(appscale.datastore.__file__)
    return [pkg.replace('_env', '') for _, pkg, ispkg
            in pkgutil.iter_modules([datastore_package_dir])
            if ispkg and pkg.endswith('_env')]
