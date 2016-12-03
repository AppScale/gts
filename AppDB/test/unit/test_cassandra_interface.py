#!/usr/bin/env python
# Programmer: Navraj Chohan

import sys
import unittest

from appscale.datastore.cassandra_env import cassandra_interface
from appscale.datastore.unpackaged import APPSCALE_LIB_DIR
from cassandra.cluster import Cluster
from cassandra.query import BatchStatement
from flexmock import flexmock

sys.path.append(APPSCALE_LIB_DIR)
import file_io


class TestCassandra(unittest.TestCase):
  def testConstructor(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(Cluster).should_receive('connect').\
        and_return(flexmock(execute=lambda x: None))

    db = cassandra_interface.DatastoreProxy()

  def testGet(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(Cluster).should_receive('connect').\
        and_return(flexmock(execute=lambda x, **y: []))

    db = cassandra_interface.DatastoreProxy()

    # Make sure no exception is thrown
    assert {} == db.batch_get_entity('table', [], [])

  def testPut(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    session = flexmock(prepare=lambda x: '', execute=lambda x: None)
    flexmock(BatchStatement).should_receive('add')
    flexmock(Cluster).should_receive('connect').\
        and_return(session)

    db = cassandra_interface.DatastoreProxy()

    # Make sure no exception is thrown
    assert None == db.batch_put_entity('table', [], [], {})

  def testDeleteTable(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(Cluster).should_receive('connect').\
        and_return(flexmock(execute=lambda x: None))

    db = cassandra_interface.DatastoreProxy()

    # Make sure no exception is thrown
    db.delete_table('table')    

  def testRangeQuery(self):
    flexmock(file_io) \
        .should_receive('read') \
        .and_return('127.0.0.1')

    flexmock(Cluster).should_receive('connect').\
        and_return(flexmock(execute=lambda x, **y: []))

    db = cassandra_interface.DatastoreProxy()

    self.assertListEqual([], db.range_query("table", [], "start", "end", 0))

  def test_batch_mutate(self):
    app_id = 'guestbook'
    transaction = 1
    flexmock(file_io).should_receive('read').and_return('127.0.0.1')

    flexmock(Cluster).should_receive('connect').\
      and_return(flexmock(execute=lambda x, **y: []))

    db = cassandra_interface.DatastoreProxy()

    db.batch_mutate(app_id, [], [], transaction)


if __name__ == "__main__":
  unittest.main()    
