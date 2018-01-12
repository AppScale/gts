""" Fetches RabbitMQ status. """
import base64
import json
import random

import six
from tornado import gen
from tornado import web
from tornado.httpclient import AsyncHTTPClient

from appscale.common.appscale_info import get_taskqueue_nodes
from appscale.hermes.constants import HTTP_Codes


class APICallFailed(Exception):
  """ Indicates that a RabbitMQ API call failed. """
  pass


class RabbitMQStatus(web.RequestHandler):
  """ Fetches RabbitMQ status. """
  # The port used by the RabbitMQ management plugin.
  API_PORT = 15672

  # Credentials used to access the RabbitMQ API.
  USER = 'guest'
  PASS = 'guest'

  # Relevant RabbitMQ API endpoints and fields.
  APIS = {
    'nodes': ('/api/nodes', ['name', 'mem_alarm', 'disk_free_alarm']),
    'queues': ('/api/queues', ['name', 'messages'])
  }

  def initialize(self):
    """ Defines resources needed to access the RabbitMQ API. """
    self.taskqueue_machines = get_taskqueue_nodes()
    self.client = AsyncHTTPClient()

  @gen.coroutine
  def _fetch_api_info(self, endpoint, fields):
    """ Performs a RabbitMQ API request.

    Args:
      endpoint: A string specifying the API endpoint.
      fields: A list of strings specifying fields to include.
    Returns:
      A list of API resources.
    """
    ip = random.choice(self.taskqueue_machines)
    url = 'http://{}:{}{}'.format(ip, self.API_PORT, endpoint)
    creds = base64.b64encode(':'.join([self.USER, self.PASS]))
    headers = {'Authorization': 'Basic {}'.format(creds)}
    try:
      response = yield self.client.fetch(url, headers=headers)
    except Exception as error:
      raise APICallFailed('Call to {} failed: {}'.format(url, error))

    items = [
      {key: value for key, value in six.iteritems(item) if key in fields}
      for item in json.loads(response.body)]
    raise gen.Return(items)

  @gen.coroutine
  def get(self):
    """ Fetches RabbitMQ status. """
    try:
      response = yield {api: self._fetch_api_info(*self.APIS[api])
                        for api in self.APIS}
    except APICallFailed as error:
      self.set_status(HTTP_Codes.HTTP_INTERNAL_ERROR)
      self.write(str(error))
      raise gen.Return()

    # Remove irrelevant queues.
    response['queues'] = [queue for queue in response['queues']
                          if '___' in queue['name']]
    json.dump(response, self)
