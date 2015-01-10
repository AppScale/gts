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

class FakeDocument():
  INDEX_NAME = "indexname"
  INDEX_LOCALE = "indexlocale"
  def __init__(self):
    self.fields = []
    self.id = "id"
    self.language = "lang"

class FakeIndex():
  def __init__(self):
    self.name = "name"

class FakeUpdate():
  def __init__(self, name, field_type):
    self.name = name
    self.field_type = field_type

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

  def test_update_schema(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").and_return("somelocation")
    solr = solr_interface.Solr()

    flexmock(urllib2)
    urllib2.should_receive("urlopen").and_return(FakeConnection(False))
    updates = []
    self.assertRaises(search_exceptions.InternalError, solr.update_schema, updates)

    updates = [{'name': 'name1', 'type':'type1'}]
    flexmock(simplejson)
    simplejson.should_receive("load").and_raise(ValueError)
    urllib2.should_receive("urlopen").and_return(FakeConnection(True))
    self.assertRaises(search_exceptions.InternalError, solr.update_schema, updates)

    dictionary = {"responseHeader":{"status":1}}
    simplejson.should_receive("load").and_return(dictionary)
    self.assertRaises(search_exceptions.InternalError, solr.update_schema, updates)
    
    dictionary = {"responseHeader":{"status":0}}
    simplejson.should_receive("load").and_return(dictionary)
    solr.update_schema(updates)

  def test_to_solr_hash_map(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").and_return("somelocation")
    solr = solr_interface.Solr()
    self.assertNotEqual(solr.to_solr_hash_map(FakeIndex(), FakeDocument()), {})

  def test_commit_update(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").and_return("somelocation")
    solr = solr_interface.Solr()
    
    flexmock(simplejson)
    simplejson.should_receive("loads").and_return({})

    flexmock(urllib2)
    urllib2.should_receive("urlopen").and_return(FakeConnection(False))
    self.assertRaises(search_exceptions.InternalError, solr.commit_update, {})

    simplejson.should_receive("load").and_raise(ValueError)
    urllib2.should_receive("urlopen").and_return(FakeConnection(True))
    self.assertRaises(search_exceptions.InternalError, solr.commit_update, {})

    dictionary = {'responseHeader':{'status': 1}}
    simplejson.should_receive("load").and_return(dictionary).once()
    self.assertRaises(search_exceptions.InternalError, solr.commit_update, {})

    dictionary = {'responseHeader':{'status': 0}}
    simplejson.should_receive("load").and_return(dictionary).once()
    solr.commit_update({})

  def test_update_document(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").and_return("somelocation")
    solr = solr_interface.Solr()
    solr = solr_interface.Solr()
    solr = flexmock(solr) 
    solr.should_receive("to_solr_doc").and_return(None).once()
    solr.should_receive("get_index").and_return(None).once()
    solr.should_receive("compute_updates").and_return([]).once()
    solr.should_receive("to_solr_hash_map").and_return(None).once()
    solr.should_receive("commit_update").and_return(None).once()
    solr.update_document("app_id", None, None)
     
    solr.should_receive("compute_updates").and_return([1,2]).once()
    solr.should_receive("update_schema").twice()
    solr.update_document("app_id", None, None)

    solr.should_receive("to_solr_hash_map").and_return(None).once()
