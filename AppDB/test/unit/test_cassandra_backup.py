#!/usr/bin/env python

import datetime
import os
import sys
import tarfile
import time
import subprocess
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup/"))  
import cassandra_backup

class FakeTar():
  def __init__(self):
    self.add_count = 0
  def add(self, name):
    self.add_count += 1
  def close(self):
    pass

class TestCassandraBackup(unittest.TestCase):
  """
  A set of test cases for the cassandra backup.
  """
  def test_get_snapshot_file_names(self):
    os_mock = flexmock(os)
    os_mock.should_call('walk')
    os_mock.should_receive('walk').and_yield(('/snapshots/xxx', ['dirname'], 
      '')).once()
    self.assertEquals(['/snapshots/xxx'], 
      cassandra_backup.get_cassandra_snapshot_file_names())

   # Test with no files present that match the filters.
    os_mock.should_receive('walk').and_yield(('', ['dirname'], 
      ['/what/what'])).once()
    self.assertEquals([], cassandra_backup.get_cassandra_snapshot_file_names())

  def test_tar_snapshot(self):
    flexmock(subprocess)
    subprocess.should_receive('call').\
      with_args("rm", "-f", cassandra_backup.BACKUP_FILE_LOCATION)
    flexmock(tarfile)
    fake_tar = FakeTar()
    tarfile.should_receive('open').and_return(fake_tar)
    cassandra_backup.tar_backup_files(['1', '2'])
    self.assertEquals(fake_tar.add_count, 2)

  def test_backup_data(self):
    flexmock(cassandra_backup).should_receive('clear_old_snapshots')
    flexmock(cassandra_backup).should_receive('create_snapshot').and_return(
      True)
    flexmock(cassandra_backup).should_receive(
      'get_cassandra_snapshot_file_names').and_return(['some file'])
    flexmock(cassandra_backup).should_receive('tar_backup_files').and_return(
      'some tar')
    cassandra_backup.backup_data("", "")

if __name__ == "__main__":
  unittest.main()    
