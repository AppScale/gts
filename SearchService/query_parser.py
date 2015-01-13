""" Code for turning a GAE Search query into a SOLR query. """
import logging
import os
import sys
import urllib

from solr_interface import Document

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api.search import query_parser
from google.appengine.api.search import search_util
from google.appengine.api.search import QueryParser

class SolrQueryParser():
  """ Class for parsing search queries. """
  def __init__(self, index):
    """ Constructor for query parsing. 
    
    Args:
      index: An Index for the query to run.
    """
    self.__index = index
    self.__fields = []
    self.__expression = ""

  def get_solr_query_string(self, query):
    """ Parses the query and returns a query string.

    The fields must be replaced by the internal field name given.

    Args:
      query: The query string.
    Returns:
      A SOLR string.
    """
    expression = "q={0}:{1}".format(Document.INDEX_NAME, self.__index.name) 
    if len(query) > 0:
      self.__fields = []
      self.__expression = ""
      query = urllib.unquote(query)
      query = query.strip()
      if not isinstance(query, unicode):
        query = unicode(query, 'utf-8')
      logging.info("Query: {0}".format(query))
      query_tree = query_parser.ParseAndSimplify(query)
      logging.info("DUMP :{0}".format(self.__dump_tree(query_tree)))
      query_string = expression + self.create_string(query_tree)
    return ""

  def __create_string(self, query_tree):
    """ Creates a SOLR query string from a antlr3 parse tree.
    
    Args:
      query_tree: A antlr3.tree.CommonTree.
    Returns:
      A string which can be sent to SOLR.
    """
    if query_tree.getType() == QueryParser.CONJUNCTION:
      for child in query_tree.children:
        q_str += self.__create_string(child)
      return q_str
    else:
      return ""

  def __dump_tree(self, node):
    """ Dumps the tree contents. """
    logging.info("To string: {0}".format(query_tree.toStringTree()))

