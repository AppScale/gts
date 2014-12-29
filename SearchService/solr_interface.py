""" Top level functions for SOLR functions. """
import logging
import os
import simplejson
import sys
import urllib2

import search_exceptions

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import appscale_info

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.datastore.document_pb import FieldValue

class Solr():
  """ Class for doing solar operations. """

  # The port SOLR is running on.
  SOLR_SERVER_PORT = 8983

  def __init__(self):
    """ Constructor for solr interface. """
    self._search_location = appscale_info.get_search_location()

  def __get_index_name(self, app_id, namespace, name):
    """ Gets the internal index name.

    Args:
      app_id: A str, the application identifier.
      namespace: A str, the application namespace.
      name: A str, the index name.
    Returns:
      A str, the internal name of the index.
    """
    return app_id + "_" + namespace + "_" + name  

  def get_index(self, app_id, namespace, name):
    """ Gets an index from SOLR.

    Performs a JSON request to the SOLR schema API to get the list of defined
    fields. Extracts the fields that match the naming convention
    appid_[namespace]_index_name.

    Args:
      app_id: A str, the application identifier.
      namespace: A str, the application namespace.
      name: A str, the index name.
    Raises:
      search_exception.InternalError: Bad response from SOLR server.
    Returns:
      An index item. 
    """
    index_name = self.__get_index_name(app_id, namespace, name)
    solr_url = "http://{0}:{1}/solr/schema/fields".format(self._search_location,
      self.SOLR_SERVER_PORT)
    logging.debug("URL: {0}".format(solr_url))
    try:
      conn = urllib2.urlopen(solr_url)
      if conn.getcode() != 200:
        raise search_exceptions.InternalError("Malformed response from SOLR.")
      response = simplejson.load(conn)
      logging.debug("Response: {0}".format(response))
    except ValueError, exception:
      logging.error("Unable to decode json from SOLR server: {0}".format(
        exception))
      raise search_exceptions.InternalError("Malformed response from SOLR.")

    # Make sure the response we got from SOLR was with a good status. 
    status = response['responseHeader']['status'] 
    if status != 0:
      raise search_exceptions.InternalError(
        "SOLR response status of {0}".format(status))
 
    # Get only fields which match the index name prefix. 
    filtered_fields = []
    for field in response['fields']:
      if field['name'].startswith("{0}_".format(index_name)):
        filtered_fields.append(field)

    schema = Schema(filtered_fields, response['responseHeader'])
    return Index(index_name, schema)

  def update_document(self, app_id, doc_id, doc, index_spec):
    """ Updates a document in SOLR.

    Args:
      app_id: A str, the application identifier.
      doc_id: A str, the unique ID a document.
      doc: The document to update.
      index_spec: An index specification.
    """
    solr_url = "http://{0}:{1}/solr/update/json?commit=true".format(
      self._search_location, self.SOLR_SERVER_PORT)
    index = self.get_index(app_id, index_spec.namespace(), index_spec.name())
    # TODO is field_list right? Correct types?
    updates = self.compute_updates(index.schema.fields, doc.field_list())
    if len(updates) == 0:
      return

    field_list = []
    for update in updates:
      field_list.append({'name': update['name'], 'type': udpate['type'],
        'stored': True, 'indexed': True, 'multiValued': false})

    json_request = simplejson.dumps(field_list)
    try:
      conn = urllib2.urlopen(solr_url, json_request)
      if conn.getcode() != 200:
        raise search_exceptions.InternalError("Malformed response from SOLR.")
      response = simplejson.load(conn)
      logging.debug("Response: {0}".format(response))
    except ValueError, exception:
      logging.error("Unable to decode json from SOLR server: {0}".format(
        exception))
      raise search_exceptions.InternalError("Malformed response from SOLR.")

    # Create a list of documents to update.
    docs = []
    #docs.append(

  def to_dictionary(self, index, document):
    """ Converted an index and document into a dictionary for document updates.

    Args:
      index:
      document:
    Returns:
      A dictionary which can be sent as a payload to SOLR.
    """
    INDEX_NAME = "_gaeindex_name"

    solr_dict = {}
    solr_dict['id'] = document.id()
    solr_dict[INDEX_NAME] = index.name
    solr_dict[INDEX_LOCALE] = "en"
    # TODO handle different languages. Each value also has a lang.
    # TODO map the types to the values that SOLR accepts.
    for field in document.field_list():
      value = field.value()
      if value.type() == FieldValue.DATE:
        pass #TODO
      elif value.type() == FieldValue.GEO:
        pass #TODO
      elif value.type() == FieldValue.HTML: 
        pass #TODO
      elif value.type() == FieldValue.NUMBER:
        pass #TODO
      elif value.type() == FieldValue.TEXT:
        solr_dict[index_name + "_" + field.name()] = value.string_value()
      else:
        solr_dict[index_name + "_" + field.name()] = value.string_value()
    return

  def compute_updates(self, current_fields, doc_fields):
    """ Computes the updates needed to update a document in SOLR.
  
    Args:
      current_fields: The current SOLR schema fields set.
      doc_fields: The fields that need to be updated.
    Returns:
      A list of updates required.
    """
    fields_to_update = []
    for doc_field in doc_fields:
      doc_name = doc_field['name']  
      found = False
      for current_field in current_fields:
        current_name = current_field['name']
        if current_name == doc_name:
          found = True
      if not found:
        fields_to_update.append(doc_field)
    return fields_to_update

class Schema():
  """ Represents a schema in SOLR. """
  def __init__(self, fields , response_header):
    """ Constructor for SOLR schema. """
    self.fields = fields
    self.response_header = response_header

class Index():
  """ Represents an index in SOLR. """
  def __init__(self, name, schema):
    """ Constructor for SOLR index. """
    self.name = name
    self.schema = schema

class Document():
  """ Represents a document stored in SOLR. """
  def __init__(self, identifier, language, fields):
    """ Constructor for Document in SOLR. """
    self.id = identifier
    self.language = language
    self.fields = fields

class Header():
  """ Represents a header in SOLR. """
  def __init__(self, status, qtime):
    self.status = status
    self.qtime = qtime

class Field():
  """ """
  def __init__(self):
    pass

