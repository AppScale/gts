""" Code for turning a GAE Search query into a SOLR query. """
import logging
import os
import sys
import urllib

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api.search import query_parser
from google.appengine.api.search import QueryParser

# Encoded value for a comma ','.
COMMA = "%2C"

# Encoded value for a colon ':'.
COLON = "%3A"

# Encoded value for a space ' '.
SPACE = "%20"

class SolrQueryParser():
  """ Class for parsing search queries. """
  def __init__(self, index, app_id, namespace, field_spec, sort_list,
    limit, offset):
    """ Constructor for query parsing. 
    
    Args:
      index: An Index for the query to run.
      app_id: A str, the application ID.
      namespace: A str, the current namespace.
      field_spec: A search_service_pb.FieldSpec.
      sort_list: A list of search_service_pb.SortSpec.
      limit: An int, the max number of results to return.
      offset: An int, the number of items to skip.
    """
    self.__index = index
    self.__app_id = app_id
    self.__namespace = namespace
    self.__field_spec = field_spec
    self.__sort_list  = sort_list
    self.__limit = limit
    self.__offset = offset

  def get_solr_query_string(self, query):
    """ Parses the query and returns a query string.

    The fields must be replaced by the internal field name given.

    Args:
      query: The query string.
    Returns:
      A SOLR string.
    """
    query_string = "q={0}{1}{2}".format(Document.INDEX_NAME, COLON, 
      self.__index.name) 
    if len(query) > 0:
      query = urllib.unquote(query)
      query = query.strip()
      if not isinstance(query, unicode):
        query = unicode(query, 'utf-8')
      logging.debug("Query: {0}".format(query))
      query_tree = query_parser.ParseAndSimplify(query)
      logging.debug("Tree dump:{0}".format(self.__dump_tree(query_tree)))
      query_string += "+AND+" + self.__create_query_string(query_tree)
      logging.debug("Query string {0}".format(query_string))
    # Use edismax as the parsing engine for more query abilities.
    query_string += "&defType=edismax"

    query_fields = self.__get_query_fields()
   
    # Get the field list for the query.
    field_list = self.__get_field_list()
    logging.debug("Field list: {0}".format(field_list))
    if field_list:
      query_string += field_list
    else:
      logging.debug("Using default field list")
      query_string += "&fl=id+" + Document.INDEX_LOCALE + "+" + query_fields
     
    # Set sort order.
    query_string += self.__get_sort_list()

    # Restrict to only fields requested or all of the fields from the schema. 
    query_string += "&qf=" + query_fields
    query_string += "&pf=" + query_fields

    query_string += self.__get_row_limit()

    query_string += self.__get_offset()
 
    logging.debug("SOLR STRING: {0}".format(query_string))
    return query_string

  def __get_row_limit(self):
    """ Returns the SOLR string that restricts the number of results.

    Returns:
      A str that is the rows limit in a SOLR query.
    """
    return "&rows={0}".format(self.__limit)

  def __get_offset(self):
    """ Returns the SOLR string that offsets the results.

    Returns:
      A str that tells SOLR how many documents to skip.
    """
    return "&start={0}".format(self.__offset) 

  def __get_query_fields(self):
    """ Gets the query fields for a SOLR query.

    Return:
      A str, a list of fields we want to restrict the result by.
    """
    if self.__field_spec.name_size() == 0:
      # Select all fields from the schema.
      schema_fields = self.__index.schema.fields
      field_names = []
      for field in schema_fields:
        field_names.append(field['name'])
      if field_names:
        return '+'.join(field_names)
      else:
        return Document.INDEX_NAME
    else:
      field_names = []
      for field_name in self.__field_spec.name_list():
        field_names.append("{0}_{1}".format(self.__index.name, field_name))
      if field_names:
        return '+'.join(field_names)
      else:
        return ""

  def __get_sort_list(self):
    """ Gets the SOLR sort list argument for the SOLR query.

    Returns:
      A str, the sort portion of the SOLR query string.
    """
    #TODO deal with default values of sort expressions.
    field_list = []
    for sort_spec in self.__sort_list:
      new_field = "{0}_{1}".format(self.__index.name,
        sort_spec.sort_expression())
      if sort_spec.sort_descending() == 1:
        new_field += "+desc" 
      else:
        new_field += "+asc"   
      field_list.append(new_field)

    if field_list: 
      return "&sort={0}".format(COMMA.join(field_list))
    else:
      return ""

  def __get_field_list(self):
    """ Gets the field list for the SOLR query.

    Returns:
      A str, the field list for the query.
    """
    field_string = ""
    field_list = []
    if self.__field_spec.name_size() > 0:
      field_string += "&fl=id,"
      for field_name in self.__field_spec.name_list():
        field_list.append("{0}_{1}".format(self.__index.name, field_name))
      field_string += SPACE.join(field_list) 
      logging.debug("Field string: {0}".format(field_string))
      return field_string
    else:
      return field_string 

  def __create_query_string(self, query_tree):
    """ Creates a SOLR query string from a antlr3 parse tree.
    
    Args:
      query_tree: A antlr3.tree.CommonTree.
    Returns:
      A string which can be sent to SOLR.
    """
    q_str = ""
    if query_tree.getType() == QueryParser.CONJUNCTION:
      q_str += "("
      for index, child in enumerate(query_tree.children):
        if index != 0:
          q_str += "+AND"
        q_str += self.__create_query_string(child)
      q_str += ")"
    elif query_tree.getType() == QueryParser.DISJUNCTION:
      q_str += "+AND+("
      for index, child in enumerate(query_tree.children):
        if index != 0:
          q_str += "+OR"
        q_str += self.__create_query_string(child)
      q_str += ")"
    elif query_tree.getType() == QueryParser.NEGATION:
      q_str += "+NOT+("
      for index, child in enumerate(query_tree.children):
        if index != 0:
          q_str += "+AND"
        q_str += self.__create_query_string(child)
      q_str += ")"
    elif query_tree.getType() in query_parser.COMPARISON_TYPES:
      field, match = query_tree.children
      if field.getType() == QueryParser.GLOBAL:
        field = query_parser.GetQueryNodeText(match)
        field = self.__escape_chars(field) #TODO
        q_str += "\"{0}\"".format(field)
      else:
        field = query_parser.GetQueryNodeText(field)
        match = query_parser.GetQueryNodeText(match)
        internal_field_name = self.__get_internal_field_name(field) #TODO
        escaped_value = self.__escape_chars(match) #TODO
        oper = self.__get_operator(query_tree.getType())
        q_str += "{0}{1}\"{2}\"".format(internal_field_name, oper,
          escaped_value)
    else:
      logging.warning("No node match for {0}".format(query_tree.getType()))
    logging.debug("Query string: {0}".format(q_str))
    q_str = urllib.quote_plus(q_str, '+')
    logging.debug("Encoded: {0}".format(q_str))
    return q_str

  # TODO handle range operators

  def __get_operator(self, op_code):
    """ Returns the string equivalent of the operation code.
   
    Args:
      op_code: An int which maps to a comparison operator.
    Returns:
      A str, the SOLR operator which maps from the operator code.
    """
    # TODO
    if op_code == QueryParser.EQ:
      return ":"
    return ":"

  def __escape_chars(self, value):
    """ Puts in escape characters for certain characters which are a part of
    query syntax.

    Args:
      value: A str, the field value.
    Returns:
      A str, the escaped value.
    """
    new_value = ""
    for char in value:
      if char in ['\\', '+', '-', '!', '(', ')', ':', '^', '[', ']', '"', 
        '{', '}', '~', '*', '?', '|', '&', ';', '/', " "]:
        new_value += '\\'
      new_value += char 
    return new_value

  def __get_internal_field_name(self, field_name):
    """ Converts a field name to the internal field name used in SOLR.

    Args:
      field_name: A str, the field name supplied by the application.
    Returns:
      A str, the internal field name for SOLR. 
    """
    for field in self.__index.schema.fields:
      if field['name'].endswith(field_name) and \
        field['name'].startswith("{0}_{1}_".format(self.__app_id,
        self.__namespace)):
        return field['name']
    logging.error("Unable to find field name {0}".format(field_name))
    return ""

  def __dump_tree(self, node):
    """ Dumps the tree contents. 

    Args:
      node: The head node to convert to a human readable string.
    Returns:
      A str, the tree in human readable format.
    """
    return node.toStringTree()

class Document(): 
  """ Represents a document stored in SOLR. """ 
 
  # Prefix code for index name. 
  INDEX_NAME = "_gaeindex_name" 
   
  # Prefix code for index locale. 
  INDEX_LOCALE = "_gaeindex_locale" 
 
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

