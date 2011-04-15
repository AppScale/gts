#!/usr/bin/env python
# 
# delete all application record for testing.
# 
# Author: Soo Hwan Park (suwanny@gmail.com)
#

import sys, os

APPSCALE_HOME = os.environ.get("APPSCALE_HOME")
if APPSCALE_HOME:
  pass
else:
  APPSCALE_HOME = "/etc/appscale"
  os.environ["APPSCALE_HOME"] =  APPSCALE_HOME
  print "APPSCALE_HOME env var not set. Setting to " + APPSCALE_HOME

sys.path.append("/usr/lib/python2.6/site-packages")
sys.path.append("/etc/appscale/AppDB")
sys.path.append("/etc/appscale/AppDB/hypertable/src/hypertable-0.9.2.5-alpha/src/py/ThriftClient/gen-py")

from appscale_datastore import Datastore

USER_ID="a@a.a"
entityDict = {"guestbook":"Greeting", }
DEBUG=False

def main(argv):
  DB_TYPE="hbase"
  if len(argv) < 2:
    print "usage: ./delete_app_recode.py db_type table_name"
  else:
    DB_TYPE = argv[1]
  
  db = Datastore(DB_TYPE)

  app_schema = db.get_schema("APPS__")[1:]
  user_schema = db.get_schema("USERS__")[1:]
  #print "APPS", app_schema
  #print "USER", user_schema
  
  app = db.get_entity("USERS__", USER_ID, ['applications'])[1]
  if DEBUG: print "application:", app
  
  #app_table = app + "___" + entityDict[app]
  #if DEBUG: print "app table:", app_table 

  version, classes, count = db.get_entity("APPS__", app, ['version', 'classes', 'num_entries'])[1:]
  version = int(version)
  count = int(count)
  print "version:", version, ", classes:", classes, ", num_entries:", count

  if DEBUG: print "delete all rows"

  for i in range(version + 1):
    app_table = app + "___" + classes + "___" + str(i)
    print "table name:", app_table 
    for i in range(count + 1): 
      db.delete_row(app_table, str(i)) 
      if DEBUG: print "delete table: %s, key: %s" % (app_table, str(i))
  print "delete_all_table is completed"
  
  #for i in range(count + 1):
  #  db.delete_row(app_table, str(i))
  #print "deleted entrites:", count

if __name__ == "__main__":
  try:
    main(sys.argv)
  except:
    raise

