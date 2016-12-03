#!/usr/bin/python
# See LICENSE file

import appscale.datastore
import importlib
import os
import pkgutil

DB_ERROR = "DB_ERROR:"

ERROR_CODES = [DB_ERROR]


class DatastoreFactory:
  @classmethod
  def getDatastore(cls, d_type):
    db_module = importlib.import_module(
      'appscale.datastore.{0}_env.py_{0}'.format(d_type))
    return db_module.DatastoreProxy()

  @classmethod
  def valid_datastores(cls):
    datastore_package_dir = os.path.dirname(appscale.datastore.__file__)
    return [pkg.replace('_env', '') for _, pkg, ispkg
            in pkgutil.iter_modules([datastore_package_dir])
            if ispkg and pkg.endswith('_env')]

  @classmethod
  def error_codes(cls):
    return ERROR_CODES
