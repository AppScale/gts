""" Top level functions for SOLR functions. """
import calendar
import urllib
from datetime import datetime
import logging
import os
import json
import sys
import urllib2

from appscale.common import appscale_info

import query_converter
import search_exceptions
from constants import (
  HTTP_OK, INDEX_NAME_FIELD, INDEX_LOCALE_FIELD, SOLR_SERVER_PORT
)

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.datastore.document_pb import FieldValue
from google.appengine.api.search import search_service_pb


def get_index_name(app_id, namespace, name):
  """ Gets the internal index name.

  Args:
    app_id: A str, the application identifier.
    namespace: A str, the application namespace.
    name: A str, the index name.
  Returns:
    A str, the internal name of the index.
  """
  return '{}_{}_{}'.format(app_id, namespace, name)


class Solr(object):
  """ Class for doing solr operations. """

  def __init__(self):
    """ Constructor for solr interface. """
    self._search_location = 'http://{}:{}'.format(
      appscale_info.get_search_location(), SOLR_SERVER_PORT
    )

  def delete_doc(self, doc_id):
    """ Deletes a document by doc ID.

    Args:
      doc_id: A list of document IDs.
    Raises:
      search_exceptions.InternalError on internal errors.
    """
    solr_request = {"delete": {"id": doc_id}}
    solr_url = "{}/solr/update?commit=true".format(self._search_location)
    logging.debug("SOLR URL: {0}".format(solr_url))
    json_request = json.dumps(solr_request)
    logging.debug("SOLR JSON: {0}".format(json_request))
    try:
      req = urllib2.Request(solr_url, data=json_request)
      req.add_header('Content-Type', 'application/json')
      conn = urllib2.urlopen(req)
      if conn.getcode() != HTTP_OK:
        raise search_exceptions.InternalError("Malformed response from SOLR.")
      response = json_load_byteified(conn)
      status = response['responseHeader']['status']
      logging.debug("Response: {0}".format(response))
    except ValueError, exception:
      logging.error("Unable to decode json from SOLR server: {0}".format(
        exception))
      raise search_exceptions.InternalError("Malformed response from SOLR.")

    if status != 0:
      raise search_exceptions.InternalError(
        "SOLR response status of {0}".format(status))

  def _get_index_adapter(self, app_id, namespace, name):
    """ Gets an index from SOLR.

    Performs a JSON request to the SOLR schema API to get the list of defined
    fields. Extracts the fields that match the naming convention
    appid_[namespace]_index_name.

    Args:
      app_id: A str, the application identifier.
      namespace: A str, the application namespace.
      name: A str, the index name.
    Raises:
      search_exceptions.InternalError: Bad response from SOLR server.
    Returns:
      An index item. 
    """
    index_name = get_index_name(app_id, namespace, name)
    solr_url = "{}/solr/schema/fields".format(self._search_location)
    logging.debug("URL: {0}".format(solr_url))
    try:
      conn = urllib2.urlopen(solr_url)
      if conn.getcode() != HTTP_OK:
        raise search_exceptions.InternalError("Malformed response from SOLR.")
      response = json_load_byteified(conn)
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
    return IndexAdapter(index_name, filtered_fields)

  def update_schema(self, updates):
    """ Updates the schema of a document.

    Args:
      updates: A list of updates to apply.
    Raises:
      search_exceptions.InternalError on internal errors from SOLR.
    """
    field_list = []
    for update in updates:
      field_list.append({'name': update['name'], 'type': update['type'],
        'stored': 'true', 'indexed': 'true', 'multiValued': 'false'})

    solr_url = "{}/solr/schema/fields".format(self._search_location)
    json_request = json.dumps(field_list)
    try:
      req = urllib2.Request(solr_url, data=json_request)
      req.add_header('Content-Type', 'application/json')
      conn = urllib2.urlopen(req)
      if conn.getcode() != HTTP_OK:
        raise search_exceptions.InternalError("Malformed response from SOLR.")
      response = json_load_byteified(conn)
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
    hash_map[INDEX_NAME_FIELD] = index.name
    if solr_doc.language:
      hash_map[INDEX_LOCALE_FIELD] = solr_doc.language

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
        iso8601 = datetime.fromtimestamp(float(value)/1000).isoformat()
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
    json_payload = json.dumps(docs)
    solr_url = "{}/solr/update/json?commit=true".format(self._search_location)
    try:
      req = urllib2.Request(solr_url, data=json_payload)
      req.add_header('Content-Type', 'application/json')
      conn = urllib2.urlopen(req)
      if conn.getcode() != HTTP_OK:
        logging.error("Got code {0} with URL {1} and payload {2}".format(
        conn.getcode(), solr_url, json_payload))
        raise search_exceptions.InternalError("Bad request sent to SOLR.")
      response = json_load_byteified(conn)
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

    index = self._get_index_adapter(
      app_id, index_spec.namespace(), index_spec.name()
    )
    updates = self.compute_updates(index.name, index.schema, solr_doc.fields)
    if len(updates) > 0:
      try:
        self.update_schema(updates)
      except search_exceptions.InternalError, internal_error:
        logging.error("Error updating schema.")
        logging.exception(internal_error)
    # Create a list of documents to update.
    hash_map = self.to_solr_hash_map(index, solr_doc)
    self.commit_update(hash_map)

  def to_solr_doc(self, doc):
    """ Converts to an internal SOLR document. 

    Args:
      doc: A document_pb.Document type.
    Returns:
      A converted Document type.
    Raises:
      search_exceptions.InternalError if field type is not valid.
    """
    fields = []
    for field in doc.field_list():
      value = field.value().string_value()
      field_type = field.value().type()
      if field_type == FieldValue.TEXT:
        lang = field.value().language()
        name = field.name()
        new_field = Field(name, Field.TEXT_ + lang, value=value)
      elif field_type == FieldValue.HTML:
        lang = field.value().language()
        name = field.name()
        new_field = Field(name, Field.HTML, value=value)
      elif field_type == FieldValue.ATOM:
        name = field.name()
        new_field = Field(name, Field.ATOM, value=value.lower())
      elif field_type == FieldValue.DATE:
        name = field.name()
        new_field = Field(name, Field.DATE, value=value)
      elif  field_type == FieldValue.NUMBER:
        name = field.name()
        new_field = Field(name, Field.NUMBER, value=value)
      elif field_type == FieldValue.GEO:
        geo = field.value.geo()
        name = field.name()
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
    known_fields = {current_field['name'] for current_field in current_fields}
    fields_to_update = []
    for doc_field in doc_fields:
      full_field_name = index_name + '_' + doc_field.name
      if full_field_name in known_fields:
        continue
      fields_to_update.append({
        'name': full_field_name,
        'type': doc_field.field_type
      })
      known_fields.add(full_field_name)
    #TODO add fields to delete also.
    return fields_to_update

  def run_query(self, result, app_id, namespace, index_name, query,
                projection_fields, sort_fields, limit, offset):
    """ Creates a SOLR query string and runs it on SOLR. 

    Args:
      result: A search_service_pb.SearchResponse.
      app_id: A str, the application identifier.
      namespace: A str, the application namespace.
      index_name: A str, the index name.
      query: A str representing query sent by user.
      projection_fields: A list of fields to fetch for each document.
      sort_fields: a list of tuples of form (<FieldName>, "desc"/"asc")
      limit: a max number of document to return.
      offset: an integer representing offset.
    """
    index = self._get_index_adapter(app_id, namespace, index_name)
    solr_query_params = query_converter.prepare_solr_query(
      index, query, projection_fields, sort_fields, limit, offset
    )
    solr_results = self.__execute_query(solr_query_params)
    logging.debug("Solr results: {0}".format(solr_results))
    self.__convert_to_gae_results(result, solr_results, index)

  def __execute_query(self, solr_query_params):
    """ Executes query on SOLR.

    Args:
      solr_query_params: a dict containing query params to send in request.
    Returns:
      The results from the query executing.
    Raises:
      search_exceptions.InternalError on internal SOLR error.
    """
    solr_query_params['wt'] = 'json'
    solr_url = "{}/solr/select/?{}".format(
      self._search_location, urllib.urlencode(solr_query_params)
    )
    try:
      req = urllib2.Request(solr_url)
      req.add_header('Content-Type', 'application/json')
      conn = urllib2.urlopen(req)
      if conn.getcode() != HTTP_OK:
        logging.error("Got code {0} with URL {1}.".format(
          conn.getcode(), solr_url))
        raise search_exceptions.InternalError("Bad request sent to SOLR.")
      response = json_load_byteified(conn)
      status = response['responseHeader']['status']
    except ValueError, exception:
      logging.error("Unable to decode json from SOLR server: {0}".format(
        exception))
      raise search_exceptions.InternalError("Malformed response from SOLR.")
    except urllib2.HTTPError, http_error:
      logging.exception(http_error)
      # We assume no results were returned.
      status = 0
      response = {'response': {'docs': [], 'start': 0}}

    if status != 0:
      raise search_exceptions.InternalError(
        "SOLR response status of {0}".format(status))
    return response

  def __convert_to_gae_results(self, result, solr_results, index):
    """ Converts SOLR results in to GAE compatible documents. 

    Args:
      result: A search_service_pb.SearchResponse.
      solr_results: A dictionary returned from SOLR on a search query.
      index: A Index that we are querying for.
    """
    result.set_matched_count(
      len(solr_results['response']['docs']) +
      int(solr_results['response']['start'])
    )
    result.mutable_status().set_code(search_service_pb.SearchServiceError.OK)
    for doc in solr_results['response']['docs']:
      new_result = result.add_result()
      self.__add_new_doc(doc, new_result, index)

  def __add_new_doc(self, doc, new_result, index):
    """ Add a new document to a query result.

    Args:
      doc: A dictionary of SOLR document attributes.
      new_result: A search_service_pb.SearchResult.
      index: Index we queried for.
    """
    new_doc = new_result.mutable_document()
    new_doc.set_id(doc['id'])
    if INDEX_LOCALE_FIELD in doc:
      new_doc.set_language(doc[INDEX_LOCALE_FIELD][0])
    for key in doc.keys():
      if not key.startswith(index.name):
        continue
      field_name = key.split("{0}_".format(index.name), 1)[1]
      new_field = new_doc.add_field()
      new_field.set_name(field_name)
      new_value = new_field.mutable_value()
      field_type = ""
      for field in index.schema:
        if field['name'] == "{0}_{1}".format(index.name, field_name):
          field_type = field['type']
      if field_type == "":
        logging.warning(
          'Unable to find type for {}_{}'.format(index.name, field_name))
      self.__add_field_value(new_value, doc[key], field_type)

  def __add_field_value(self, new_value, value, ftype):
    """ Adds a value to a result field.

    Args:
      new_value: Value object to fill in.
      value: A str, the internal value to be converted.
      ftype: A str, the field type.
    """
    if ftype == Field.DATE:
      value = calendar.timegm(datetime.strptime(
        value[:-1], "%Y-%m-%dT%H:%M:%S").timetuple())
      new_value.set_string_value(str(int(value * 1000)))
      new_value.set_type(FieldValue.DATE)
    elif ftype == Field.TEXT:
      new_value.set_string_value(value)
      new_value.set_type(FieldValue.TEXT)
    elif ftype == Field.HTML:
      new_value.set_string_value(value)
      new_value.set_type(FieldValue.HTML)
    elif ftype == Field.ATOM:
      new_value.set_string_value(value)
      new_value.set_type(FieldValue.ATOM)
    elif ftype == Field.NUMBER:
      new_value.set_string_value(str(value))
      new_value.set_type(FieldValue.NUMBER)
    elif ftype == Field.GEO:
      geo = new_value.mutable_geo()
      lat, lng = value.split(',')
      geo.set_lat(float(lat))
      geo.set_lng(float(lng))
      new_value.set_type(FieldValue.GEO)
    elif ftype.startswith(Field.TEXT_):
      new_value.set_string_value(value)
      new_value.set_type(FieldValue.TEXT)
    else:
      logging.warning("Default field found! {0}".format(ftype))
      new_value.set_string_value(value)
      new_value.set_type(FieldValue.TEXT)


class IndexAdapter(object):
  """ Represents an index in SOLR. """
  def __init__(self, name, schema):
    """ Constructor for SOLR index. 

    Args:
      name: A str, the name of the index.
      schema: A dict, representing schema for this index.
    """
    self.name = name
    self.schema = schema


class Document(object):
  """ Represents a document stored in SOLR. """
  def __init__(self, identifier, language, fields):
    """ Constructor for Document in SOLR.

    Args:
      identifier: A str, the ID of the document.
      language: The language the document is in.
      fields: Field list for the document.
    """
    self.id = identifier
    self.language = language
    self.fields = fields


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
    """ Constructor for Field type. 

    Args:
      name: The name of the field.
      stored: Boolean if the field is stored.
      indexed: Boolean if the field is indexed.
      multi_valued: Boolean if the field has multiple values.
      value: The value of the field.
    """
    self.name = name
    self.field_type = field_type
    self.stored = stored
    self.indexed = indexed
    self.multi_valued = multi_valued
    self.value = value


# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>
# Thanks to Mirec Miskuf (https://stackoverflow.com/a/33571117)
# >>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>

def json_load_byteified(file_handle):
    return _byteify(
      json.load(file_handle, object_hook=_byteify),
      ignore_dicts=True
    )


def json_loads_byteified(json_text):
  return _byteify(
    json.loads(json_text, object_hook=_byteify),
    ignore_dicts=True
  )


def _byteify(data, ignore_dicts=False):
  # if this is a unicode string, return its string representation
  if isinstance(data, unicode):
    return data.encode('utf-8')
  # if this is a list of values, return list of byteified values
  if isinstance(data, list):
    return [_byteify(item, ignore_dicts=True) for item in data]
  # if this is a dictionary, return dictionary of byteified keys and values
  # but only if we haven't already byteified it
  if isinstance(data, dict) and not ignore_dicts:
    return {
      _byteify(key, ignore_dicts=True): _byteify(value, ignore_dicts=True)
      for key, value in data.iteritems()
    }
  # if it's anything else, return it in its original form
  return data

# <<<<<<<<<<<<<<<<<<<
#  END of copy-paste
# <<<<<<<<<<<<<<<<<<<
