"""
api_methods module handles high level processing of protocol buffer
requests to search service:
  - extracts information from search_pb2 protobuf requests;
  - asynchronously calls particular method implementation in SolrAdapter
    (interaction with SolrAdapter is done using objects described in
    appscale.search.models which corresponds to Google Search API objects);
  - fills search_pb2 protobuf response.
"""
import logging
import time
import uuid
from datetime import datetime

from appscale.search import solr_adapter
from appscale.search.constants import (
  InvalidRequest, UnknownFieldTypeException,
  UnknownFacetTypeException
)
from appscale.search.models import Field, Document, Facet, FacetRefinement, \
  FacetRequest
from appscale.search.protocols import search_pb2

logger = logging.getLogger(__name__)


class APIMethods(object):
  """
  An instance of APIMethods implements async coroutines which
  process Search API protocol buffer requests.

  SolrAdapter implements Google Search API methods using Solr as a backend,
  when APIMethods just wraps it with protocol buffer.
  """

  def __init__(self, zk_client):
    """ Initialises an instance of APIMethods.
    In particular it creates SoldAdapter.

    Args:
      zk_client: An instance of kazoo.client.KazooClient.
    """
    self.solr_adapter = solr_adapter.SolrAdapter(zk_client)

  async def index_document(self, index_doc_request, index_doc_response):
    """ Indexes/updates documents.

    Args:
      index_doc_request: A search_pb2.IndexDocumentRequest.
      index_doc_response: A search_pb2.IndexDocumentResponse.
    """
    app_id = index_doc_request.app_id.decode('utf-8')
    params = index_doc_request.params
    index_spec = params.index_spec
    namespace = index_spec.namespace
    index_name = index_spec.name
    document_list = params.document

    # Ensure document IDs are specified.
    for pb_doc in document_list:
      if not pb_doc.id:
        pb_doc.id = str(uuid.uuid4())

    documents = [_from_pb_document(pb_doc) for pb_doc in document_list]
    await self.solr_adapter.index_documents(
      app_id=app_id, namespace=namespace, index_name=index_name,
      documents=documents
    )

    index_doc_response.doc_id.extend([pb_doc.id for pb_doc in document_list])
    ok = search_pb2.RequestStatus(code=search_pb2.SearchServiceError.OK)
    index_doc_response.status.extend([ok] * len(document_list))

  async def delete_document(self, delete_doc_request, delete_doc_response):
    """ Deletes specified documents.

    Args:
      delete_doc_request: A search_pb2.DeleteDocumentRequest.
      delete_doc_response: A search_pb2.DeleteDocumentResponse.
    """
    app_id = delete_doc_request.app_id.decode('utf-8')
    params = delete_doc_request.params
    index_spec = params.index_spec
    namespace = index_spec.namespace
    index_name = index_spec.name
    ids = list(params.doc_id)

    await self.solr_adapter.delete_documents(
      app_id=app_id, namespace=namespace, index_name=index_name, ids=ids
    )

    ok = search_pb2.RequestStatus(code=search_pb2.SearchServiceError.OK)
    delete_doc_response.status.extend([ok] * len(ids))

  async def list_indexes(self, list_indexes_request, list_indexes_response):
    """ Lists all indexes for an application.

    Args:
      list_indexes_request: A search_pb2.ListIndexesRequest.
      list_indexes_response: A search_pb2.ListIndexesResponse.
    """
    raise InvalidRequest("List indexes method is not implemented "
                         "in AppScale SearchService2 yet")

  async def list_documents(self, list_documents_request, list_documents_response):
    """ List all documents within an index.

    Args:
      list_documents_request: A search_pb2.ListDocumentsRequest.
      list_documents_response: A search_pb2.ListDocumentsResponse.
    """
    app_id = list_documents_request.app_id.decode('utf-8')
    params = list_documents_request.params
    index_spec = params.index_spec
    start_doc_id = params.start_doc_id
    include_start_doc = params.include_start_doc
    limit = params.limit
    keys_only = params.keys_only
    namespace = index_spec.namespace
    index_name = index_spec.name

    documents = await self.solr_adapter.list_documents(
      app_id=app_id, namespace=namespace, index_name=index_name,
      start_doc_id=start_doc_id, include_start_doc=include_start_doc,
      limit=limit, keys_only=keys_only
    )
    list_documents_response.status.code = search_pb2.SearchServiceError.OK
    for doc in documents:
      new_doc = list_documents_response.document.add()
      _fill_pb_document(new_doc, doc)

  async def search(self, search_request, search_response):
    """ Searches for documents matching a query.

    Args:
      search_request: A search_pb2.SearchRequest.
      search_response: A search_pb2.SearchResponse.
    """
    app_id = search_request.app_id.decode('utf-8')
    # Extract basic search params
    params = search_request.params
    query = params.query
    projection_fields = params.field_spec.name
    sort_fields = [
      (field.sort_expression, 'desc' if field.sort_descending else 'asc')
      for field in params.sort_spec
    ]
    limit = params.limit
    offset = params.offset
    index_spec = params.index_spec
    namespace = index_spec.namespace
    index_name = index_spec.name
    cursor = params.cursor or None
    keys_only = params.keys_only

    # Extract facets-specific params
    auto_discover_facet_count = params.auto_discover_facet_count
    facet_requests = [
      _from_pb_facet_request(pb_facet_request)
      for pb_facet_request in params.include_facet
    ]
    facet_refinements = [
      _from_pb_facet_refinement(pb_facet_refinement)
      for pb_facet_refinement in params.facet_refinement
    ]
    facet_auto_detect_limit = params.facet_auto_detect_param.value_limit
    # facet_depth = params.facet_depth  # Ignoring facet_depth

    # Select documents using Solr
    search_result = await self.solr_adapter.query(
      app_id=app_id, namespace=namespace, index_name=index_name,
      query=query, projection_fields=projection_fields,
      sort_expressions=sort_fields, limit=limit, offset=offset,
      cursor=cursor, keys_only=keys_only,
      auto_discover_facet_count=auto_discover_facet_count,
      facet_requests=facet_requests, facet_refinements=facet_refinements,
      facet_auto_detect_limit=facet_auto_detect_limit,
    )
    _fill_search_response(search_response, search_result)


def _fill_search_response(pb_response, search_result):
  """ Fills pb_response according to the data in search_results.

  Args:
    pb_response: A search_pb2.SearchResponse.
    search_result: An instance of models.SearchResult.
  """
  pb_response.matched_count = search_result.num_found
  pb_response.status.code = search_pb2.SearchServiceError.OK
  if search_result.cursor:
    pb_response.cursor = search_result.cursor
  for facet_result in search_result.facet_results:
    new_facet = pb_response.facet_result.add()
    _fill_pb_facet_result(new_facet, facet_result)
  for doc in search_result.scored_documents:
    new_result = pb_response.result.add()
    # new_result.score.extend([<SCORES ACCORDING TO SORT>])
    _fill_pb_document(new_result.document, doc)


def _fill_pb_document(pb_document, doc):
  """ Fills pb_doc according to the data in doc.

  Args:
    pb_document: A search_pb2.Document.
    doc: An instance of models.ScoredDocument.
  Raises:
    UnknownFieldTypeException: If doc contains field of unknown type.
  """
  pb_document.id = doc.doc_id
  if doc.language:
    pb_document.language = doc.language
  for field in doc.fields:
    lang = field.language or doc.language or None

    new_field = pb_document.field.add()
    new_field.name = field.name
    if lang:
      new_field.value.language = lang

    if field.type == Field.Type.TEXT:
      new_field.value.type = search_pb2.FieldValue.TEXT
      new_field.value.string_value = field.value
    elif field.type == Field.Type.HTML:
      new_field.value.type = search_pb2.FieldValue.HTML
      new_field.value.string_value = field.value
    elif field.type == Field.Type.ATOM:
      new_field.value.type = search_pb2.FieldValue.ATOM
      new_field.value.string_value = field.value
    elif field.type == Field.Type.NUMBER:
      new_field.value.type = search_pb2.FieldValue.NUMBER
      new_field.value.string_value = str(field.value)
    elif field.type == Field.Type.DATE:
      new_field.value.type = search_pb2.FieldValue.DATE
      timestamp = int(time.mktime(field.value.timetuple()) * 1000)
      new_field.value.string_value = str(timestamp)
    elif field.type == Field.Type.GEO:
      new_field.value.type = search_pb2.FieldValue.GEO
      new_field.value.geo.lat = field.value[0]
      new_field.value.geo.lng = field.value[1]
    else:
      raise UnknownFieldTypeException(
        "A document contains a field of unknown type: {}"
        .format(field.type)
      )

  for facet in doc.facets:
    new_facet = pb_document.facet.add()
    new_facet.name = facet.name
    if facet.type == Facet.Type.ATOM:
      new_facet.value.type = search_pb2.FacetValue.ATOM
      new_facet.value.string_value = facet.value
    elif facet.type == Facet.Type.NUMBER:
      new_facet.value.type = search_pb2.FacetValue.NUMBER
      new_facet.value.string_value = str(facet.value)
    else:
      raise UnknownFacetTypeException(
        "A document contains a facet of unknown type: {}"
        .format(facet.type)
      )


def _from_pb_document(pb_document):
  """ Converts pb_document to an instance of models.Document.

  Args:
    pb_document: A search_pb2.Document.
  Returns:
    An instance of models.Document.
  Raises:
    UnknownFieldTypeException: If pb_document contains field of unknown type.
  """
  fields = []
  for pb_field in pb_document.field:
    pb_value = pb_field.value
    if pb_value.type == search_pb2.FieldValue.TEXT:
      type_ = Field.Type.TEXT
      value = pb_value.string_value
    elif pb_value.type == search_pb2.FieldValue.HTML:
      type_ = Field.Type.HTML
      value = pb_value.string_value
    elif pb_value.type == search_pb2.FieldValue.ATOM:
      type_ = Field.Type.ATOM
      value = pb_value.string_value
    elif pb_value.type == search_pb2.FieldValue.NUMBER:
      type_ = Field.Type.NUMBER
      value = float(pb_value.string_value)
    elif pb_value.type == search_pb2.FieldValue.DATE:
      type_ = Field.Type.DATE
      timestamp = float(pb_value.string_value) / 1000
      value = datetime.fromtimestamp(timestamp)
    elif pb_value.type == search_pb2.FieldValue.GEO:
      type_ = Field.Type.GEO
      value = (pb_value.geo.lat, pb_value.geo.lng)
    else:
      raise UnknownFieldTypeException(
        "GAE document contains a field of unknown type: {}"
        .format(pb_value.type)
      )
    field = Field(type_, pb_field.name, value,
                  pb_field.value.language or pb_document.language)
    fields.append(field)

  facets = []
  for pb_facet in pb_document.facet:
    pb_value = pb_facet.value
    if pb_value.type == search_pb2.FacetValue.ATOM:
      type_ = Facet.Type.ATOM
      value = pb_value.string_value
    elif pb_value.type == search_pb2.FacetValue.NUMBER:
      type_ = Facet.Type.NUMBER
      value = float(pb_value.string_value)
    else:
      raise UnknownFacetTypeException(
        "GAE document contains a facet of unknown type: {}"
        .format(pb_value.type)
      )
    facet = Facet(type_, pb_facet.name, value)
    facets.append(facet)

  return Document(
    doc_id=pb_document.id,
    fields=fields,
    facets=facets,
    language=pb_document.language,
    rank=pb_document.order_id or int(time.time())
  )


def _fill_pb_facet_result(pb_facet_result, facet_result):
  pb_facet_result.name = facet_result.name
  for value, count in facet_result.values:
    new_value = pb_facet_result.value.add()
    new_value.name = value
    new_value.count = count
    new_value.refinement.name = facet_result.name
    new_value.refinement.value = value
  for start, end, count in facet_result.ranges:
    new_value = pb_facet_result.value.add()
    new_value.name = '[{}, {})'.format(start if start is not None else '*',
                                       end if end is not None else '*')
    new_value.count = count
    new_value.refinement.name = facet_result.name
    new_value.refinement.range.start = str(start)
    new_value.refinement.range.end = str(end)


def _from_pb_facet_request(pb_facet_request):
  params = pb_facet_request.params
  return FacetRequest(
    name=pb_facet_request.name,
    value_limit=params.value_limit,
    values=list(params.value_constraint),
    ranges=[
      (int(range_.start) if range_.start else None,
       int(range_.end) if range_.end else None)
      for range_ in params.range
    ],
  )


def _from_pb_facet_refinement(pb_facet_refinement):
  range_ = pb_facet_refinement.range
  if not range_.start and not range_.end:
    range_ = None
  return FacetRefinement(
    name=pb_facet_refinement.name,
    value=pb_facet_refinement.value or None,
    range=(range_.start, range_.end) if range_ else None
  )
