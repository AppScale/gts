"""
Implements Search API functionality using Solr as a backend.

Interaction between APIMethods and SolrAdapter is done using objects
described in appscale.search.models.
"""

import collections
import logging
import re
import time
from datetime import datetime

from appscale.search import query_converter, facet_converter
from appscale.search.constants import (
  SOLR_ZK_ROOT, SUPPORTED_LANGUAGES, UnknownFieldTypeException,
  UnknownFacetTypeException, InvalidRequest)
from appscale.search.models import (
  Field, ScoredDocument, SearchResult, SolrIndexSchemaInfo, SolrSchemaFieldInfo,
  Facet, IndexMetadata
)
from appscale.search.settings import SearchServiceSettings
from appscale.search.solr_api import SolrAPI

logger = logging.getLogger(__name__)

# The regex helps to identify no supported sort expression
EXPRESSION_SIGN = re.compile('[-+*/,()]')


class SolrAdapter(object):
  """
  SolrAdapter implements Google Search API methods using Solr as a backend.
  Solr adapter is used by APIMethods which
  wraps it with protocol buffer conversion.
  """

  def __init__(self, zk_client):
    """ Initialises an instance of SolrAdapter.
    In particular it creates SolrAPI object which helps to perform
    basic operation with Solr API.

    Args:
      zk_client: An instance of kazoo.client.KazooClient.
    """
    self._settings = SearchServiceSettings(zk_client)
    self.solr = SolrAPI(zk_client, SOLR_ZK_ROOT, self._settings)

  async def list_indexes(self, app_id):
    """ Retrieves basic indexes metadata.

    Args:
      app_id: a str representing Application ID.
    Return (asynchronously):
      A list of models.IndexMetadata.
    """
    solr_collections, broken = await self.solr.list_collections()
    indexes_metadata = []
    for collection in solr_collections:
      _, app, namespace, index = collection.split('_')
      if app != app_id:
        continue
      metadata = IndexMetadata(app, namespace, index)
      indexes_metadata.append(metadata)
    return indexes_metadata

  async def index_documents(self, app_id, namespace, index_name, documents):
    """ Puts specified documents into the index (asynchronously).

    Args:
      app_id: a str representing Application ID.
      namespace: a str representing GAE namespace or None.
      index_name: a str representing name of Search API index.
      documents: a list of documents to put into the index.
    """
    collection = get_collection_name(app_id, namespace, index_name)
    solr_documents = [_to_solr_document(doc) for doc in documents]
    await self.solr.put_documents(collection, solr_documents)

  async def delete_documents(self, app_id, namespace, index_name, ids):
    """ Deletes documents with specified IDs from the index (asynchronously).

    Args:
      app_id: a str representing Application ID.
      namespace: a str representing GAE namespace or None.
      index_name: a str representing name of Search API index.
      ids: a list of document IDs to delete.
    """
    collection = get_collection_name(app_id, namespace, index_name)
    await self.solr.delete_documents(collection, ids)

  async def list_documents(self, app_id, namespace, index_name, start_doc_id,
                           include_start_doc, limit, keys_only,
                           max_doc_id=None, include_max_doc=True):
    """ Retrieves up to limit documents starting from start_doc_id
    and converts it from Solr format to unified Search API documents.

    Args:
      app_id: a str representing Application ID.
      namespace: a str representing GAE namespace or None.
      index_name: a str representing name of Search API index.
      start_doc_id: a str - doc ID to start from.
      include_start_doc: a bool indicating if the start doc should be included.
      limit: a int - max number of documents to retrieve.
      keys_only: a bool indicating if only document keys should be returned.
      max_doc_id: a str - max doc ID to retrieve.
      include_max_doc: a bool indicating if the max doc should be included.
    Return (asynchronously):
      A list of models.ScoredDocument.
    """
    collection = get_collection_name(app_id, namespace, index_name)

    if start_doc_id or max_doc_id:
      # Apply range filter to ID
      start_doc_id = '*' if start_doc_id is None else start_doc_id
      max_doc_id = '*' if max_doc_id is None else max_doc_id
      left_bracket = '[' if include_start_doc else '{'
      right_bracket = ']' if include_max_doc else '}'
      solr_filter_query = 'id:{}{} TO {}{}'.format(
        left_bracket, start_doc_id, max_doc_id, right_bracket
      )
    else:
      solr_filter_query = None
    # Order by ID
    solr_sort_fields = ['id asc']

    solr_projection_fields = None
    if keys_only:
      # Skip everything but ID
      solr_projection_fields = ['id']

    # Use *:* to match any document
    solr_search_result = await self.solr.query_documents(
      collection=collection, query='*:*', filter_=solr_filter_query,
      limit=limit, fields=solr_projection_fields, sort=solr_sort_fields
    )
    docs = [_from_solr_document(solr_doc)
            for solr_doc in solr_search_result.documents]
    return docs

  async def query(self, app_id, namespace, index_name, query, projection_fields,
                  sort_expressions, limit, offset, cursor, keys_only,
                  auto_discover_facet_count, facet_requests,  facet_refinements,
                  facet_auto_detect_limit):
    """ Retrieves documents which matches query from Solr collection
    and converts it to unified documents.

    Args:
      app_id: a str representing Application ID.
      namespace: a str representing GAE namespace or None.
      index_name: a str representing name of Search API index.
      query: a str containing Search API query.
      projection_fields: a list of field names to return in results.
      sort_expressions: a list of sort expressions, e.g.: ("field1", "asc").
      limit: an int specifying maximum number of results to return.
      offset: an int specifying number of first document to skip.
      cursor: a str representing query cursor.
      keys_only: a bool indicating if only document IDs should be returned.
      auto_discover_facet_count: An int - number of top facets to discover.
      facet_requests: A list of FacetRequest.
      facet_refinements: A list of FacetRefinement.
      facet_auto_detect_limit: An int - number of top terms to return.
    Returns (asynchronously):
      An instance of models.SearchResult.
    """
    index_schema = await self._get_schema_info(app_id, namespace, index_name)
    # Convert Search API query to Solr query with a list of fields to search.
    query_options = query_converter.prepare_solr_query(
      query, index_schema.fields, index_schema.grouped_fields
    )
    # Process GAE projection fields
    solr_projection_fields = self._convert_projection(
      keys_only, projection_fields, index_schema
    )
    # Process GAE sort expressions
    solr_sort_fields = self._convert_sort_expressions(
      sort_expressions, index_schema
    )
    # Process GAE facet-related parameters
    refinement_filter = None
    if facet_refinements:
      # Determine if we need to filter by refinement.
      refinement_filter = facet_converter.generate_refinement_filter(
        index_schema.grouped_facet_indexes, facet_refinements
      )
    facet_items, stats_items = await self._convert_facet_args(
      auto_discover_facet_count, facet_auto_detect_limit, facet_requests,
      index_schema, query_options, refinement_filter
    )
    stats_fields = [stats_line for solr_field, stats_line in stats_items]

    # DO ACTUAL QUERY:
    solr_result = await self.solr.query_documents(
      collection=index_schema.collection,
      query=query_options.query_string, offset=offset, limit=limit,
      cursor=cursor, fields=solr_projection_fields, sort=solr_sort_fields,
      def_type=query_options.def_type, query_fields=query_options.query_fields,
      facet_dict=dict(facet_items) if facet_items else None,
      stats_fields=stats_fields or None, filter_=refinement_filter
    )

    # Convert Solr results to unified models
    docs = [_from_solr_document(solr_doc)
            for solr_doc in solr_result.documents]
    # Read stats results
    stats_results = []
    for solr_field, stats_line in stats_items:
      stats_info = solr_result.stats_results[solr_field.solr_name]
      stats_results.append((solr_field.gae_name, stats_info))
    # Convert facet results from Solr facets and stats
    facet_results = facet_converter.convert_facet_results(
      solr_result.facet_results, stats_results
    )
    result = SearchResult(
      num_found=solr_result.num_found, scored_documents=docs,
      cursor=cursor, facet_results=facet_results
    )
    return result

  @staticmethod
  def _convert_projection(keys_only, gae_projection_fields, index_schema):
    """ Converts GAE projection field names to Solr field names.

    Args:
      keys_only: A boolean indicating if only document IDs should be returned.
      gae_projection_fields: A list of GAE field names to retrieve.
      index_schema: An instance of SolrIndexSchemaInfo.
    Returns:
      A list of Solr fields to retrieve for documents.
    """
    if gae_projection_fields:
      # Process projection_fields
      solr_projection_fields = ['id', 'rank', 'language']
      for gae_name in gae_projection_fields:
        # (1) In GAE fields with different type can have the same name,
        # in Solr they are stored as fields with different name (type suffix).
        try:
          solr_projection_fields += [
            solr_field.solr_name for solr_field in
            index_schema.grouped_fields[gae_name]
          ]
        except KeyError:
          logger.warning('Unknown field "{}" in projection'.format(gae_name))
      return solr_projection_fields
    elif keys_only:
      # Skip everything but ID.
      return ['id', 'rank', 'language']
    else:
      # Return all fields.
      return None

  @staticmethod
  def _convert_sort_expressions(gae_sort_expressions, index_schema):
    """ Converts GAE sort expressions to Solr sort expressions.

    Args:
      gae_sort_expressions: A list of GAE sort expressions.
      index_schema: An instance of SolrIndexSchemaInfo.
    Returns:
      A list of
    """
    solr_sort_expressions = []
    if gae_sort_expressions:
      for sort_expression, direction in gae_sort_expressions:
        try:
          # Date fields are indexes as two fields. DATE_FIELD should be ignored.
          fields_group = [
            solr_field
            for solr_field in index_schema.grouped_fields[sort_expression]
            if solr_field.type != SolrSchemaFieldInfo.Type.DATE_FIELD
          ]
        except KeyError:
          if EXPRESSION_SIGN.search(sort_expression):
            raise InvalidRequest(
              'Sort expression currently supports only field names, '
              'can not sort by expression "{}"'.format(sort_expression)
            )
          else:
            logger.warning('Unknown field "{}" in sort expression'
                           .format(sort_expression))
            continue
        if len(fields_group) > 1:
          # Multiple field types are used for field with the same GAE name [*1],
          # so let's pick most "popular" field of those.
          field_types = ', '.join(
            '{}: {} docs'.format(field.type, field.docs_number)
            for field in fields_group
          )
          logger.warning(
            'Multiple field types are used for field {} ({}). Sorting by {}.'
            .format(sort_expression, field_types, fields_group[0].type)
          )
        solr_field = fields_group[0]
        solr_name = solr_field.solr_name
        if solr_field.type == SolrSchemaFieldInfo.Type.TEXT_FIELD:
          solr_sort_expr = 'field({}) {}'.format(solr_name, direction)
          solr_sort_expressions.append(solr_sort_expr)
        elif solr_field.type == SolrSchemaFieldInfo.Type.ATOM_FIELD:
          solr_sort_expr = 'field({}) {}'.format(solr_name, direction)
          solr_sort_expressions.append(solr_sort_expr)
        else:
          solr_sort_expr = '{} {}'.format(solr_name, direction)
          solr_sort_expressions.append(solr_sort_expr)
    if not solr_sort_expressions:
      solr_sort_expressions = ['rank desc']
    return solr_sort_expressions

  async def _convert_facet_args(self, auto_discover_facet_count,
                                facet_auto_detect_limit, facet_requests,
                                index_schema, query_options, refinement_filter):
    """ Converts GAE facet arguments to Solr facet items
    and Solr stats fields.

    Args:
      auto_discover_facet_count: An int - number of top facets to discover.
      facet_auto_detect_limit: An int - number of top terms to return.
      facet_requests: A list of FacetRequest.
      index_schema: An instance of SolrIndexSchemaInfo.
      query_options: An instance of SolrQueryOptions.
      refinement_filter: A str - Solr filter corresponding to refinement.
    Returns (asynchronously):
      A tuple of two lists (<facet_items>, <stats_items>).
    """
    # Process Facet params
    facet_items = []
    stats_items = []
    if auto_discover_facet_count:
      # Figure out what facets are specified for greater number of documents.
      atom_facets_stats = await self._get_facets_stats(
        index_schema, query_options, refinement_filter
      )
      # Add auto-discovered facets to the list.
      auto_facet_items, auto_stats_items = facet_converter.discover_facets(
        atom_facets_stats, auto_discover_facet_count,
        facet_auto_detect_limit
      )
      facet_items += auto_facet_items
      stats_items += auto_stats_items
    if facet_requests:
      # Add explicitly specified facets to the list.
      explicit_facet_items, explicit_stats_items = (
        facet_converter.convert_facet_requests(
          index_schema.grouped_facet_indexes, facet_requests
        )
      )
      facet_items += explicit_facet_items
      stats_items += explicit_stats_items
    return facet_items, stats_items

  async def _get_schema_info(self, app_id, namespace, gae_index_name):
    """ Retrieves information about schema of Solr collection
    corresponding to Search API index.

    Args:
      app_id: a str representing Application ID.
      namespace: a str representing GAE namespace or None.
      gae_index_name: a str representing name of Search API index.
    Returns (asynchronously):
      An instance of SolrIndexSchemaInfo.
    """
    collection = get_collection_name(app_id, namespace, gae_index_name)
    solr_schema_info = await self.solr.get_schema_info(collection)
    fields_info = solr_schema_info['fields']
    id_field = SolrSchemaFieldInfo(
      solr_name='id', gae_name='doc_id', type=Field.Type.ATOM,
      language=None, docs_number=fields_info.get('id', {}).get('docs', 0)
    )
    rank_field = SolrSchemaFieldInfo(
      solr_name='rank', gae_name='rank', type=Field.Type.NUMBER,
      language=None, docs_number=fields_info.get('rank', {}).get('docs', 0)
    )
    fields = [id_field, rank_field]
    grouped_fields = {
      'doc_id': [id_field],
      'rank': [rank_field]
    }
    facets = []
    grouped_facet_indexes = {}

    for solr_field_name, info in fields_info.items():
      try:
        gae_name, type_, language = parse_solr_field_name(solr_field_name)
      except ValueError:
        continue
      schema_field = SolrSchemaFieldInfo(
        solr_field_name, gae_name, type_, language, info.get('docs', 0)
      )
      if SolrSchemaFieldInfo.Type.is_facet_index(type_):
        add_value(grouped_facet_indexes, gae_name, schema_field)
      if SolrSchemaFieldInfo.Type.is_facet(type_):
        facets.append(schema_field)
      else:
        fields.append(schema_field)
        add_value(grouped_fields, gae_name, schema_field)

    for fields_group in grouped_fields.values():
      if len(fields_group) > 1:
        # Sadly app uses the same name for fields with different types [*1].
        # Let's sort them from high popularity to low.
        fields_group.sort(key=lambda solr_field: -solr_field.docs_number)

    for facets_group in grouped_facet_indexes.values():
      if len(facets_group) > 1:
        # Sadly app uses the same name for facets with different types [*1].
        # Let's sort them from high popularity to low.
        facets_group.sort(key=lambda solr_field: -solr_field.docs_number)

    index_info = solr_schema_info['index']
    return SolrIndexSchemaInfo(
      app_id=app_id,
      namespace=namespace,
      gae_index_name=gae_index_name,
      collection=collection,
      docs_number=index_info['numDocs'],
      heap_usage=index_info['indexHeapUsageBytes'],
      size_in_bytes=index_info['segmentsFileSizeInBytes'],
      fields=fields,
      facets=facets,
      grouped_fields=grouped_fields,
      grouped_facet_indexes=grouped_facet_indexes
    )

  async def _get_facets_stats(self, index_schema, query_options,
                              refinement_filter):
    """ Retrieves statistics of fields corresponding to facets of atom type.
    Statistics per fields contains only number of documents containing
    that solr field from those documents which matches the query.

    Args:
      index_schema: an instance of SolrIndexSchemaInfo.
      query_options: a instance of SolrQueryOptions.
      refinement_filter: a str representing Solr filter.
    Returns:
      A list of tuples (<SolrSchemaFieldInfo>, <documents count>).
    """
    facets_fields = [
      facet for facet in index_schema.facets
      if SolrSchemaFieldInfo.Type.is_facet_index(facet.type)
    ]
    request_facet_stats = [
      # e.g.: '{!count=true}myfacetname_facet'
      '{{!count=true}}{field_name}'.format(field_name=facet.solr_name)
      for facet in facets_fields
    ]
    solr_result = await self.solr.query_documents(
      collection=index_schema.collection, query=query_options.query_string,
      offset=0, limit=0, fields=['id'], def_type=query_options.def_type,
      query_fields=query_options.query_fields, filter_=refinement_filter,
      stats_fields=request_facet_stats
    )
    field_stats_items = []
    for facet in facets_fields:
      documents_count = solr_result.stats_results[facet.solr_name]['count']
      field_stats_items.append((facet, documents_count))
    return field_stats_items


def get_collection_name(app_id, namespace, gae_index_name):
  return u'appscale_{}_{}_{}'.format(app_id, namespace, gae_index_name)


def add_value(dict_, key, value):
  """ Helps to have functionality of defaultdict(list) using a regular dict.
  It's needed because a regular dict raises KeyError when key is not present
  in the dict_, which is more transparent behaviour.

  Args:
    dict_: a dict to add value to.
    key: a key, under which value should be added to.
    value: a value to append to a list under the key in dict_.
  """
  values = dict_.get(key)
  if not values:
    dict_[key] = [value]
  else:
    values.append(value)


def _to_solr_document(document):
  """ Converts an instance of models.Document
  to dictionary in format supported by Solr.

  Args:
    document: an instance of models.Document.
  Returns:
    A dictionary in Solr format.
  """
  solr_doc = collections.defaultdict(list)
  solr_doc['id'] = document.doc_id
  solr_doc['rank'] = document.rank
  solr_doc['language'] = document.language or ''

  for field in document.fields:

    lang_suffix = ''
    lang = field.language or document.language
    if lang in SUPPORTED_LANGUAGES:
      lang_suffix = '_{}'.format(lang)
    elif lang is not None:
      logger.warning('Language "{}" is not supported'.format(lang))

    if field.type == Field.Type.TEXT:
      solr_field_name = '{}_{}{}'.format(field.name, 'txt', lang_suffix)
      solr_doc[solr_field_name].append(field.value)
    elif field.type == Field.Type.HTML:
      raise InvalidRequest('Indexing HTML fields is not supported yet')
    elif field.type == Field.Type.ATOM:
      solr_field_name = '{}_{}'.format(field.name, 'atom')
      solr_doc[solr_field_name].append(field.value)
    elif field.type == Field.Type.NUMBER:
      solr_field_name = '{}_{}'.format(field.name, 'number')
      solr_doc[solr_field_name].append(field.value)
    elif field.type == Field.Type.DATE:
      # A single GAE date field goes as two Solr fields.
      # <field_name>_date is DateRange field which is used for queries
      solr_field_name = '{}_{}'.format(field.name, 'date')
      datetime_str = field.value.strftime('%Y-%m-%dT%H:%M:%SZ')
      solr_doc[solr_field_name].append(datetime_str)
      # <field_name>_date_ms is integer field which is used for sorting
      solr_field_name = '{}_{}'.format(field.name, 'date_ms')
      datetime_ms = int(time.mktime(field.value.timetuple()) * 1000)
      solr_doc[solr_field_name].append(datetime_ms)
    elif field.type == Field.Type.GEO:
      solr_field_name = '{}_{}'.format(field.name, 'geo')
      geo_str = '{},{}'.format(field.value[0], field.value[1])
      solr_doc[solr_field_name].append(geo_str)
    else:
      raise UnknownFieldTypeException(
        "A document contains a field of unknown type: {}".format(field.type)
      )

  for facet in document.facets:
    if facet.type == Facet.Type.ATOM:
      # A single GAE facet goes as two Solr fields.
      # <field_name>_atom_facet_value stores original value (not indexed).
      solr_field_name = '{}_{}'.format(facet.name, 'atom_facet_value')
      solr_doc[solr_field_name].append(facet.value)
      # <field_name>_atom_facet stores lowercased value (indexed).
      solr_field_name = '{}_{}'.format(facet.name, 'atom_facet')
      solr_doc[solr_field_name].append(facet.value.lower())
    elif facet.type == Facet.Type.NUMBER:
      solr_field_name = '{}_{}'.format(facet.name, 'number_facet')
      solr_doc[solr_field_name].append(facet.value)
    else:
      raise UnknownFacetTypeException(
        "A document contains a facet of unknown type: {}".format(facet.type)
      )

  return solr_doc


def _from_solr_document(solr_doc):
  """ Converts solr_doc to models.ScoredDocument.

  Args:
    solr_doc: a dict containing a document as returned from Solr.
  Returns:
    An instance of models.ScoredDocument.
  """
  fields = []
  facets = []
  for solr_field_name, values in solr_doc.items():
    try:
      # Extract field name, type and language from solr_field_name
      name, solr_type_, language = parse_solr_field_name(solr_field_name)
      gae_type = _SOLR_TO_GAE_TYPE_MAPPING[solr_type_]
    except (ValueError, KeyError):
      # Skip Solr fields created outside SearchService2
      # or internal index fields.
      continue

    # Convert string values to python types if applicable
    if gae_type == Field.Type.DATE:
      values = [datetime.strptime(datetime_str, '%Y-%m-%dT%H:%M:%SZ')
                for datetime_str in values]
    elif gae_type == Field.Type.GEO:
      lat_lng_strs = (geo_str.split(',') for geo_str in values)
      values = [(lat_str, lng_str) for lat_str, lng_str in lat_lng_strs]

    if SolrSchemaFieldInfo.Type.is_facet(solr_type_):
      # Add facet for each value
      for value in values:
        facet = Facet(gae_type, name, value)
        facets.append(facet)
    else:
      # Add field for each value
      for value in values:
        field = Field(gae_type, name, value, language)
        fields.append(field)

  return ScoredDocument(
    doc_id=solr_doc['id'],
    fields=fields,
    facets=facets,
    language=solr_doc['language'],
    sort_scores=None,   # Is not supported yet
    expressions=None,   # Is not supported yet
    cursor=None,        # Is not supported yet
    rank=solr_doc['rank']
  )


_FIELD_TYPE = (
  'atom|number|date|date_ms|geo|txt'
  '|atom_facet|atom_facet_value|number_facet'
)
_SOLR_TO_GAE_TYPE_MAPPING = {
  SolrSchemaFieldInfo.Type.ATOM_FIELD: Field.Type.ATOM,
  SolrSchemaFieldInfo.Type.NUMBER_FIELD: Field.Type.NUMBER,
  SolrSchemaFieldInfo.Type.DATE_FIELD: Field.Type.DATE,
  # SolrSchemaFieldInfo.Type.DATE_MS_FIELD: Field.Type.DATE,
  SolrSchemaFieldInfo.Type.GEO_FIELD: Field.Type.GEO,
  SolrSchemaFieldInfo.Type.TEXT_FIELD: Field.Type.TEXT,
  # SolrSchemaFieldInfo.Type.ATOM_FACET_INDEX: Facet.Type.ATOM,
  SolrSchemaFieldInfo.Type.ATOM_FACET: Facet.Type.ATOM,
  SolrSchemaFieldInfo.Type.NUMBER_FACET: Facet.Type.NUMBER,
}
_LANGUAGE = '|'.join(SUPPORTED_LANGUAGES)
_FIELD_NAME_PATTERN = re.compile(
  '^(?P<field_name>[\w_]+?)_(?P<solr_type>{})(_(?P<language>{}))?$'
  .format(_FIELD_TYPE, _LANGUAGE)
)


def parse_solr_field_name(solr_field_name):
  """ Extracts GAE field/facet name, field/facet type and language
  from Solr field name.

  Args:
    solr_field_name: a str representing field name of Solr collection.
  Returns:
    A tuple of (<field/facet_name>, <field/facet_type>, <language>).
  """
  match = _FIELD_NAME_PATTERN.match(solr_field_name)
  if not match:
    raise ValueError('Provided Solr field does not belong to Search Service')
  field_name = match.group('field_name')
  solr_type = match.group('solr_type')
  language = match.group('language') or ''
  return field_name, solr_type, language
