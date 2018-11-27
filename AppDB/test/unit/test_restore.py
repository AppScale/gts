#!/usr/bin/env python

""" Unit tests for restore_data.py """

import argparse
import glob
import time
import unittest

from appscale.datastore import appscale_datastore_batch
from appscale.datastore import datastore_distributed
from appscale.datastore.backup.datastore_restore import DatastoreRestore
from appscale.datastore.index_manager import IndexManager
from appscale.datastore.zkappscale.zktransaction import ZKTransactionException
from appscale.datastore.zkappscale.transaction_manager import (
  TransactionManager)
from flexmock import flexmock


class FakeArgumentParser(object):
  def __init__(self):
    pass
  def parse_args(self):
    return argparse.Namespace(app_id='app_id',
      backup_dir='some/dir', clear_datastore=False, debug=False)


class FakeDatastore(object):
  def __init__(self):
    pass

  def range_query(self, table, schema, start, end, batch_size,
    start_inclusive=True, end_inclusive=True):
    return []

  def valid_data_version_sync(self):
    return True


class FakeZookeeper(object):
  def __init__(self):
    pass
  def get_lock_with_path(self, path):
    return True
  def close(self):
    return

FAKE_ENCODED_ENTITY = \
  {'guestbook27\x00\x00Guestbook:default_guestbook\x01Greeting:1\x01':
    {
      'txnID': '1',
      'entity': 'j@j\x0bguestbook27r1\x0b\x12\tGuestbook"\x11default_guestbook'
                '\x0c\x0b\x12\x08Greeting\x18\xaa\xe7\xfb\x18\x0cr=\x1a\x06'
                'author \x00*1CJ\x07a@a.comR\tgmail.com\x90\x01\x00\x9a\x01'
                '\x15120912168209190119424Dr\x15\x08\x07\x1a\x04date \x00*\t'
                '\x08\xf6\xfc\xd2\x92\xa4\xa3\xc3\x02z\x17\x08\x0f\x1a\x07'
                'content \x00*\x08\x1a\x06111111\x82\x01 \x0b\x12\tGuestbook"'
                '\x11default_guestbook\x0c'
    }
  }

FAKE_PICKLED_ENTITY = """
S'j@j\x0bguestbook27r1\x0b\x12\tGuestbook"\x11default_guestbook\x0c\x0b\x12\x08Greeting\x18\xaa\xe7\xfb\x18\x0cr=\x1a\x06author \x00*1CJ\x07a@a.comR\tgmail.com\x90\x01\x00\x9a\x01\x15120912168209190119424Dr\x15\x08\x07\x1a\x04date \x00*\t\x08\xf6\xfc\xd2\x92\xa4\xa3\xc3\x02z\x17\x08\x0f\x1a\x07content \x00*\x08\x1a\x06111111\x82\x01 \x0b\x12\tGuestbook"\x11default_guestbook\x0c'
p1
.
"""


class TestRestore(unittest.TestCase):
  """
  A set of test cases for the datastore restore thread.
  """
  def test_init(self):
    zookeeper = flexmock()
    fake_restore = flexmock(DatastoreRestore('app_id', 'backup/dir',
      zookeeper, "cassandra"))

  def test_stop(self):
    pass

  def test_run(self):
    zk_client = flexmock()
    zk_client.should_receive('add_listener')

    zookeeper = flexmock(handle=zk_client)
    ds_factory = flexmock(appscale_datastore_batch.DatastoreFactory)
    ds_factory.should_receive("getDatastore").and_return(FakeDatastore())
    flexmock(datastore_distributed).should_receive(
      'DatastoreDistributed').and_return()
    flexmock(TransactionManager).should_receive('__new__')
    flexmock(IndexManager).should_receive('__new__')
    fake_restore = flexmock(DatastoreRestore('app_id', 'backup/dir',
      zookeeper, "cassandra"))

    # Test with failure to get the restore lock.
    fake_restore.should_receive('get_restore_lock').and_return(False)
    flexmock(time).should_receive('sleep').and_return()

    # Test with successfully obtaining the restore lock.
    fake_restore.should_receive('get_restore_lock').and_return('some/path')
    fake_restore.should_receive('run_restore').and_return()

    # ... and successfully releasing the lock.
    zookeeper.should_receive('release_lock_with_path').and_return(True)
    self.assertEquals(None, fake_restore.run())

    # ... and failure to release the lock.
    zookeeper.should_receive('release_lock_with_path').\
      and_raise(ZKTransactionException)
    self.assertEquals(None, fake_restore.run())

  def test_get_restore_lock(self):
    zookeeper = flexmock()
    zookeeper.should_receive("get_lock_with_path").and_return(True)
    fake_restore = flexmock(DatastoreRestore('app_id', 'backup/dir',
      zookeeper, "cassandra"))

    # Test with successfully obtaining the restore lock.
    self.assertEquals(True, fake_restore.get_restore_lock())

  def test_store_entity_batch(self):
    # TODO
    pass

  def test_read_from_file_and_restore(self):
    # TODO
    pass

  def test_run_restore(self):
    zookeeper = flexmock()
    fake_restore = flexmock(DatastoreRestore('app_id', 'backup/dir',
      zookeeper, "cassandra"))

    flexmock(glob).should_receive('glob').and_return(['some/file.backup'])
    fake_restore.should_receive('read_from_file_and_restore').and_return()

    fake_restore.run_restore()

  def test_init_parser(self):
    pass

  def test_app_is_deployed(self):
    pass

  def test_backup_dir_exists(self):
    pass

  def test_main(self):
    # TODO
    pass


if __name__ == "__main__":
  unittest.main()
