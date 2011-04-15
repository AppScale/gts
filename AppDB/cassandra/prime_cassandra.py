#!/usr/bin/env python

import sys, time

import py_cassandra
from dbconstants import *

def prime_cassandra():
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
  sys.exit(prime_cassandra())
