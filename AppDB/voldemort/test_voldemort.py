#!/usr/bin/env python
#
# Soo Hwan Park (suwanny@gmail.com)
#

import py_voldemort
import sys

KEY_REPOSITORY="__keys_" # special key for storing keys information.
TABLE_PREFIX="__table_" # special keys for storing a table information.

USER_TABLE = "USERS__"
APPS_TABLE = "APPS__"

USERS = ["email",
         "pw",
         "date_creation",
         "date_change",
         "date_last_login",
         "applications",
         "appdrop_rem_token",
         "appdrop_rem_token_exp",
         "visit_cnt",
         "cookie",
         "cookie_ip",
         "cookie_exp",
         "cksum",
         "enabled"
        ]

APPS = ["name",
        "version",
        "owner",
        "admins_list",
        "host",
        "port",
        "creation_date",
        "last_time_updated_date",
        "yaml_file",
        "cksum",
        "num_entries",
        "tar_ball",
        "enabled"
       ]

USER_VALUES = ["suwanny@gmail.com", "11", "2009", "2009", "2009", 
    "bbs", "xxx", "xxx", "1", "yyy", 
    "0.0.0.0", "2009", "zzz", "yes"]

APPS_VALUES = ["name",  "version","owner","admins_list","host",
    "port","creation_date", "last_time_updated_date", "yaml_file", "cksum", 
    "num_entries", "xxxx", "yes"]

def printCurrentDB(status, debug = False):
  nodeId, version, timestamp, value = db.get(KEY_REPOSITORY)
  tables = eval(value)
  print status
  print "print current records"
  for table in tables:
    print "  -", table
    nodeId, version, timestamp, value = db.get(KEY_REPOSITORY + table)
    keys = eval(value)
    for key in keys:
      if debug:
        nodeId, version, timestamp, value = db.get(TABLE_PREFIX + table + "_" + key)
        print "    #", key, value 
      else:
        print "    #", key
    print "    "

if __name__ == "__main__":
  print "test voldemort interface"
  db = py_voldemort.AppVoldemort('localhost', 9090)
  db.create_table(USER_TABLE, USERS)
  db.create_table(APPS_TABLE, APPS)
  
  debug = False
  if(len(sys.argv) > 1 and sys.argv[1] == "debug"):
    debug = True

  printCurrentDB("after making tables")

  db.put_entity(USER_TABLE, "1", USERS, USER_VALUES)  
  db.put_entity(USER_TABLE, "2", USERS, USER_VALUES)  
  db.put_entity(APPS_TABLE, "1", APPS, APPS_VALUES)  
  db.put_entity(APPS_TABLE, "2", APPS, APPS_VALUES)  

  printCurrentDB("after put entity", False)

  print "get_entity1", db.get_entity(USER_TABLE, "1", USERS)
  print "get_entity2", db.get_entity(APPS_TABLE, "1", APPS)

  print "get_table1", db.get_table(USER_TABLE, USERS)
  print "get_table2", db.get_table(APPS_TABLE, APPS)

  print "get_schema1", db.get_schema(USER_TABLE)
  print "get_schema2", db.get_schema(APPS_TABLE)

  db.delete_row(USER_TABLE, "2")
  db.delete_row(APPS_TABLE, "2")
  printCurrentDB("after delete row 2", False)

  db.delete_table(USER_TABLE) 
  printCurrentDB("after delete user table", False)
  db.delete_table(APPS_TABLE) 
  printCurrentDB("after delete apps table", False)
  
   
  

