#!/usr/bin/env python
# Programmer: Navraj Chohan <nlake44@gmail.com>
""" 
 View all application entities.
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

def view_all(entities, table, db):
  """ View all entities for a table
  
  Args:
    entities: Shows all entities in a list
    table: The table these entities are from
    db: database accessor
  """
  print 
  print "TABLE:",table
  for ii in entities:
    print ii
  print

def main(argv):
  """ Main 
  """
  DB_TYPE="cassandra"
  if len(argv) < 2:
    print "usage: ./view_all_records.py db_type"
  else:
    DB_TYPE = argv[1]
  
  db = appscale_datastore_batch.DatastoreFactory.getDatastore(DB_TYPE)

  entities = get_entities(APP_ENTITY_TABLE, APP_ENTITY_SCHEMA, db)   
  view_all(entities, APP_ENTITY_TABLE, db) 

  entities = get_entities(ASC_PROPERTY_TABLE, PROPERTY_SCHEMA, db)
  view_all(entities, ASC_PROPERTY_TABLE, db) 

  entities = get_entities(DSC_PROPERTY_TABLE, PROPERTY_SCHEMA, db)
  view_all(entities, DSC_PROPERTY_TABLE, db) 

  entities = get_entities(COMPOSITE_TABLE, PROPERTY_SCHEMA, db)
  view_all(entities, COMPOSITE_TABLE, db) 

  entities = get_entities(APP_KIND_TABLE, APP_KIND_SCHEMA, db)
  view_all(entities, APP_KIND_TABLE, db) 

  entities = get_entities(JOURNAL_TABLE, JOURNAL_SCHEMA, db)
  view_all(entities, JOURNAL_TABLE, db) 

  entities = get_entities(COMPOSITE_TABLE, COMPOSITE_SCHEMA, db)
  view_all(entities, COMPOSITE_SCHEMA, db) 
   
  entities = get_entities(METADATA_TABLE, METADATA_SCHEMA, db)
  view_all(entities, METADATA_SCHEMA, db)

if __name__ == "__main__":
  try:
    main(sys.argv)
  except:
    raise

