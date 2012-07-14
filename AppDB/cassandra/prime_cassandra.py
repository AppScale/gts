#!/usr/bin/env python

import sys, time

import py_cassandra
import dbconstants
import pycassa
from pycassa.system_manager import *
import cassandra.cassandra_interface
CASS_PORT = 9160
KEYSPACE = "Keyspace1"
STANDARD_COL_FAM = "Standard1"
# Set this to False to keep old data
DROP_TABLES = True

def create_keyspaces(replication):
  print "Creating Cassandra Key Spaces" 
  f = open(dbconstants.APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
  host = f.read()
  sys = SystemManager(host + ":" + str(CASS_PORT))

  if DROP_TABLES:
    try:
      sys.drop_keyspace(KEYSPACE)
    except pycassa.cassandra.ttypes.InvalidRequestException, e:
      pass

  sys.create_keyspace(KEYSPACE, 
                      pycassa.SIMPLE_STRATEGY, 
                      {'replication_factor':str(replication)})

  # This column family is for testing
  sys.create_column_family(KEYSPACE, STANDARD_COL_FAM, 
                          comparator_type=UTF8_TYPE)

  for ii in dbconstants.INITIAL_TABLES:
    sys.create_column_family(KEYSPACE, ii,
                          comparator_type=UTF8_TYPE)
  
  sys.close()

  print "CASSANDRA SETUP SUCCESSFUL"

def prime_cassandra(replication):
  create_keyspaces(int(replication))
  print "prime cassandra database"
  db = py_cassandra.DatastoreProxy()
  db.create_table(dbconstants.USERS_TABLE, dbconstants.USERS_SCHEMA)
  db.create_table(dbconstants.APPS_TABLE, dbconstants.APPS_SCHEMA)

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
