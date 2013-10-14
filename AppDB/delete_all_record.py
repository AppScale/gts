#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>

""" 
 Delete all application record for testing.
""" 


import os
import sys
from dbconstants import *
import appscale_datastore_batch

_MAX_ENTITIES = 1000000 
def get_entities(table, schema, db):
  """ Gets entities from a table.
    
  Args:
    table: Name of the table
    schema: The schema of table to get from
    db: The database accessor
  Returns: 
    The entire table up to _MAX_ENTITIES
  """
  return db.range_query(table, schema, "", "", _MAX_ENTITIES)

def delete_all(entities, table, db):
  """ Delets all entities in a table.
  
  Args: 
    table: The table to delete from
    db: The database accessor
  """
  for ii in entities:
    db.batch_delete(table, ii.keys())

def main(argv):
  DB_TYPE="cassandra"
  if len(argv) < 2:
    print "usage: ./delete_app_recode.py db_type"
  else:
    DB_TYPE = argv[1]
  
  db = appscale_datastore_batch.DatastoreFactory.getDatastore(DB_TYPE)
  entities = get_entities(APP_ENTITY_TABLE, APP_ENTITY_SCHEMA, db)   
  delete_all(entities, APP_ENTITY_TABLE, db) 

  entities = get_entities(ASC_PROPERTY_TABLE, PROPERTY_SCHEMA, db)
  delete_all(entities, ASC_PROPERTY_TABLE, db) 

  entities = get_entities(DSC_PROPERTY_TABLE, PROPERTY_SCHEMA, db)
  delete_all(entities, DSC_PROPERTY_TABLE, db) 

  entities = get_entities(COMPOSITE_TABLE, PROPERTY_SCHEMA, db)
  delete_all(entities, COMPOSITE_TABLE, db) 

  entities = get_entities(APP_KIND_TABLE, APP_KIND_SCHEMA, db)
  delete_all(entities, APP_KIND_TABLE, db) 

  entities = get_entities(JOURNAL_TABLE, JOURNAL_SCHEMA, db)
  delete_all(entities, JOURNAL_TABLE, db) 
  
if __name__ == "__main__":
  try:
    main(sys.argv)
  except:
    raise

