"""
This module provides helper scripts for managing Solr collections.
"""
import argparse
import asyncio
import logging

import sys

from appscale.search.constants import SolrServerError, SolrClientError
from kazoo.client import KazooClient
from appscale.common.constants import LOG_FORMAT, ZK_PERSISTENT_RECONNECTS
from tornado import gen

from appscale.search import solr_adapter

logger = logging.getLogger(__name__)


def list_solr_collections():
  """ Lists all Solr collections.
  """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
  parser.add_argument(
    '--zk-locations', required=True, nargs='+', help='ZooKeeper location(s)')
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  zk_client = KazooClient(
    hosts=','.join(args.zk_locations),
    connection_retry=ZK_PERSISTENT_RECONNECTS
  )
  zk_client.start()
  adapter = solr_adapter.SolrAdapter(zk_client)

  async def list_collections():
    """ Asynchronously fetches a list of Solr collections
    from SolrCloud and prints it to stdout.
    """
    try:
      collections, broken = await adapter.solr.list_collections()
      logger.info('Collections:\n    {}'.format('\n    '.join(collections)))
      if broken:
        logger.warning('Broken collections:\n    {}'.format('\n  '.join(broken)))
    except (SolrServerError, SolrClientError) as err:
      logger.error('Failed to list Solr collections ({}).'.format(err))

  asyncio.get_event_loop().run_until_complete(list_collections())


def delete_solr_collection():
  """ Deletes specific Solr collection.
  """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
  parser.add_argument(
    '--no-prompt', action='store_true', help='Do not ask for confirmation')
  parser.add_argument(
    '--zk-locations', required=True, nargs='+', help='ZooKeeper location(s)')
  parser.add_argument(
    '--collection', required=True, help='Collection name to delete')
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  zk_client = KazooClient(
    hosts=','.join(args.zk_locations),
    connection_retry=ZK_PERSISTENT_RECONNECTS
  )
  zk_client.start()
  adapter = solr_adapter.SolrAdapter(zk_client)

  async def delete_collection():
    """ Asynchronously deletes Solr collection.
    """
    try:
      await adapter.solr.delete_collection(args.collection)
    except (SolrServerError, SolrClientError) as err:
      logger.error('Failed to delete Solr collection ({}).'.format(err))

  if args.no_prompt:
    asyncio.get_event_loop().run_until_complete(delete_collection())

  else:
    answer = input('Type collection name to confirm you want to delete it: '
                   .format(args.collection))
    if answer.strip() != args.collection:
      logger.error('Collection deletion was not confirmed')
      sys.exit(1)
    asyncio.get_event_loop().run_until_complete(delete_collection())


def reindex():
  """ Reindexes all documents in specified collection.
  This command suppose to be used when Solr schema is changed.
  """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)

  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true', help='Output debug-level logging')
  parser.add_argument(
    '--project', required=True, help='The name of GAE project')
  parser.add_argument(
    '--namespace', default='', help='The name of GAE namespace')
  parser.add_argument(
    '--index', required=True, help='The name of GAE Search index')
  parser.add_argument(
    '--zk-locations', required=True, nargs='+', help='ZooKeeper location(s)')
  args = parser.parse_args()

  if args.verbose:
    logging.getLogger('appscale').setLevel(logging.DEBUG)

  zk_client = KazooClient(
    hosts=','.join(args.zk_locations),
    connection_retry=ZK_PERSISTENT_RECONNECTS
  )
  zk_client.start()
  adapter = solr_adapter.SolrAdapter(zk_client)

  async def reindex_documents():
    """ Loops through all documents in the index and
    puts it to index again in order to apply any schema changes.
    """
    logger.info('Reindexing documents from {}|{}|{}'
                .format(args.project, args.namespace, args.index))
    has_more = True
    start_doc_id = None
    total = 0
    while has_more:
      try:
        documents = await adapter.list_documents(
          args.project, args.namespace, args.index, start_doc_id=start_doc_id,
          include_start_doc=False, limit=100, keys_only=False
        )
        logger.info('Retrieved {} documents starting from doc_id "{}"'
                    .format(len(documents), start_doc_id))
        if documents:
          await adapter.index_documents(
            args.project, args.namespace, args.index, documents
          )
          total += len(documents)
          logger.info('Indexed {} documents starting from doc_id "{}"'
                      .format(len(documents), start_doc_id))
          start_doc_id = documents[-1].doc_id
        else:
          has_more = False
      except SolrServerError as err:
        logger.exception(err)
        logger.info("Retrying in 1 second")
        await gen.sleep(1)
        continue

    logger.info('Successfully reindexed {} documents'.format(total))

  asyncio.get_event_loop().run_until_complete(reindex_documents())
