#!/usr/bin/env python

import re
import sys
import subprocess
import unittest
from flexmock import flexmock

from appscale.datastore.backup import backup_exceptions
from appscale.datastore.backup import cassandra_backup
from appscale.datastore.cassandra_env.cassandra_interface import NODE_TOOL
from appscale.datastore.unpackaged import APPSCALE_LIB_DIR
from appscale.datastore.unpackaged import INFRASTRUCTURE_MANAGER_DIR

sys.path.append(APPSCALE_LIB_DIR)
import appscale_info

sys.path.append(INFRASTRUCTURE_MANAGER_DIR)
from utils import utils


class TestCassandraBackup(unittest.TestCase):
  """ A set of test cases for the Cassandra backup. """

  def test_clear_old_snapshots(self):
    flexmock(subprocess).should_receive('check_call').with_args([NODE_TOOL,
      'clearsnapshot']).and_return().times(1)
    cassandra_backup.clear_old_snapshots()

  def test_create_snapshot(self):
    flexmock(subprocess).should_receive('check_call').with_args([NODE_TOOL,
      'snapshot']).and_return().times(1)
    cassandra_backup.create_snapshot()

  def test_remove_old_data(self):
    pass

  def test_restore_snapshots(self):
    pass

  def test_backup_data(self):
    db_ips = ['192.168.33.10', '192.168.33.11']
    keyname = 'key1'
    path = '~/cassandra_backup.tar'

    flexmock(appscale_info).should_receive('get_db_ips').and_return(db_ips)

    flexmock(utils).should_receive('ssh').with_args(re.compile('^192.*'),
      keyname, re.compile('.*snapshot$'))

    flexmock(utils).should_receive('ssh').with_args(db_ips[0], keyname,
      re.compile('.*du -s.*'), method=subprocess.check_output).\
      and_return('200 file1\n500 file2\n')
    flexmock(utils).should_receive('ssh').with_args(db_ips[1], keyname,
      re.compile('.*du -s.*'), method=subprocess.check_output).\
      and_return('900 file1\n100 file2\n')

    # Assume first DB machine does not have enough space.
    flexmock(utils).should_receive('ssh').with_args(db_ips[0], keyname,
      re.compile('^df .*'), method=subprocess.check_output).\
      and_return('headers\ndisk blocks used 100 etc')
    self.assertRaises(backup_exceptions.BRException,
      cassandra_backup.backup_data, path, keyname)

    flexmock(utils).should_receive('ssh').with_args(db_ips[0], keyname,
      re.compile('^df .*'), method=subprocess.check_output).\
      and_return('headers\ndisk blocks used 2000 etc')
    flexmock(utils).should_receive('ssh').with_args(db_ips[1], keyname,
      re.compile('^df .*'), method=subprocess.check_output).\
      and_return('headers\ndisk blocks used 3000 etc')

    flexmock(utils).should_receive('ssh').with_args(re.compile('^192.*'),
      keyname, re.compile('.*tar --transform.*'))
    cassandra_backup.backup_data(path, keyname)

  def test_restore_data(self):
    db_ips = ['192.168.33.10', '192.168.33.11']
    keyname = 'key1'
    path = '~/cassandra_backup.tar'

    flexmock(appscale_info).should_receive('get_db_ips').and_return(db_ips)

    flexmock(utils).should_receive('ssh').with_args(re.compile('^192.*'),
      keyname, 'ls {}'.format(path), method=subprocess.call).and_return(0)

    flexmock(utils).should_receive('ssh').with_args(re.compile('^192.*'),
      keyname, 'monit summary', method=subprocess.check_output).\
      and_return('summary output')
    flexmock(utils).should_receive('monit_status').and_return('Not monitored')

    flexmock(utils).should_receive('ssh').with_args(re.compile('^192.*'),
      keyname, re.compile('^find.* -exec rm .*'))
    flexmock(utils).should_receive('ssh').with_args(re.compile('^192.*'),
      keyname, re.compile('^tar xf .*'))
    flexmock(utils).should_receive('ssh').with_args(re.compile('^192.*'),
      keyname, re.compile('^monit start .*'))
    flexmock(utils).should_receive('ssh').with_args(
      re.compile('^192.*'), keyname, re.compile('^chown -R cassandra /opt/.*'))

    cassandra_backup.restore_data(path, keyname)


if __name__ == "__main__":
  unittest.main()    
