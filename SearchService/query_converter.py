""" Code for turning a GAE Search query into a SOLR query. """
import logging
import sys

from constants import INDEX_NAME_FIELD, INDEX_LOCALE_FIELD

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.search import query_parser
from google.appengine.api.search import QueryParser


class ParsingError(ValueError):
  pass


def prepare_solr_query(index, gae_query, projection_fields,
                       sort_fields, limit, offset):
  """ Constructor query parameters dict to be sent to Solr.

  Args:
    index: An Index for the query to run.
    gae_query: A str representing query sent by user.
    projection_fields: A list of fields to fetch for each document.
    sort_fields: a list of tuples of form (<FieldName>, "desc"/"asc")
    limit: a max number of document to return.
    offset: an integer representing offset.
  Returns:
    A dict containing http query params to be sent to Solr.
  """
  params = {}
  solr_query = '{}:{}'.format(INDEX_NAME_FIELD, index.name)
  if not isinstance(gae_query, unicode):
    gae_query = unicode(gae_query, 'utf-8')
  logging.debug(u'GAE Query: {}'.format(gae_query))
  if gae_query:
    query_tree = query_parser.ParseAndSimplify(gae_query)
    logging.debug(u'Tree dump: {}'.format(query_tree.toStringTree()))
    solr_query += ' AND ' + _create_query_string(index.name, query_tree)
  params['q'] = solr_query
  # Use edismax as the parsing engine for more query abilities.
  params['defType'] = 'edismax'

  # Restrict to only known index fields.
  search_fields = ['id'] + [field['name'] for field in index.schema]
  params['qf'] = ' '.join(search_fields)

  # Get the field list for the query.
  if projection_fields:
    fields_list = ['id', INDEX_NAME_FIELD, INDEX_LOCALE_FIELD] + [
      '{}_{}'.format(index.name, field_name)
      for field_name in projection_fields
    ]
    params['fl'] = ' '.join(fields_list)

  # Set sort order.
  if sort_fields:
    sort_list = _get_sort_list(index.name, sort_fields)
    params['sort'] = ','.join(sort_list)

  params['rows'] = limit
  params['start'] = offset

  logging.debug(u'Solr request params: {}'.format(params))
  return params


def _get_sort_list(index_name, sort_fields):
  """ Generates a list of Solr sort expressions:
  strings containing fields name and direction.

  Args:
    index_name: A str representing full index name (appID_namespace_index).
    sort_fields: A list of tuples of form (<FieldName>, "desc"/"asc").
  Returns:
    A list containing fields with direction to order by.
  """
  #TODO deal with default values of sort expressions.
  field_list = []
  for field_name, direction in sort_fields:
    new_field = '{}_{} {}'.format(index_name, field_name, direction)
    field_list.append(new_field)
  return field_list


def _create_query_string(index_name, query_tree):
  """ Creates a SOLR query string from a antlr3 parse tree.

  Args:
    index_name: A str representing full index name (appID_namespace_index).
    query_tree: A antlr3.tree.CommonTree.
  Returns:
    A string which can be sent to SOLR.
  """
  query_tree_type = query_tree.getType()
  has_nested = query_tree_type in [
    QueryParser.CONJUNCTION, QueryParser.DISJUNCTION, QueryParser.NEGATION
  ]
  if has_nested:
    # Processes nested query parts
    nested = [
      _create_query_string(index_name, child)
      for child in query_tree.children
    ]
    if query_tree_type == QueryParser.CONJUNCTION:
      return '({})'.format(' AND '.join(nested))
    if query_tree_type == QueryParser.DISJUNCTION:
      return '({})'.format(' OR '.join(nested))
    if query_tree_type == QueryParser.NEGATION:
      return 'NOT ({})'.format(' AND '.join(nested))

  # Process leaf of the tree
  if query_tree_type in query_parser.COMPARISON_TYPES:
    field, match = query_tree.children
    if field.getType() == QueryParser.GLOBAL:
      value = query_parser.GetQueryNodeText(match).strip('"')
      escaped_value = value.replace('"', '\\"')
      return '"{}"'.format(escaped_value)
    else:
      field_name = query_parser.GetQueryNodeText(field)
      value = query_parser.GetQueryNodeText(match).strip('"')
      internal_field_name = '{}_{}'.format(index_name, field_name)
      escaped_value = value.replace('"', '\\"')
      oper = _get_operator(query_tree_type)
      return '{}{}"{}"'.format(internal_field_name, oper, escaped_value)
  else:
    raise ParsingError('Unexpected query tree type: {}'.format(query_tree_type))


# TODO handle range operators
def _get_operator(op_code):
  """ Returns the string equivalent of the operation code.

  Args:
    op_code: An int which maps to a comparison operator.
  Returns:
    A str, the SOLR operator which maps from the operator code.
  """
  # TODO
  if op_code == QueryParser.EQ:
    return ':'
  return ':'
