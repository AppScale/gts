#!/usr/bin/env python

import sys
import time

from cassandra import cassandra_interface
import py_cassandra
import pycassa

import dbconstants

from pycassa.system_manager import *

def create_keyspaces(replication):
  """ Creates keyspace which AppScale uses for storing application 
      and user data
  """

  print "Creating Cassandra Key Spaces" 

  # Set this to False to keep old data
  _DROP_TABLES = True

  f = open(dbconstants.APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
  host = f.read()
  f.close()

  sysman = SystemManager(host + ":" + str(cassandra_interface.CASS_DEFAULT_PORT))

  if _DROP_TABLES:
    try:
      sysman.drop_keyspace(cassandra_interface.KEYSPACE)
    except pycassa.cassandra.ttypes.InvalidRequestException, e:
      pass

  try:
    sysman.create_keyspace(cassandra_interface.KEYSPACE, 
                      pycassa.SIMPLE_STRATEGY, 
                      {'replication_factor':str(replication)})
    # This column family is for testing
    sysman.create_column_family(cassandra_interface.KEYSPACE, 
                           cassandra_interface.STANDARD_COL_FAM, 
                           comparator_type=UTF8_TYPE)

    for table_name in dbconstants.INITIAL_TABLES:
      sysman.create_column_family(cassandra_interface.KEYSPACE, 
                               table_name,
                               comparator_type=UTF8_TYPE)
  
    sysman.close()
  except Exception, e:
    if _DROP_TABLES:
      raise e

  print "CASSANDRA SETUP SUCCESSFUL"

def prime_cassandra(replication):
  create_keyspaces(int(replication))
  print "prime cassandra database"
  try:
    db = py_cassandra.DatastoreProxy()
    db.create_table(dbconstants.USERS_TABLE, dbconstants.USERS_SCHEMA)
    db.create_table(dbconstants.APPS_TABLE, dbconstants.APPS_SCHEMA)
  except Exception, e:
    if _DROP_TABLES:
      raise e

  if len(db.get_schema(dbconstants.USERS_TABLE)) > 1 and \
     len(db.get_schema(dbconstants.APPS_TABLE)) > 1:
    print "CREATE TABLE SUCCESS FOR USER AND APPS"
    print "USERS:",db.get_schema(dbconstants.USERS_TABLE)
    print "APPS:",db.get_schema(dbconstants.APPS_TABLE)
    return 0
  else: 
    print "FAILED TO CREATE TABLE FOR USER AND APPS"
    return 1

if __name__ == "__main__":
  sys.exit(prime_cassandra(sys.argv[1]))
