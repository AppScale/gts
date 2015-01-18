""" Top level functions for SOLR functions. """
import logging
import os
import simplejson
import sys
import time
import urllib
import urllib2

import query_parser
import search_exceptions

from query_parser import Document

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

  def update_schema(self, updates):
    """ Updates the schema of a document.

    Args:
      updates: A list of updates to apply.
    """
    field_list = []
    for update in updates:
      field_list.append({'name': update['name'], 'type': update['type'],
        'stored': 'true', 'indexed': 'true', 'multiValued': 'false'})

    solr_url = "http://{0}:{1}/solr/schema/fields".format(
      self._search_location, self.SOLR_SERVER_PORT)
    json_request = simplejson.dumps(field_list)
    try:
      content_length = len(json_request)
      req = urllib2.Request(solr_url, data=json_request)
      req.add_header('Content-Type', 'application/json')
      conn = urllib2.urlopen(req) 
      if conn.getcode() != 200:
        raise search_exceptions.InternalError("Malformed response from SOLR.")
      response = simplejson.load(conn)
      status = response['responseHeader']['status'] 
      logging.debug("Response: {0}".format(response))
    except ValueError, exception:
      logging.error("Unable to decode json from SOLR server: {0}".format(
        exception))
      raise search_exceptions.InternalError("Malformed response from SOLR.")

    if status != 0:
      raise search_exceptions.InternalError(
        "SOLR response status of {0}".format(status))

  def to_solr_hash_map(self, index, solr_doc):
    """ Converts a set of fields to a hash map/dictionary to send to SOLR.

    Args:
      index: A Index type.
      solr_doc: A Document type.
    Returns:
      A dictionary to send for field/value updates.
    """
    hash_map = {}
    hash_map['id'] = solr_doc.id
    hash_map[Document.INDEX_NAME] = index.name
    if solr_doc.language:
      hash_map[Document.INDEX_LOCALE] = solr_doc.language

    for field in solr_doc.fields:
      value = field.value
      field_type = field.field_type
      if field_type == Field.HTML:
        hash_map[index.name + "_" + field.name] = value
      elif field_type == Field.ATOM:
        hash_map[index.name + "_" + field.name] = value
      elif field_type == Field.NUMBER:
        hash_map[index.name + "_" + field.name] = value
      elif field_type == Field.DATE:
        iso8601 = time.strftime("%Y-%m-%dT%H:%M:%S", 
          time.localtime(int(value)))
        hash_map[index.name + "_" + field.name] = iso8601
      elif field_type == Field.GEO:
        hash_map[index.name + "_" + field.name] = value
      else: 
        hash_map[index.name + "_" + field.name] = value
    return hash_map

  def commit_update(self, hash_map):
    """ Commits field/value changes to SOLR.

    Args:
      hash_map: A dictionary to send to SOLR.
    Raises:
       search_exceptions.InternalError: On failure.
    """
    docs = []
    docs.append(hash_map)
    json_payload = simplejson.dumps(docs)
    solr_url = "http://{0}:{1}/solr/update/json?commit=true".format(
      self._search_location, self.SOLR_SERVER_PORT)
    try:
      req = urllib2.Request(solr_url, data=json_payload)
      req.add_header('Content-Type', 'application/json')
      conn = urllib2.urlopen(req) 
      if conn.getcode() != 200:
        logging.error("Got code {0} with URL {1} and payload {2}".format(conn.getcode(), 
          solr_url, json_payload))
        raise search_exceptions.InternalError("Bad request sent to SOLR.")
      response = simplejson.load(conn)
      status = response['responseHeader']['status'] 
      logging.debug("Response: {0}".format(response))
    except ValueError, exception:
      logging.error("Unable to decode json from SOLR server: {0}".format(
        exception))
      raise search_exceptions.InternalError("Malformed response from SOLR.")

    if status != 0:
      raise search_exceptions.InternalError(
        "SOLR response status of {0}".format(status))

  def update_document(self, app_id, doc, index_spec):
    """ Updates a document in SOLR.

    Args:
      app_id: A str, the application identifier.
      doc: The document to update.
      index_spec: An index specification.
    """
    solr_doc = self.to_solr_doc(doc)

    index = self.get_index(app_id, index_spec.namespace(), index_spec.name())
    updates = self.compute_updates(index.name, index.schema.fields, solr_doc.fields)
    if len(updates) > 0:
      self.update_schema(updates)

    # Create a list of documents to update.
    hash_map = self.to_solr_hash_map(index, solr_doc)
    self.commit_update(hash_map)

  def to_solr_doc(self, doc):
    """ Converts to an internal SOLR document. 

    Args:
      doc: A document_pb.Document type.
    Returns:
      A converted Document type.
    """
    fields = []
    for field in doc.field_list():
      value = field.value().string_value()
      field_type = field.value().type()
      if field_type == FieldValue.TEXT:
        lang = field.value().language()
        name = field.name()# + "_" + Field.TEXT_ + lang
        new_field = Field(name, Field.TEXT_ + lang, value=value)
      elif field_type == FieldValue.HTML:
        lang = field.value().language()
        name = field.name()# + "_" + Field.HTML + lang
        new_field = Field(name, Field.HTML, value=value)
      elif field_type == FieldValue.ATOM:
        name = field.name()# + "_" + Field.ATOM
        new_field = Field(name, Field.ATOM, value=value.lower())
      elif field_type == FieldValue.DATE:
        name = field.name()# + "_" + Field.DATE
        new_field = Field(name, Field.DATE, value=value)
      elif  field_type == FieldValue.NUMBER:
        name = field.name()# + "_" + Field.NUMBER
        new_field = Field(name, Field.NUMBER, value=value)
      elif field_type == FieldValue.GEO:
        geo = field.value.geo()
        name = field.name()# + "_" + Field.GEO
        new_field = Field(name, Field.GEO, geo.lat + "," + geo.lng())
      else:
        logging.error("Unknown field type {0}".format(field_type))
        raise search_exceptions.InternalError(
          "Unknown or unimplemented field type!")
      fields.append(new_field)
    return Document(doc.id(), doc.language(), fields)

  def compute_updates(self, index_name, current_fields, doc_fields):
    """ Computes the updates needed to update a document in SOLR.
  
    Args:
      index_name: A str, the index name.
      current_fields: The current SOLR schema fields set.
      doc_fields: The fields that need to be updated.
    Returns:
      A list of dictionaries with SOLR field names that require updates.
    """
    fields_to_update = []
    for doc_field in doc_fields:
      doc_name = doc_field.name
      found = False
      for current_field in current_fields:
        current_name = current_field['name']
        if current_name == index_name + "_" + doc_name:
          found = True
      if not found:
        new_field = {'name': index_name + "_" + doc_name, 'type':
          doc_field.field_type}
        fields_to_update.append(new_field)
    #TODO add fields to delete also.
    logging.debug("Fields to update: {0}".format(fields_to_update))
    return fields_to_update

  def run_query(self, index, app_id, namespace, query, search_parms):
    """ Creates a SOLR query string and runs it on SOLR. 

    Args:
      index: Index for which we're running the query.
      app_id: A str, the application identifier.
      namespace: A str, the namespace.
      query: A str, the query the user is executing.
      search_parms: A search_service_pb.SearchParams.
      field_spec: A search_service_pb.FieldSpec.
      sort_list: A list of search_service_pb.SortSpec.
    """
    field_spec = search_params.field_spec()
    sort_list = search_params.sort_spec_list()
    parser = query_parser.SolrQueryParser(index, app_id, namespace,
      field_spec, sort_list, search_params.limit(),
      search_params.offset())
    solr_query = parser.get_solr_query_string(query)
    logging.info("Solr query: {0}".format(solr_query))
    solr_results = self.__execute_query(solr_query)
    logging.info("Solr results: {0}".format(solr_results))
    gae_results = self.__convert_to_gae_results(solr_results)
    logging.info("GAE results: {0}".format(gae_results))
    return gae_results

  def __execute_query(self, solr_query):
    """ Executes query string on SOLR. """
    solr_url = "http://{0}:{1}/solr/select/?defType=edismax&wt=json&{2}"\
      .format(self._search_location, self.SOLR_SERVER_PORT,
      urllib.quote_plus(solr_query))
    logging.info("SOLR URL: {0}".format(solr_url))
    try:
      req = urllib2.Request(solr_url)
      req.add_header('Content-Type', 'application/json')
      conn = urllib2.urlopen(req) 
      if conn.getcode() != 200:
        logging.error("Got code {0} with URL {1} and payload {2}".format(conn.getcode(), 
          solr_url, json_payload))
        raise search_exceptions.InternalError("Bad request sent to SOLR.")
      response = simplejson.load(conn)
      status = response['responseHeader']['status'] 
      logging.info("Response: {0}".format(response))
    except ValueError, exception:
      logging.error("Unable to decode json from SOLR server: {0}".format(
        exception))
      raise search_exceptions.InternalError("Malformed response from SOLR.")

    if status != 0:
      raise search_exceptions.InternalError(
        "SOLR response status of {0}".format(status))

  def __convert_to_gae_results(self, solr_results):
    """ Converts SOLR results in to GAE compatible documents. """
    return
 
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

class Header():
  """ Represents a header in SOLR. """
  def __init__(self, status, qtime):
    """ Constructor for Header type. """
    self.status = status
    self.qtime = qtime

class Field():
  """ Field item in a document. """

  TEXT = "text_ws"
  TEXT_FR = "text_fr"
  TEXT_ = "text_"
  HTML = "html"
  ATOM = "atom"
  GEO = "geo"
  DATE = "date"
  NUMBER = "number"

  def __init__(self, name, field_type, stored=True, indexed=True, 
    multi_valued=False, value=None):
    """ Constructor for Field type. """
    self.name = name
    self.field_type = field_type
    self.stored = stored
    self.indexed = indexed
    self.multi_valued = multi_valued
    self.value = value

class Results():
  """ Results from SOLR. """

  def __init__(self, num_found, docs, header):
    """ Constructor for Results type. """
    self.num_found = num_found
    self.docs = docs
    self.header = header
