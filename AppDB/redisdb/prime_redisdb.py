import sys, time

sys.path.append("/root/appscale/AppDB")

import appscale_datastore
from dbconstants import *

def prime_redisdb():
  print "prime redis database"
  db = appscale_datastore.DatastoreFactory.getDatastore("redisdb")

  result1 = db.create_table(USERS_TABLE, USERS_SCHEMA)
  result2 = db.create_table(APPS_TABLE, APPS_SCHEMA)

  if(result1) and (result2):
    print "CREATE TABLE SUCCESS FOR USER AND APPS"
    return 0
  else:
    print "FAILED TO CREATE TABLE FOR USER AND APPS"
    return 1

if __name__ == "__main__":
  sys.exit(prime_redisdb())

