""" Primes the HBase datastore with the required AppScale tables. """
import sys
import os 

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__)))

import dbconstants
import hbase_interface
import py_hbase

def create_table(table_name, columns):
  """ Calls the HBase interface to create a table.

  Args:
    table_name: A str, table to create.
    columns: A list of columns for the table.
  Returns:
    A list of current tables.
  """
  client = py_hbase.DatastoreProxy()
  return client.create_table(table_name, columns)

def create_app_tables():
  """ Creates application tables for AppScale. """
  db_store = hbase_interface.DatastoreProxy()
  db_store.create_table(dbconstants.ASC_PROPERTY_TABLE, 
    dbconstants.PROPERTY_SCHEMA)
  db_store.create_table(dbconstants.DSC_PROPERTY_TABLE, 
    dbconstants.PROPERTY_SCHEMA)
  db_store.create_table(dbconstants.APP_ID_TABLE, 
    dbconstants.APP_ID_SCHEMA)
  db_store.create_table(dbconstants.APP_ENTITY_TABLE, 
    dbconstants.APP_ENTITY_SCHEMA)
  db_store.create_table(dbconstants.APP_KIND_TABLE, 
    dbconstants.APP_KIND_SCHEMA)
  db_store.create_table(dbconstants.JOURNAL_TABLE, 
    dbconstants.JOURNAL_SCHEMA)

def prime_hbase():
  """ Creates tables required for AppScale
  """
  print "prime hbase database"
  create_app_tables()
  create_table(dbconstants.USERS_TABLE, dbconstants.USERS_SCHEMA)
  result = create_table(dbconstants.APPS_TABLE, dbconstants.APPS_SCHEMA)
  if (dbconstants.USERS_TABLE in result) and (dbconstants.APPS_TABLE in result):
    print "CREATE TABLE SUCCESS FOR USER AND APPS:"
    print result
    return 0
  else:
    print "FAILED TO CREATE TABLE FOR USER AND APPS"
    return 1

if __name__ == "__main__":
  sys.exit(prime_hbase())

