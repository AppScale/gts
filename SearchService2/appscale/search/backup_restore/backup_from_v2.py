"""
Backup script for new Search Service.
"""
import argparse
from datetime import datetime
import logging
import random

from appscale.search.constants import SolrClientError
from kazoo.client import KazooClient
from tornado import gen, ioloop
from appscale.common.constants import LOG_FORMAT, ZK_PERSISTENT_RECONNECTS
from appscale.search import solr_adapter, api_methods
from appscale.search.backup_restore import storage

from appscale.search.protocols import search_pb2

logger = logging.getLogger(__name__)


class IDRangesGenerator(object):
  """
  Asynchronous ID ranges generator.
  Helps to quickly determine chunks of work for further processing.
  """

  def __init__(self, solr_api, project_id, namespace, index,
               page_size, max_retries):
    """
    Args:
      solr_api: an instance of SolrAPI.
      project_id: a str - GAE project ID.
      namespace: a str - GAE search service namespace.
      index: a str - GAE Search index name.
      page_size: an int - max length of ID range.
      max_retries: an int - max attempts to perform before failing.
    """
    self.solr_api = solr_api
    self.collection = solr_adapter.get_collection_name(
      project_id, namespace, index
    )
    self.last_seen_id = '*'
    self.page_size = page_size
    self.max_retries = max_retries

  def __aiter__(self):
    """ Returns: asynchronous iterator. """
    return self

  async def __anext__(self):
    """ Retrieves another IDs page from Solr and returns
    min and max IDs on the page.

    Returns:
      a tuple (left_id, right_id) representing next IDs range.
    Raises:
      StopAsyncIteration or Solr-related error.
    """
    solr_filter_query = 'id:{{{} TO *]'.format(self.last_seen_id)

    for attempt in range(self.max_retries):
      try:
        # >>> DO MULTIPLE RETRIES FOR THE FRAGMENT OF CODE: >>>
        solr_result = await self.solr_api.query_documents(
          collection=self.collection, query='*:*', filter_=solr_filter_query,
          limit=self.page_size, fields=['id'], sort=['id asc']
        )
        # <<< --------------------------------------------- <<<
        break
      except SolrClientError:
        raise
      except Exception as err:
        logger.error('Failed to get another IDs range {}/{} ({})'
                     .format(self.collection, solr_filter_query, err))
        if attempt < self.max_retries - 1:
          backoff = 0.2 * 2**attempt
          logger.info('Retrying in {:.1f}s'.format(backoff))
          await gen.sleep(backoff)
        else:
          raise

    if not solr_result.documents:
      raise StopAsyncIteration()
    left = self.last_seen_id
    right = self.last_seen_id = solr_result.documents[-1]['id']
    return left, right


class Exporter(object):
  """
  Exports data from Search Service 2 to target storage.
  """

  max_retries = 10
  page_size = 100

  def __init__(self, io_loop, zk_locations, target, max_concurrency):
    """
    Args:
      io_loop: an instance of tornado IOLoop.
      zk_locations: a list - Zookeeper locations.
      target: an instance of export Target (e.g.: S3Target).
      max_concurrency: an int - maximum number of concurrent jobs.
    """
    zk_client = KazooClient(
      hosts=','.join(zk_locations),
      connection_retry=ZK_PERSISTENT_RECONNECTS
    )
    zk_client.start()
    self.ioloop = io_loop
    self.target = target
    self.start_time = None
    self.status = 'Not started'
    self.finish_time = None
    self.solr_adapter = solr_adapter.SolrAdapter(zk_client)
    self.scheduled_indexes = set()
    self.failed_indexes = set()
    self.succeeded_indexes = set()
    self.scheduled_jobs = set()
    self.failed_jobs = set()
    self.succeeded_jobs = set()
    self.max_concurrency = max_concurrency
    self.docs_exported = 0

  async def export(self):
    """ Start concurrent export jobs for each Search index.
    Waits for all export jobs to be completed.
    """
    self.start_time = self.ioloop.time()
    self.status = 'In progress'

    solr_collections, broken = await self.solr_adapter.solr.list_collections()
    if broken:
      logger.warning('There are {} broken collections: {}. It will be ignored.'
                     .format(len(broken), list(broken)))
    for collection_name in solr_collections:
      if not collection_name.startswith('appscale_'):
        logger.info('Collection {} does not belong to Search Service. Ignoring.'
                    .format(collection_name))
        continue
      _, project_id, namespace, index = collection_name.split('_')
      self.scheduled_indexes.add((project_id, namespace, index))
      self.ioloop.add_callback(self.export_index, project_id, namespace, index)

    logger.info('Waiting for all export jobs to be completed')
    while self.scheduled_indexes or self.scheduled_jobs:
      await gen.sleep(0.25)

    logger.info('Export has been finished and took {:.2f}s'
                .format(self.ioloop.time() - self.start_time))

    logger.info(' - {} jobs failed'
                .format(len(self.failed_jobs)))
    logger.info(' - {} jobs succeeded ({} documents)'
                .format(len(self.succeeded_jobs), self.docs_exported))
    self.status = 'Done'
    self.finish_time = self.ioloop.time()

  async def export_index(self, project_id, namespace, index):
    """ Starts export of a particular Search index.
    Initiates asynchronous jobs for each IDs range and waits
    for all jobs to be completed.

    Args:
      project_id: a str - GAE project ID.
      namespace: a str - namespace name.
      index: a str - search index name.
    """
    logger.info('Starting export of index: {}/{}/{}'
                .format(project_id, namespace, index))
    id_ranges_generator = IDRangesGenerator(
      self.solr_adapter.solr, project_id, namespace, index,
      self.page_size, self.max_retries
    )
    try:
      async for left_id, right_id in id_ranges_generator:
        while len(self.scheduled_jobs) > self.max_concurrency:
          await gen.sleep(0.25 * (random.random() + 0.5))
        page_key = project_id, namespace, index, left_id, right_id
        self.scheduled_jobs.add(page_key)
        self.ioloop.add_callback(self.export_page, *page_key)
      self.scheduled_indexes.remove((project_id, namespace, index))
      self.succeeded_indexes.add((project_id, namespace, index))
    except Exception:
      self.scheduled_indexes.remove((project_id, namespace, index))
      self.failed_indexes.add((project_id, namespace, index))
      raise

  async def export_page(self, project_id, namespace, index, left_id, right_id):
    """ Exports a single page of Search documents.

    Args:
      project_id: a str - GAE project ID.
      namespace: a str - namespace name.
      index: a str - search index name.
      left_id: a str - min document ID to retrieve.
      right_id: a str - max document ID to retrieve.
    """
    logger.debug('Starting export of page: {}/{}/{}/["{}", "{}"]'
                 .format(project_id, namespace, index, left_id, right_id))
    page_key = project_id, namespace, index, left_id, right_id

    index_docs_pb = search_pb2.IndexDocumentRequest()
    index_docs_pb.app_id = project_id.encode()
    index_docs_pb.params.index_spec.name = index
    index_docs_pb.params.index_spec.namespace = namespace

    for attempt in range(self.max_retries):
      try:
        # >>> DO MULTIPLE RETRIES FOR THE FRAGMENT OF CODE: >>>
        documents = await self.solr_adapter.list_documents(
          project_id, namespace, index,
          start_doc_id=left_id, include_start_doc=True,
          max_doc_id =right_id, include_max_doc=True,
          limit=self.page_size*2, keys_only=False
        )
        for doc in documents:
          document_pb = index_docs_pb.params.document.add()
          api_methods._fill_pb_document(document_pb, doc)
        self.target.save(project_id, namespace, index, index_docs_pb)
        # <<< --------------------------------------------- <<<
        self.scheduled_jobs.remove(page_key)
        self.succeeded_jobs.add(page_key)
        self.docs_exported += len(documents)
        break
      except SolrClientError:
        raise
      except Exception as err:
        logger.error(
          'Failed to export page {}/{}/{}/["{}", "{}"] ({})'
          .format(project_id, namespace, index, left_id, right_id, err)
        )
        if attempt < self.max_retries - 1:
          backoff = 0.2 * 2**attempt
          logger.info('Retrying in {:.1f}s'.format(backoff))
          await gen.sleep(backoff)
        else:
          self.scheduled_jobs.remove(page_key)
          self.failed_jobs.add(page_key)
          raise


def main():
  """
  Saves all search documents from new Search Service
  to S3 storage.
  """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  parser.add_argument(
    '--s3-location', help='Host and port S3 is listening on.')
  parser.add_argument(
    '--s3-access-key-id', help='S3 access key ID.')
  parser.add_argument(
    '--s3-secret-key', help='S3 secret key.')
  parser.add_argument(
    '--zk-locations', nargs='+', help='ZooKeeper location(s)', required=True)
  parser.add_argument(
    '--max-concurrency', type=int, help='Max import concurrency', default=10)
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  io_loop = ioloop.IOLoop(make_current=False)
  bucket_name = 'search-backup.{:%Y-%m-%d.%H-%M-%S}'.format(datetime.now())
  export_target = storage.S3Target(
    endpoint_url=args.s3_location,
    bucket_name=bucket_name,
    access_key_id=args.s3_access_key_id,
    secret_key=args.s3_secret_key
  )
  exporter = Exporter(
    io_loop=io_loop,
    zk_locations=args.zk_locations,
    target=export_target,
    max_concurrency=args.max_concurrency
  )

  try:
    io_loop.run_sync(exporter.export)
    logger.info('Backup bucket name: {}'.format(bucket_name))
  finally:
    io_loop.close()
