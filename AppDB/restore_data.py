""" This process performs a restore of all the application entities from a
given restore.
"""
import argparse
import cPickle
import glob
import logging
import multiprocessing
import os
import random
import sys
import time

import appscale_datastore_batch
from backup_data import DatastoreBackup
import datastore_server
import delete_all_record

from google.appengine.api import datastore_errors
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import entity_pb

from zkappscale import zktransaction as zk

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

class DatastoreRestore(multiprocessing.Process):
  """ Backs up all the entities for a set application ID. """

  # The amount of time to wait for SIGINT in seconds.
  SIGINT_TIMEOUT = 8

  # The number of entities retrieved in a datastore request.
  BATCH_SIZE = 100

  # Retry sleep on datastore error in seconds.
  DB_ERROR_PERIOD = 30

  # The amount of seconds between polling to get the restore lock.
  LOCK_POLL_PERIOD = 60

  def __init__(self, app_id, backup_dir, zoo_keeper, table_name):
    """ Constructor.

    Args:
      app_id: A str, the application ID.
      backup_file: A str, the location of the backup file.
      zoo_keeper: A ZooKeeper client.
      table_name: The database used (e.g. cassandra).
    """
    multiprocessing.Process.__init__(self)

    self.app_id = app_id
    self.backup_dir = backup_dir
    self.zoo_keeper = zoo_keeper
    datastore_batch = appscale_datastore_batch.DatastoreFactory.getDatastore(
      table_name)
    self.ds_distributed = datastore_server.DatastoreDistributed(
      datastore_batch, zookeeper=zoo_keeper)
    self.entities_restored = 0

  def stop(self):
    """ Stops the restore process. """
    pass

  def run(self):
    """ Starts the main loop of the restore thread. """
    while True:
      logging.debug("Trying to get restore lock.")
      if self.get_restore_lock():
        logging.info("Got the restore lock.")
        self.run_restore()
        try:
          self.zoo_keeper.release_lock_with_path(zk.DS_RESTORE_LOCK_PATH)
        except zk.ZKTransactionException, zk_exception:
          logging.error("Unable to release zk lock {0}.".\
            format(str(zk_exception)))
        break
      else:
        logging.info("Did not get the restore lock. Another instance may be "
          "running.")
        time.sleep(random.randint(1, self.LOCK_POLL_PERIOD))

  def get_restore_lock(self):
    """ Tries to acquire the lock for a datastore restore.

    Returns:
      True on success, False otherwise.
    """
    return self.zoo_keeper.get_lock_with_path(zk.DS_RESTORE_LOCK_PATH)

  def store_entity_batch(self, entity_batch):
    """ Stores the given entity batch.

    Args:
      entity_batch: A list of entities to store.
    Returns:
      True on success, False otherwise.
    """
    logging.debug("Entity batch to process: {0}".format(entity_batch))

    # Convert encoded entities to EntityProto objects, change the app ID if
    # it's different than the original and encode again.
    new_entities_encoded = []
    ent_protos = []
    for entity in entity_batch:
      ent_proto = entity_pb.EntityProto()
      ent_proto.ParseFromString(entity)
      ent_proto.key().set_app(self.app_id)

      ent_protos.append(ent_proto)
      new_entities_encoded.append(ent_proto.Encode())
    logging.debug("Entities encoded: {0}".format(new_entities_encoded))

    # Create a PutRequest with the entities to be stored.
    put_request = datastore_pb.PutRequest()
    for entity in new_entities_encoded:
      new_entity = put_request.add_entity()
      new_entity.MergeFromString(entity)
    logging.debug("Put request: {0}".format(put_request))

    while True:
      # Get locks for the batch of entities.
      try:
        txn_hash = self.ds_distributed.acquire_locks_for_trans(ent_protos,
          put_request.transaction().handle())
      except zk.ZKTransactionException, zk_exception:
        logging.error("ERROR while requesting locks: {0}".
          format(zk_exception.message))
        time.sleep(self.DB_ERROR_PERIOD)
        continue

      # Retrieve existing app indexes.
      indexes_encoded = self.ds_distributed.get_indices(self.app_id)
      logging.debug("Retrieved indexes: {0}".format(indexes_encoded))
      indexes = []
      for index in indexes_encoded:
        index_proto = entity_pb.CompositeIndex()
        index_proto.ParseFromString(index)
        indexes.append(index_proto)

      # Store entities.
      try:
        self.ds_distributed.put_entities(self.app_id, ent_protos, txn_hash,
          composite_indexes=indexes)
        self.entities_restored += len(ent_protos)
      except datastore_errors.InternalError, internal_error:
        logging.error("ERROR inserting entities: {0}.".\
          format(internal_error))
        return False

      return True

  def run_restore(self):
    """ Runs the restore process. Reads the backup file and stores entities
    in batches.
    """
    logging.info("Restore started")
    start = time.time()

    for backup_file in glob.glob('{0}/*{1}'.
        format(self.backup_dir, DatastoreBackup.BACKUP_FILE_SUFFIX)):
      if backup_file.endswith(".backup"):
        logging.info("Restoring \"{0}\" data from: {1}".\
          format(self.app_id, backup_file))
        # Read entities from backup file.
        entities_to_store = []
        with open(backup_file, 'rb') as file_object:
          while True:
            try:
              entity = cPickle.load(file_object)
              entities_to_store.append(entity)

              # If batch size is met, store entities.
              if len(entities_to_store) == self.BATCH_SIZE:
                logging.info("Storing a batch of {0} entities...".
                  format(len(entities_to_store)))
                self.store_entity_batch(entities_to_store)
                entities_to_store = []
            except EOFError:
              break

        # Store any remaining entities.
        if entities_to_store:
          logging.info("Storing {0} entities...".format(len(entities_to_store)))
          self.store_entity_batch(entities_to_store)

    time_taken = time.time() - start
    logging.info("Restored {0} entities".format(self.entities_restored))
    logging.info("Restore took {0} seconds".format(str(time_taken)))

def init_parser():
  """ Initializes the command line argument parser.

  Returns:
    A parser object.
  """
  parser = argparse.ArgumentParser(
    description='Restore application code and data.')
  main_args = parser.add_argument_group('Main args')
  main_args.add_argument('-a', '--app-id', required=True,
    help='the application ID to restore data under')
  main_args.add_argument('-b', '--backup-dir', required=True,
    help='the backup directory to restore data from')
  main_args.add_argument('-c', '--clear-datastore', required=False,
    action="store_true", default=False, help='start with a clean datastore')
  main_args.add_argument('-d', '--debug',  required=False, action="store_true",
    default=False, help='display debug messages')

  # TODO
  # Read in source code location and owner and deploy the app
  # before restoring data.
  # source_args = parser.add_argument_group('Source args',
  #   'Source code related arguments')
  # source_args.add_argument('-s', '--source', required=False,
  #   default=True, help='the source code file to restore from')
  # source_args.add_argument('-o', '--owner-email', required=False,
  #   help='the email of the application owner')

  return parser

def main():
  """ This main function allows you to run the restore manually. """

  # Parse CLI arguments.
  parser = init_parser()
  args = parser.parse_args()

  # TODO
  # Check if the app is deployed.

  # Display warning to the user.
  print "Please make sure \"{0}\" is deployed.".format(args.app_id)
  print "If it's not, cancel this process now and deploy the app. (CTRL-C)"
  try:
    time.sleep(DatastoreRestore.SIGINT_TIMEOUT)
  except KeyboardInterrupt:
    print "Aborting..."
    sys.exit(0)

  # Set up logging.
  level = logging.INFO
  if args.debug:
    level = logging.DEBUG
  logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
    '%(lineno)s %(message)s ', level=level)
  logging.info("Logging started")

  # Verify backup file exists.
  if not os.path.exists(args.backup_dir):
    logging.error("Error while accessing backup. Please provide a valid "
      "backup directory.")
    sys.exit(1)

  if args.clear_datastore:
    message = "Deleting \"{0}\" data...".\
      format(args.app_id, args.backup_dir)
    logging.info(message)
    try:
      delete_all_record.main('cassandra', args.app_id)
    except Exception, exception:
      logging.error("Unhandled exception while deleting \"{0}\" data. " \
        "Exiting...".format(args.app_id))
      sys.exit(1)

  # Initialize connection to Zookeeper and database related variables.
  zk_connection_locations = appscale_info.get_zk_locations_string()
  zookeeper = zk.ZKTransaction(host=zk_connection_locations)
  db_info = appscale_info.get_db_info()
  table = db_info[':table']

  # Start restore process.
  ds_restore = DatastoreRestore(args.app_id, args.backup_dir, zookeeper, table)
  try:
    ds_restore.run()
  finally:
    zookeeper.close()

if __name__ == "__main__":
  main()
