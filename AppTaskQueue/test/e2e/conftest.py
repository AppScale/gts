import asyncio
import functools
import json
import os
import time

import kazoo.client
import pytest

from helpers import api_helper, taskqueue_service_pb2


TEST_PROJECT = os.environ['TEST_PROJECT']
PROJECT_QUEUES_NODE = f'/appscale/projects/{TEST_PROJECT}/queues'
PROJECT_QUEUES_CONFIG = {
  'queue': {
    'pull-queue-a': {'mode': 'pull'},
    'pull-queue-b': {'mode': 'pull'},
    'pull-queue-5-retry': {'mode': 'pull', 'task_retry_limit': 5},
    'pull-queue-3-retry': {'mode': 'pull', 'task_retry_limit': 3},
    'push-queue': {}
  }
}
PROJECT_QUEUES_CONFIG_BYTES = bytes(json.dumps(PROJECT_QUEUES_CONFIG), 'utf-8')


def async_test(test):
  @functools.wraps(test)
  def wrapper(*args, **kwargs):
    coro = asyncio.coroutine(test)
    future = coro(*args, **kwargs)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(future)
  return wrapper


def pytest_addoption(parser):
  parser.addoption('--tq-locations', nargs='+',
                   help='TCP addresses of TaskQueue')
  parser.addoption('--zk-location',
                   help='TCP address of Zookeeper')


@pytest.fixture(scope='session')
def taskqueue(request):
  """ Initializes TaskQueue access point
  """
  tq_locations = request.config.getoption('--tq-locations')
  return api_helper.TaskQueue(tq_locations, TEST_PROJECT)


@pytest.fixture(scope='session', autouse=True)
def init_queues_config(request):
  # Configure Zookeeper client
  zk_location = request.config.getoption('--zk-location')
  zk_client = kazoo.client.KazooClient(hosts=zk_location)
  zk_client.start()

  # Ensure queue configs are set
  zk_client.ensure_path(PROJECT_QUEUES_NODE)
  zk_client.set(PROJECT_QUEUES_NODE, PROJECT_QUEUES_CONFIG_BYTES)
  zk_client.stop()

  # Give Taskqueue some time to update queues config
  time.sleep(3)


@pytest.fixture(autouse=True)
def purge_queues(taskqueue):
  # Nothing to setup
  yield
  # Cleanup after every test
  for queue_name, info in PROJECT_QUEUES_CONFIG['queue'].items():
    if info.get('mode') == 'pull':
      purge_request = taskqueue_service_pb2.TaskQueuePurgeQueueRequest()
      purge_request.queue_name = bytes(queue_name, 'utf-8')
      taskqueue.protobuf_sync('PurgeQueue', purge_request)
