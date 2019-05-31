#!/usr/bin/env python2
""" Cassandra data backup. """

import logging
import os
import subprocess
import time

import appscale.datastore.backup.utils as utils

from appscale.common import appscale_info
from appscale.common import appscale_utils
from appscale.common import monit_interface
from appscale.common.constants import APPSCALE_DATA_DIR
from appscale.common.constants import MonitStates
from appscale.common.constants import SCHEMA_CHANGE_TIMEOUT
from subprocess import CalledProcessError
from . import backup_recovery_helper
from .backup_exceptions import BRException
from .br_constants import CASSANDRA_DATA_SUBDIRS
from .br_constants import PADDING_PERCENTAGE
from .br_constants import SERVICE_RETRIES
from ..cassandra_env import cassandra_interface
from ..cassandra_env.cassandra_interface import NODE_TOOL
from ..cassandra_env.cassandra_interface import CASSANDRA_MONIT_WATCH_NAME

logger = logging.getLogger(__name__)

def clear_old_snapshots():
  """ Remove any old snapshots to minimize disk space usage locally. """
  logger.info('Removing old Cassandra snapshots...')
  try:
    subprocess.check_call([NODE_TOOL, 'clearsnapshot'])
  except CalledProcessError as error:
    logger.error('Error while deleting old Cassandra snapshots. Error: {0}'.\
      format(str(error)))


def create_snapshot(snapshot_name=''):
  """ Perform local Cassandra backup by taking a new snapshot.

  Args:
    snapshot_name: A str, optional. A fixed name for the snapshot to create.
  Returns:
    True on success, False otherwise.
  """
  logger.info('Creating new Cassandra snapshots...')
  try:
    subprocess.check_call([NODE_TOOL, 'snapshot'])
  except CalledProcessError as error:
    logger.error('Error while creating new Cassandra snapshots. Error: {0}'.\
      format(str(error)))
    return False
  return True


def remove_old_data():
  """ Removes previous node data from the Cassandra store. """
  for directory in CASSANDRA_DATA_SUBDIRS:
    data_dir = "{0}/{1}/{2}".format(APPSCALE_DATA_DIR, "cassandra",
      directory)
    logger.warning("Removing data from {0}".format(data_dir))
    try:
      subprocess.Popen('find /opt/appscale/cassandra -name "*" | '
        'grep ".db\|.txt\|.log" | grep -v snapshot | xargs rm', shell=True)
      logger.info("Done removing data!")
    except CalledProcessError as error:
      logger.error("Error while removing old data from db. Overwriting... "
        "Error: {0}".format(str(error)))


def restore_snapshots():
  """ Restore snapshot into correct directories.

  Returns:
    True on success, False otherwise.
  """
  logger.info("Restoring Cassandra snapshots.")

  for directory in CASSANDRA_DATA_SUBDIRS:
    data_dir = "{0}/{1}/{2}/".format(APPSCALE_DATA_DIR, "cassandra",
      directory)
    logger.debug("Restoring in dir {0}".format(data_dir))
    for path, _, filenames in os.walk(data_dir):
      for filename in filenames:
        logger.debug("Restoring: {0}".format(filename))
        if not filename:
          logger.warn("skipping...")
          continue
        full_path = "{0}/{1}".format(path, filename)
        new_full_path = "{0}/../../{1}".format(path, filename)
        logger.debug("{0} -> {1}".format(full_path, new_full_path))
        # Move the files up into the data directory.
        if not backup_recovery_helper.rename(full_path, new_full_path):
          logger.error("Error while moving Cassandra snapshot in place. "
            "Aborting restore...")
          return False

  logger.info("Done restoring Cassandra snapshots.")
  return True


def shutdown_datastore():
  """ Top level function for bringing down Cassandra.

  Returns:
    True on success, False otherwise.
  """
  logger.info("Shutting down Cassandra.")
  monit_interface.stop(
    cassandra_interface.CASSANDRA_MONIT_WATCH_NAME, is_group=False)
  logger.warning("Done!")
  return True


def backup_data(path, keyname):
  """ Backup Cassandra snapshot data directories/files.

  Args:
    path: A string containing the location to store the backup on each of the
      DB machines.
    keyname: A string containing the deployment's keyname.
  Raises:
    BRException if unable to find any Cassandra machines or if DB machine has
      insufficient space.
  """
  logger.info("Starting new db backup.")

  db_ips = appscale_info.get_db_ips()
  if not db_ips:
    raise BRException('Unable to find any Cassandra machines.')

  for db_ip in db_ips:
    appscale_utils.ssh(db_ip, keyname, '{} clearsnapshot'.format(NODE_TOOL))
    appscale_utils.ssh(db_ip, keyname, '{} snapshot'.format(NODE_TOOL))

    get_snapshot_size = 'find {0} -name "snapshots" -exec du -s {{}} \;'.\
      format(APPSCALE_DATA_DIR)
    du_output = appscale_utils.ssh(db_ip, keyname, get_snapshot_size,
                                   method=subprocess.check_output)
    backup_size = sum(int(line.split()[0])
                      for line in du_output.split('\n') if line)

    output_dir = '/'.join(path.split('/')[:-1]) + '/'
    df_output = appscale_utils.ssh(db_ip, keyname, 'df {}'.format(output_dir),
                                   method=subprocess.check_output)
    available = int(df_output.split('\n')[1].split()[3])

    if backup_size > available * PADDING_PERCENTAGE:
      raise BRException('{} has insufficient space: {}/{}'.
        format(db_ip, available * PADDING_PERCENTAGE, backup_size))

  cassandra_dir = '{}/cassandra'.format(APPSCALE_DATA_DIR)
  for db_ip in db_ips:
    create_tar = 'find . -regex ".*/snapshots/[0-9]*/.*" -exec tar '\
      '--transform="s/snapshots\/[0-9]*\///" -cf {0} {{}} +'.format(path)
    appscale_utils.ssh(db_ip, keyname,
                       'cd {} && {}'.format(cassandra_dir, create_tar))

  logger.info("Done with db backup.")


def restore_data(path, keyname, force=False):
  """ Restores the Cassandra backup.

  Args:
    path: A string containing the location on each of the DB machines to use
      for restoring data.
    keyname: A string containing the deployment's keyname.
  Raises:
    BRException if unable to find any Cassandra machines or if DB machine has
      insufficient space.
  """
  logger.info("Starting new db restore.")

  db_ips = appscale_info.get_db_ips()
  if not db_ips:
    raise BRException('Unable to find any Cassandra machines.')

  machines_without_restore = []
  for db_ip in db_ips:
    exit_code = appscale_utils.ssh(db_ip, keyname, 'ls {}'.format(path),
                                   method=subprocess.call)
    if exit_code != utils.ExitCodes.SUCCESS:
      machines_without_restore.append(db_ip)

  if machines_without_restore and not force:
    logger.info('The following machines do not have a restore file: {}'.
      format(machines_without_restore))
    response = raw_input('Would you like to continue? [y/N] ')
    if response not in ['Y', 'y']:
      return

  for db_ip in db_ips:
    logger.info('Stopping Cassandra on {}'.format(db_ip))
    summary = appscale_utils.ssh(db_ip, keyname, 'appscale-admin summary',
                                 method=subprocess.check_output)
    status_line = next((line for line in summary.split('\n')
                        if line.startswith(CASSANDRA_MONIT_WATCH_NAME)), '')
    retries = SERVICE_RETRIES
    while MonitStates.UNMONITORED not in status_line:
      appscale_utils.ssh(
        db_ip, keyname,
        'appscale-stop-service {}'.format(CASSANDRA_MONIT_WATCH_NAME),
        method=subprocess.call)
      time.sleep(3)
      summary = appscale_utils.ssh(db_ip, keyname, 'appscale-admin summary',
                                   method=subprocess.check_output)
      status_line = next((line for line in summary.split('\n')
                          if line.startswith(CASSANDRA_MONIT_WATCH_NAME)), '')
      retries -= 1
      if retries < 0:
        raise BRException('Unable to stop Cassandra')

  cassandra_dir = '{}/cassandra'.format(APPSCALE_DATA_DIR)
  for db_ip in db_ips:
    logger.info('Restoring Cassandra data on {}'.format(db_ip))
    clear_db = 'find {0} -regex ".*\.\(db\|txt\|log\)$" -exec rm {{}} \;'.\
      format(cassandra_dir)
    appscale_utils.ssh(db_ip, keyname, clear_db)

    if db_ip not in machines_without_restore:
      appscale_utils.ssh(db_ip, keyname,
                         'tar xf {} -C {}'.format(path, cassandra_dir))
      appscale_utils.ssh(db_ip, keyname,
                         'chown -R cassandra {}'.format(cassandra_dir))

    logger.info('Starting Cassandra on {}'.format(db_ip))
    retries = SERVICE_RETRIES
    status_line = MonitStates.UNMONITORED
    while MonitStates.RUNNING not in status_line:
      appscale_utils.ssh(
        db_ip, keyname,
        'appscale-start-service {}'.format(CASSANDRA_MONIT_WATCH_NAME),
        method=subprocess.call)
      time.sleep(3)
      summary = appscale_utils.ssh(db_ip, keyname, 'appscale-admin summary',
                                   method=subprocess.check_output)
      status_line = next((line for line in summary.split('\n')
                          if line.startswith(CASSANDRA_MONIT_WATCH_NAME)), '')
      retries -= 1
      if retries < 0:
        raise BRException('Unable to start Cassandra')

    appscale_utils.ssh(
      db_ip, keyname,
      'appscale-start-service {}'.format(CASSANDRA_MONIT_WATCH_NAME))

  logger.info('Waiting for Cassandra cluster to be ready')
  db_ip = db_ips[0]
  deadline = time.time() + SCHEMA_CHANGE_TIMEOUT
  while True:
    ready = True
    try:
      output = appscale_utils.ssh(
        db_ip, keyname, '{} status'.format(NODE_TOOL),
        method=subprocess.check_output)
      nodes_ready = len([line for line in output.split('\n')
                         if line.startswith('UN')])
      if nodes_ready < len(db_ips):
        ready = False
    except CalledProcessError:
      ready = False

    if ready:
      break

    if time.time() > deadline:
      logger.warning('Cassandra cluster still not ready.')
      break

    time.sleep(3)

  logger.info("Done with db restore.")
