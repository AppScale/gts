#!/usr/bin/env python
#
# Yoshihide Nomura (nomura@pobox.com)
# Original: Soo Hwan Park (suwanny@gmail.com)
#

import py_scalaris
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
  value = db.get(KEY_REPOSITORY)
  print value
  tables = eval(value)
  print status
  print "print current records"
  for table in tables:
    print "  -", table
    value = db.get(KEY_REPOSITORY + table)
    keys = eval(value)
    for key in keys:
      if debug:
        value = db.get(TABLE_PREFIX + table + "_" + key)
        print "    #", key, value 
      else:
        print "    #", key
    print "    "

if __name__ == "__main__":
  print "test scalaris interface"
  db = py_scalaris.AppScalaris('localhost', 8008)
  db.create_table(USER_TABLE, USERS)
  db.create_table(APPS_TABLE, APPS)
  
  debug = False
  if(len(sys.argv) > 1 and sys.argv[1] == "debug"):
    debug = True

  printCurrentDB("after making tables", debug)

  db.put_entity(USER_TABLE, "1", USERS, USER_VALUES)  
  db.put_entity(USER_TABLE, "2", USERS, USER_VALUES)  
  db.put_entity(APPS_TABLE, "1", APPS, APPS_VALUES)  
  db.put_entity(APPS_TABLE, "2", APPS, APPS_VALUES)  

  printCurrentDB("after put entity", debug)

  print "get_entity1", db.get_entity(USER_TABLE, "1", USERS)
  print "get_entity2", db.get_entity(APPS_TABLE, "1", APPS)

  print "get_table1", db.get_table(USER_TABLE, USERS)
  print "get_table2", db.get_table(APPS_TABLE, APPS)

  print "get_schema1", db.get_schema(USER_TABLE)
  print "get_schema2", db.get_schema(APPS_TABLE)

  db.delete_row(USER_TABLE, "2")
  db.delete_row(APPS_TABLE, "2")
  printCurrentDB("after delete row 2", debug)

  db.delete_table(USER_TABLE) 
  printCurrentDB("after delete user table", debug)
  db.delete_table(APPS_TABLE) 
  printCurrentDB("after delete apps table", debug)
