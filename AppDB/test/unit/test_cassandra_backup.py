#!/usr/bin/env python

import os
import sys
import tarfile
import subprocess
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup/"))
import backup_exceptions
import backup_recovery_constants
import backup_recovery_helper
import cassandra_backup
import gcs_helper

sys.path.append(os.path.join(os.path.dirname(__file__), "../../cassandra/"))
import shut_down_cassandra
import start_cassandra
from cassandra_interface import NODE_TOOL

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

  def test_clear_old_snapshots(self):
    flexmock(subprocess).should_receive('check_call').with_args([NODE_TOOL,
      'clearsnapshot']).and_return().times(1)
    cassandra_backup.clear_old_snapshots()

  def test_create_snapshot(self):
    flexmock(subprocess).should_receive('check_call').with_args([NODE_TOOL,
      'snapshot']).and_return().times(1)
    cassandra_backup.create_snapshot()

  def test_delete_local_backup_file(self):
    flexmock(backup_recovery_helper).should_receive('remove').\
      and_return().times(1)
    cassandra_backup.delete_local_backup_file()

  def test_delete_secondary_backup(self):
    flexmock(backup_recovery_helper).should_receive('remove').\
      and_return().times(1)
    cassandra_backup.delete_secondary_backup()

  def test_enough_disk_space(self):
    # Test with inadequate disk space.
    flexmock(cassandra_backup).should_receive(
      'get_available_disk_space').and_return(1)
    flexmock(cassandra_backup).should_receive(
      'get_backup_size').and_return(2)
    self.assertEquals(False, cassandra_backup.enough_disk_space())

    # Test with adequate disk space available.
    flexmock(cassandra_backup).should_receive(
      'get_available_disk_space').and_return(2)
    flexmock(cassandra_backup).should_receive(
      'get_backup_size').and_return(1)
    self.assertEquals(True, cassandra_backup.enough_disk_space())

  def test_get_available_disk_space(self):
    pass

  def test_get_backup_size(self):
    pass

  def test_get_cassandra_snapshot_file_names(self):
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

  def test_move_secondary_backup(self):
    flexmock(backup_recovery_helper).should_receive("rename").\
      and_return().and_return().times(1)
    cassandra_backup.move_secondary_backup()

  def test_refresh_data(self):
    flexmock(subprocess).should_receive("check_call").and_return().\
      at_least.times(1)
    cassandra_backup.refresh_data()

  def test_remove_old_data(self):
    pass

  def test_restore_snapshots(self):
    pass

  def test_shutdown_datastore(self):
    flexmock(shut_down_cassandra).should_receive('run').times(1)
    cassandra_backup.shutdown_datastore()

  def test_tar_backup_files(self):
    # Test with no disk space availability.
    flexmock(backup_recovery_helper).should_receive('mkdir').\
      with_args(cassandra_backup.BACKUP_DIR_LOCATION).\
      and_return(True)
    flexmock(cassandra_backup).should_receive(
      "enough_disk_space").and_return(False)
    self.assertEquals(None, cassandra_backup.tar_backup_files([]))

    # Test with enough disk space available.
    flexmock(cassandra_backup).should_receive(
      "enough_disk_space").and_return(True)
    flexmock(backup_recovery_helper).should_receive("rename").and_return(True)
    fake_tar = FakeTar()
    flexmock(tarfile).should_receive('open').and_return(fake_tar)
    cassandra_backup.tar_backup_files(['1', '2'])
    self.assertEquals(fake_tar.add_count, 2)

  def test_untar_backup_files(self):
    pass

  def test_backup_data(self):
    # Test for unsupported storage backend.
    flexmock(backup_recovery_constants.StorageTypes()).\
      should_receive("get_storage_types").and_return([])
    self.assertEquals(None, cassandra_backup.backup_data('blah', ''))

    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()

    # Test with failure to create new snapshots.
    flexmock(cassandra_backup).should_receive('create_snapshot').\
      and_return(False)
    self.assertEquals(None, cassandra_backup.backup_data('', ''))

    # Test with missing Cassandra snapshots.
    flexmock(cassandra_backup).should_receive('create_snapshot').\
      and_return(True)
    flexmock(cassandra_backup).\
      should_receive('get_cassandra_snapshot_file_names').\
      and_return([])
    self.assertEquals(None, cassandra_backup.backup_data('', ''))

    # Test with at least one Cassandra snapshot and failure to create the tar.
    flexmock(cassandra_backup).\
      should_receive('get_cassandra_snapshot_file_names').\
      and_return(['some/snapshot'])
    flexmock(cassandra_backup).should_receive('tar_backup_files').\
      and_return(None)
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(cassandra_backup).should_receive('delete_local_backup_file').\
      and_return()
    flexmock(cassandra_backup).should_receive('move_secondary_backup').\
      and_return()
    self.assertEquals(None, cassandra_backup.backup_data('', ''))

    # Test with successful tar creation and local storage.
    flexmock(cassandra_backup).\
      should_receive('get_cassandra_snapshot_file_names').\
      and_return(['some/snapshot'])
    flexmock(cassandra_backup).should_receive('tar_backup_files').\
      and_return('some/tar')
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(cassandra_backup).should_receive('delete_secondary_backup').\
      and_return()
    self.assertIsNotNone(cassandra_backup.backup_data('', ''))

    # Test with GCS as storage backend and failure to upload.
    flexmock(gcs_helper).should_receive('upload_to_bucket').and_return(False)
    flexmock(cassandra_backup).should_receive('move_secondary_backup').\
      and_return()
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(cassandra_backup).should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(None, cassandra_backup.backup_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with GCS as storage backend and successful upload.
    flexmock(gcs_helper).should_receive('upload_to_bucket').and_return(True)
    flexmock(cassandra_backup).should_receive('delete_secondary_backup').\
      and_return()
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(cassandra_backup).should_receive('delete_local_backup_file').\
      and_return()
    self.assertIsNotNone(cassandra_backup.backup_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

  def test_restore_data(self):
    # Test for unsupported storage backend.
    flexmock(backup_recovery_constants.StorageTypes()).\
      should_receive("get_storage_types").and_return([])
    self.assertEquals(False, cassandra_backup.restore_data('blah', ''))

    # Test with failure to download backup from GCS.
    flexmock(gcs_helper).should_receive('download_from_bucket').and_return(
      False)
    self.assertEquals(False, cassandra_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with successful download from GCS and failure to shut down Cassandra.
    flexmock(gcs_helper).should_receive('download_from_bucket').and_return(
      True)
    flexmock(shut_down_cassandra).should_receive('run').and_return(False)
    flexmock(cassandra_backup).should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(False, cassandra_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with successful Cassandra shutdown and failure to untar.
    flexmock(gcs_helper).should_receive('download_from_bucket').and_return(
      True)
    flexmock(shut_down_cassandra).should_receive('run').and_return(True)
    flexmock(cassandra_backup).should_receive('remove_old_data').and_return()
    flexmock(cassandra_backup).should_receive(
      'untar_backup_files').and_raise(backup_exceptions.BRException)
    flexmock(start_cassandra).should_receive('run').and_return()
    flexmock(cassandra_backup).should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(False, cassandra_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test normal case for GCS.
    flexmock(gcs_helper).should_receive('download_from_bucket').and_return(
      True)
    flexmock(shut_down_cassandra).should_receive('run').and_return(True)
    flexmock(cassandra_backup).should_receive('remove_old_data').and_return()
    flexmock(cassandra_backup).should_receive('untar_backup_files').and_return()
    flexmock(cassandra_backup).should_receive('restore_snapshots').and_return()
    flexmock(start_cassandra).should_receive('run').and_return()
    flexmock(cassandra_backup).should_receive('refresh_data').and_return()
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(cassandra_backup).should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(True, cassandra_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with failure to shut down Cassandra in local mode.
    flexmock(shut_down_cassandra).should_receive('run').and_return(False)
    self.assertEquals(False, cassandra_backup.restore_data('', ''))

    # Test with successful Cassandra shutdown and failure to untar in local
    # mode.
    flexmock(shut_down_cassandra).should_receive('run').and_return(True)
    flexmock(cassandra_backup).should_receive('remove_old_data').and_return()
    flexmock(cassandra_backup).should_receive(
      'untar_backup_files').and_raise(backup_exceptions.BRException)
    flexmock(start_cassandra).should_receive('run').and_return()
    self.assertEquals(False, cassandra_backup.restore_data('', ''))

    # Test normal case in local mode.
    flexmock(shut_down_cassandra).should_receive('run').and_return(True)
    flexmock(cassandra_backup).should_receive('remove_old_data').and_return()
    flexmock(cassandra_backup).should_receive('untar_backup_files').and_return()
    flexmock(cassandra_backup).should_receive('restore_snapshots').and_return()
    flexmock(start_cassandra).should_receive('run').and_return()
    flexmock(cassandra_backup).should_receive('refresh_data').and_return()
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    self.assertEquals(True, cassandra_backup.restore_data('', ''))

if __name__ == "__main__":
  unittest.main()    
