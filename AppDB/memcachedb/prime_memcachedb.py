# Programmer: Chris Bunch
# Creates a USERS__ and APPS__ table

import sys, time
import os 

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  print "APPSCALE_HOME env var not set"
  exit(1)

import appscale_datastore
import string
from dbconstants import *

def prime_memcachedb():
  print "prime memcachedb database"
  db = appscale_datastore.DatastoreFactory.getDatastore("memcachedb")

  db.create_table(USERS_TABLE, USERS_SCHEMA)
  db.create_table(APPS_TABLE, APPS_SCHEMA)

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
  sys.exit(prime_memcachedb())

