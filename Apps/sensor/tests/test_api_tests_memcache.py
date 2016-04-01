#!/usr/bin/env python
""" Testing for Memcache API checker. """

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
from common import util
from common import constants
from api_tests import memcache

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.api import memcache as memc

class TestMemcache(unittest.TestCase):
  def test_set_test(self):
    mock = flexmock(memc)

    # Test execution without exceptions.
    mock.should_receive("set").and_return()
    results = memcache.set('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), 0)

    # Test with exceptions being thrown up.
    mock.should_receive("set").and_raise(Exception("test exception"))
    results = memcache.set('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)

    # All sets caused an exception.
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)

  def test_get_test(self):
    mock = flexmock(memc)

    # Test execution without exceptions.
    value = 'xxx' + util.random_string(constants.MAX_STRING_LENGTH)
    mock.should_receive("get").and_return(value)
    results = memcache.get('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), 0)

    # Test with exceptions being thrown up.
    mock.should_receive("get").and_raise(Exception("test exception"))
    results = memcache.get('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)

    # All puts caused an exception.
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)

  def test_delete_test(self):
    mock = flexmock(memc)

    # Test execution without exceptions.
    mock.should_receive("delete").and_return()
    results = memcache.delete('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)
    self.assertEquals(len(results[1]), 0)

    # Test with exceptions being thrown up.
    mock.should_receive("delete").and_raise(Exception("test exception"))
    results = memcache.delete('xxx')
    self.assertEquals(len(results), 2)
    self.assertEquals(len(results[0]), constants.NUM_SAMPLES)

    # All puts caused an exception.
    self.assertEquals(len(results[1]), constants.NUM_SAMPLES)
