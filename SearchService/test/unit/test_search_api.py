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
  def update_document(self, app_id, doc_id, doc, index_spec):
    pass

class FakeDocument():
  def __init__(self):
    self.doc_id = None
  def id(self):
    return self.doc_id
  def set_id(self, doc_id):
    self.doc_id = doc_id

class FakeIndexSpec():
  def __init__(self):
    pass
  
class FakeParams():
  def __init__(self):
    pass
  def document_list(self):
    return [FakeDocument()]
  def index_spec(self):
    return FakeIndexSpec()

class FakeIndexDocumentRequest():
  def __init__(self, data):
    pass
  def params(self):
    return FakeParams()
  def app_id(self):
    return "appid"

class FakeStatus():
  def __init__(self):
    pass
  def set_code(self, code):
    pass

class FakeIndexDocumentResponse():
  def __init__(self):
    pass
  def add_doc_id(self, doc_id):
    pass
  def add_status(self):
    return FakeStatus()

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
    solr_interface = flexmock()
    solr_interface.should_receive("Solr").and_return(FakeSolr())
    solr_interface.should_receive("update_document") 
    fake_response = FakeIndexDocumentResponse()
    flexmock(search_service_pb) 
    search_service_pb.should_receive("IndexDocumentRequest").and_return(FakeIndexDocumentRequest("data"))
    search_service_pb.should_receive("IndexDocumentResponse").and_return(fake_response)
    search_service = search_api.SearchService() 
    search_service = flexmock(search_service)

    self.assertEquals(search_service.index_document("app_data"), (fake_response, 0, ""))

