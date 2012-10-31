#!/usr/bin/env python
# 
# view all application record for testing.
# 
# Author: Navraj Chohan
#

import os
import sys
from dbconstants import *
import appscale_datastore_batch

def get_entities(table, schema, db):
  return db.range_query(table, schema, "", "", 1000000)

def view_all(entities, table, db):
  print 
  print "TABLE:",table
  for ii in entities:
    print ii
  print
def main(argv):
  DB_TYPE="cassandra"
  if len(argv) < 2:
    print "usage: ./view_all_records.py db_type"
  else:
    DB_TYPE = argv[1]
  
  db = appscale_datastore_batch.DatastoreFactory.getDatastore(DB_TYPE)
  entities = get_entities(APP_NAMESPACE_TABLE, APP_NAMESPACE_SCHEMA, db)
  view_all(entities, APP_NAMESPACE_TABLE, db) 

  entities = get_entities(APP_ENTITY_TABLE, APP_ENTITY_SCHEMA, db)   
  view_all(entities, APP_ENTITY_TABLE, db) 

  entities = get_entities(ASC_PROPERTY_TABLE, PROPERTY_SCHEMA, db)
  view_all(entities, ASC_PROPERTY_TABLE, db) 

  entities = get_entities(DSC_PROPERTY_TABLE, PROPERTY_SCHEMA, db)
  view_all(entities, DSC_PROPERTY_TABLE, db) 

  entities = get_entities(APP_KIND_TABLE, APP_KIND_SCHEMA, db)
  view_all(entities, APP_KIND_TABLE, db) 
  
if __name__ == "__main__":
  try:
    main(sys.argv)
  except:
    raise

