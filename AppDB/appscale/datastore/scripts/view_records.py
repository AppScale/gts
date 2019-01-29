""" View all application entities. """

import sys

from .. import appscale_datastore_batch
from ..dbconstants import APP_ENTITY_SCHEMA
from ..dbconstants import APP_ENTITY_TABLE
from ..dbconstants import APP_KIND_SCHEMA
from ..dbconstants import APP_KIND_TABLE
from ..dbconstants import ASC_PROPERTY_TABLE
from ..dbconstants import COMPOSITE_SCHEMA
from ..dbconstants import COMPOSITE_TABLE
from ..dbconstants import DATASTORE_METADATA_SCHEMA
from ..dbconstants import DATASTORE_METADATA_TABLE
from ..dbconstants import DSC_PROPERTY_TABLE
from ..dbconstants import PROPERTY_SCHEMA
from ..dbconstants import TERMINATING_STRING

_MAX_ENTITIES = 1000000


def get_entities(table, schema, db, first_key, last_key):
  """ Gets entities from a table.
    
  Args:
    table: Name of the table
    schema: The schema of table to get from
    db: The database accessor
    first_key: The entity key to start from
    last_key: The entity key to stop at
  Returns: 
    The entire table up to _MAX_ENTITIES.
  """
  return db.range_query_sync(
    table, schema, first_key, last_key, _MAX_ENTITIES)


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


def main():
  # Parse args.
  DB_TYPE="cassandra"
  first_key = ""
  last_key = ""

  if len(sys.argv) > 2:
    print "usage: appscale-view-all-records [app_id]"
    exit(1)

  if len(sys.argv) == 2:
    first_key = sys.argv[1]
    last_key = first_key + TERMINATING_STRING

  # Fetch entities.
  db = appscale_datastore_batch.DatastoreFactory.getDatastore(DB_TYPE)

  tables_to_schemas = {
    APP_ENTITY_TABLE: APP_ENTITY_SCHEMA,
    ASC_PROPERTY_TABLE: PROPERTY_SCHEMA,
    DSC_PROPERTY_TABLE: PROPERTY_SCHEMA,
    COMPOSITE_TABLE: COMPOSITE_SCHEMA,
    APP_KIND_TABLE: APP_KIND_SCHEMA,
    DATASTORE_METADATA_TABLE: DATASTORE_METADATA_SCHEMA,
  }

  for table in tables_to_schemas:
    entities = get_entities(table, tables_to_schemas[table],
                            db, first_key, last_key)
    view_all(entities, table, db)
