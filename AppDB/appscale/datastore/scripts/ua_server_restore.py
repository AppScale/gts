""" UA Server data restore. """

import argparse
import csv
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

  parser = argparse.ArgumentParser(description='Restore UA Server data.')
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
  parser.add_argument(
    '-i', '--input', help='File with UA Server backup', required=True)
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  datastore_type = 'cassandra'

  ERROR_CODES = appscale_datastore.DatastoreFactory.error_codes()

  db = appscale_datastore.DatastoreFactory.getDatastore(datastore_type)

  # Keep trying until it gets the schema.
  backoff = 5
  retries = 3
  while retries >= 0:
    try:
      user_schema = db.get_schema_sync(USERS_TABLE)
    except AppScaleDBConnectionError:
      retries -= 1
      time.sleep(backoff)
      continue

    if user_schema[0] in ERROR_CODES:
      user_schema = user_schema[1:]
    else:
      retries -= 1
      time.sleep(backoff)
      continue
    break

  # If no response from cassandra
  if retries == -1:
    raise AppScaleDBConnectionError('No response from cassandra.')

  input = args.input

  with open(input, 'r') as fin:
    reader = csv.reader(fin, delimiter=',')
    # Iterate through all users in file
    for row in reader:
      put_entity_sync(db, USERS_TABLE, row[0], user_schema, row)
