#!/usr/bin/env python

import sys, time

import py_cassandra
from dbconstants import *
import pycassa
from pycassa.system_manager import *
CASS_PORT = 9160
def create_keyspaces(replication):
  print "Creating Key Spaces" 
  f = open(APPSCALE_HOME + '/.appscale/my_private_ip', 'r')
  host = f.read()
  sys = SystemManager(host + ":" + str(CASS_PORT))

  try:
    sys.drop_keyspace('Keyspace1')
  except pycassa.cassandra.ttypes.InvalidRequestException, e:
    pass

  sys.create_keyspace('Keyspace1', pycassa.SIMPLE_STRATEGY, {'replication_factor':str(replication)})
  sys.create_column_family('Keyspace1', 'Standard1', #column_type="Standard",
                          comparator_type=UTF8_TYPE)
  sys.create_column_family('Keyspace1', 'Standard2', #column_type="Standard",
                          comparator_type=UTF8_TYPE)
  sys.create_column_family('Keyspace1', 'StandardByTime1', #column_type="Standard",
                          comparator_type=TIME_UUID_TYPE)
  sys.create_column_family('Keyspace1', 'StandardByTime2', #column_type="Standard",
                          comparator_type=TIME_UUID_TYPE)
  #sys.create_column_family('Keyspace1', 'Super1',  column_type="Super",
  #                        comparator_type=UTF8_TYPE)
  #sys.create_column_family('Keyspace1', 'Super2', column_type="Super",
  #                        comparator_type=UTF8_TYPE)
  sys.close()
  print "SUCCESS"

def prime_cassandra(replication):
  create_keyspaces(int(replication))
  print "prime cassandra database"
  db = py_cassandra.DatastoreProxy()
  #print db.get("__keys_") 
  db.create_table(USERS_TABLE, USERS_SCHEMA)
  db.create_table(APPS_TABLE, APPS_SCHEMA)
  if len(db.get_schema(USERS_TABLE)) > 1 and len(db.get_schema(APPS_TABLE)) > 1:
    print "CREATE TABLE SUCCESS FOR USER AND APPS"
    print db.get_schema(USERS_TABLE)
    print db.get_schema(APPS_TABLE)
    return 0
  else: 
    print "FAILED TO CREATE TABLE FOR USER AND APPS"
    return 1

if __name__ == "__main__":
  sys.exit(prime_cassandra(sys.argv[1]))
