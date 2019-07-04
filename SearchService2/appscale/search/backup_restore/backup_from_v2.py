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
  def __init__(self, solr_api, project_id, namespace, index,
               page_size, max_retries):
    self.solr_api = solr_api
    self.collection = solr_adapter.get_collection_name(
      project_id, namespace, index
    )
    self.last_seen_id = '*'
    self.page_size = page_size
    self.max_retries = max_retries

  def __aiter__(self):
    return self

  async def __anext__(self):
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
          logger.info('Retrying in {:.1}s'.format(backoff))
          await gen.sleep(backoff)
        else:
          raise

    if not solr_result.documents:
      raise StopAsyncIteration()
    left = self.last_seen_id
    right = self.last_seen_id = solr_result.documents[-1]['id']
    return left, right


class Exporter(object):

  max_retries = 10
  page_size = 100

  def __init__(self, io_loop, zk_locations, target, max_concurrency):
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
    self.start_time = self.ioloop.time()
    self.status = 'In progress'

    collections, broken = await self.solr_adapter.solr.list_collections()
    if broken:
      logger.warning('There are {} broken collections: {}. It will be ignored.'
                     .format(len(broken), list(broken)))
    for collection_name in collections:
      if not collection_name.startswith('appscale_'):
        logger.info('Collection {} does not belong to Search Service. Ignoring.'
                    .format(collection_name))
      _, project_id, namespace, index = collection_name.split('_')
      self.scheduled_indexes.add((project_id, namespace, index))
      self.ioloop.add_callback(self.export_index, project_id, namespace, index)

    logger.info('Waiting for all export jobs to be completed')
    while self.scheduled_indexes or self.scheduled_jobs:
      await gen.sleep(0.25)

    logger.info('Export has been finished and took {:.2}s'
                .format(self.ioloop.time() - self.start_time))

    logger.info(' - {} jobs failed'
                .format(len(self.failed_jobs)))
    logger.info(' - {} jobs succeeded ({} documents)'
                .format(len(self.succeeded_jobs), self.docs_exported))
    self.status = 'Done'
    self.finish_time = self.ioloop.time()

  async def export_index(self, project_id, namespace, index):
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
    except:
      self.scheduled_indexes.remove((project_id, namespace, index))
      self.failed_indexes.add((project_id, namespace, index))
      raise

  async def export_page(self, project_id, namespace, index, left_id, right_id):
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
          logger.info('Retrying in {:.1}s'.format(backoff))
          await gen.sleep(backoff)
        else:
          self.scheduled_jobs.remove(page_key)
          self.failed_jobs.add(page_key)
          raise


def main():
  """ Start Backup process. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  parser.add_argument(
    '--s3-location', help='Host and port S3 is listening on.', required=True)
  parser.add_argument(
    '--s3-access-key-id', help='S3 access key ID.', required=True)
  parser.add_argument(
    '--s3-secret-key', help='S3 secret key.', required=True)
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
