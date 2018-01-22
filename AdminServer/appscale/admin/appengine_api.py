""" Implements the App Engine services API.

This API is not documented, but it is used by the Google Cloud SDK.
"""

import json
import logging
import yaml
from kazoo.exceptions import NoNodeError
from yaml.parser import ParserError

from appscale.appcontroller_client import AppControllerException
from appscale.common.constants import HTTPCodes
from .base_handler import BaseHandler
from .constants import CustomHTTPError
from .constants import InvalidConfiguration
from .utils import cron_from_dict
from .utils import queues_from_dict

logger = logging.getLogger('appscale-admin')


class UpdateQueuesHandler(BaseHandler):
  """ Handles UpdateQueues operations. """
  def initialize(self, zk_client, ua_client):
    """ Defines required resources to handle requests.

    Args:
      zk_client: A KazooClient.
      ua_client: A UAClient.
    """
    self.zk_client = zk_client
    self.ua_client = ua_client

  def post(self):
    """ Handles UpdateQueues operations. """
    project_id = self.get_argument('app_id', None)
    if project_id is None:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='app_id parameter is required')
    self.authenticate(project_id, self.ua_client)

    try:
      payload = yaml.safe_load(self.request.body)
    except ParserError:
      raise InvalidConfiguration('Payload must be valid YAML')

    try:
      queues = queues_from_dict(payload)
    except InvalidConfiguration as error:
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

    logger.info('Updated queues for {}'.format(project_id))


class UpdateCronHandler(BaseHandler):
  """ Handles UpdateCron operations. """
  def initialize(self, acc, zk_client, ua_client):
    """ Defines required resources to handle requests.

    Args:
      acc: An AppControllerClient.
      zk_client: A KazooClient.
      ua_client: A UAClient.
    """
    self.acc = acc
    self.zk_client = zk_client
    self.ua_client = ua_client

  def post(self):
    """ Handles UpdateCron operations. """
    project_id = self.get_argument('app_id', None)
    if project_id is None:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='app_id parameter is required')

    self.authenticate(project_id, self.ua_client)

    try:
      payload = yaml.safe_load(self.request.body)
    except ParserError:
      raise InvalidConfiguration('Payload must be valid YAML')

    try:
      cron_jobs = cron_from_dict(payload)
    except InvalidConfiguration as error:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message=error.message)

    cron_node = '/appscale/projects/{}/cron'.format(project_id)
    try:
      self.zk_client.set(cron_node, json.dumps(cron_jobs))
    except NoNodeError:
      try:
        self.zk_client.create(cron_node, json.dumps(cron_jobs))
      except NoNodeError:
        raise CustomHTTPError(HTTPCodes.NOT_FOUND,
                              message='{} not found'.format(project_id))

    try:
      self.acc.update_cron(project_id)
    except AppControllerException as error:
      message = 'Error while updating cron: {}'.format(error)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

    logger.info('Updated cron jobs for {}'.format(project_id))
