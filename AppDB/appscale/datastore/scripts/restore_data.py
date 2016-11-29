""" This process performs a restore of all the application entities from a
given restore.
"""
import argparse
import logging
import os
import sys

from ..backup.datastore_restore import DatastoreRestore
from ..dbconstants import APP_ENTITY_SCHEMA
from ..dbconstants import APP_ENTITY_TABLE
from ..dbconstants import APP_KIND_SCHEMA
from ..dbconstants import APP_KIND_TABLE
from ..dbconstants import ASC_PROPERTY_TABLE
from ..dbconstants import COMPOSITE_SCHEMA
from ..dbconstants import COMPOSITE_TABLE
from ..dbconstants import DSC_PROPERTY_TABLE
from ..dbconstants import PROPERTY_SCHEMA
from ..dbconstants import TRANSACTIONS_SCHEMA
from ..dbconstants import TRANSACTIONS_TABLE
from ..unpackaged import APPSCALE_LIB_DIR
from ..utils import fetch_and_delete_entities
from ..zkappscale import zktransaction as zk

sys.path.append(APPSCALE_LIB_DIR)
import appscale_info

# Where to look to verify the app is deployed.
_APPS_LOCATION = '/var/apps/'


def init_parser():
  """ Initializes the command line argument parser.

  Returns:
    A parser object.
  """
  parser = argparse.ArgumentParser(
    description='Restore application code and data.')
  main_args = parser.add_argument_group('main args')
  main_args.add_argument('-a', '--app-id', required=True,
    help='The application ID to restore data under.')
  main_args.add_argument('-b', '--backup-dir', required=True,
    help='The backup directory to restore data from.')
  main_args.add_argument('-c', '--clear-datastore', required=False,
    action="store_true", default=False, help='Start with a clean datastore.')
  main_args.add_argument('-d', '--debug',  required=False, action="store_true",
    default=False, help='Display debug messages.')

  # TODO
  # Read in source code location and owner and deploy the app
  # before restoring data.

  return parser


def app_is_deployed(app_id):
  """ Looks for the app directory in the deployed apps location.

  Args:
    app_id: A str, the application ID.
  Returns:
    True on success, False otherwise.
  """
  if not os.path.exists('{0}{1}/'.format(_APPS_LOCATION, app_id)):
    logging.error("Seems that \"{0}\" is not deployed.".format(app_id))
    logging.info("Please deploy \"{0}\" and try again.".\
      format(app_id))
    return False
  return True


def backup_dir_exists(backup_dir):
  """ Checks it the given backup directory exists.

  Args:
    backup_dir: A str, the location of the backup directory containing all
      backup files.
  Returns:
    True on success, False otherwise.
  """
  if not os.path.exists(backup_dir):
    logging.error("Error while accessing backup files.")
    logging.info("Please provide a valid backup directory.")
    return False
  return True


def main():
  """ This main function allows you to run the restore manually. """

  # Parse CLI arguments.
  parser = init_parser()
  args = parser.parse_args()

  # Set up logging.
  level = logging.INFO
  if args.debug:
    level = logging.DEBUG
  logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
    '%(lineno)s %(message)s ', level=level)
  logging.info("Logging started")

  logging.info(args)

  # Verify app is deployed.
  if not app_is_deployed(args.app_id):
    return

  # Verify backup dir exists.
  if not backup_dir_exists(args.backup_dir):
    return

  if args.clear_datastore:
    message = "Deleting \"{0}\" data...".\
      format(args.app_id, args.backup_dir)
    logging.info(message)
    try:
      tables_to_clear = {
        APP_ENTITY_TABLE: APP_ENTITY_SCHEMA,
        ASC_PROPERTY_TABLE: PROPERTY_SCHEMA,
        DSC_PROPERTY_TABLE: PROPERTY_SCHEMA,
        COMPOSITE_TABLE: COMPOSITE_SCHEMA,
        APP_KIND_TABLE: APP_KIND_SCHEMA,
        TRANSACTIONS_TABLE: TRANSACTIONS_SCHEMA
      }
      for table, schema in tables_to_clear.items():
        fetch_and_delete_entities('cassandra', table, schema, args.app_id, False)
    except Exception as exception:
      logging.error("Unhandled exception while deleting \"{0}\" data: {1} " \
        "Exiting...".format(args.app_id, exception.message))
      return

  # Initialize connection to Zookeeper and database related variables.
  zk_connection_locations = appscale_info.get_zk_locations_string()
  zookeeper = zk.ZKTransaction(host=zk_connection_locations)
  db_info = appscale_info.get_db_info()
  table = db_info[':table']

  # Start restore process.
  ds_restore = DatastoreRestore(args.app_id.strip('/'), args.backup_dir,
    zookeeper, table)
  try:
    ds_restore.run()
  finally:
    zookeeper.close()
