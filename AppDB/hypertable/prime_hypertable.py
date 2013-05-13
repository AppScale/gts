#!/usr/bin/python
""" 
  Creates datastore tables required for AppScale.
"""
import py_hypertable
import sys

import dbconstants

def create_app_tables():
  """ Creates required tables for storing application data.

  Tables include entity data, indexes, and transaction journalling. Tables
  are created by using the AppScale hypertable interface.
  """
  datastore = py_hypertable.DatastoreProxy()
  datastore.create_table(dbconstants.ASC_PROPERTY_TABLE, 
    dbconstants.PROPERTY_SCHEMA)
  datastore.create_table(dbconstants.DSC_PROPERTY_TABLE, 
    dbconstants.PROPERTY_SCHEMA)
  datastore.create_table(dbconstants.APP_ID_TABLE, 
    dbconstants.APP_ID_SCHEMA)
  datastore.create_table(dbconstants.APP_ENTITY_TABLE, 
    dbconstants.APP_ENTITY_SCHEMA)
  datastore.create_table(dbconstants.APP_KIND_TABLE, 
    dbconstants.APP_KIND_SCHEMA)
  datastore.create_table(dbconstants.JOURNAL_TABLE, dbconstants.JOURNAL_SCHEMA)

def prime_hypertable():
  """ Primes the hypertable datastore with the tables required by an 
  AppScale deployment.

  Returns:
    The int 0 on success, and the int 1 on failure.
  """
  print "prime hypertable database"
  
  client = py_hypertable.DatastoreProxy()
  print "Creating users table"
  print client.create_table(dbconstants.USERS_TABLE, dbconstants.USERS_SCHEMA)
  print "Creating apps table"
  tables = client.create_table(dbconstants.APPS_TABLE, dbconstants.APPS_SCHEMA)

  create_app_tables() 

  if dbconstants.USERS_TABLE in tables and dbconstants.APPS_TABLE in tables:
    print "CREATE TABLE SUCCESS FOR USER AND APPS"
    return 0
  else:
    print "FAILED TO CREATE TABLE FOR USER AND APPS"
    return 1
  
   
if __name__ == "__main__":
  sys.exit(prime_hypertable())
