#!/usr/bin/env python
""" Testing for utility functions. """

import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import util

class TestUtils(unittest.TestCase):
  def test_random_string(self):
    self.assertEquals(len(util.random_string(10)), 10)
    self.assertEquals(len(util.random_string(100)), 100)
    self.assertEquals(len(util.random_string(1000)), 1000)
