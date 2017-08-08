""" Implements the App Engine services API.

This API is not documented, but it is used by the Google Cloud SDK.
"""

import json
import logging
import yaml
from kazoo.exceptions import NoNodeError
from yaml.parser import ParserError

from appscale.common.constants import HTTPCodes
from appscale.taskqueue.queue import InvalidQueueConfiguration
from .base_handler import BaseHandler
from .constants import CustomHTTPError
from .utils import queues_from_dict


class UpdateQueuesHandler(BaseHandler):
  """ Handles UpdateQueues operations. """
  def initialize(self, zk_client):
    """ Defines required resources to handle requests.

    Args:
      zk_client: A KazooClient.
    """
    self.zk_client = zk_client

  def post(self):
    """ Handles UpdateQueues operations. """
    self.authenticate()
    project_id = self.get_argument('app_id', None)
    if project_id is None:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='app_id parameter is required')

    try:
      payload = yaml.safe_load(self.request.body)
    except ParserError:
      raise InvalidQueueConfiguration('Payload must be valid YAML')

    try:
      queues = queues_from_dict(payload)
    except InvalidQueueConfiguration as error:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=error.message)

    queue_node = '/appscale/projects/{}/queues'.format(project_id)
    try:
      self.zk_client.set(queue_node, json.dumps(queues))
    except NoNodeError:
      try:
        self.zk_client.create(queue_node, json.dumps(queues))
      except NoNodeError:
        raise CustomHTTPError(HTTPCodes.NOT_FOUND,
                              message='{} not found'.format(project_id))

    logging.info('Updated queues for {}'.format(project_id))
