""" Class for handling searialized Search requests. """
import logging
import os
import sys
import uuid

import search_exceptions
import solr_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api.search import search_service_pb
from google.appengine.ext.remote_api import remote_api_pb

class SearchService():
  """ Search service class. """
  def __init__(self):
    """ Constructor function for the search service. Initializes the lucene
    connection. 
    """
    self.solr_conn = solr_interface.Solr()

  def unknown_request(self, pb_type):
    """ Handles unknown request types.

    Args:
      pb_type: The protocol buffer type.
    Raises:
      NotImplementedError: The unknown type is not implemented.
    """
    raise NotImplementedError("Unknown request of operation {0}".format(
      pb_type))

  def remote_request(self, app_data):
    """ Handles remote requests with serialized protocol buffers. 

    Args:
      app_data: A str. Serialized request data of the application.
    Returns:
      A str. Serialized protocol buffer response.  
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
      response, errcode, errdetail = self.index_document(http_request_data)
    elif method == "DeleteDocument":
      response, errcode, errdetail = self.delete_document(http_request_data)
    elif method == "ListIndexes":
      response, errcode, errdetail = self.list_indexes(http_request_data)
    elif method == "ListDocuments":
      response, errcode, errdetail = self.list_documents(http_request_data)
    elif method == "Search":
      response, errcode, errdetail = self.search(http_request_data)

    if response:
      apiresponse.set_response(response)

    # If there was an error add it to the response.
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)

    return apiresponse.Encode()

  def index_document(self, data):
    """ Index a new document or update an existing document.
 
    Args:
      data: A str. Serialized protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.IndexDocumentRequest(data)
    logging.debug("APP ID: {0}".format(request.app_id())) 
    response = search_service_pb.IndexDocumentResponse()
    params = request.params()

    document_list = params.document_list()
    index_spec = params.index_spec()
    
    for doc in document_list:
      doc_id = doc.id()
      # Assign an ID if not present.
      if not doc_id:
        doc_id = str(uuid.uuid4())
        doc.set_id(doc_id)
      response.add_doc_id(doc_id)
   
      new_status = response.add_status()
      try:
        self.solr_conn.update_document(request.app_id(), doc, index_spec)
        new_status.set_code(search_service_pb.SearchServiceError.OK) 
      except Exception, exception:
        logging.error("Exception raised while indexing document")
        logging.exception(exception)
        new_status.set_code(
          search_service_pb.SearchServiceError.INTERNAL_ERROR)

    return response.Encode(), 0, ""

  def delete_document(self, data):
    """ Deletes a document.
 
    Args:
      data: A str. Serialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.DeleteDocumentRequest(data)
    response = search_service_pb.DeleteDocumentResponse()
    return response, 0, ""

  def list_indexes(self, data):
    """ Lists all indexes for an application.
   
    Args:
      data: A str. Serialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.ListIndexesRequest(data)
    response = search_service_pb.ListIndexesResponse()
    return response, 0, ""
  
  def list_documents(self, data):
    """ List all documents for an application.
 
    Args:
      data: A str. Serialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.ListDocumentsRequest(data)
    response = search_service_pb.ListDocumentsResponse()
    return response, 0, ""

  def search(self, data):
    """ Search within a document.
 
    Args:
      data: A str. Serialize protocol buffer.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = search_service_pb.SearchRequest(data)
    logging.info("Search request: {0}".format(request))
    params = request.params()
    app_id = request.app_id()
    index_spec = params.index_spec()
    namespace = index_spec.namespace()
    response = search_service_pb.SearchResponse()
    try:
      index = self.solr_conn.get_index(app_id, index_spec.namespace(),
        index_spec.name())
      self.solr_conn.run_query(response, index, app_id, namespace,
        request.params())
    except search_exceptions.InternalError, internal_error:
      logging.error("Exception while doing a search.")
      logging.exception(internal_error)
      status = response.mutable_status()
      status.set_code(
        search_service_pb.SearchServiceError.INTERNAL_ERROR)
      response.set_matched_count(0)
      return response.Encode(), 3, "Internal error."
     
    logging.debug("Search response: {0}".format(response))
    return response.Encode(), 0, ""
