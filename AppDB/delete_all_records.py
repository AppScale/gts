#!/usr/bin/env python

""" Deletes all application data. """

import logging
import sys

from appscale.datastore.dbconstants import APP_ENTITY_SCHEMA
from appscale.datastore.dbconstants import APP_ENTITY_TABLE
from appscale.datastore.dbconstants import APP_KIND_SCHEMA
from appscale.datastore.dbconstants import APP_KIND_TABLE
from appscale.datastore.dbconstants import ASC_PROPERTY_TABLE
from appscale.datastore.dbconstants import COMPOSITE_SCHEMA
from appscale.datastore.dbconstants import COMPOSITE_TABLE
from appscale.datastore.dbconstants import DSC_PROPERTY_TABLE
from appscale.datastore.dbconstants import METADATA_SCHEMA
from appscale.datastore.dbconstants import METADATA_TABLE
from appscale.datastore.dbconstants import PROPERTY_SCHEMA
from appscale.datastore.dbconstants import TRANSACTIONS_SCHEMA
from appscale.datastore.dbconstants import TRANSACTIONS_TABLE
from appscale.datastore.unpackaged import APPSCALE_LIB_DIR
from appscale.datastore.utils import fetch_and_delete_entities

sys.path.append(APPSCALE_LIB_DIR)
from constants import LOG_FORMAT


if __name__ == "__main__":
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  database = "cassandra"
  first_key = ""
  last_key = ""

  if len(sys.argv) > 2:
    print "usage: ./delete_all_records.py [app_id]"
    exit(1)

  if len(sys.argv) == 2:
    first_key = sys.argv[1]

  try:
    tables_to_schemas = {
      APP_ENTITY_TABLE: APP_ENTITY_SCHEMA,
      ASC_PROPERTY_TABLE: PROPERTY_SCHEMA,
      DSC_PROPERTY_TABLE: PROPERTY_SCHEMA,
      COMPOSITE_TABLE: COMPOSITE_SCHEMA,
      APP_KIND_TABLE: APP_KIND_SCHEMA,
      METADATA_TABLE: METADATA_SCHEMA,
      TRANSACTIONS_TABLE: TRANSACTIONS_SCHEMA
    }
    for table, schema in tables_to_schemas.items():
      fetch_and_delete_entities(database, table, schema, first_key, False)
  except:
    raise
