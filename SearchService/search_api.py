""" Class for handling searialized Search requests. """
import lucene
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api.search import search_service_pb
from google.appengine.ext.remote_api import remote_api_pb

class SearchService():
  """ Search service class. """
  def __init__(self):
    """ Constructor function for the search service. Initializes the lucene
    connection. 
    """
    return

  def unknown_request(self, pb_type):
    """ Handlers unknown request types.

    Args:
      pb_type: The protocol buffer type.
    Raises:
      NotImplementedError: The unknown type is not implemented.
    """
    raise NotImplementedError("Unknown request of operation {0}".format(
      pb_type))

  def remote_request(self, app_id, app_data):
    """ Handles remote requests with serialized protocol buffers. 

    Args:
      app_id: A str. The application identifier.
      app_data: A str. Serialized request data of the application.
    Returns:
      A str. Searialized protocol buffer response.  
    """
    apirequest = remote_api_pb.Request()
    apirequest.ParseFromString(app_data)
    apiresponse = remote_api_pb.Response()
    response = None
    errcode = 0
    errdetail = ""
    apperror_pb = None
    method = ""
    http_request_data = ""

    if not apirequest.has_method():
      errcode = search_service_pb.SearchServiceError.INVALID_REQUEST
      errdetail = "Method was not set in request"
      apirequest.set_method("NOT_FOUND")
    else:
      method = apirequest.method()

    if not apirequest.has_request():
      errcode = search_service_pb.SearchServiceError.INVALID_REQUEST
      errdetail = "Request missing in call"
      apirequest.set_method("NOT_FOUND")
      apirequest.clear_request()
    else:
      http_request_data = apirequest.request()

    if method == "IndexDocument":
      response, errcode, errdetail = self.index_document(app_id,
        http_request_data)
    elif method == "DeleteDocument":
      response, errcode, errdetail = self.delete_document(app_id,
        http_request_data)
    elif method == "ListIndexes":
      response, errcode, errdetail = self.list_indexes(app_id,
        http_request_data)
    elif method == "ListDocuments":
      response, errcode, errdetail = self.list_documents(app_id,
        http_request_data)
    elif method == "Search":
      response, errcode, errdetail = self.search(app_id,
        http_request_data)

    if response:
      apiresponse.set_response(response)

    # If there was an error add it to the response.
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)

    return apiresponse.Encode()

  def index_document(self, app_id, data):
    """ Index a new document or update an existing document.
 
    Args:
      app_id: A str. The application identifier.
      data: A str. Searialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.IndexDocumentRequest(data)
    response = search_service_pb.IndexDocumentResponse()
    return response, 0, "" 

  def delete_document(self, app_id, data):
    """ Deletes a document.
 
    Args:
      app_id: A str. The application identifier.
      data: A str. Searialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.DeleteDocumentRequest(data)
    response = search_service_pb.DeleteDocumentResponse()
    return response, 0, ""

  def list_indexes(self, app_id, data):
    """ Lists all indexes for an application.
   
    Args:
      app_id: A str. The application identifier.
      data: A str. Searialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.ListIndexesRequest(data)
    response = search_service_pb.ListIndexesResponse()
    return response, 0, ""
  
  def list_documents(self, app_id, data):
    """ List all documents for an application.
 
    Args:
      app_id: A str. The application identifier.
      data: A str. Searialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.ListDocumentsRequest(data)
    response = search_service_pb.ListDocumentsResponse()
    return response, 0, ""

  def search(self, app_id, data):
    """ Search within a document.
 
    Args:
      app_id: A str. The application identifier.
      data: A str. Searialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.SearchRequest(data)
    response = search_service_pb.SearchResponse()
    return response, 0, ""

