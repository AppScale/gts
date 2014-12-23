#!/usr/bin/env python

import os
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import search_server

class TestDistributedSearchServer(unittest.TestCase):                              
  """                                                                           
  A set of test cases for the search module.
  """            
  def test_get_application(self):
    self.assertNotEqual(None, search_server.get_application())
