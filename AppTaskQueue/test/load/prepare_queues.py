import argparse
import json
import logging
import os
import time

import kazoo.client

from helpers import api_helper, taskqueue_service_pb2

RETRY_LIMIT = 3
PULL_QUEUE = 'pull-queue'


if __name__ == '__main__':
  parser = argparse.ArgumentParser()
  parser.add_argument("--zookeeper-location",
                      help="Directory containing validation log.")
  parser.add_argument("--taskqueue-location", default=None,
                      help="Taskqueue location (for syncing with remote time)")
  args = parser.parse_args()

  logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')

  zk_client = kazoo.client.KazooClient(hosts=args.zookeeper_location)
  zk_client.start()

  TEST_PROJECT = os.environ['TEST_PROJECT']
  PROJECT_QUEUES_NODE = f'/appscale/projects/{TEST_PROJECT}/queues'
  PROJECT_QUEUES_CONFIG = {
    'queue': {
      PULL_QUEUE: {'mode': 'pull', 'task_retry_limit': RETRY_LIMIT},
    }
  }
  PROJECT_QUEUES_CONFIG_BYTES = bytes(json.dumps(PROJECT_QUEUES_CONFIG), 'utf-8')

  # Ensure queue configs are set
  logging.info(f'Setting value to zookeeper node "{PROJECT_QUEUES_NODE}":\n'
               f'{PROJECT_QUEUES_CONFIG_BYTES}')
  zk_client.ensure_path(PROJECT_QUEUES_NODE)
  zk_client.set(PROJECT_QUEUES_NODE, PROJECT_QUEUES_CONFIG_BYTES)
  time.sleep(1)

  # Make sure queues are empty
  taskqueue = api_helper.TaskQueue([args.taskqueue_location], TEST_PROJECT)
  for queue_name, info in PROJECT_QUEUES_CONFIG['queue'].items():
    if info.get('mode') == 'pull':
      logging.info(f'Purging pull queue "{queue_name}"')
      purge_request = taskqueue_service_pb2.TaskQueuePurgeQueueRequest()
      purge_request.queue_name = bytes(queue_name, 'utf-8')
      taskqueue.protobuf_sync('PurgeQueue', purge_request)
  time.sleep(1)
