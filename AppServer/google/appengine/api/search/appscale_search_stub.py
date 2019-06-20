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
import socket

import errno

from google.appengine.api import apiproxy_stub
from google.appengine.api.search import search
from google.appengine.api.search import search_util
from google.appengine.ext.remote_api import remote_api_pb                       
from google.appengine.runtime import apiproxy_errors

# Where the SSL certificate is placed for encrypted communication.
CERT_LOCATION = "/etc/appscale/certs/mycert.pem"

# Where the SSL private key is placed for encrypted communication.
KEY_LOCATION = "/etc/appscale/certs/mykey.pem"

# The location on the system that has the IP of the search server.
SEARCH_LOCATION_FILE = "/etc/appscale/search_ip"
SEARCH_PROXY_FILE = "/etc/appscale/load_balancer_ips"
SEARCH_PROXY_PORT = 9999

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
    self._search_locations = None
    try:
      # Trying old search service first
      with open(SEARCH_LOCATION_FILE) as locations_file:
        host = locations_file.read().strip()
        if host:
          self._search_locations = ['{}:{}'.format(host.strip(), _SEARCH_PORT)]
        else:
          logging.info('Old SearchServices was not found')
      logging.info('Using old SearchService at {}'
                   .format(self._search_locations[0]))
    except IOError:
      try:
        # Using new search service
        with open(SEARCH_PROXY_FILE) as locations_file:
          lbs = [host.strip() for host in locations_file if host.strip()]
          if not lbs:
            logging.error('No LB nodes were found. Search API won\'t work')
          self._search_locations = ['{}:{}'.format(host, SEARCH_PROXY_PORT)
                                    for host in lbs]
        logging.info('Using managed SearchService at {}'
                     .format(self._search_locations))
      except IOError:
        logging.error('No LB nodes were found. Search API won\'t work')

    self.__app_id = app_id
 
  def _Dynamic_IndexDocument(self, request, response):
    """ A local implementation of SearchService.IndexDocument RPC.

    Index a new document or update an existing document.

    Args:
      request: A search_service_pb.IndexDocumentRequest.
      response: A search_service_pb.IndexDocumentResponse.
    """
    if not request.has_app_id():
      request.set_app_id(self.__app_id)
    self._RemoteSend(request, response, "IndexDocument")

  def _Dynamic_DeleteDocument(self, request, response):
    """ A local implementation of SearchService.DeleteDocument RPC.

    Args:
      request: A search_service_pb.DeleteDocumentRequest.
      response: A search_service_pb.DeleteDocumentResponse.
    """
    if not request.has_app_id():
      request.set_app_id(self.__app_id)
    self._RemoteSend(request, response, "DeleteDocument")

  def _Dynamic_ListIndexes(self, request, response):
    """ A local implementation of SearchService.ListIndexes RPC.

    Args:
      request: A search_service_pb.ListIndexesRequest.
      response: A search_service_pb.ListIndexesResponse.

    Raises:
      ResponseTooLargeError: raised for testing admin console.
    """
    if not request.has_app_id():
      request.set_app_id(self.__app_id)
    self._RemoteSend(request, response, "ListIndexes")

  def _Dynamic_ListDocuments(self, request, response):
    """ A local implementation of SearchService.ListDocuments RPC.

    Args:
      request: A search_service_pb.ListDocumentsRequest.
      response: A search_service_pb.ListDocumentsResponse.
    """
    if not request.has_app_id():
      request.set_app_id(self.__app_id)
    self._RemoteSend(request, response, "ListDocuments")
 
  def _Dynamic_Search(self, request, response):
    """ A local implementation of SearchService.Search RPC.

    Args:
      request: A search_service_pb.SearchRequest.
      response: A search_service_pb.SearchResponse.
    """
    if not request.has_app_id():
      request.set_app_id(self.__app_id)
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
    """ Sends a request remotely to the search server.

    Args:
      request: A request object.
      response: A response object to be filled in.
      method: A str, the dynamic function doing the call.
    """
    if not self._search_locations:
      raise search.InternalError("Search service not configured.")

    api_request = remote_api_pb.Request()
    api_request.set_method(method)
    api_request.set_service_name("search")
    api_request.set_request(request.Encode())

    for search_location in self._search_locations:
      api_response = remote_api_pb.Response()
      try:
        api_request.sendCommand(search_location, "", api_response,
                                1, False, KEY_LOCATION, CERT_LOCATION)
        break
      except socket.error as socket_error:
        if socket_error.errno in (errno.ECONNREFUSED, errno.EHOSTUNREACH):
          logging.warning('Failed to connect to search service at {}.'
                          .format(search_location))
          if search_location != self._search_locations[-1]:
            logging.info('Retrying using another proxy.')
            continue
        raise

    if api_response.has_application_error():
      error_pb = api_response.application_error()
      logging.error(error_pb.detail())
      raise apiproxy_errors.ApplicationError(error_pb.code(),
                                             error_pb.detail())

    if api_response.has_exception():
      raise api_response.exception()

    if not api_response or not api_response.has_response():
      raise search.InternalError(
          'No response from search server on %s requests.' % method)

    response.ParseFromString(api_response.response())
