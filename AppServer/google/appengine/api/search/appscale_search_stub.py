#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
""" AppScale Search API stub."""

import logging

from google.appengine.api import apiproxy_stub
from google.appengine.api.search import search
from google.appengine.api.search import search_service_pb
from google.appengine.api.search import search_util
from google.appengine.ext.remote_api import remote_api_pb                       
from google.appengine.runtime import apiproxy_errors

# Where the SSL certificate is placed for encrypted communication.
CERT_LOCATION = "/etc/appscale/certs/mycert.pem"

# Where the SSL private key is placed for encrypted communication.
KEY_LOCATION = "/etc/appscale/certs/mykey.pem"

# The location on the system that has the IP of the search server.
_SEARCH_LOCATION_FILE = "/etc/appscale/search_ip"

# The port that the search server is running on.  
_SEARCH_PORT = 53423

class SearchServiceStub(apiproxy_stub.APIProxyStub):
  """ AppScale backed Search service stub.

  This stub provides the search_service_pb.SearchService. But this is
  NOT a subclass of SearchService itself.  Services are provided by
  the methods prefixed by "_Dynamic_".
  """

  _VERSION = 1


  def __init__(self, service_name='search', app_id=""):
    """ Constructor.

    Args:
      service_name: Service name expected for all calls.
      app_id: The application identifier. 
    """
    super(SearchServiceStub, self).__init__(service_name)
    contents = None
    try:
      FILE = open(_SEARCH_LOCATION_FILE, 'r')
      contents = FILE.read()
      contents += ":" + str(_SEARCH_PORT)
      FILE.close()
      logging.info("Search server set to {0}".format(contents)) 
    except Exception, e:
      logging.warn("No search role configured. Search location set to None.")
    self.__search_location = contents
    self.__app_id = app_id
 
  def _Dynamic_IndexDocument(self, request, response):
    """ A local implementation of SearchService.IndexDocument RPC.

    Index a new document or update an existing document.

    Args:
      request: A search_service_pb.IndexDocumentRequest.
      response: An search_service_pb.IndexDocumentResponse.
    """
    if not request.has_app_id():
      request.set_app_id(self.__app_id)
    self._RemoteSend(request, response, "IndexDocument")

  def _Dynamic_DeleteDocument(self, request, response):
    """ A local implementation of SearchService.DeleteDocument RPC.

    Args:
      request: A search_service_pb.DeleteDocumentRequest.
      response: An search_service_pb.DeleteDocumentResponse.
    """
    self._RemoteSend(request, response, "DeleteDocument")

  def _Dynamic_ListIndexes(self, request, response):
    """ A local implementation of SearchService.ListIndexes RPC.

    Args:
      request: A search_service_pb.ListIndexesRequest.
      response: An search_service_pb.ListIndexesResponse.

    Raises:
      ResponseTooLargeError: raised for testing admin console.
    """
    self._RemoteSend(request, response, "ListIndexes")

  def _Dynamic_ListDocuments(self, request, response):
    """ A local implementation of SearchService.ListDocuments RPC.

    Args:
      request: A search_service_pb.ListDocumentsRequest.
      response: An search_service_pb.ListDocumentsResponse.
    """
    self._RemoteSend(request, response, "ListDocuments")
 
  def _Dynamic_Search(self, request, response):
    """ A local implementation of SearchService.Search RPC.

    Args:
      request: A search_service_pb.SearchRequest.
      response: An search_service_pb.SearchResponse.
    """
    self._RemoteSend(request, response, "Search")

  def __repr__(self):
    return search_util.Repr(self, [('__indexes', self.__indexes)])

  def Write(self):
    """ Write search indexes to the index file.

    This method is a no-op.
    """
    return

  def Read(self):
    """ Read search indexes from the index file.

    This method is a no-op if index_file is set to None.
    """
    return

  def _RemoteSend(self, request, response, method):
    """ Sends a request remotely to the datstore server. """
    if not self.__search_location:
      raise search.InternalError("Search service not configured.")

    api_request = remote_api_pb.Request()
    api_request.set_method(method)
    api_request.set_service_name("search")
    api_request.set_request(request.Encode())

    api_response = remote_api_pb.Response()
    api_response = api_request.sendCommand(self.__search_location,
      "",
      api_response,
      1,
      False,
      KEY_LOCATION,
      CERT_LOCATION)

    if not api_response or not api_response.has_response():
      raise search.InternalError(
          'No response from db server on %s requests.' % method)

    if api_response.has_application_error():
      error_pb = api_response.application_error()
      logging.error(error_pb.detail())
      raise apiproxy_errors.ApplicationError(error_pb.code(),
                                             error_pb.detail())

    if api_response.has_exception():
      raise api_response.exception()

    response.ParseFromString(api_response.response())
