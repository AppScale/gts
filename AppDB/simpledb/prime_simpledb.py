# Programmer: Chris Bunch
# Creates a USERS__ and APPS__ table

import boto
import sys, time
import os 

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  print "APPSCALE_HOME env var not set"
  exit(1)

ACCESS_KEY = os.environ.get("SIMPLEDB_ACCESS_KEY")
if ACCESS_KEY:
  pass
else:
  print "SIMPLEDB_ACCESS_KEY env var not set"
  exit(1)

SECRET_KEY = os.environ.get("SIMPLEDB_SECRET_KEY")
if SECRET_KEY:
  pass
else:
  print "SIMPLEDB_SECRET_KEY env var not set"
  exit(1)

APPSCALE_DOMAIN = "appscale"

import appscale_datastore
import string
from dbconstants import *

def domain_exists(sdb, name):
  try:
    sdb.get_domain(name, validate=True)
    print "domain exists"
    return True
  except:
    print "domain does not exist"
    return False

def prime_simpledb():
  print "prime simpledb database"
  print "access key is " + ACCESS_KEY
  print "secret key is " + SECRET_KEY

  sdb = boto.connect_sdb(ACCESS_KEY, SECRET_KEY)

  while True:
    if not domain_exists(sdb, APPSCALE_DOMAIN):
      break

    try:
      sdb.delete_domain(APPSCALE_DOMAIN)
      print "trying to delete domain"
    except:
      print "delete - got an exception"

    time.sleep(5)

  while True:
    if domain_exists(sdb, APPSCALE_DOMAIN):
      break

    print "creating domain"
    sdb.create_domain(APPSCALE_DOMAIN)
    time.sleep(5)

  db = appscale_datastore.DatastoreFactory.getDatastore("simpledb")

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
  sys.exit(prime_simpledb())

