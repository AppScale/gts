#Author: Mayuri Karra 
# Drops all tables

import sys
import os 

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  print "APPSCALE_HOME env var not set"
  APPSCALE_HOME = "/root/appscale/"

sys.path.append(APPSCALE_HOME + "/AppDB/python")
import pyodbc
import MySQLdb
import _mysql
import socket
import py_timesten

ROW_KEY = "timesten__row_key__"
USER_TABLE = "USERS__"
APPS_TABLE = "APPS__"
SLAVES_FILE = APPSCALE_HOME + "/.appscale/slaves"

DB_CONN_STR = "dsn=TT_tt70"
#DEBUG_PRINT_SQL=True
DEBUG_PRINT_SQL=False
TT_ERROR = "TT_ERROR : "

def set_db_location():
  global DB_CONN_STR
  file = open(SLAVES_FILE, "r")
  DB_CONN_STR = file.readline()
  file.close()

def drop_all():
  try:
    client = pyodbc.connect(DB_CONN_STR)
    cursor = client.cursor()
    if (py_timesten.__table_exist (USER_TABLE) == 1): 
	cursor.execute("DROP TABLE " + USER_TABLE)
	if DEBUG_PRINT_SQL: print "   DROP TABLE " + USER_TABLE
    	client.commit()
    if (py_timesten.__table_exist (APPS_TABLE) == 1): 
	cursor.execute("DROP TABLE " + APPS_TABLE)
	if DEBUG_PRINT_SQL: print "   DROP TABLE " + APPS_TABLE
    	client.commit()
    
    cursor.execute ("select tblname from sys.tables where tblowner = 'ROOT'")	

    list = []
    for row in cursor:
	list += [row[0]]
 
    for ii in range (0, len(list)):
       if (py_timesten.__table_exist (list[ii]) == 1): 
		cursor.execute("DROP TABLE ROOT." + list[ii])
		if DEBUG_PRINT_SQL: print "   DROP TABLE " + list[ii]
		client.commit()
	
  except pyodbc.Error, e:
    print e.args[0]
    print TT_ERROR + "Unable to drop tables "
    return 0  
  return 1  

# main() 

if drop_all() == 0:
  print "Unable to drop database..."
  exit(1)

