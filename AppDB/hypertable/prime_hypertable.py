#!/usr/bin/python
# Creates a USERS__ and APPS__ table

# Author: Navraj Chohan
# Author: Kowshik Prakasam

import string
import sys
import py_hypertable
from dbconstants import *

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  print "APPSCALE_HOME env var not set"
  exit(1)

def prime_hypertable():
  print "prime hypertable database"
  
  client = py_hypertable.DatastoreProxy()
  print "Creating users table"
  print client.create_table(USERS_TABLE,USERS_SCHEMA)
  print "Creating apps table"
  tables = client.create_table(APPS_TABLE,APPS_SCHEMA)
  
  if USERS_TABLE in tables and APPS_TABLE in tables:
    print "CREATE TABLE SUCCESS FOR USER AND APPS"
    return 0
  else:
    print "FAILED TO CREATE TABLE FOR USER AND APPS"
    return 1
   
if __name__ == "__main__":
  sys.exit(prime_hypertable())

