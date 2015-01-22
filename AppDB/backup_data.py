""" This process performs a backup of all the application entities for the given
app ID to the local filesystem.
"""
import argparse
import cPickle
import logging
import multiprocessing
import os
import random
import re
import shutil
import sys
import time

import appscale_datastore_batch
import dbconstants
import datastore_server
import entity_utils

from zkappscale import zktransaction as zk

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

class DatastoreBackup(multiprocessing.Process):
  """ Backs up all the entities for a set application ID. """

  # The amount of seconds between polling to get the backup lock.
  LOCK_POLL_PERIOD = 60

  # The location where the backup files will be stored.
  BACKUP_FILE_LOCATION = "/opt/appscale/backups/"

  # The backup filename suffix.
  BACKUP_FILE_SUFFIX = ".backup"

  # The number of entities retrieved in a datastore request.
  BATCH_SIZE = 100

  # Retry sleep on datastore error in seconds.
  DB_ERROR_PERIOD = 30

  # Max backup file size in bytes.
  MAX_FILE_SIZE = 100 * 100 * 100 # <- 100 MB

  # Any kind that is of __*__ is private.
  PRIVATE_KINDS = '(.*)__(.*)__(.*)'

  # Any kind that is of _*_ is protected.
  PROTECTED_KINDS = '(.*)_(.*)_(.*)'

  def __init__(self, app_id, zoo_keeper, table_name, ds_path):
    """ Constructor.

    Args:
      zk: ZooKeeper client.
      table_name: The database used (e.g. cassandra).
      ds_path: The connection path to the datastore_server.
    """
    multiprocessing.Process.__init__(self)

    self.app_id = app_id
    self.last_key = self.app_id + dbconstants.TERMINATING_STRING
    self.zoo_keeper = zoo_keeper
    self.table_name = table_name
    self.db_access = appscale_datastore_batch.DatastoreFactory.\
      getDatastore(self.table_name)
    self.datastore_path = ds_path
    self.entities_backed_up = 0
    self.current_fileno = 0
    self.current_file_size = 0
    self.filename_prefix = '{0}{1}-{2}'.format(
      self.BACKUP_FILE_LOCATION, self.app_id, time.strftime("%Y%m%d-%H%M%S"))
    self.filename = '{0}-{1}{2}'.format(self.filename_prefix,
      self.current_fileno, self.BACKUP_FILE_SUFFIX)

  def stop(self):
    """ Stops the backup thread. """
    pass

  def run(self):
    """ Starts the main loop of the backup thread. """
    while True:
      logging.debug("Trying to get backup lock.")
      if self.get_backup_lock():
        logging.info("Got the backup lock.")
        self.run_backup()
        try:
          self.zoo_keeper.release_lock_with_path(zk.DS_BACKUP_LOCK_PATH)
        except zk.ZKTransactionException, zk_exception:
          logging.error("Unable to release zk lock {0}.".\
            format(str(zk_exception)))
        break
      else:
        logging.info("Did not get the backup lock. Another instance may be "
          "running.")
        time.sleep(random.randint(1, self.LOCK_POLL_PERIOD))

  def get_backup_lock(self):
    """ Tries to acquire the lock for a datastore backup.

    Returns:
      True on success, False otherwise.
    """
    return self.zoo_keeper.get_lock_with_path(zk.DS_BACKUP_LOCK_PATH)

  def get_entity_batch(self, first_key, batch_size, start_inclusive):
    """ Gets a batch of entities to operate on.

    Args:
      first_key: The last key from a previous query.
      batch_size: The number of entities to fetch.
      start_inclusive: True if first row should be included, False otherwise.
    Returns:
      A list of entities.
    """
    return self.db_access.range_query(dbconstants.APP_ENTITY_TABLE,
      dbconstants.APP_ENTITY_SCHEMA, first_key, self.last_key,
      batch_size, start_inclusive=start_inclusive)

  def verify_entity(self, key, txn_id):
    """ Verify that the entity is not blacklisted.

    Args:
      key: The key to the entity table.
      txn_id: An int, a transaction ID.
    Returns:
      True on success, False otherwise.
    """
    app_prefix = entity_utils.get_prefix_from_entity_key(key)
    try:
      if self.zoo_keeper.is_blacklisted(app_prefix, txn_id):
        logging.error("Found a blacklisted item for version {0} on key {1}".\
          format(txn_id, key))
        return False
    except zk.ZKTransactionException, zk_exception:
      logging.error("Caught exception {0}, backing off!".format(zk_exception))
      time.sleep(self.DB_ERROR_PERIOD)
    except zk.ZKInternalException, zk_exception:
      logging.error("Caught exception: {0}, backing off!".format(
        zk_exception))
      time.sleep(self.DB_ERROR_PERIOD)

    return True

  def dump_entity(self, entity):
    """ Dumps the entity content into a backup file.

    Args:
      entity: The entity to be backed up.
    Returns:
      True on success, False otherwise.
    """
    # Open file and write pickled batch.
    if self.current_file_size + len(entity) > self.MAX_FILE_SIZE:
      self.current_fileno += 1
      self.current_file_size = 0
      self.filename = '{0}-{1}{2}'.format(self.filename_prefix,
        self.current_fileno, self.BACKUP_FILE_SUFFIX)

    try:
      with open(self.filename, 'a+') as file_object:
        cPickle.dump(entity, file_object, cPickle.HIGHEST_PROTOCOL)

      self.entities_backed_up += 1
      self.current_file_size += len(entity)
    except IOError as io_error:
      logging.error(
        "Encountered IOError while accessing backup file {0}".
        format(self.filename))
      logging.error(io_error.message)
      return False
    except OSError as os_error:
      logging.error(
        "Encountered OSError while accessing backup file {0}".
        format(self.filename))
      logging.error(os_error.message)
      return False
    except Exception as exception:
      logging.error(
        "Encountered an unexpected error while accessing backup file {0}".
        format(self.filename))
      logging.error(exception.message)
      return False

    return True

  def process_entity(self, entity):
    """ Verifies entity, fetches from journal if necessary and calls
    dump_entity.

    Args:
      entity: The entity to be backed up.
    Returns:
      True on success, False otherwise.
    """
    key = entity.keys()[0]
    if re.match(self.PRIVATE_KINDS, key) or re.match(self.PROTECTED_KINDS, key):
      return False
    logging.debug("Entity: {0}".format(entity))

    one_entity = entity[key][dbconstants.APP_ENTITY_SCHEMA[0]]
    if one_entity == datastore_server.TOMBSTONE:
      return False
    app_prefix = entity_utils.get_prefix_from_entity_key(key)
    root_key = entity_utils.get_root_key_from_entity_key(key)

    success = True
    while True:
      # Acquire lock.
      txn_id = self.zoo_keeper.get_transaction_id(app_prefix)
      try:
        if self.zoo_keeper.acquire_lock(app_prefix, txn_id, root_key):
          version = entity[key][dbconstants.APP_ENTITY_SCHEMA[1]]
          if not self.verify_entity(key, version):
            # Fetch from the journal.
            entity = entity_utils.fetch_journal_entry(self.db_access, key)
            one_entity = entity[key][dbconstants.APP_ENTITY_SCHEMA[0]]
            if not entity:
              logging.error("Bad journal entry for key: {0} \nAnd result: {1}".
                format(key, entity))
              success = False

          self.dump_entity(one_entity)
          success = True
        else:
          success = False
      except zk.ZKTransactionException, zk_exception:
        logging.error("Zookeeper exception {0} while requesting entity lock".
          format(zk_exception))
        success = False
      except zk.ZKInternalException, zk_exception:
        logging.error("Zookeeper exception {0} while requesting entity lock".
          format(zk_exception))
        success = False
      except dbconstants.AppScaleDBConnectionError, db_exception:
        logging.error("Database exception {0} while requesting entity lock".
          format(db_exception))
        success = False
      finally:
        if not success:
          if not self.zoo_keeper.notify_failed_transaction(app_prefix, txn_id):
            logging.error("Unable to invalidate txn for {0} with txnid: {1}"\
              .format(app_prefix, txn_id))
          logging.error("Failed to backup entity. Retrying shortly...")

        try:
          self.zoo_keeper.release_lock(app_prefix, txn_id)
        except zk.ZKTransactionException, zk_exception:
          logging.error(
            "Zookeeper exception {0} while releasing entity lock.".
              format(zk_exception))
        except zk.ZKInternalException, zk_exception:
          logging.error(
            "Zookeeper exception {0} while releasing entity lock.".
              format(zk_exception))

      if success:
        break
      else:
        time.sleep(self.DB_ERROR_PERIOD)

    return success

  def run_backup(self):
    """ Runs the backup process. Loops on the entire dataset and dumps it into
    a file.
    """
    logging.info("Backup started")
    logging.info("Backup file: {0}".format(self.filename))
    start = time.time()

    first_key = '{0}\x00'.format(self.app_id)
    start_inclusive = True
    entities_remaining = []
    while True:
      try:
        # Compute batch size.
        batch_size = self.BATCH_SIZE - len(entities_remaining)

        # Fetch batch.
        entities = entities_remaining + self.get_entity_batch(first_key,
          batch_size, start_inclusive)

        if not entities:
          break

        for entity in entities:
          self.process_entity(entity)

        first_key = entities[-1].keys()[0]
        start_inclusive = False
      except dbconstants.AppScaleDBConnectionError, connection_error:
        logging.error("Error getting a batch: {0}".format(connection_error))
        time.sleep(self.DB_ERROR_PERIOD)

    del self.db_access

    time_taken = time.time() - start
    logging.info("Backed up {0} entities".format(self.entities_backed_up))
    logging.info("Backup took {0} seconds".format(str(time_taken)))

def init_parser():
  """ Initializes the command line argument parser.

  Returns:
    A parser object.
  """
  parser = argparse.ArgumentParser(
    description='Backup application code and data.')
  parser.add_argument('-a', '--app-id', required=True,
    help='the application ID to run the backup for')
  parser.add_argument('-s', '--source', action='store_true',
    default=False, help='backup the source code too. Disabled by default.')

  return parser

def main():
  """ This main function allows you to run the backup manually. """

  parser = init_parser()
  args = parser.parse_args()

  logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
    '%(lineno)s %(message)s ', level=logging.INFO)
  logging.info("Logging started")

  message = "Backing up "
  if args.source:
    message += "source and "
  message += "data for: {0}".format(args.app_id)
  logging.info(message)

  if args.source:
    sourcefile = '/opt/appscale/apps/{0}.tar.gz'.format(args.app_id)
    if os.path.isfile(sourcefile):
      try:
        shutil.copy(sourcefile, DatastoreBackup.BACKUP_FILE_LOCATION)
        logging.info("Source code was successfully backed up.")
      except shutil.Error, error:
        logging.error("Error: {0} while backing up source code. Skipping...".format(error))
    else:
      logging.error("Couldn't find source code for this app. Skipping...")

  zk_connection_locations = appscale_info.get_zk_locations_string()
  zookeeper = zk.ZKTransaction(host=zk_connection_locations)
  db_info = appscale_info.get_db_info()
  table = db_info[':table']
  master = appscale_info.get_db_master_ip()
  datastore_path = "{0}:8888".format(master)

  ds_backup = DatastoreBackup(args.app_id, zookeeper, table, datastore_path)

  try:
    ds_backup.run()
  finally:
    zookeeper.close()

if __name__ == "__main__":
  main()
