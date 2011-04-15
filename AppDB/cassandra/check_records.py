#!/usr/bin/env python
#
# Soo Hwan Park (suwanny@gmail.com)
#

import py_cassandra
import sys

KEY_REPOSITORY="__keys_" # special key for storing keys information.
TABLE_PREFIX="__table_" # special keys for storing a table information.

print "check cassandra records"

#print sys.argv

db = py_cassandra.AppCassandra('localhost', 9160)
tables = eval(db.get(KEY_REPOSITORY))
debug = False
if(len(sys.argv) > 1 and sys.argv[1] == "debug"):
  debug = True 

print "select tables:"
for table in tables:
  print "  -", table
  keys = eval(db.get(KEY_REPOSITORY + table))
  for key in keys:
    if debug:
      print "    #", key, db.get(TABLE_PREFIX + table + "_" + key)
    else:
      print "    #", key
  print "    "


