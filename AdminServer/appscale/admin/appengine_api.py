""" Implements the App Engine services API.

This API is not documented, but it is used by the Google Cloud SDK.
"""

import json
import logging
import six
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

logger = logging.getLogger(__name__)


class IndexProperty(object):
  """ Represents a datastore index property. """

  __slots__ = ['name', 'direction']

  def __init__(self, name, direction):
    """ Creates a new IndexProperty object.

    Args:
      name: A string specifying the property name.
      direction: A string specifying the index direction (asc or desc).
    """
    if not name:
      raise InvalidConfiguration('Index property missing "name"')

    if direction not in ('asc', 'desc'):
      raise InvalidConfiguration(
        'Invalid "direction" value: {}'.format(direction))

    self.name = name
    self.direction = direction

  @property
  def id(self):
    if self.direction == 'asc':
      return self.name
    else:
      return ','.join([self.name, 'desc'])

  def to_dict(self):
    """ Generates a JSON-safe dictionary representation of the property.

    Returns:
      A dictionary containing the property details.
    """
    return {'name': self.name, 'direction': self.direction}

  @classmethod
  def from_dict(cls, prop):
    """ Constructs an IndexProperty from a JSON-derived dictionary.

    Args:
      prop: A dictionary containing the name and direction fields.
    Returns:
      An IndexProperty object.
    """
    return cls(prop['name'], prop['direction'])


class DatastoreIndex(object):
  """ Represents a datastore index. """

  __slots__ = ['kind', 'ancestor', 'properties']

  # Separates fields of an encoded index.
  ENCODING_DELIMITER = '|'

  def __init__(self, kind, ancestor, properties):
    """ Creates a new DatastoreIndex object.

    Args:
      kind: A string specifying the datastore kind.
      ancestor: A boolean indicating whether or not the index is for
        satisfying ancestor queries.
      properties: A list of IndexProperty objects.
    """
    self.kind = kind
    self.ancestor = ancestor
    self.properties = properties

  @property
  def id(self):
    encoded_ancestor = '1' if self.ancestor else '0'
    encoded_properties = self.ENCODING_DELIMITER.join(
      [prop.id for prop in self.properties])
    return self.ENCODING_DELIMITER.join(
      [self.kind, encoded_ancestor, encoded_properties])

  @classmethod
  def from_yaml(cls, entry):
    """ Constructs a DatastoreIndex from a parsed index.yaml entry.

    Args:
      entry: A dictionary generated from a index.yaml file.
    Returns:
      A DatastoreIndex object.
    Raises:
      InvalidConfiguration exception if entry is invalid.
    """
    kind = entry.get('kind')
    if not kind:
      raise InvalidConfiguration('Index entry is missing "kind" field')

    ancestor = entry.get('ancestor', False)
    if not isinstance(ancestor, bool):
      if ancestor.lower() not in ('yes', 'no', 'true', 'false'):
        raise InvalidConfiguration(
          'Invalid "ancestor" value: {}'.format(ancestor))

      ancestor = ancestor.lower() in ('yes', 'true')

    configured_props = entry.get('properties', [])
    if not configured_props:
      raise InvalidConfiguration('Index missing properties')

    properties = [IndexProperty(prop.get('name'), prop.get('direction', 'asc'))
                  for prop in configured_props]
    return cls(kind, ancestor, properties)

  def to_dict(self):
    """ Generates a JSON-safe dictionary representation of the index.

    Returns:
      A dictionary containing the index details.
    """
    return {
      'kind': self.kind,
      'ancestor': self.ancestor,
      'properties': [prop.to_dict() for prop in self.properties]
    }

  @classmethod
  def from_dict(cls, entry):
    """ Constructs a DatastoreIndex from a JSON-derived dictionary.

    Args:
      entry: A dictionary containing the kind, ancestor, and properties fields.
    Returns:
      A DatastoreIndex object.
    """
    properties = [IndexProperty.from_dict(prop)
                  for prop in entry['properties']]
    return cls(entry['kind'], entry['ancestor'], properties)


class UpdateIndexesHandler(BaseHandler):
  """ Handles UpdateIndexes operations. """
  def initialize(self, zk_client, ua_client):
    """ Defines required resources to handle requests.

    Args:
      zk_client: A KazooClient.
      ua_client: A UAClient.
    """
    self.zk_client = zk_client
    self.ua_client = ua_client

  def post(self):
    """ Handles UpdateIndexes operations. """
    project_id = self.get_argument('app_id', None)
    if project_id is None:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='app_id parameter is required')
    self.authenticate(project_id, self.ua_client)

    try:
      payload = yaml.safe_load(self.request.body)
    except ParserError:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Payload must be valid YAML')

    try:
      given_indexes = payload['indexes']
    except KeyError:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Payload must contain "indexes"')

    # If there are no new indexes being added, there's no work to be done.
    if not given_indexes:
      return

    try:
      given_indexes = [DatastoreIndex.from_yaml(index)
                       for index in given_indexes]
    except InvalidConfiguration as error:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message=six.text_type(error))

    indexes_node = '/appscale/projects/{}/indexes'.format(project_id)
    try:
      existing_indexes, znode_stat = self.zk_client.get(indexes_node)
    except NoNodeError:
      encoded_indexes = json.dumps(
        [index.to_dict() for index in given_indexes])
      self.zk_client.create(indexes_node, encoded_indexes)
      return

    combined_indexes = [DatastoreIndex.from_dict(index)
                        for index in json.loads(existing_indexes)]
    existing_index_ids = {index.id for index in combined_indexes}
    for new_index in given_indexes:
      if new_index.id not in existing_index_ids:
        combined_indexes.append(new_index)

    encoded_indexes = json.dumps(
      [index.to_dict() for index in combined_indexes])
    self.zk_client.set(indexes_node, encoded_indexes,
                       version=znode_stat.version)

    logger.info('Updated indexes for {}'.format(project_id))


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
