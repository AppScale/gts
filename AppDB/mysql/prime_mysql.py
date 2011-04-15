#Author: Navraj Chohan
#Creates a USERS__ and APPS__ table for mysql

import sys
import os 

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  print "APPSCALE_HOME env var not set"
  APPSCALE_HOME = "/root/appscale/"

sys.path.append(APPSCALE_HOME + "/AppDB/mysql")
sys.path.append(APPSCALE_HOME + "/AppDB")

import MySQLdb
import _mysql
import socket
from dbconstants import *

ROW_KEY = "mysql__row_key__"
SLAVES_FILE = APPSCALE_HOME + "/.appscale/slaves"
#DB_LOCATION = socket.gethostbyname(socket.gethostname())
DB_LOCATION = "127.0.0.1"

def is_master():
  if self.get_local_ip() == self.get_master_ip():
    return True
  return False

def set_db_location():
  global DB_LOCATION
  file = open(SLAVES_FILE, "r")
  DB_LOCATION = file.readline()
  file.close()

def create_table(tablename, columns):
  try:
    client = MySQLdb.connect(host=DB_LOCATION, db="appscale")
    cursor = client.cursor()
    columnscopy = []
    for ii in range(0, len(columns)):
      columnscopy += ["x" + columns[ii]]
    command = "CREATE TABLE IF NOT EXISTS " + tablename + "( " + ROW_KEY + " CHAR(80) primary key, " + ' MEDIUMBLOB, '.join(columnscopy) + " MEDIUMBLOB) ENGINE=NDBCLUSTER"
    print command
    cursor.execute(command)
  except MySQLdb.Error, e:
    print e.args[1]
    return 0
  client.close()
  return 1

if create_table("x"+USERS_TABLE, USERS_SCHEMA) == 0:
  print "Unable to create USER table, exiting..."
  exit(1)

if create_table("x"+APPS_TABLE, APPS_SCHEMA) == 0:
  print "Unable to create APPS table, but USERS table was created, exiting..."
  exit(1) 

