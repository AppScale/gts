#!/usr/bin/env python

import os
import sys
import subprocess
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup/"))
import backup_exceptions
import backup_recovery_constants
import backup_recovery_helper
import cassandra_backup
import gcs_helper

from cassandra import shut_down_cassandra
from cassandra import start_cassandra
from cassandra.cassandra_interface import NODE_TOOL

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
    flexmock(backup_recovery_helper).\
      should_receive('get_snapshot_paths').and_return([])
    self.assertEquals(None, cassandra_backup.backup_data('', ''))

    # Test with at least one Cassandra snapshot and not enough disk space.
    flexmock(backup_recovery_helper).\
      should_receive('get_snapshot_paths').and_return(['some/snapshot'])
    flexmock(backup_recovery_helper).should_receive('enough_disk_space').\
      with_args('cassandra').and_return(False)
    self.assertEquals(None, cassandra_backup.backup_data('', ''))

    # Test with at least one Cassandra snapshot and failure to create the tar.
    flexmock(backup_recovery_helper).should_receive('enough_disk_space').\
      with_args('cassandra').and_return(True)
    flexmock(backup_recovery_helper).should_receive('tar_backup_files').\
      and_return(None)
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    flexmock(backup_recovery_helper).should_receive('move_secondary_backup').\
      and_return()
    self.assertEquals(None, cassandra_backup.backup_data('', ''))

    # Test with successful tar creation and local storage.
    flexmock(backup_recovery_helper).\
      should_receive('get_snapshot_paths').\
      and_return(['some/snapshot'])
    flexmock(backup_recovery_helper).should_receive('tar_backup_files').\
      and_return('some/tar')
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(backup_recovery_helper).should_receive('delete_secondary_backup').\
      and_return()
    self.assertIsNotNone(cassandra_backup.backup_data('', ''))

    # Test with GCS as storage backend and failure to upload.
    flexmock(gcs_helper).should_receive('upload_to_bucket').and_return(False)
    flexmock(backup_recovery_helper).should_receive('move_secondary_backup').\
      and_return()
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(None, cassandra_backup.backup_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with GCS as storage backend and successful upload.
    flexmock(gcs_helper).should_receive('upload_to_bucket').and_return(True)
    flexmock(backup_recovery_helper).should_receive('delete_secondary_backup').\
      and_return()
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
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
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(False, cassandra_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with successful Cassandra shutdown and failure to untar.
    flexmock(gcs_helper).should_receive('download_from_bucket').and_return(
      True)
    flexmock(shut_down_cassandra).should_receive('run').and_return(True)
    flexmock(cassandra_backup).should_receive('remove_old_data').and_return()
    flexmock(backup_recovery_helper).should_receive(
      'untar_backup_files').and_raise(backup_exceptions.BRException)
    flexmock(start_cassandra).should_receive('run').and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(False, cassandra_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test normal case for GCS.
    flexmock(gcs_helper).should_receive('download_from_bucket').and_return(
      True)
    flexmock(shut_down_cassandra).should_receive('run').and_return(True)
    flexmock(cassandra_backup).should_receive('remove_old_data').and_return()
    flexmock(backup_recovery_helper).should_receive('untar_backup_files').\
      and_return()
    flexmock(cassandra_backup).should_receive('restore_snapshots').and_return()
    flexmock(start_cassandra).should_receive('run').and_return()
    flexmock(cassandra_backup).should_receive('refresh_data').and_return()
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
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
    flexmock(backup_recovery_helper).should_receive(
      'untar_backup_files').and_raise(backup_exceptions.BRException)
    flexmock(start_cassandra).should_receive('run').and_return()
    self.assertEquals(False, cassandra_backup.restore_data('', ''))

    # Test normal case in local mode.
    flexmock(shut_down_cassandra).should_receive('run').and_return(True)
    flexmock(cassandra_backup).should_receive('remove_old_data').and_return()
    flexmock(backup_recovery_helper).should_receive('untar_backup_files').\
      and_return()
    flexmock(cassandra_backup).should_receive('restore_snapshots').and_return()
    flexmock(start_cassandra).should_receive('run').and_return()
    flexmock(cassandra_backup).should_receive('refresh_data').and_return()
    flexmock(cassandra_backup).should_receive('clear_old_snapshots').\
      and_return()
    self.assertEquals(True, cassandra_backup.restore_data('', ''))

if __name__ == "__main__":
  unittest.main()    
