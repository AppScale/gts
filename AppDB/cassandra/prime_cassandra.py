#!/usr/bin/env python

import os
import pycassa
import sys
import time

import dbconstants
import helper_functions
import py_cassandra

from cassandra import cassandra_interface

from pycassa import system_manager
sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
import file_io

def create_keyspaces(replication):
  """ 
  Creates keyspace which AppScale uses for storing application 
  and user data

  Args:
    replication: Replication factor for Cassandra
  Raises:
    AppScaleBadArg: When args are bad
  """
  if int(replication) <= 0: 
    raise dbconstants.AppScaleBadArg("Replication must be greater than zero")

  print "Creating Cassandra Key Spaces" 

  # TODO use shared library to get constants
  host = file_io.read('/etc/appscale/my_private_ip')

  sysman = system_manager.SystemManager(host + ":" +\
              str(cassandra_interface.CASS_DEFAULT_PORT))

  try:
    sysman.create_keyspace(cassandra_interface.KEYSPACE, 
                      pycassa.SIMPLE_STRATEGY, 
                      {'replication_factor':str(replication)})

    # This column family is for testing for functional testing
    sysman.create_column_family(cassandra_interface.KEYSPACE, 
                           cassandra_interface.STANDARD_COL_FAM, 
                           comparator_type=system_manager.UTF8_TYPE)

    for table_name in dbconstants.INITIAL_TABLES:
      sysman.create_column_family(cassandra_interface.KEYSPACE, 
                               table_name,
                               comparator_type=system_manager.UTF8_TYPE)
  
    sysman.close()
  # TODO: Figure out the exact exceptions we're trying to catch in the 
  # case where we are doing data persistance
  except Exception, e:
    sysman.close()
    # TODO: Figure out the exact exceptions we're trying to catch in the 
    print "Received an exception of type " + str(e.__class__) +\
          " with message: " + str(e)

  print "CASSANDRA SETUP SUCCESSFUL"
  return True

def prime_cassandra(replication):
  """
  Create required tables for AppScale

  Args:
    replication: Replication factor of data
  Raises:
    AppScaleBadArg if replication factor is not greater than 0
    Cassandra specific exceptions upon failure
  Returns:
    0 on success, 1 on failure. Passed up as process exit value.
  """ 
  if int(replication) <= 0: 
    raise AppScaleBadArg("Replication must be greater than zero")

  db = py_cassandra.DatastoreProxy()
  if len(db.get_schema(dbconstants.USERS_TABLE)) > 1 and \
     len(db.get_schema(dbconstants.APPS_TABLE)) > 1:
    print "TABLES FOR USER AND APPS ALREADY EXIST"
    return 0

  create_keyspaces(int(replication))
  print "Prime Cassandra database"
  try:
    db.create_table(dbconstants.USERS_TABLE, dbconstants.USERS_SCHEMA)
    db.create_table(dbconstants.APPS_TABLE, dbconstants.APPS_SCHEMA)
  # TODO: Figure out the exact exceptions we're trying to catch in the 
  # case where we are doing data persistance
  except Exception, e:
    print "Received an exception of type " + str(e.__class__) +\
          " with message: " + str(e)

  if len(db.get_schema(dbconstants.USERS_TABLE)) > 1 and \
     len(db.get_schema(dbconstants.APPS_TABLE)) > 1:
    print "CREATE TABLE SUCCESS FOR USER AND APPS"
    print "USERS:",db.get_schema(dbconstants.USERS_TABLE)
    print "APPS:",db.get_schema(dbconstants.APPS_TABLE)
    return 0
  else: 
    print str(db.get_schema(dbconstants.USERS_TABLE))
    print str(db.get_schema(dbconstants.APPS_TABLE))
    print "FAILED TO CREATE TABLE FOR USER AND APPS"
    return 1

if __name__ == "__main__":
  sys.exit(prime_cassandra(sys.argv[1]))
