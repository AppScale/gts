import argparse

from ..appscale_datastore_batch import DatastoreFactory


def main():
  parser = argparse.ArgumentParser(
    description='Checks if the data layout is valid')
  parser.add_argument('--db-type', help='The database type')
  args = parser.parse_args()

  datastore_batch = DatastoreFactory.getDatastore(args.db_type)
  try:
    assert datastore_batch.valid_data_version()
  finally:
    datastore_batch.close()
