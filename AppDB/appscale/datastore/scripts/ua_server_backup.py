""" UA Server data backup. """

import argparse
import csv
import errno
import logging
import os
import time

from tornado import gen

from appscale.common.constants import LOG_FORMAT
from appscale.datastore import appscale_datastore
from appscale.datastore.dbconstants import (
  AppScaleDBConnectionError,
  USERS_SCHEMA,
  USERS_TABLE
)
from appscale.datastore.utils import tornado_synchronous

# The location where the backup files will be stored.
BACKUP_FILE_LOCATION = "/opt/appscale/backups/"

logger = logging.getLogger(__name__)


@tornado_synchronous
@gen.coroutine
def get_table_sync(datastore, table_name, schema):
  """ Gets data from datastore.

  Args:
    datastore: Cassandra adapter.
    table_name: Table name in datastore.
    schema: Table schema.
  """
  result = yield datastore.get_table(table_name, schema)
  raise gen.Return(result)

def reshape(array, step):
  """ Reshapes array of size n to matrix with dimensions n/step by step.

  Args:
    array: List to reshape.
    step: Number of elements in row after reshaping.
  """
  result = []
  for i in range(0, len(array), step):
    result.append(array[i:i+step])
  return result

def create_backup_dir(backup_dir):
  """ Creates backup directory.

  Args:
    backup_dir: Backup directory name.
  """
  try:
    os.makedirs(backup_dir)
  except OSError as os_error:
    if os_error.errno != errno.EEXIST:
      raise

  logger.info("Backup dir created: {0}".format(backup_dir))

def main():
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser(description='Backup UA Server data.')
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
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

  schema_cols_num = len(USERS_SCHEMA)
  table = get_table_sync(db, USERS_TABLE, user_schema)[1:]
  reshaped_table = reshape(table, schema_cols_num)

  try:
    create_backup_dir(BACKUP_FILE_LOCATION)
  except OSError as os_error:
    logger.error('OSError occurred!')
    logger.error(os_error.message)
    raise

  backup_timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
  output = '{0}ua_server_{1}.csv'.format(BACKUP_FILE_LOCATION, backup_timestamp)

  with open(output, 'w') as fout:
    writer = csv.writer(fout, delimiter=',')
    writer.writerows(reshaped_table)
