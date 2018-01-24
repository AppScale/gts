""" Fetches RabbitMQ status. """
import base64
import json
import logging
import socket
import time

import attr
from tornado.httpclient import HTTPClient

from appscale.hermes.stats.converter import include_list_name

# The port used by the RabbitMQ management plugin.
API_PORT = 15672

# Credentials used to access the RabbitMQ API.
USER = 'guest'
PASS = 'guest'

# The endpoint used for retrieving node stats.
NODES_API = '/api/nodes'


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


class RabbitMQStatsSource(object):
  """ Fetches RabbitMQ stats. """

  first_run = True

  @staticmethod
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
    client = HTTPClient()
    try:
      response = client.fetch(url, headers=headers)
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
      name=node_info['name']
    )
    logging.info('Prepared RabbitMQ node stats in '
                 '{elapsed:.1f}s.'.format(elapsed=time.time()-start))
    return snapshot
