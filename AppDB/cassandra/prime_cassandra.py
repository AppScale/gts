#!/usr/bin/env python

import pycassa
import sys
import time

import dbconstants
import helper_functions
import py_cassandra

from cassandra import cassandra_interface

from pycassa import system_manager

def create_keyspaces(replication):
  """ 
  Creates keyspace which AppScale uses for storing application 
  and user data

  Args:
    replication: Replication factor for Cassandra
  """
  if int(replication) <= 0: 
    raise dbconstants.AppScaleBadArg("Replication must be greater than zero")

  print "Creating Cassandra Key Spaces" 

  # Set this to False to keep old data
  _DROP_TABLES = True

  host = helper_functions.read_file('/etc/appscale/my_private_ip')

  sysman = system_manager.SystemManager(host + ":" +\
              str(cassandra_interface.CASS_DEFAULT_PORT))

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
                           comparator_type=system_manager.UTF8_TYPE)

    for table_name in dbconstants.INITIAL_TABLES:
      sysman.create_column_family(cassandra_interface.KEYSPACE, 
                               table_name,
                               comparator_type=system_manager.UTF8_TYPE)
  
    sysman.close()
  # TODO: Figure out the exact exceptions we're trying to catch in the 
  # case where we are doing data persistance
  except Exception, e:
    print "Received an exception of type " + str(e.__class__) +\
          " with message: " + str(e)
    if _DROP_TABLES:
      raise e

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

  create_keyspaces(int(replication))
  print "Prime Cassandra database"
  try:
    db = py_cassandra.DatastoreProxy()
    db.create_table(dbconstants.USERS_TABLE, dbconstants.USERS_SCHEMA)
    db.create_table(dbconstants.APPS_TABLE, dbconstants.APPS_SCHEMA)
  # TODO: Figure out the exact exceptions we're trying to catch in the 
  # case where we are doing data persistance
  except Exception, e:
    print "Received an exception of type " + str(e.__class__) +\
          " with message: " + str(e)
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
