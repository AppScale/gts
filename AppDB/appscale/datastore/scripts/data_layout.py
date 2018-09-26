import argparse
import sys

from ..appscale_datastore_batch import DatastoreFactory

# The exit code that indicates the data layout version is unexpected.
INVALID_VERSION_EXIT_CODE = 64


def main():
  parser = argparse.ArgumentParser(
    description='Checks if the data layout is valid')
  parser.add_argument('--db-type', help='The database type')
  args = parser.parse_args()

  datastore_batch = DatastoreFactory.getDatastore(args.db_type)
  try:
    is_valid = datastore_batch.valid_data_version_sync()
  finally:
    datastore_batch.close()

  if not is_valid:
    sys.exit(INVALID_VERSION_EXIT_CODE)
