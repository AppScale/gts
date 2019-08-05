""" Fetches RabbitMQ status. """
import base64
import json
import logging
import socket
import time

import attr
from tornado import gen
from tornado.httpclient import AsyncHTTPClient

from appscale.hermes.converter import Meta, include_list_name

# The port used by the RabbitMQ management plugin.
API_PORT = 15672

# Credentials used to access the RabbitMQ API.
USER = 'guest'
PASS = 'guest'

# The endpoint used for retrieving node stats.
NODES_API = '/api/nodes'

# The endpoint used for retrieving queue stats.
QUEUES_API = '/api/queues'

logger = logging.getLogger(__name__)


class APICallFailed(Exception):
  """ Indicates that a RabbitMQ API call failed. """
  pass


@include_list_name('rabbitmq')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class RabbitMQStatsSnapshot(object):
  """ The fields reported for each RabbitMQ node. """
  utc_timestamp = attr.ib()
  disk_free_alarm = attr.ib()
  mem_alarm = attr.ib()
  name = attr.ib()
  partitions = attr.ib()


@include_list_name('queue')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class PushQueueStats(object):
  """ The fields reported for each push queue. """
  messages = attr.ib()
  name = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class PushQueueStatsSnapshot(object):
  """ A stats container for all existing push queues. """
  utc_timestamp = attr.ib()
  queues = attr.ib(metadata={Meta.ENTITY_LIST: PushQueueStats})


class RabbitMQStatsSource(object):
  """ Fetches RabbitMQ stats. """

  first_run = True

  @staticmethod
  @gen.coroutine
  def get_current():
    """ Retrieves RabbitMQ stats for the current node.

    Returns:
      An instance of RabbitMQStatsSnapshot.
    """
    start = time.time()

    node_name = 'rabbit@{}'.format(socket.gethostname())
    url = 'http://localhost:{}{}/{}'.format(API_PORT, NODES_API, node_name)
    creds = base64.b64encode(':'.join([USER, PASS]))
    headers = {'Authorization': 'Basic {}'.format(creds)}
    async_client = AsyncHTTPClient()
    try:
      response = yield async_client.fetch(url, headers=headers)
    except Exception as error:
      raise APICallFailed('Call to {} failed: {}'.format(url, error))

    try:
      node_info = json.loads(response.body)
    except ValueError:
      raise APICallFailed('Invalid response from '
                          '{}: {}'.format(url, response.body))

    snapshot = RabbitMQStatsSnapshot(
      utc_timestamp=int(time.time()),
      disk_free_alarm=node_info['disk_free_alarm'],
      mem_alarm=node_info['mem_alarm'],
      name=node_info['name'],
      partitions=node_info['partitions']
    )
    logger.info('Prepared RabbitMQ node stats in '
                '{elapsed:.1f}s.'.format(elapsed=time.time()-start))
    raise gen.Return(snapshot)


class PushQueueStatsSource(object):
  """ Fetches push queue stats. """

  first_run = True

  @staticmethod
  @gen.coroutine
  def get_current():
    """ Retrieves push queue stats.

    Returns:
      An instance of PushQueueStatsSnapshot.
    """
    start = time.time()

    url = 'http://localhost:{}{}'.format(API_PORT, QUEUES_API)
    creds = base64.b64encode(':'.join([USER, PASS]))
    headers = {'Authorization': 'Basic {}'.format(creds)}
    async_client = AsyncHTTPClient()
    try:
      response = yield async_client.fetch(url, headers=headers)
    except Exception as error:
      raise APICallFailed('Call to {} failed: {}'.format(url, error))

    try:
      queues_info = json.loads(response.body)
    except ValueError:
      raise APICallFailed('Invalid response from '
                          '{}: {}'.format(url, response.body))

    queue_stats = [
      PushQueueStats(name=queue['name'], messages=queue['messages'])
      for queue in queues_info if '___' in queue['name']]
    snapshot = PushQueueStatsSnapshot(
      utc_timestamp=int(time.time()),
      queues=queue_stats
    )
    logger.info('Prepared push queue stats in '
                '{elapsed:.1f}s.'.format(elapsed=time.time()-start))
    raise gen.Return(snapshot)
