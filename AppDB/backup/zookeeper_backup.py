#!/usr/bin/env python2
""" Backup or restore ZooKeeper data. """

import argparse
import json
import kazoo.client
import kazoo.exceptions
import logging
import os
import subprocess
import sys
import time
from StringIO import StringIO

sys.path.append(os.path.join(os.path.dirname(__file__), '../../lib'))
import appscale_info
from constants import CONTROLLER_SERVICE
from constants import LOG_FORMAT

sys.path.append(os.path.join(os.path.dirname(__file__), '../../AppDB'))
from zkappscale import zktransaction

sys.path.append(
  os.path.join(os.path.dirname(__file__), '../../InfrastructureManager'))
from utils import utils
from utils.utils import KEY_DIRECTORY

from backup_exceptions import AmbiguousKeyException
from backup_exceptions import BRException
from backup_exceptions import NoKeyException
from backup_recovery_constants import BACKUP_DIR_LOCATION
from backup_recovery_constants import ZK_DATA_DIR
from backup_recovery_constants import ZK_KEEP_PATHS
from backup_recovery_constants import ZK_TOP_LEVEL

from zkappscale import shut_down_zookeeper
from zkappscale.zktransaction import DEFAULT_HOST as ZK_DEFAULT_HOST
from zkappscale.zktransaction import PATH_SEPARATOR

def dump_zk(filename):
  """ Dumps Zookeeper application data to a file.

  Args:
    filename: A str, the path to the temporary Zookeeper backup file.
  """
  handle = kazoo.client.KazooClient(hosts=ZK_DEFAULT_HOST)
  handle.start()
  with open(filename, "w") as f:
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
    logging.debug("Processing path: {0}".format(path))
    for child in children:
      logging.debug("Processing child: {0}".format(child))
      new_path = '{0}{1}'.format(path, child)
      if path != ZK_TOP_LEVEL:
        new_path = PATH_SEPARATOR.join([path, child])
      recursive_dump(handle, new_path, file_handler)
    if path != ZK_TOP_LEVEL:
      value = handle.get(path)[0].encode('base64')
      file_handler.write("{}\n".format(json.dumps({path: value})))
  except kazoo.exceptions.NoNodeError:
    logging.debug('Reached the end of the zookeeper path.')

def recursive_flush(handle, path):
  """ Recursively deletes the path and the value of the children of the given
  node.

  Args:
    handle: A Zookeeper client handler.
    path: The Zookeeper path to delete.
  """
  try:
    children = handle.get_children(path)
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
    except kazoo.exceptions.NotEmptyError:
      logging.warning('NotEmptyError while deleting path: {0}. Skipping..'.
        format(path))
  except kazoo.exceptions.NoNodeError:
    logging.debug('Reached the end of the zookeeper path.')

def restore_zk(handle, zk_persist_file):
  """ Restores Zookeeper data from a fixed file in the local FS.

  Args:
    handle: A Zookeeper client handler.
    zk_persist_file: A file object containing the ZooKeeper data.
  """
  for line in zk_persist_file.readlines():
    pair = json.loads(line)
    path = pair.keys()[0]
    value = pair.values()[0].decode('base64')
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

def shutdown_zookeeper():
  """ Top level function for bringing down Zookeeper.

  Returns:
    True on success, False otherwise.
  """
  logging.info("Shutting down Zookeeper.")
  if not shut_down_zookeeper.run():
    return False
  return True

def backup_data(path, keyname):
  """ Backup Zookeeper data to path.

  Args:
    path: A str, the name of the backup file to be created.
    keyname: A string containing the deployment's keyname.
  Raises:
    BRException if unable to find any ZooKeeper machines.
  """
  logging.info("Starting new zk backup.")

  running = subprocess.call(['service', CONTROLLER_SERVICE, 'status']) == 0
  if not running:
    logging.error('Please start AppScale before backing up ZooKeeper.')
    sys.exit(1)

  # Stop ZooKeeper and backup data on only one ZooKeeper machine.
  # This is to avoid downtime on deployments with multiple ZooKeeper machines.
  zk_ips = appscale_info.get_zk_node_ips()
  if not zk_ips:
    raise BRException('Unable to find any ZooKeeper machines.')
  zk_ip = zk_ips[0]

  timestamp = int(time.time())
  backup_file = '{}/zk_backup_{}.tar.gz'.format(BACKUP_DIR_LOCATION, timestamp)
  try:
    utils.ssh(zk_ip, keyname, 'monit stop -g zookeeper')
    utils.ssh(zk_ip, keyname,
      'tar czf {} -C {} .'.format(backup_file, ZK_DATA_DIR))
    utils.scp_from(zk_ip, keyname, backup_file, path)
  finally:
    utils.ssh(zk_ip, keyname, 'rm -f {}'.format(backup_file))
    utils.ssh(zk_ip, keyname, 'monit start -g zookeeper')

def restore_data(path, keyname):
  """ Restores the Zookeeper snapshot.

  Args:
    path: A str, the name of the backup file to restore from.
    keyname: A string containing the deployment's keyname.
  Raises:
    BRException if unable to find any ZooKeeper machines.
  """
  logging.info("Starting new zk restore.")

  running = subprocess.call(['service', CONTROLLER_SERVICE, 'status']) == 0
  if running:
    logging.error('Please stop AppScale before restoring ZooKeeper.')
    sys.exit(1)

  zk_ips = appscale_info.get_zk_node_ips()
  if len(zk_ips) < 1:
    raise BRException('Unable to find any ZooKeeper machines.')

  timestamp = int(time.time())
  restore_file = '{}/zk_restore_{}.tar.gz'.\
    format(BACKUP_DIR_LOCATION, timestamp)

  # Cache name of ZooKeeper service for each machine.
  zk_service_names = {}
  for zk_ip in zk_ips:
    zk_service_names[zk_ip] = utils.zk_service_name(zk_ip, keyname)

  # Copy restore file to and start ZooKeeper on relevant machines.
  logging.info('Copying data to ZooKeeper machines.')
  for zk_ip in zk_ips:
    zk_service = zk_service_names[zk_ip]
    try:
      utils.scp_to(zk_ip, keyname, path, restore_file)
      utils.ssh(zk_ip, keyname, 'service {} restart'.format(zk_service))
    except subprocess.CalledProcessError as error:
      logging.exception('Failed to prepare restore on {}'.format(zk_ip))
      utils.ssh(zk_ip, keyname, 'rm -f {}'.format(restore_file))
      utils.ssh(zk_ip, keyname, 'service {} stop'.format(zk_service))
      raise error

  # Save deployment-specific data.
  deployment_data = StringIO()
  hosts_template = ':{},'.join(zk_ips) + ':{}'
  zk = kazoo.client.KazooClient(
    hosts=hosts_template.format(zktransaction.DEFAULT_PORT))
  zk.start()
  for zk_node in ZK_KEEP_PATHS:
    recursive_dump(zk, zk_node, deployment_data)
  zk.stop()

  # Stop ZooKeeper and clear existing data directory.
  logging.info('Clearing existing data on ZooKeeper machines.')
  for zk_ip in zk_ips:
    zk_service = zk_service_names[zk_ip]
    try:
      utils.ssh(zk_ip, keyname, 'service {} stop'.format(zk_service))
      utils.ssh(zk_ip, keyname, 'rm -rf {}/*'.format(ZK_DATA_DIR))
    except subprocess.CalledProcessError as error:
      logging.exception('Unable to clear data on {}'.format(zk_ip))
      deployment_data.close()
      utils.ssh(zk_ip, keyname, 'rm -f {}'.format(restore_file))
      utils.ssh(zk_ip, keyname, 'service {} stop'.format(zk_service))
      raise error

  # Restore data and restart ZooKeeper on relevant machines.
  logging.info('Restoring data on ZooKeeper machines.')
  for zk_ip in zk_ips:
    zk_service = zk_service_names[zk_ip]
    try:
      utils.ssh(zk_ip, keyname,
        'tar xzf {} -C {}'.format(restore_file, ZK_DATA_DIR))
      utils.ssh(zk_ip, keyname, 'service {} start'.format(zk_service))
    except subprocess.CalledProcessError as error:
      logging.exception('Unable to restore on {}'.format(zk_ip))
      deployment_data.close()
      utils.ssh(zk_ip, keyname, 'rm -f {}'.format(restore_file))
      utils.ssh(zk_ip, keyname, 'service {} stop'.format(zk_service))
      raise error

  # Restore deployment-specific data.
  logging.info('Restoring deployment-specific data.')
  zk = kazoo.client.KazooClient(hosts=':2181,'.join(zk_ips) + ':2181')
  zk.start()
  for zk_node in ZK_KEEP_PATHS:
    recursive_flush(zk, zk_node)
  deployment_data.seek(0)
  restore_zk(zk, deployment_data)
  zk.stop()

  # Stop ZooKeeper on relevant machines.
  logging.info('Stopping ZooKeeper.')
  for zk_ip in zk_ips:
    zk_service = zk_service_names[zk_ip]
    try:
      utils.ssh(zk_ip, keyname, 'service {} stop'.format(zk_service))
      utils.ssh(zk_ip, keyname, 'rm -rf {}'.format(restore_file))
    finally:
      deployment_data.close()

  logging.info("Done with zk restore.")
  return True

if "__main__" == __name__:
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser(
    description='Backup or restore ZooKeeper data.')
  io_group = parser.add_mutually_exclusive_group(required=True)
  io_group.add_argument('--input',
    help='The file to use for restoring ZooKeeper data.')
  io_group.add_argument('--output',
    help='The location to store the ZooKeeper backup.')
  parser.add_argument('--verbose', action='store_true',
    help='Enable debug-level logging.')

  args = parser.parse_args()

  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  keys = [key for key in os.listdir(KEY_DIRECTORY) if key.endswith('.key')]
  if len(keys) > 1:
    raise AmbiguousKeyException(
      'There is more than one ssh key in {}'.format(KEY_DIRECTORY))
  if len(keys) < 1:
    raise NoKeyException('There is no ssh key in {}'.format(KEY_DIRECTORY))
  keyname = keys[0].split('.')[0]

  if args.input is not None:
    restore_data(args.input, keyname)
  else:
    backup_data(args.output, keyname)
