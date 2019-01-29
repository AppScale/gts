#!/usr/bin/env python

import os
import json
import sys
import unittest
import urllib2

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import solr_interface
import search_exceptions

class FakeSolrDoc():
  def __init__(self):
    self.fields = []

class FakeDocument():
  INDEX_NAME = "indexname"
  INDEX_LOCALE = "indexlocale"
  def __init__(self):
    self.fields = []
    self.id = "id"
    self.language = "lang"

class FakeSchema():
  def __init__(self):
    self.fields = []

class FakeIndex():
  def __init__(self):
    self.name = "name"
    self.schema = FakeSchema()

class FakeIndexSpec():
  def __init__(self):
    pass
  def namespace(self):
    return 'ns'
  def name(self):
    return self.name

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
  def test_get_index_adapter(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").\
      and_return("somelocation")
    solr = solr_interface.Solr()
    solr = flexmock(solr)
    flexmock(solr_interface)
    solr_interface.should_receive("get_index_name").and_return("index_ns_name")
    flexmock(urllib2)
    urllib2.should_receive("urlopen").and_return(FakeConnection(False))
    self.assertRaises(search_exceptions.InternalError,
                      solr._get_index_adapter, "app_id", "ns", "name")

    # Test the case of ValueError on a json.load.
    urllib2.should_receive("urlopen").and_return(FakeConnection(True))
    flexmock(json)
    json.should_receive("load").and_raise(ValueError)
    self.assertRaises(search_exceptions.InternalError,
                      solr._get_index_adapter, "app_id", "ns", "name")

    # Test a bad status from SOLR.
    dictionary = {'responseHeader':{'status': 1}}
    json.should_receive("load").and_return(dictionary)
    self.assertRaises(search_exceptions.InternalError,
                      solr._get_index_adapter, "app_id", "ns", "name")

    fields = [{'name':"index_ns_name_"}]
    dictionary = {'responseHeader':{'status': 0}, "fields": fields}
    json.should_receive("load").and_return(dictionary)
    index = solr._get_index_adapter("app_id", "ns", "name")
    self.assertEquals(index.schema[0]['name'], "index_ns_name_")

  def test_update_schema(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").\
      and_return("somelocation")
    solr = solr_interface.Solr()

    flexmock(urllib2)
    urllib2.should_receive("urlopen").and_return(FakeConnection(False))
    updates = []
    self.assertRaises(search_exceptions.InternalError,
                      solr.update_schema, updates)

    updates = [{'name': 'name1', 'type':'type1'}]
    flexmock(json)
    json.should_receive("load").and_raise(ValueError)
    urllib2.should_receive("urlopen").and_return(FakeConnection(True))
    self.assertRaises(search_exceptions.InternalError,
                      solr.update_schema, updates)

    dictionary = {"responseHeader":{"status":1}}
    json.should_receive("load").and_return(dictionary)
    self.assertRaises(search_exceptions.InternalError,
                      solr.update_schema, updates)

    dictionary = {"responseHeader":{"status":0}}
    json.should_receive("load").and_return(dictionary)
    solr.update_schema(updates)

  def test_to_solr_hash_map(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").\
      and_return("somelocation")
    solr = solr_interface.Solr()
    self.assertNotEqual(solr.to_solr_hash_map(FakeIndex(), FakeDocument()), {})

  def test_commit_update(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").\
      and_return("somelocation")
    solr = solr_interface.Solr()

    flexmock(json)
    json.should_receive("loads").and_return({})

    flexmock(urllib2)
    urllib2.should_receive("urlopen").and_return(FakeConnection(False))
    self.assertRaises(search_exceptions.InternalError, solr.commit_update, {})

    json.should_receive("load").and_raise(ValueError)
    urllib2.should_receive("urlopen").and_return(FakeConnection(True))
    self.assertRaises(search_exceptions.InternalError, solr.commit_update, {})

    dictionary = {'responseHeader':{'status': 1}}
    json.should_receive("load").and_return(dictionary).once()
    self.assertRaises(search_exceptions.InternalError, solr.commit_update, {})

    dictionary = {'responseHeader':{'status': 0}}
    json.should_receive("load").and_return(dictionary).once()
    solr.commit_update({})

  def test_update_document(self):
    appscale_info = flexmock()
    appscale_info.should_receive("get_search_location").\
      and_return("somelocation")
    solr = solr_interface.Solr()
    solr = flexmock(solr)
    solr.should_receive("to_solr_doc").and_return(FakeSolrDoc())
    solr.should_receive("_get_index_adapter").and_return(FakeIndex())
    solr.should_receive("compute_updates").and_return([])
    solr.should_receive("to_solr_hash_map").and_return(None)
    solr.should_receive("commit_update").and_return(None)
    solr.update_document("app_id", None, FakeIndexSpec())

    solr.should_receive("compute_updates").and_return([1,2])
    solr.should_receive("update_schema").twice()
    solr.update_document("app_id", None, FakeIndexSpec())

    solr.should_receive("to_solr_hash_map").and_return(None).once()
    solr.update_document("app_id", None, FakeIndexSpec())

  def test_json_loads_byteified(self):
    json_with_unicode = (
      '{"key2": [{"\\u2611": 28, "\\u2616": ["\\u263a"]}, "second", "third"], '
      '"key1": "value", '
      '"\\u2604": {"\\u2708": "\\u2708"}}'
    )
    parsed_obj = solr_interface.json_loads_byteified(json_with_unicode)

    def walk_and_check_type(obj):
      if isinstance(obj, dict):
        for key, value in obj.iteritems():
          self.assertIsInstance(key, str)
          walk_and_check_type(value)
      elif isinstance(obj, list):
        for value in obj:
          walk_and_check_type(value)
      else:
        self.assertIsInstance(obj, (str, int))

    walk_and_check_type(parsed_obj)
    self.assertEqual(parsed_obj, {
      'key1': 'value',
      'key2': [
        {'\xe2\x98\x91': 28, '\xe2\x98\x96': ['\xe2\x98\xba']},
        'second',
        'third'
      ],
      '\xe2\x98\x84': {'\xe2\x9c\x88': '\xe2\x9c\x88'}
    })
