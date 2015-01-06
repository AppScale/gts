#!/usr/bin/env python

import os
import simplejson
import sys
import unittest
import urllib2

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import solr_interface
import search_exceptions

class FakeConnection():
  def __init__(self, is_good_code):
    self.code = 200
    if not is_good_code:
      self.code = 500 
  def getcode(self):
    return self.code

class TestSolrInterface(unittest.TestCase):                              
  """                                                                           
  A set of test cases for the solr interface module.
  """            
  def test_get_index(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").and_return("somelocation")
    solr = solr_interface.Solr()
    solr = flexmock(solr)
    solr.should_receive("__get_index_name").and_return("index_ns_name")
    flexmock(urllib2)
    urllib2.should_receive("urlopen").and_return(FakeConnection(False))
    self.assertRaises(search_exceptions.InternalError, solr.get_index, "app_id", "ns", "name")

    # Test the case of ValueError on a simplejson.load.
    urllib2.should_receive("urlopen").and_return(FakeConnection(True))
    flexmock(simplejson)
    simplejson.should_receive("load").and_raise(ValueError)
    self.assertRaises(search_exceptions.InternalError, solr.get_index, "app_id", "ns", "name")

    # Test a bad status from SOLR.
    dictionary = {'responseHeader':{'status': 1}}
    simplejson.should_receive("load").and_return(dictionary)
    self.assertRaises(search_exceptions.InternalError, solr.get_index, "app_id", "ns", "name")

    fields = [{'name':"index_ns_name_"}]
    dictionary = {'responseHeader':{'status': 0}, "fields": fields}
    simplejson.should_receive("load").and_return(dictionary)
    index = solr.get_index("app_id", "ns", "name")
    self.assertEquals(index.schema.fields[0]['name'], "index_ns_name_")
