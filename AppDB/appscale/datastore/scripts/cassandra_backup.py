""" Cassandra data backup. """

import argparse
import logging
import os
import sys

from ..backup.backup_exceptions import AmbiguousKeyException
from ..backup.backup_exceptions import NoKeyException
from ..backup.cassandra_backup import backup_data
from ..backup.cassandra_backup import restore_data
from ..unpackaged import APPSCALE_LIB_DIR
from ..unpackaged import INFRASTRUCTURE_MANAGER_DIR

sys.path.append(APPSCALE_LIB_DIR)
from constants import LOG_FORMAT

sys.path.append(INFRASTRUCTURE_MANAGER_DIR)
from utils.utils import KEY_DIRECTORY


def main():
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser(
    description='Backup or restore Cassandra data.')
  io_group = parser.add_mutually_exclusive_group(required=True)
  io_group.add_argument('--input',
                        help='The location on each of the DB machines to use '
                        'for restoring data.')
  io_group.add_argument('--output',
                        help='The location to store the backup on each of '
                        'the DB machines.')

  parser.add_argument('--verbose', action='store_true',
                      help='Enable debug-level logging.')
  parser.add_argument('--force', action='store_true',
                      help='Restore without prompting.')

  args = parser.parse_args()

  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  keys = [key for key in os.listdir(KEY_DIRECTORY) if key.endswith('.key')]
  if len(keys) > 1:
    raise AmbiguousKeyException(
      'There is more than one ssh key in {}'.format(KEY_DIRECTORY))
  if not keys:
    raise NoKeyException('There is no ssh key in {}'.format(KEY_DIRECTORY))
  keyname = keys[0].split('.')[0]

  if args.input is not None:
    restore_data(args.input, keyname, force=args.force)
  else:
    backup_data(args.output, keyname)
