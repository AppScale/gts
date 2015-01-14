""" Code for turning a GAE Search query into a SOLR query. """
import logging
import os
import sys
import urllib

from solr_interface import Document

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api.search import query_parser
from google.appengine.api.search import QueryParser

class SolrQueryParser():
  """ Class for parsing search queries. """
  def __init__(self, index, app_id, namespace):
    """ Constructor for query parsing. 
    
    Args:
      index: An Index for the query to run.
      app_id: A str, the application ID.
      namespace: A str, the current namespace.
    """
    self.__index = index
    self.__fields = []
    self.__app_id = app_id
    self.__namespace = namespace

  def get_solr_query_string(self, query):
    """ Parses the query and returns a query string.

    The fields must be replaced by the internal field name given.

    Args:
      query: The query string.
    Returns:
      A SOLR string.
    """
    query_string = "q={0}:{1} ".format(Document.INDEX_NAME, self.__index.name) 
    if len(query) > 0:
      self.__fields = []
      query = urllib.unquote(query)
      query = query.strip()
      if not isinstance(query, unicode):
        query = unicode(query, 'utf-8')
      logging.debug("Query: {0}".format(query))
      query_tree = query_parser.ParseAndSimplify(query)
      logging.debug("DUMP :{0}".format(self.__dump_tree(query_tree)))
      query_string += "AND " + self.__create_string(query_tree)
    # Deal with orders and other fields. TODO
    logging.debug("SOLR STRING: {0}".format(query_string))
    return query_string

  def __create_string(self, query_tree):
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
          q_str += " AND "
        q_str += self.__create_string(child)
      q_str += ")"
      return q_str
    elif query_tree.getType() == QueryParser.DISJUNCTION:
      q_str += " AND ("
      for index, child in enumerate(query_tree.children):
        if index != 0:
          q_str += " OR "
        q_str += self.__create_string(child)
      q_str += ")"
      return q_str
    elif query_tree.getType() == QueryParser.NEGATION:
      q_str += " NOT ("
      for index, child in enumerate(query_tree.children):
        if index != 0:
          q_str += " AND "
        q_str += self.__create_string(child)
      q_str += ")"
      return q_str
    elif query_tree.getType() in query_parser.COMPARISON_TYPES:
      field, match = query_tree.children
      if field.getType() == QueryParser.GLOBAL:
        field = query_parser.GetQueryNodeText(match)
        field = self.__escape_chars(field) #TODO
        q_str += " \"{0}\" ".format(field)
      else:
        field = query_parser.GetQueryNodeText(field)
        match = query_parser.GetQueryNodeText(match)
        internal_field_name = self.__get_internal_field_name(field) #TODO
        escaped_value = self.__escape_chars(match) #TODO
        op = self.__get_operator(query_tree.getType())
        q_str += " {0}{1}\"{2}\" ".format(internal_field_name, op, escaped_value)
      return q_str
    logging.warning("No node match for {0}".format(query_tree.getType()))
    return ""

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
    """ Dumps the tree contents. """
    return node.toStringTree()

