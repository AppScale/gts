#!/usr/bin/env python

import os
import sys
import unittest

from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import search_api
import solr_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer"))
from google.appengine.api.search import search_service_pb
from google.appengine.ext.remote_api import remote_api_pb

class FakeSolr():
  def __init__(self):
    pass

class FakeRequest():
  def __init__(self):
    pass
  def ParseFromString(self, data):
    pass
  def has_method(self):
    return True
  def method(self):
    return "IndexDocument"
  def has_request(self):
    return True
  def request(self):
    return "data"

class FakeResponse():
  def __init__(self):
    pass
  def set_response(self, response):
    pass
  def Encode(self):
    return "encoded"

class TestSearchApi(unittest.TestCase):                              
  """                                                                           
  A set of test cases for the search api module.
  """            
  def test_unknown_request(self):
    flexmock(solr_interface)
    solr_interface.should_receive("Solr").and_return(FakeSolr())
    search_service = search_api.SearchService() 
    self.assertRaises(NotImplementedError, 
      search_service.unknown_request, "some_unknown_type")

  def test_remote_request(self):
    solr_interface = flexmock()
    solr_interface.should_receive("Solr").and_return(FakeSolr())

    flexmock(remote_api_pb) 
    remote_api_pb.should_receive("Request").and_return(FakeRequest())
    remote_api_pb.should_receive("Response").and_return(FakeResponse())
   
    search_service = search_api.SearchService() 
    search_service = flexmock(search_service)
    search_service.should_receive("index_document").and_return("response_data", 0, "").once()

    self.assertEquals(search_service.remote_request("app_data"), "encoded")

    
  def test_index_document(self):
    pass
