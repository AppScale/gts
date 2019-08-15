"""
Restore script for new Search Service.
"""
import argparse
import logging
import random

from kazoo.client import KazooClient
from tornado import ioloop, gen

from appscale.common.constants import LOG_FORMAT, ZK_PERSISTENT_RECONNECTS
from appscale.search import api_methods
from appscale.search.backup_restore import storage

from appscale.search.protocols import search_pb2

logger = logging.getLogger(__name__)


class Importer(object):

  max_retries = 10

  def __init__(self, io_loop, source, zk_locations, max_concurrency):
    """
    Args:
      io_loop: an instance of tornado IOLoop.
      source: an instance of import Source (e.g.: S3Source).
      zk_locations: a list - Zookeeper locations.
      max_concurrency: an int - maximum number of concurrent jobs.
    """
    zk_client = KazooClient(
      hosts=','.join(zk_locations),
      connection_retry=ZK_PERSISTENT_RECONNECTS
    )
    zk_client.start()
    self.ioloop = io_loop
    self.source = source
    self.start_time = None
    self.status = 'Not started'
    self.finish_time = None
    self.api_methods = api_methods.APIMethods(zk_client)
    self.scheduled_indexes = set()
    self.scheduled_jobs = set()
    self.failed_jobs = set()
    self.succeeded_jobs = set()
    self.max_concurrency = max_concurrency
    self.docs_imported = 0

  async def import_(self):
    """ Starts concurrent jobs for importing all search indexes.
    Then it waits for all started jobs to be completed.
    """
    self.start_time = self.ioloop.time()
    self.status = 'In progress'

    for project_id, namespace, index in self.source.iter_indexes():
      self.scheduled_indexes.add((project_id, namespace, index))
      self.ioloop.add_callback(self.import_index,
                               project_id, namespace, index)

    logger.info('Waiting for all import jobs to be completed')
    while self.scheduled_indexes or self.scheduled_jobs:
      await gen.sleep(0.25)

    logger.info('Import has been finished and took {:.2f}s'
                .format(self.ioloop.time() - self.start_time))

    logger.info(' - {} jobs failed'
                .format(len(self.failed_jobs)))
    logger.info(' - {} jobs succeeded ({} documents)'
                .format(len(self.succeeded_jobs), self.docs_imported))
    self.status = 'Done'
    self.finish_time = self.ioloop.time()

  async def import_index(self, project_id, namespace, index):
    """ Starts concurrent jobs for importing entire index.
    import_ method will wait for these jobs to be completed.

    Args:
      project_id: a str - GAE project ID.
      namespace: a str - GAE search service namespace.
      index: a str - GAE Search index name.
    """
    logger.info('Starting import of index: {}/{}/{}'
                .format(project_id, namespace, index))
    first_page = True
    for key in self.source.iter_object_keys(project_id, namespace, index):
      while len(self.scheduled_jobs) > self.max_concurrency:
        await gen.sleep(0.25 * (random.random() + 0.5))
      self.scheduled_jobs.add(key)
      self.ioloop.add_callback(self.import_page, key)
      if first_page:
        # Give the first self.import_page time to create index
        # so we won't see warnings about collisions.
        await gen.sleep(1)
        first_page = False

    self.scheduled_indexes.remove((project_id, namespace, index))

  async def import_page(self, object_key):
    """ Imports a single object from backup.
    An object is instance of search_pb2.IndexDocumentResponse.

    Args:
      object_key: a str - storage object identifier.
    """
    logger.debug('Starting import of object: {}'.format(object_key))
    for attempt in range(self.max_retries):
      try:
        # >>> DO MULTIPLE RETRIES FOR THE FRAGMENT OF CODE: >>>
        index_documents_pb = self.source.get_index_documents_pb(object_key)
        response = search_pb2.IndexDocumentResponse()
        await self.api_methods.index_document(index_documents_pb, response)
        # <<< --------------------------------------------- <<<
        self.docs_imported += len(index_documents_pb.params.document)
        self.succeeded_jobs.add(object_key)
        self.scheduled_jobs.remove(object_key)
        logger.debug('Successfully imported object: {}'.format(object_key))
        break
      except Exception as err:
        logger.error('Failed to import object with key "{}" ({})'
                     .format(object_key, err))
        if attempt < self.max_retries - 1:
          backoff = 0.2 * 2**attempt
          logger.info('Retrying in {:.1f}s'.format(backoff))
          await gen.sleep(backoff)
        else:
          self.failed_jobs.add(object_key)
          self.scheduled_jobs.remove(object_key)
          raise


def main():
  """
  Reads all Search documents in backup and
  saves it to new Search Service.
  """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  parser.add_argument(
    '--s3-bucket', help='S3 bucket name holding search backup.', required=True)
  parser.add_argument(
    '--zk-locations', nargs='+', help='ZooKeeper location(s)', required=True)
  parser.add_argument(
    '--s3-location', help='Host and port S3 is listening on.')
  parser.add_argument(
    '--s3-access-key-id', help='S3 access key ID.')
  parser.add_argument(
    '--s3-secret-key', help='S3 secret key.')
  parser.add_argument(
    '--max-concurrency', type=int, help='Max import concurrency', default=10)
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  io_loop = ioloop.IOLoop(make_current=False)
  import_source = storage.S3Source(
    endpoint_url=args.s3_location,
    bucket_name=args.s3_bucket,
    access_key_id=args.s3_access_key_id,
    secret_key=args.s3_secret_key
  )
  importer = Importer(
    io_loop=io_loop,
    source=import_source,
    zk_locations=args.zk_locations,
    max_concurrency=args.max_concurrency
  )

  try:
    io_loop.run_sync(importer.import_)
  finally:
    io_loop.close()
