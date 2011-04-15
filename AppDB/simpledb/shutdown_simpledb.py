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

print "deleting simpledb domain"
sdb = boto.connect_sdb(ACCESS_KEY, SECRET_KEY)
sdb.delete_domain(APPSCALE_DOMAIN) 

