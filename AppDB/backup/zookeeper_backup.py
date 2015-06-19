""" Zookeeper data backup. """

import json
import kazoo.client
import logging
import os

import backup_exceptions
import backup_recovery_helper
import gcs_helper

from backup_recovery_constants import ZK_IGNORE_PATHS
from backup_recovery_constants import ZK_TOP_LEVEL
from backup_recovery_constants import ZOOKEEPER_BACKUP_FILE_LOCATION
from backup_recovery_constants import StorageTypes
from backup_recovery_constants import TMP_ZOOKEEPER_BACKUP

from zkappscale import shut_down_zookeeper
from zkappscale.zktransaction import DEFAULT_HOST as ZK_DEFAULT_HOST
from zkappscale.zktransaction import PATH_SEPARATOR

logging.getLogger().setLevel(logging.INFO)

def dump_zk(filename):
  """ Dumps Zookeeper application data to a file.

  Args:
    filename: A str, the path to the temporary Zookeeper backup file.
  """
  handle = kazoo.client.KazooClient(hosts=ZK_DEFAULT_HOST)
  handle.start()
  with open(filename, "wb") as f:
    recursive_dump(handle, ZK_TOP_LEVEL, f)
  handle.stop()

def recursive_dump(handle, path, file_handler):
  """ Recursively dumps the path and the value of the children of the given
  node.

  Args:
    handle: A Zookeeper client handler.
    path: The Zookeeper path to dump to a file.
    file_handler: A file handler to dump the data to.
  """
  try:
    children = handle.get_children(path)
    if not any(path.startswith(item) for item in ZK_IGNORE_PATHS):
      logging.debug("Processing path: {0}".format(path))
      for child in children:
        logging.debug("Processing child: {0}".format(child))
        new_path = '{0}{1}'.format(path, child)
        if path != ZK_TOP_LEVEL:
          new_path = PATH_SEPARATOR.join([path, child])
        recursive_dump(handle, new_path, file_handler)
      if path != ZK_TOP_LEVEL:
        value = handle.get(path)[0]
        file_handler.write('{0}\n'.format(json.dumps({path: value})))
  except kazoo.exceptions.NoNodeError:
    logging.debug('Reached the end of the zookeeper path.')

def flush_zk():
  """ Deletes Zookeeper data. """
  handle = kazoo.client.KazooClient(hosts=ZK_DEFAULT_HOST)
  handle.start()
  recursive_flush(handle, ZK_TOP_LEVEL)
  handle.stop()

def recursive_flush(handle, path):
  """ Recursively deletes the path and the value of the children of the given
  node.

  Args:
    handle: A Zookeeper client handler.
    path: The Zookeeper path to delete.
  """
  try:
    children = handle.get_children(path)
    if not any(path.startswith(item) for item in ZK_IGNORE_PATHS):
      logging.debug("Processing path: {0}".format(path))
      for child in children:
        logging.debug("Processing child: {0}".format(child))
        new_path = '{0}{1}'.format(path, child)
        if path != ZK_TOP_LEVEL:
          new_path = PATH_SEPARATOR.join([path, child])
        recursive_flush(handle, new_path)
      try:
        handle.delete(path)
      except kazoo.exceptions.BadArgumentsError:
        logging.warning('BadArgumentsError while deleting path: {0}.'.format(
          path))
  except kazoo.exceptions.NoNodeError:
    logging.debug('Reached the end of the zookeeper path.')

def restore_zk(filename):
  """ Restores Zookeeper data from a fixed file in the local FS.

  Args:
    filename: A str, the path to the temporary Zookeeper backup file.
  """
  handle = kazoo.client.KazooClient(hosts=ZK_DEFAULT_HOST)
  handle.start()
  with open(filename, 'rb') as f:
    for line in f.readlines():
      pair = json.loads(line)
      path = pair.keys()[0]
      value = pair.values()[0]
      try:
        handle.create(path, bytes(value), makepath=True)
        logging.debug("Created '{0}'".format(path))
      except kazoo.exceptions.NodeExistsError:
        try:
          handle.set(path, bytes(value))
          logging.debug("Updated '{0}'".format(path))
        except kazoo.exceptions.BadArgumentsError:
          logging.warning("BadArgumentsError for path '{0}'".format(path))
      except kazoo.exceptions.NoNodeError:
        logging.warning("NoNodeError for path '{0}'. Parent nodes are "
          "missing".format(path))
      except kazoo.exceptions.ZookeeperError:
        logging.warning("ZookeeperError for path '{0}'".format(path))
  handle.stop()

def shutdown_zookeeper():
  """ Top level function for bringing down Zookeeper.

  Returns:
    True on success, False otherwise.
  """
  logging.info("Shutting down Zookeeper.")
  if not shut_down_zookeeper.run():
    return False
  return True

def backup_data(storage, path=''):
  """ Backup Zookeeper directories/files.

  Args:
    storage: A str, one of the StorageTypes class members.
    path: A str, the name of the backup file to be created.
  Returns:
    The path to the backup file on success, None otherwise.
  """
  if storage not in StorageTypes().get_storage_types():
    logging.error("Storage '{0}' not supported.")
    return None

  logging.info("Starting new zk backup.")
  dump_zk(TMP_ZOOKEEPER_BACKUP)

  tar_file = backup_recovery_helper.tar_backup_files([TMP_ZOOKEEPER_BACKUP],
    ZOOKEEPER_BACKUP_FILE_LOCATION)
  if not tar_file:
    logging.error('Error while tarring up Zookeeper files. Aborting backup...')
    backup_recovery_helper.remove(TMP_ZOOKEEPER_BACKUP)
    backup_recovery_helper.delete_local_backup_file(tar_file)
    backup_recovery_helper.move_secondary_backup(tar_file)
    return None

  if storage == StorageTypes.LOCAL_FS:
    logging.info("Done with local zk backup!")
    backup_recovery_helper.remove(TMP_ZOOKEEPER_BACKUP)
    backup_recovery_helper.\
      delete_secondary_backup(ZOOKEEPER_BACKUP_FILE_LOCATION)
    return tar_file
  elif storage == StorageTypes.GCS:
    return_value = path
    # Upload to GCS.
    if not gcs_helper.upload_to_bucket(path, tar_file):
      logging.error("Upload to GCS failed. Aborting backup...")
      backup_recovery_helper.move_secondary_backup(tar_file)
      return_value = None
    else:
      logging.info("Done with zk backup!")
      backup_recovery_helper.\
        delete_secondary_backup(ZOOKEEPER_BACKUP_FILE_LOCATION)

    # Remove local backup files.
    backup_recovery_helper.remove(TMP_ZOOKEEPER_BACKUP)
    backup_recovery_helper.delete_local_backup_file(tar_file)
    return return_value

def restore_data(storage, path=''):
  """ Restores the Zookeeper snapshot.

  Args:
    storage: A str, one of the StorageTypes class members.
    path: A str, the name of the backup file to restore from.
  """
  if storage not in StorageTypes().get_storage_types():
    logging.error("Storage '{0}' not supported.")
    return False

  logging.info("Starting new zk restore.")

  if storage == StorageTypes.GCS:
    # Download backup file and store locally with a fixed name.
    if not gcs_helper.download_from_bucket(path,
        ZOOKEEPER_BACKUP_FILE_LOCATION):
      logging.error("Download from GCS failed. Aborting recovery...")
      return False

  # TODO Make sure there's a snapshot to rollback to if restore fails.
  # Not pressing for fresh deployments.

  flush_zk()

  # if not shut_down_zookeeper.run():
  #   logging.error("Unable to shut down Zookeeper. Aborting restore...")
  #   if storage == StorageTypes.GCS:
  #     backup_recovery_helper.\
  #       delete_local_backup_file(ZOOKEEPER_BACKUP_FILE_LOCATION)
  #   return False
  #
  # # Start Zookeeper.
  # logging.info("Starting Zookeeper.")
  # start_zookeeper.run()

  try:
    backup_recovery_helper.untar_backup_files(ZOOKEEPER_BACKUP_FILE_LOCATION)
  except backup_exceptions.BRException as br_exception:
    logging.exception("Error while unpacking backup files. Exception: {0}".
      format(str(br_exception)))
    if storage == StorageTypes.GCS:
      backup_recovery_helper.\
        delete_local_backup_file(ZOOKEEPER_BACKUP_FILE_LOCATION)
    return False
  restore_zk(TMP_ZOOKEEPER_BACKUP)

  # Local cleanup.
  backup_recovery_helper.remove(TMP_ZOOKEEPER_BACKUP)
  if storage == StorageTypes.GCS:
    backup_recovery_helper.\
      delete_local_backup_file(ZOOKEEPER_BACKUP_FILE_LOCATION)

  logging.info("Done with zk restore.")
  return True

if "__main__" == __name__:
  backup_data(storage='', path='')
  # restore_data(storage='', path='')
