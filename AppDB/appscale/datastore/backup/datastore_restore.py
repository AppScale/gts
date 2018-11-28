import cPickle
import glob
import logging
import multiprocessing
import random
import time

from appscale.datastore import appscale_datastore_batch
from appscale.datastore.backup.datastore_backup import DatastoreBackup
from appscale.datastore.datastore_distributed import DatastoreDistributed
from appscale.datastore.dbconstants import InternalError
from appscale.datastore.index_manager import IndexManager
from appscale.datastore.utils import tornado_synchronous
from appscale.datastore.zkappscale import zktransaction as zk
from appscale.datastore.zkappscale.transaction_manager import (
  TransactionManager)

from google.appengine.datastore import datastore_pb
from google.appengine.datastore import entity_pb

logger = logging.getLogger(__name__)


class DatastoreRestore(multiprocessing.Process):
  """ Backs up all the entities for a set application ID. """

  # The amount of time to wait for SIGINT in seconds.
  SIGINT_TIMEOUT = 5

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
      backup_dir: A str, the location of the backup file.
      zoo_keeper: A ZooKeeper client.
      table_name: The database used (e.g. cassandra).
    """
    multiprocessing.Process.__init__(self)

    self.app_id = app_id
    self.backup_dir = backup_dir
    self.zoo_keeper = zoo_keeper
    self.table = table_name

    self.entities_restored = 0
    self.indexes = []
    self.ds_distributed = None
    self.dynamic_put_sync = None

  def stop(self):
    """ Stops the restore process. """
    pass

  def run(self):
    """ Starts the main loop of the restore thread. """
    datastore_batch = appscale_datastore_batch.\
      DatastoreFactory.getDatastore(self.table)
    transaction_manager = TransactionManager(self.zoo_keeper.handle)
    self.ds_distributed = DatastoreDistributed(
      datastore_batch, transaction_manager, zookeeper=self.zoo_keeper)
    index_manager = IndexManager(self.zoo_keeper.handle, self.ds_distributed)
    self.ds_distributed.index_manager = index_manager

    self.dynamic_put_sync = tornado_synchronous(
      self.ds_distributed.dynamic_put)

    while True:
      logger.debug("Trying to get restore lock.")
      if self.get_restore_lock():
        logger.info("Got the restore lock.")
        self.run_restore()
        try:
          self.zoo_keeper.release_lock_with_path(zk.DS_RESTORE_LOCK_PATH)
        except zk.ZKTransactionException, zk_exception:
          logger.error("Unable to release zk lock {0}.".\
            format(str(zk_exception)))
        break
      else:
        logger.info("Did not get the restore lock. Another instance may be "
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
    logger.debug("Entity batch to process: {0}".format(entity_batch))

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
    logger.debug("Entities encoded: {0}".format(new_entities_encoded))

    # Create a PutRequest with the entities to be stored.
    put_request = datastore_pb.PutRequest()
    put_response = datastore_pb.PutResponse()
    for entity in new_entities_encoded:
      new_entity = put_request.add_entity()
      new_entity.MergeFromString(entity)
    logger.debug("Put request: {0}".format(put_request))

    try:
      self.dynamic_put_sync(self.app_id, put_request, put_response)
      self.entities_restored += len(ent_protos)
    except zk.ZKInternalException, zkie:
      logger.error("ZK internal exception for app id {0}, " \
        "info {1}".format(self.app_id, str(zkie)))
      return False
    except zk.ZKTransactionException, zkte:
      logger.error("Concurrent transaction exception for app id {0}, " \
        "info {1}".format(self.app_id, str(zkte)))
      return False
    except InternalError:
      logger.exception('Unable to write entity')
      return False

    return True

  def read_from_file_and_restore(self, backup_file):
    """ Reads entities from backup file and stores them in the datastore.

    Args:
      backup_file: A str, the backup file location to restore from.
    """
    entities_to_store = []
    with open(backup_file, 'rb') as file_object:
      while True:
        try:
          entity = cPickle.load(file_object)
          entities_to_store.append(entity)

          # If batch size is met, store entities.
          if len(entities_to_store) == self.BATCH_SIZE:
            logger.info("Storing a batch of {0} entities...".
              format(len(entities_to_store)))
            self.store_entity_batch(entities_to_store)
            entities_to_store = []
        except EOFError:
          break

    if entities_to_store:
      logger.info("Storing {0} entities...".format(len(entities_to_store)))
      self.store_entity_batch(entities_to_store)

  def run_restore(self):
    """ Runs the restore process. Reads the backup file and stores entities
    in batches.
    """
    logger.info("Restore started")
    start = time.time()

    for backup_file in glob.glob('{0}/*{1}'.
        format(self.backup_dir, DatastoreBackup.BACKUP_FILE_SUFFIX)):
      if backup_file.endswith(".backup"):
        logger.info("Restoring \"{0}\" data from: {1}".\
          format(self.app_id, backup_file))
        self.read_from_file_and_restore(backup_file)

    time_taken = time.time() - start
    logger.info("Restored {0} entities".format(self.entities_restored))
    logger.info("Restore took {0} seconds".format(str(time_taken)))
