#!/usr/bin/env python

""" 
 Deletes all application data.
""" 

import logging
import sys
import time

from dbconstants import *
import appscale_datastore_batch

# The amount of time to wait before retrying.
_BACKOFF_TIMEOUT = 30

# The default number of entities to fetch from a datastore table.
_BATCH_SIZE = 1000

def get_entities(table, schema, db, start_inclusive, first_key="", last_key="",
    batch_size=_BATCH_SIZE):
  """ Gets entities from a table.
    
  Args:
    table: A str, the name of the table.
    schema: The schema of the table to get from.
    db: The database accessor.
    first_key: A str, the last key from a previous query.
    last_key: A str, the last key to fetch.
    batch_size: The number of entities to fetch.
    start_inclusive: True if first row should be included, False otherwise.
  Returns: 
    A list of entities.
  """
  return db.range_query(table, schema, first_key, last_key, batch_size,
    start_inclusive=start_inclusive)

def delete_all(entities, table, db):
  """ Deletes all given entities from the given table.
  
  Args:
    entities: A list of entities to delete.
    table: The table to delete from.
    db: The database accessor.
  """
  for ii in entities:
    db.batch_delete(table, ii.keys())
  logging.info("Deleted {0} entities".format(len(entities)))

def main(database, first_key, entities_only=False):
  """ Deletes all data from datastore.

  Args:
    database: The datastore type (e.g. cassandra).
    first_key: A str, the first key to be deleted.
      Either the app ID or "" to delete all db data.
    entities_only: True to delete entities from APP_ENTITY/PROPERTY tables,
      False to delete every trace of the given app ID.
  """
  logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
    '%(lineno)s %(message)s ', level=logging.INFO)

  # Tables to delete from.
  tables_to_schemas = {
    APP_ENTITY_TABLE: APP_ENTITY_SCHEMA,
    ASC_PROPERTY_TABLE: PROPERTY_SCHEMA,
    DSC_PROPERTY_TABLE: PROPERTY_SCHEMA,
    COMPOSITE_TABLE: COMPOSITE_SCHEMA,
    APP_KIND_TABLE: APP_KIND_SCHEMA,
    JOURNAL_TABLE: JOURNAL_SCHEMA,
    METADATA_TABLE: METADATA_SCHEMA
  }

  # Set the last key.
  last_key = first_key + '\0' + TERMINATING_STRING
  logging.debug("Deleting application data in the range: {0} - {1}".
    format(first_key, last_key))

  db = appscale_datastore_batch.DatastoreFactory.getDatastore(database)

  # Do not delete metadata, just entities.
  if entities_only:
    tables_to_schemas = {k:v for k,v in tables_to_schemas.iteritems()
      if not k == METADATA_TABLE}

  # Loop through the datastore tables and delete data.
  for table, schema in tables_to_schemas.items():
    logging.debug("Deleting data from {0}".format(table))

    start_inclusive = True
    while True:
      try:
        entities = get_entities(table, schema, db,
          start_inclusive, first_key=first_key, last_key=last_key)
        if not entities:
          break

        delete_all(entities, table, db)

        first_key = entities[-1].keys()[0]
        start_inclusive = False
      except AppScaleDBConnectionError, connection_error:
        logging.error("ERROR while deleting data from {0}.".
          format(connection_error))
        logging.error(connection_error.message)
        time.sleep(_BACKOFF_TIMEOUT)

if __name__ == "__main__":
  database = "cassandra"
  first_key = ""
  last_key = ""

  if len(sys.argv) < 2:
    print "usage: ./delete_all_record.py db_type [app_id]"
  else:
    database = sys.argv[1]
    if len(sys.argv) == 3:
      first_key = sys.argv[2]

  try:
    main(database, first_key, False)
  except:
    raise

