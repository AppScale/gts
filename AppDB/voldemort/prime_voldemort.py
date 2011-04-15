#!/usr/bin/env python

import sys, time

sys.path.append("/root/appscale/AppDB")

import py_voldemort
from dbconstants import *

def prime_voldemort():
  print "prime voldemort database"
  db = py_voldemort.DatastoreProxy()
  print "Create users table:", str(db.create_table(USERS_TABLE, USERS_SCHEMA))
  print "Create apps table:", str(db.create_table(APPS_TABLE, APPS_SCHEMA))

  users_schema = db.get_schema(USERS_TABLE)
  apps_schema = db.get_schema(APPS_TABLE)
  if len(users_schema) > 1 and len(apps_schema) > 1:
    print "CREATE TABLE SUCCESS FOR USER AND APPS"
    print users_schema
    print apps_schema
    return 0
  else: 
    print "FAILED TO CREATE TABLE FOR USER AND APPS"
    return 1

if __name__ == "__main__":
  sys.exit(prime_voldemort())
