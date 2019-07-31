""" UA Server data backup. """

import argparse
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


@tornado_synchronous
@gen.coroutine
def get_table_sync(datastore, table_name, schema):
  """ Gets data from datastore.

  Args:
    datastore: Datastore entity.
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
  Returns:
    True if directory was created or existed before, false otherwise.
  """
  logger = logging.getLogger(__name__)
  try:
    os.makedirs(backup_dir)
    logger.info("Backup dir created: {0}".format(backup_dir))
    return True
  except OSError, os_error:
    if os_error.errno == errno.EEXIST:
      logger.warn("OSError: Backup directory already exists.")
      return True
    elif os_error.errno == errno.ENOSPC:
      logger.error("OSError: No space left to create backup directory.")
      logger.error(os_error.message)
      return False
    elif os_error.errno == errno.EROFS:
      logger.error("OSError: READ-ONLY filesystem detected.")
      logger.error(os_error.message)
      return False
  except IOError, io_error:
    logger.error("IOError while creating backup dir.")
    logger.error(io_error.message)
    return False

def main():
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser(description='Backup UA Server data.')
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
  parser.add_argument('-t', '--type', help='Datastore type')
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

  schema_cols_num = len(USERS_SCHEMA)
  table = get_table_sync(db, USERS_TABLE, user_schema)[1:]
  reshaped_table = reshape(table, schema_cols_num)

  is_created = create_backup_dir(BACKUP_FILE_LOCATION)

  if not is_created:
    return

  backup_timestamp = time.strftime("%Y-%m-%d_%H-%M-%S")
  output = '{0}ua_server_{1}.csv'.format(BACKUP_FILE_LOCATION, backup_timestamp)

  with open(output, 'w') as fout:
    fout.write(','.join(USERS_SCHEMA) + '\n')
    for row in reshaped_table:
      fout.write(','.join(row) + '\n')
