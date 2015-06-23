#!/usr/bin/env python

import os
import sys
import tarfile
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup/"))
import backup_recovery_helper

class FakeTar():
  def __init__(self):
    self.add_count = 0
  def add(self, name):
    self.add_count += 1
  def close(self):
    pass

class TestBRHelper(unittest.TestCase):
  """ A set of test cases for the BR helper functions. """

  def test_delete_local_backup_file(self):
    flexmock(backup_recovery_helper).should_receive('remove').\
      and_return().times(1)
    backup_recovery_helper.delete_local_backup_file('foo')

  def test_delete_secondary_backup(self):
    flexmock(backup_recovery_helper).should_receive('remove').\
      and_return().times(1)
    backup_recovery_helper.delete_secondary_backup('foo')

  def test_does_file_exist(self):
    flexmock(os.path).should_receive('isfile').and_return().at_least().times(1)
    backup_recovery_helper.does_file_exist('foo')

  def test_enough_disk_space(self):
    # Test with inadequate disk space.
    flexmock(backup_recovery_helper).should_receive(
      'get_available_disk_space').and_return(1)
    flexmock(backup_recovery_helper).should_receive(
      'get_backup_size').and_return(2)
    self.assertEquals(False, backup_recovery_helper.enough_disk_space('foo'))

    # Test with adequate disk space available.
    flexmock(backup_recovery_helper).should_receive(
      'get_available_disk_space').and_return(2)
    flexmock(backup_recovery_helper).should_receive(
      'get_backup_size').and_return(1)
    self.assertEquals(True, backup_recovery_helper.enough_disk_space('foo'))

  def test_get_available_disk_space(self):
    pass

  def test_get_backup_size(self):
    pass

  def test_get_snapshot_paths(self):
    os_mock = flexmock(os)
    os_mock.should_call('walk')
    os_mock.should_receive('walk').and_yield(('/snapshots/xxx', ['dirname'],
      '')).once()
    self.assertEquals(['/snapshots/xxx'],
      backup_recovery_helper.get_snapshot_paths('cassandra'))

   # Test with no files present that match the filters.
    self.assertEquals([], backup_recovery_helper.get_snapshot_paths('foo'))

  def test_move_secondary_backup(self):
    flexmock(backup_recovery_helper).should_receive("rename").\
      and_return().times(1)
    backup_recovery_helper.move_secondary_backup('foo')

  def test_mkdir(self):
    flexmock(os).should_receive('mkdir').and_return().at_least().times(1)
    self.assertEquals(True, backup_recovery_helper.mkdir('foo'))

    flexmock(os).should_receive('mkdir').and_raise(OSError)
    self.assertEquals(False, backup_recovery_helper.mkdir('foo'))

  def test_rename(self):
    flexmock(os).should_receive('rename').and_return().at_least().times(1)
    self.assertEquals(True, backup_recovery_helper.rename('foo', 'bar'))

    flexmock(os).should_receive('rename').and_raise(OSError)
    self.assertEquals(False, backup_recovery_helper.rename('foo', 'bar'))

  def test_remove(self):
    flexmock(os).should_receive('remove').and_return().at_least().times(1)
    self.assertEquals(True, backup_recovery_helper.remove('foo'))

    flexmock(os).should_receive('remove').and_raise(OSError)
    self.assertEquals(False, backup_recovery_helper.remove('foo'))

  def test_tar_backup_files(self):
    flexmock(backup_recovery_helper).should_receive("rename").and_return(True)
    fake_tar = FakeTar()
    flexmock(tarfile).should_receive('open').and_return(fake_tar)
    backup_recovery_helper.tar_backup_files(['1', '2'], 'some/tar')
    self.assertEquals(fake_tar.add_count, 2)

  def test_untar_backup_files(self):
    pass

if __name__ == "__main__":
  unittest.main()    
