#!/usr/bin/env python

""" Unit tests for backup_data.py """

import os
import re
import sys
import time
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import backup_data as backup
import appscale_datastore_batch
from dbconstants import AppScaleDBConnectionError
import entity_utils

from zkappscale.zktransaction import ZKTransactionException

class FakeDatastore(object):
  def __init__(self):
    pass
  def range_query(self, table, schema, start, end, batch_size,
    start_inclusive=True, end_inclusive=True):
    return []

FAKE_ENCODED_ENTITY = \
  {'guestbook27\x00\x00Guestbook:default_guestbook\x01Greeting:1\x01':
    {
      'txnID': '1',
      'entity': 'j@j\x0bguestbook27r1\x0b\x12\tGuestbook"\x11default_guestbook\x0c\x0b\x12\x08Greeting\x18\xaa\xe7\xfb\x18\x0cr=\x1a\x06author \x00*1CJ\x07a@a.comR\tgmail.com\x90\x01\x00\x9a\x01\x15120912168209190119424Dr\x15\x08\x07\x1a\x04date \x00*\t\x08\xf6\xfc\xd2\x92\xa4\xa3\xc3\x02z\x17\x08\x0f\x1a\x07content \x00*\x08\x1a\x06111111\x82\x01 \x0b\x12\tGuestbook"\x11default_guestbook\x0c'
    }
  }

FAKE_PICKLED_ENTITY = """
S'j@j\x0bguestbook27r1\x0b\x12\tGuestbook"\x11default_guestbook\x0c\x0b\x12\x08Greeting\x18\xaa\xe7\xfb\x18\x0cr=\x1a\x06author \x00*1CJ\x07a@a.comR\tgmail.com\x90\x01\x00\x9a\x01\x15120912168209190119424Dr\x15\x08\x07\x1a\x04date \x00*\t\x08\xf6\xfc\xd2\x92\xa4\xa3\xc3\x02z\x17\x08\x0f\x1a\x07content \x00*\x08\x1a\x06111111\x82\x01 \x0b\x12\tGuestbook"\x11default_guestbook\x0c'
p1
.
"""

class TestBackup(unittest.TestCase):
  """
  A set of test cases for the datastore backup thread.
  """
  def test_init(self):
    zookeeper = flexmock()
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))
    fake_backup.should_receive('set_filename').and_return()

  def test_stop(self):
    pass

  def test_run(self):
    zookeeper = flexmock()
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))

    # Test with failure to get the backup lock.
    fake_backup.should_receive('get_backup_lock').and_return(False)
    flexmock(time).should_receive('sleep').and_return()

    # Test with successfully obtaining the backup lock.
    fake_backup.should_receive('get_backup_lock').and_return('some/path')
    fake_backup.should_receive('run_backup').and_return()

    # ... and successfully releasing the lock.
    zookeeper.should_receive('release_lock_with_path').and_return(True)
    self.assertEquals(None, fake_backup.run())

    # ... and failure to release the lock.
    zookeeper.should_receive('release_lock_with_path').\
      and_raise(ZKTransactionException)
    self.assertEquals(None, fake_backup.run())

  def test_get_backup_lock(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_lock_with_path").and_return(True)
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))

    # Test with successfully obtaining the backup lock.
    self.assertEquals(True, fake_backup.get_backup_lock())

  def test_get_entity_batch(self):
    zookeeper = flexmock()
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))
    fake_backup.db_access = FakeDatastore()
    self.assertEquals([], fake_backup.get_entity_batch('app_id', 100, True))

  def test_verify_entity(self):
    zookeeper = flexmock()
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))
    flexmock(entity_utils).\
      should_receive('get_prefix_from_entity_key').and_return('app_prefix')

    # Test with valid entity.
    zookeeper.should_receive('is_blacklisted').and_return(False)
    self.assertEquals(True, fake_backup.verify_entity('key', 'txn_id'))

    # Test with blacklisted entity.
    zookeeper.should_receive('is_blacklisted').and_return(True)
    self.assertEquals(False, fake_backup.verify_entity('key', 'txn_id'))

    # Test with exception tossed.
    zookeeper.should_receive('is_blacklisted').and_raise(ZKTransactionException)
    flexmock(time).should_receive('sleep').and_return()
    flexmock(entity_utils).\
      should_receive('get_prefix_from_entity_key').and_return('app_prefix')
    fake_backup.verify_entity('key', 'txn_id')

  def test_set_filename(self):
    pass

  def test_dump_entity(self):
    zookeeper = flexmock()
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))
    fake_backup.should_receive('set_filename').at_most().times(1).and_return()
    fake_backup.filename = '/root/backup'
    self.assertEquals(True, fake_backup.dump_entity(FAKE_ENCODED_ENTITY))

  def test_process_entity(self):
    zookeeper = flexmock()
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))

    flexmock(re).should_receive('match').at_least().times(2).and_return(None)
    flexmock(entity_utils).\
      should_receive('get_prefix_from_entity_key').and_return('app_prefix')
    flexmock(entity_utils).\
      should_receive('get_root_key_from_entity_key').and_return('root_key')
    fake_backup.zoo_keeper.should_receive('get_transaction_id').\
      and_return('txn_id')

    # Test successful operation.
    fake_backup.zoo_keeper.should_receive('acquire_lock').and_return(True)

    # ... with valid entity.
    fake_backup.should_receive('verify_entity').and_return(True)
    fake_backup.should_receive('dump_entity').and_return(True)
    fake_backup.zoo_keeper.should_receive("release_lock").and_return()
    self.assertEquals(True, fake_backup.process_entity(FAKE_ENCODED_ENTITY))

    # ... with blacklisted entity.
    fake_backup.should_receive('verify_entity').and_return(False)
    flexmock(entity_utils).should_receive('fetch_journal_entry').\
      and_return(FAKE_ENCODED_ENTITY)
    fake_backup.should_receive('dump_entity').and_return(True)
    fake_backup.zoo_keeper.should_receive("release_lock").and_return()
    self.assertEquals(True, fake_backup.process_entity(FAKE_ENCODED_ENTITY))

    # Test with failure to get the entity lock.
    fake_backup.zoo_keeper.should_receive('acquire_lock').and_return(False)
    fake_backup.zoo_keeper.\
      should_receive("notify_failed_transaction").and_return()
    fake_backup.zoo_keeper.should_receive("release_lock").and_return()
    flexmock(time).should_receive('sleep').and_return()
    fake_backup.zoo_keeper.should_receive('acquire_lock').and_return(True)
    self.assertEquals(True, fake_backup.process_entity(FAKE_ENCODED_ENTITY))

  def test_run_backup(self):
    zookeeper = flexmock()

    # Test with entities.
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))
    fake_backup.should_receive("get_entity_batch").\
      and_return([FAKE_ENCODED_ENTITY])
    fake_backup.should_receive("process_entity").\
      with_args(FAKE_ENCODED_ENTITY).and_return()
    fake_backup.should_receive("get_entity_batch").\
      and_return([])
    self.assertEquals(None, fake_backup.run_backup())

    # Test with no entities.
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))
    fake_backup.should_receive("get_entity_batch").and_return([])
    self.assertEquals(None, fake_backup.run_backup())

    # Test with exception tossed.
    fake_backup = flexmock(backup.DatastoreBackup('app_id', zookeeper,
      "cassandra"))
    fake_backup.should_receive("get_entity_batch").\
      and_raise(AppScaleDBConnectionError)
    flexmock(time).should_receive('sleep').and_return()
    fake_backup.should_receive("get_entity_batch").and_return([])
    self.assertEquals(None, fake_backup.run_backup())

if __name__ == "__main__":
  unittest.main()
