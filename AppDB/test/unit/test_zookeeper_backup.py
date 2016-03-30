#!/usr/bin/env python

import kazoo.client
import os
import re
import subprocess
import sys
import tempfile
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
from backup import zookeeper_backup

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../lib'))
import appscale_info

sys.path.append(
  os.path.join(os.path.dirname(__file__), '../../../InfrastructureManager'))
from utils import utils

from zkappscale import shut_down_zookeeper

class TestZookeeperBackup(unittest.TestCase):
  """ A set of test cases for the Zookeeper backup. """

  def test_dump_zk(self):
    pass

  def test_recursive_dump(self):
    pass

  def test_recursive_flush(self):
    pass

  def test_restore_zk(self):
    pass

  def test_shutdown_zookeeper(self):
    flexmock(shut_down_zookeeper).should_receive('run').times(1)
    zookeeper_backup.shutdown_zookeeper()

  def test_backup_data(self):
    zk_ips = ['192.168.33.12', '192.168.33.13']
    zk_ip = zk_ips[0]
    path = '~/zookeeper_backup.tar.gz'
    keyname = 'key1'

    flexmock(subprocess).should_receive('call').and_return(0)

    flexmock(appscale_info).should_receive('get_zk_node_ips').\
      and_return(zk_ips)

    flexmock(utils).should_receive('ssh').with_args(zk_ip, keyname,
      'monit stop -g zookeeper')
    flexmock(utils).should_receive('ssh').with_args(zk_ip, keyname,
      re.compile('^tar czf .*'))
    flexmock(utils).should_receive('scp_from').with_args(zk_ip, keyname,
      re.compile('.*zk_backup_.*.tar.gz$'), path)
    flexmock(utils).should_receive('ssh').with_args(zk_ip, keyname,
      re.compile('^rm -f .*'))
    flexmock(utils).should_receive('ssh').with_args(zk_ip, keyname,
      'monit start -g zookeeper')

  def test_restore_data(self):
    zk_ips = ['192.168.33.12', '192.168.33.13']

    flexmock(subprocess).should_receive('call').and_return(1)

    flexmock(appscale_info).should_receive('get_zk_node_ips').\
      and_return(zk_ips)

    flexmock(utils).should_receive('zk_service_name').and_return('zookeeper')

    flexmock(utils).should_receive('scp_to')
    flexmock(utils).should_receive('ssh')

    zk_file = flexmock(close=lambda: None)
    flexmock(tempfile).should_receive('TemporaryFile').and_return(zk_file)
    zk = flexmock(start=lambda: None, stop=lambda: None)
    flexmock(kazoo.client.KazooClient).should_receive('__init__').\
      and_return(zk)
    flexmock(zookeeper_backup).should_receive('recursive_dump')
    flexmock(zookeeper_backup).should_receive('recursive_flush')

if __name__ == "__main__":
  unittest.main()    
