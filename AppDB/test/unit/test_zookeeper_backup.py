#!/usr/bin/env python

import kazoo.client
import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup/"))
import backup_exceptions
import backup_recovery_constants
import backup_recovery_helper
import zookeeper_backup
import gcs_helper

from zkappscale.zktransaction import DEFAULT_HOST as ZK_DEFAULT_HOST
from zkappscale import shut_down_zookeeper

class TestZookeeperBackup(unittest.TestCase):
  """ A set of test cases for the Zookeeper backup. """

  def test_dump_zk(self):
    pass

  def test_recursive_dump(self):
    pass

  def test_flush_zk(self):
    pass

  def test_recursive_flush(self):
    pass

  def test_restore_zk(self):
    pass

  def test_shutdown_zookeeper(self):
    flexmock(shut_down_zookeeper).should_receive('run').times(1)
    zookeeper_backup.shutdown_zookeeper()

  def test_backup_data(self):
    # Test for unsupported storage backend.
    flexmock(backup_recovery_constants.StorageTypes()).\
      should_receive("get_storage_types").and_return([])
    self.assertEquals(None, zookeeper_backup.backup_data('blah', ''))

    # Test with failure to tar ZK data file.
    flexmock(zookeeper_backup).should_receive('dump_zk').\
      and_return()
    flexmock(backup_recovery_helper).should_receive('tar_backup_files').\
      and_return(None)
    flexmock(backup_recovery_helper).should_receive('remove').\
      and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    flexmock(backup_recovery_helper).should_receive('move_secondary_backup').\
      and_return()
    self.assertEquals(None, zookeeper_backup.backup_data('', ''))

    # Test with successful tar creation and local storage.
    flexmock(backup_recovery_helper).should_receive('tar_backup_files').\
      and_return('some/snapshot')
    flexmock(backup_recovery_helper).should_receive('remove').\
      and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_secondary_backup').\
      and_return()
    self.assertEquals('some/snapshot', zookeeper_backup.backup_data('', ''))

    # Test with GCS as storage backend and failure to upload.
    flexmock(gcs_helper).should_receive('upload_to_bucket').and_return(False)
    flexmock(backup_recovery_helper).should_receive('move_secondary_backup').\
      and_return()
    flexmock(backup_recovery_helper).should_receive('remove').\
      and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(None, zookeeper_backup.backup_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with GCS as storage backend and successful upload.
    flexmock(gcs_helper).should_receive('upload_to_bucket').and_return(True)
    flexmock(backup_recovery_helper).\
      should_receive('delete_secondary_backup').\
      and_return()
    flexmock(backup_recovery_helper).should_receive('remove').\
      and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    self.assertIsNotNone(zookeeper_backup.backup_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

  def test_restore_data(self):
    # Test for unsupported storage backend.
    flexmock(backup_recovery_constants.StorageTypes()).\
      should_receive("get_storage_types").and_return([])
    self.assertEquals(False, zookeeper_backup.restore_data('blah', ''))

    # Test with failure to download backup from GCS.
    flexmock(gcs_helper).should_receive('download_from_bucket').and_return(
      False)
    self.assertEquals(False, zookeeper_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with successful download from GCS and failure to untar.
    flexmock(gcs_helper).should_receive('download_from_bucket').and_return(
      True)
    flexmock(zookeeper_backup).should_receive('flush_zk').and_return()
    flexmock(backup_recovery_helper).should_receive(
      'untar_backup_files').and_raise(backup_exceptions.BRException)
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(False, zookeeper_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test normal case for GCS.
    flexmock(backup_recovery_helper).should_receive('untar_backup_files').\
      and_return()
    flexmock(zookeeper_backup).should_receive('restore_zk').and_return()
    flexmock(backup_recovery_helper).should_receive('remove').and_return()
    flexmock(backup_recovery_helper).\
      should_receive('delete_local_backup_file').\
      and_return()
    self.assertEquals(True, zookeeper_backup.restore_data(
      backup_recovery_constants.StorageTypes.GCS, ''))

    # Test with failure to untar in local mode.
    flexmock(zookeeper_backup).should_receive('flush_zk').and_return()
    flexmock(backup_recovery_helper).should_receive('untar_backup_files').\
      and_raise(backup_exceptions.BRException)
    flexmock(zookeeper_backup).should_receive('restore_zk').and_return()
    flexmock(backup_recovery_helper).should_receive('remove').and_return()
    self.assertEquals(False, zookeeper_backup.restore_data('', ''))

    # Test normal case in local mode.
    flexmock(backup_recovery_helper).should_receive('untar_backup_files').\
      and_return()
    flexmock(zookeeper_backup).should_receive('restore_zk').and_return()
    flexmock(backup_recovery_helper).should_receive('remove').and_return()
    self.assertEquals(True, zookeeper_backup.restore_data('', ''))

if __name__ == "__main__":
  unittest.main()    
