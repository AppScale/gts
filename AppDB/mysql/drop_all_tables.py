#Author: Navraj Chohan
# Drops all tables

import sys
import os 

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  print "APPSCALE_HOME env var not set"
  APPSCALE_HOME = "/root/appscale/"

sys.path.append(APPSCALE_HOME + "/AppDB/mysql")
import MySQLdb
import _mysql
import socket
ROW_KEY = "mysql__row_key__"
USER_TABLE = "USERS__"
APPS_TABLE = "APPS__"
SLAVES_FILE = APPSCALE_HOME + "/.appscale/slaves"
#DB_LOCATION = socket.gethostbyname(socket.gethostname())
DB_LOCATION = "127.0.0.1"
DATABASE = "appscale"
def set_db_location():
  global DB_LOCATION
  file = open(SLAVES_FILE, "r")
  DB_LOCATION = file.readline()
  file.close()

def drop_all():
  try:
    client = MySQLdb.connect(DB_LOCATION)
    cursor = client.cursor()
    cursor.execute("DROP DATABASE " + DATABASE)
    cursor.execute("CREATE DATABASE " + DATABASE) 
    cursor.close()
    client.commit()
    client.close()
  except MySQLdb.Error, e:
    print e.args[1]
    return 0  
  return 1  

# main() 

if drop_all() == 0:
  print "Unable to drop database..."
  exit(1)

