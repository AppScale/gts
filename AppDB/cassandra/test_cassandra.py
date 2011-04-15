#!/usr/bin/env python
#
# Soo Hwan Park (suwanny@gmail.com)
#

import py_cassandra
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
  tables = eval(db.get(KEY_REPOSITORY))
  print status
  print "print current records"
  for table in tables:
    print "  -", table
    keys = eval(db.get(KEY_REPOSITORY + table))
    for key in keys:
      if debug:
        print "    #", key, db.get(TABLE_PREFIX + table + "_" + key)
      else:
        print "    #", key
    print "    "

if __name__ == "__main__":
  print "test cassandra interface"

  db = py_cassandra.DatastoreProxy()
  
  debug = True

  printCurrentDB("after making tables", debug)
