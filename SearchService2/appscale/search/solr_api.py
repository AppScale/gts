"""
Helper module for handling routine work when communicating with Solr API.
It knows where Solr servers are located, how to pass request arguments
to API methods, etc.
"""
import itertools
import json
import logging
import socket
import time

from urllib.parse import urlencode

from tornado import httpclient, ioloop
from appscale.common import appscale_info

from appscale.search.constants import (
  SolrIsNotReachable, SOLR_TIMEOUT, SolrClientError, SolrServerError,
  SolrError, SOLR_COMMIT_WITHIN, APPSCALE_CONFIG_SET_NAME
)
from appscale.search.models import SolrSearchResult

logger = logging.getLogger(__name__)


def tornado_synchronous(coroutine):
  """ Builds synchronous function based on tornado coroutine.

  Args:
    coroutine: a generator (tornado.gen.coroutine).
  Returns:
    A regular python function.
  """
  def synchronous_coroutine(*args, **kwargs):
    async = lambda: coroutine(*args, **kwargs)
    # Like synchronous HTTPClient, create separate IOLoop for sync code
    io_loop = ioloop.IOLoop(make_current=False)
    try:
      return io_loop.run_sync(async)
    finally:
      io_loop.close()
  return synchronous_coroutine


class SolrAPI(object):
  """
  A helper class for performing basic operations with Solr.
  """
  CACHE_TTL = 600

  def __init__(self, zk_client, solr_zk_root, settings):
    """ Initializes SolrAPI object.
    Configures zookeeper watching of Solr live nodes.

    Args:
      zk_client:
      solr_zk_root:
    """
    self._zk_client = zk_client
    self._solr_zk_root = solr_zk_root
    self._settings = settings
    self._solr_live_nodes_list = []
    self._solr_live_nodes_cycle = itertools.cycle(self._solr_live_nodes_list)
    self._local_solr = None
    self._private_ip = appscale_info.get_private_ip()
    self._zk_client.ChildrenWatch(
      '{}/live_nodes'.format(self._solr_zk_root), self._update_live_nodes
    )
    self._collections_cache = set()
    self._broken_collections_cache = set()
    self._cache_timestamp = 0.0

    # Warm-up collections cache
    list_collections_sync = tornado_synchronous(self.list_collections)
    list_collections_sync()

  def _update_live_nodes(self, new_live_nodes):
    """ Updates information about Solr live nodes.

    Args:
      new_live_nodes: a list of strings representing Solr location.
    """
    self._solr_live_nodes_list = [
      node.replace('_solr', '') for node in new_live_nodes
    ]
    self._solr_live_nodes_cycle = itertools.cycle(self._solr_live_nodes_list)
    self._local_solr = next(
      (node for node in self._solr_live_nodes_list
       if node.startswith(self._private_ip)), None
    )
    logger.info('Got a new list of solr live nodes: {}'
                .format(self._solr_live_nodes_list))

  @property
  def solr_location(self):
    """
    Returns:
      A string representing Solr location (preferably local).
    """
    if self._local_solr:
      return self._local_solr
    if not self._solr_live_nodes_list:
      raise SolrIsNotReachable('There are no Solr live nodes')
    return next(self._solr_live_nodes_cycle)

  @property
  def live_nodes(self):
      return self._solr_live_nodes_list

  async def request(self, method, path, params=None, json_data=None):
    """ Sends HTTP request to one of Solr live nodes.

    Args:
      method: a str - HTTP method.
      path: a str - HTTP path.
      params: a dict containing URL params
      json_data: a json-serializable object to pass in request body.
    Returns (asynchronously):
      A httpclient.HTTPResponse.
    """
    if params:
      url_params = urlencode(params)
      url = 'http://{}{}?{}'.format(self.solr_location, path, url_params)
    else:
      url = 'http://{}{}'.format(self.solr_location, path)

    if json_data is not None:
      headers = {'Content-type': 'application/json'}
      body = json.dumps(json_data)
    else:
      headers = None
      body = None

    if path.endswith('query'):
      logger.debug(u'QUERY_BODY: {}'.format(body))

    async_http_client = httpclient.AsyncHTTPClient()
    request = httpclient.HTTPRequest(
      url=url, method=method, headers=headers, body=body,
      connect_timeout=SOLR_TIMEOUT, request_timeout=SOLR_TIMEOUT,
      allow_nonstandard_methods=True
    )
    try:
      response = await async_http_client.fetch(request)
    except socket.error as err:
      raise SolrIsNotReachable('Socket error ({})'.format(err))
    except httpclient.HTTPError as err:
      msg = u"Error during Solr call {url} ({err})".format(url=url, err=err)
      if err.response.body:
        json_resp = json.loads(err.response.body.decode('utf-8'))
        try:
          err_details = json_resp['error']['msg']
          if 'no such collection' in err_details:
            # Update collections cache in background
            ioloop.IOLoop.current().spawn_callback(self.list_collections)
        except ValueError:
          err_details = err.response.body.decode('utf-8')
        msg += u"\nError details: {}".format(err_details)
      logger.error(msg)
      if err.response.code < 500:
        raise SolrClientError(msg)
      else:
        raise SolrServerError(msg)

    return response

  async def get(self, path, params=None, json_data=None):
    """ GET wrapper of request method """
    response = await self.request('GET', path, params, json_data)
    return response

  async def post(self, path, params=None, json_data=None):
    """ POST wrapper of request method """
    response = await self.request('POST', path, params, json_data)
    return response

  async def list_collections(self):
    """ Lists names of collections created in Solr.
    Returned list can contain collection with missing core.

    Returns (asynchronously):
      A list of collection names present in Solr.
    """
    try:
      response = await self.get('/solr/admin/collections',
                                params={'action': 'CLUSTERSTATUS'})
      response_data = json.loads(response.body.decode('utf-8'))
      collections = response_data['cluster']['collections']
      has_cores = []
      has_no_cores = []
      for collection_name, collection_status in collections.items():
        shards = collection_status['shards'].values()
        if any(shard['replicas'] for shard in shards):
          has_cores.append(collection_name)
        else:
          has_no_cores.append(collection_name)
      self._collections_cache = set(has_cores)
      self._broken_collections_cache = set(has_no_cores)
      self._cache_timestamp = time.time()
      return self._collections_cache, self._broken_collections_cache
    except (SolrError, KeyError):
      logger.exception('Failed to list collections')
      raise

  async def does_collection_exist(self, collection):
    # Check if collection is already known locally
    if collection in self._collections_cache:
      return True
    if self._cache_timestamp + self.CACHE_TTL < time.time():
      if collection in self._broken_collections_cache:
        logger.warning('Collection "{}" seems to be in broken state'
                       .format(collection))
        return True

    # Update local cache and check again
    collections, broken_collections = await self.list_collections()
    if collection in collections:
      return True
    if collection in self._broken_collections_cache:
      logger.warning('Collection "{}" seems to be in broken state'
                     .format(collection))
      return True
    return False

  async def ensure_collection(self, collection):
    """ Asynchronously ensures that Solr collection is created.

    Args:
      collection: a str - name of collection to make sure is created.
    """
    if await self.does_collection_exist(collection):
      return
    # Create Solr collection
    try:
      # Collection creation in API v2 doesn't support collection.configName yet.
      # So using old API (/solr/...).
      response = await self.get(
        '/solr/admin/collections',
        params={
          'action': 'CREATE',
          'name': collection,
          'collection.configName': APPSCALE_CONFIG_SET_NAME,
          'replicationFactor': self._settings.replication_factor,
          'autoAddReplicas': True,
          'numShards': self._settings.shards_number,
          'maxShardsPerNode': self._settings.max_shards_per_node,
          'waitForFinalState': True,
        }
      )
      logger.info('Successfully created collection {} ({})'
                  .format(collection, response.body))
    except SolrError as err:
      if 'collection already exists' in err.error_detail:
        logger.info('Collection {} already exists'.format(collection))
      elif 'Cannot create collection ' in err.error_detail:
        logging.warning('Solr message: {}'.format(err.error_detail))
        logging.warning('Scheduling deletion of collection {}'
                        .format(collection))
        ioloop.IOLoop.current().spawn_callback(
          self.delete_collection, collection
        )
        raise
      else:
        logger.warning('Failed to create collection {}'.format(collection))
        raise
    # Update collections cache in background
    ioloop.IOLoop.current().spawn_callback(self.list_collections)

  async def delete_collection(self, collection):
    try:
      response = await self.get(
        '/solr/admin/collections',
        params={
          'action': 'DELETE',
          'name': collection
        }
      )
      logger.info('Successfully deleted collection {} ({})'
                  .format(collection, response.body))
    except SolrError as err:
      if 'Could not find collection' in err.error_detail:
        logger.info('Collection {} does not exits'.format(collection))
      else:
        logger.warning('Failed to delete collection {}'.format(collection))
        raise
    # Update collections cache in background
    ioloop.IOLoop.current().spawn_callback(self.list_collections)

  async def get_schema_info(self, collection):
    """ Retrieves collection shema information. It uses Luke handler
    because, in contrast to a regular get method of Schema API,
    Luke handler provides information about dynamically created fields.

    Args:
      collection:
    Returns (asynchronously):
      A dict containing information about Solr collection.
    """
    await self.ensure_collection(collection)
    try:
      # Luke handler is not supported in API v2 yet.
      # /v2/collections/<COLLECTION>/schema/fields doesn't show dynamically
      # created fields.
      # So using old API (/solr/...).
      response = await self.get(
        '/solr/{}/admin/luke?numTerms=0'.format(collection)
      )
      return json.loads(response.body.decode('utf-8'))
    except SolrError:
      logger.warning('Failed to fetch fields list for collection {}'
                     .format(collection))
      raise

  async def put_documents(self, collection, documents):
    """ Asynchronously puts documents into Solr collection.

    Args:
      collection: a str - name of Solr collection.
      documents: a list of documents to put.
    """
    await self.ensure_collection(collection)
    try:
      if SOLR_COMMIT_WITHIN:
        params = {'commitWithin': SOLR_COMMIT_WITHIN}
      else:
        params = {'commit': 'true'}
      await self.post(
        '/v2/collections/{}/update'.format(collection),
        params=params, json_data=documents
      )
      logger.info('Successfully indexed {} documents to collection {}'
                  .format(len(documents), collection))
    except SolrError:
      logger.warning('Failed to put {} documents to collection {}'
                     .format(len(documents), collection))
      raise

  async def delete_documents(self, collection, ids):
    """ Asynchronously deletes documents from Solr collection.

    Args:
      collection: a str - name of Solr collection.
      ids: a list of document IDs to delete.
    """
    await self.ensure_collection(collection)
    try:
      if SOLR_COMMIT_WITHIN:
        params = {'commitWithin': SOLR_COMMIT_WITHIN}
      else:
        params = {'commit': 'true'}
      # Delete operation doesn't work with API v2 yet.
      # So using old API (/solr/...).
      await self.post(
        '/solr/{}/update'.format(collection),
        params=params, json_data={"delete": ids}
      )
      logger.info('Successfully deleted {} documents from collection {}'
                  .format(len(ids), collection))
    except SolrError:
      logger.warning('Failed to delete {} documents from collection {}'
                     .format(len(ids), collection))
      raise

  async def query_documents(self, collection, query, filter_=None, offset=None,
                            limit=None, fields=None, sort=None, facet_dict=None,
                            cursor=None, def_type=None, query_fields=None,
                            stats_fields=None):
    """ Queries Solr for documents matching specified query.

    Args:
      collection: a str - name of Solr collection
      query: a str - Solr query string.
      filter_: a str - Solr filter criteria.
      offset: a int - number of first document to skip.
      limit: a int - max number of document to return.
      fields: a list of field names to return for each document.
      sort: a list of field names suffixed with direction to order results by.
      facet_dict: a dict describing facets to compute.
      cursor: a str - query cursors.
      def_type: a str - query parser type to use.
      query_fields: a list of field names to run query against.
      stats_fields: a list of fields to retrieve stats for.
    Returns (asynchronously):
      A SolrSearchResult containing documents, facets, cursor
      and total number of documents matching the query.
    """
    await self.ensure_collection(collection)

    # Query params which are not supported by JSON Request API yet
    # should go inside "params" attribute.
    # See https://lucene.apache.org/solr/guide/7_6/json-request-api.html
    # for more details.
    params = {
      key: value for key, value in [
        ('cursorMark', cursor),
        ('defType', def_type),
        ('qf', ' '.join(query_fields) if query_fields else ''),
        ('stats', 'true' if stats_fields else None),
        ('stats.field', stats_fields)
      ]
      if value is not None
    }
    json_data = {
      key: value for key, value in [
        ('query', query),
        ('filter', filter_),
        ('offset', offset),
        ('limit', limit),
        ('fields', fields),
        ('facet', facet_dict),
        ('sort', ','.join(sort) if sort else ''),
        ('params', params)
      ]
      if value is not None
    }

    try:
      response = await self.post(
        '/v2/collections/{}/query'.format(collection),
        json_data=json_data
      )
      json_response = json.loads(response.body.decode('utf-8'))
      query_response = json_response['response']
      stats = json_response.get('stats')
      solr_search_result = SolrSearchResult(
        num_found=query_response['numFound'],
        documents=query_response['docs'],
        cursor=json_response.get('nextCursorMark'),
        facet_results=json_response.get('facets', {}),
        stats_results=stats.get('stats_fields', {}) if stats else {}
      )
      logger.debug('Found {} and fetched {} documents from collection {}'
                   .format(solr_search_result.num_found,
                           len(solr_search_result.documents), collection))
      return solr_search_result
    except SolrError:
      logger.warning('Failed to execute query {} against collection {}'
                     .format(json_data, collection))
      raise
