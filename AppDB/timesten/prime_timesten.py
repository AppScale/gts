# Author: Mayuri Karra
# Modified: Yoshi
# Creates a USERS__ and APPS__ table for TimesTen

import sys
import os 
import socket
import appscale_datastore
from dbconstants import *

ROW_KEY = "timesten__row_key__"
DB_CONN_STRING = "dsn=TT_tt70"

# main() 

db = appscale_datastore.DatastoreFactory.getDatastore("timesten")

if not db.create_table(USERS_TABLE, USERS_SCHEMA):
  print "Unable to create USER table, exiting..."
  exit(1)

if not db.create_table(APPS_TABLE, APPS_SCHEMA):
  print "Unable to create APPS table, but USERS table was created, exiting..."
  exit(1) 

exit(0)
