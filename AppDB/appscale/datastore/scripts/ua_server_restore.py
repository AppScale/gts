""" UA Server data restore. """

import argparse
import logging
import time

from tornado import gen

from appscale.common.constants import LOG_FORMAT
from appscale.datastore import appscale_datastore
from appscale.datastore.dbconstants import AppScaleDBConnectionError, USERS_TABLE
from appscale.datastore.utils import tornado_synchronous


@tornado_synchronous
@gen.coroutine
def put_entity_sync(datastore, table_name, user, schema, array):
  """ Puts data of specified user from backup to datastore.

  Args:
    datastore: Datastore entity.
    table_name: Table name in datastore.
    user: User name.
    schema: Table schema.
    array: List of all user's fields.
  """
  result = yield datastore.put_entity(table_name, user, schema, array)
  raise gen.Return(result)

def main():
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser(description='Backup UA Server data.')
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
  parser.add_argument('-t', '--type', help='Datastore type')
  parser.add_argument(
    '-i', '--input', help='File with UA Server backup', required=True)
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  datastore_type = 'cassandra'
  if args.type:
    datastore_type = args.type

  ERROR_CODES = appscale_datastore.DatastoreFactory.error_codes()
  valid_datastores = appscale_datastore.DatastoreFactory.valid_datastores()
  if datastore_type not in valid_datastores:
    raise Exception('{} not in valid datastores ({})'.
                    format(datastore_type, valid_datastores))

  db = appscale_datastore.DatastoreFactory.getDatastore(datastore_type)

  # Keep trying until it gets the schema.
  timeout = 5
  while 1:
    try:
      user_schema = db.get_schema_sync(USERS_TABLE)
    except AppScaleDBConnectionError:
      time.sleep(timeout)
      continue

    if user_schema[0] in ERROR_CODES:
      user_schema = user_schema[1:]
    else:
      time.sleep(timeout)
      continue
    break

  input = args.input

  with open(input, 'r') as fin:
    # Skip headers
    next(fin)
    # Iterate through all users in file
    for line in fin:
      array = line.rstrip().split(',')
      put_entity_sync(db, USERS_TABLE, array[0], user_schema, array)
