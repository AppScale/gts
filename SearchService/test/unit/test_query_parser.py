#!/usr/bin/env python

import os
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import query_parser

class TestQueryParser(unittest.TestCase):                              
  """                                                                           
  A set of test cases for the query parser module.
  """            
  def test_constructor(self):
    query_parser.SolrQueryParser("what", "appid", "namespace")

