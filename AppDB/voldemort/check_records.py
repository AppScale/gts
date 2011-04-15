#!/usr/bin/env python
#
# Soo Hwan Park (suwanny@gmail.com)
#

import py_voldemort
import sys

KEY_REPOSITORY="__keys_" # special key for storing keys information.
TABLE_PREFIX="__table_" # special keys for storing a table information.

print "check voldemort records"

#print sys.argv

db = py_voldemort.AppVoldemort('localhost', 9090)
nodeId, version, timestamp, value = db.get(KEY_REPOSITORY)
tables = eval(value)
debug = False
if(len(sys.argv) > 1 and sys.argv[1] == "debug"):
  debug = True 

print "select tables:"
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


