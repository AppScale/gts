#!/usr/bin/env python
""" Testing for DB api checker. """

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from common import constants
from api_tests import db

class TestModelFake():
  def __init__(self):
    self.test_string = ""
    self.initial_ts = 123
    self.modified_ts = 321
    self.text_blob = "blob"

  def put(self):
    return

  def delete(self):
    return

class TestDB(unittest.TestCase):
  def test_put_test(self):
    mock = flexmock(db)
    mock.should_receive("TestModel").and_return(TestModelFake())
    results = db.put('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), 0)

    # Test with exceptions being thrown up.
    mock = flexmock(db)
    exception_model = flexmock(TestModelFake).should_receive("put").\
      and_raise(Exception("test exception"))
    mock.should_receive("TestModel").and_return(exception_model)
    results = db.put('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    # All puts caused an exception.
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)

  def test_get_test(self):
    mock = flexmock(db.TestModel)
    mock.should_receive("get_by_key_name").and_return(TestModelFake())
    results = db.get('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), 0)

    mock.should_receive("get_by_key_name").and_raise(\
      Exception("test exception"))

    results = db.get('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    # All puts caused an exception.
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)

    
  def test_delete_test(self):
    mock = flexmock(db.TestModel)
    mock.should_receive("get_by_key_name").and_return(TestModelFake())
    results = db.delete('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), 0)

    exception_model = flexmock(TestModelFake).should_receive("delete").\
      and_raise(Exception("test exception"))
    results = db.delete('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    # All puts caused an exception.
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)

    # Have exceptions come when doing the get instead.
    mock.should_receive("get_by_key_name").and_raise(\
      Exception("test exception"))
    results = db.delete('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    # All puts caused an exception.
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)


  def test_query_test(self):
    mock_results = []
    for ii in range(0, constants.NUM_SAMPLES):
      mock_results.append(TestModelFake())
    fake_query = flexmock()
    fake_query.should_receive("fetch").and_return(mock_results)
    fake_query.should_receive("filter")
    mock = flexmock(db.TestModel)
    mock.should_receive("all").and_return(fake_query)

    results = db.query("xxx")
    self.assertEquals(len(db.query("xxx")), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), 0)

    fake_query.should_receive("fetch").and_raise(\
      Exception("test exception"))

    results = db.query('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    # All puts caused an exception.
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)

  def test_cleanup(self):
    mock_results = []
    for ii in range(0, constants.MAX_LIMIT):
      mock_results.append(TestModelFake())
    fake_query = flexmock()
    fake_query.should_receive("fetch").and_return(mock_results)
    mock = flexmock(db.TestModel)
    mock.should_receive("all").and_return(fake_query)
    db.cleanup()
