""" Provides connection between AppTaskQueue and Datastore. """

import random
import socket
import time

import requests
from requests import exceptions

from .protocols import datastore_v3_pb2, remote_api_pb2

# The location of the file that keeps track of available load balancers.
LOAD_BALANCERS_FILE = "/etc/appscale/load_balancer_ips"

# The port on the load balancer that serves datastore requests.
PROXY_PORT = 8888

# Errors from datastore that should not be retry-able
PERMANENT_DS_ERRORS = (
  datastore_v3_pb2.Error.BAD_REQUEST,
  datastore_v3_pb2.Error.CAPABILITY_DISABLED,
  datastore_v3_pb2.Error.NEED_INDEX,
  datastore_v3_pb2.Error.SAFE_TIME_TOO_OLD,
  datastore_v3_pb2.Error.TRY_ALTERNATE_BACKEND
)


def get_random_lb():
  """ Selects a random location from the load balancers file.

  Returns:
    A string specifying a load balancer IP.
  """
  with open(LOAD_BALANCERS_FILE) as lb_file:
    return random.choice([':'.join([line.strip(), str(PROXY_PORT)])
                          for line in lb_file])


class DatastoreTransientError(Exception):
  pass


class DatastorePermanentError(Exception):
  pass


class BadFilterConfiguration(Exception):
  pass


class ApplicationError(Exception):
  def __init__(self, application_error, error_detail=''):
    self.application_error = application_error
    self.error_detail = error_detail


class Entity(object):
  """ Class for tracking task names. """
  def __init__(self, key_name, queue, state, app_id, timestamp=None, endtime=None):
    """ Entity Constructor.

    Args:
      key_name: Key name.
      queue: Queue name.
      state: Queue state.
      app_id: Application id.
      end_time: An optional parameter.
    """
    self.key_name = key_name
    self.queue = queue
    self.state = state
    self.app_id = app_id
    self.endtime = endtime
    if timestamp:
      self.timestamp = timestamp
    else:
      self.timestamp = int(time.time())

  def __str__(self):
    return 'Key name: ' + self.key_name + \
           '.\nQueue: ' + self.queue + \
           '.\nState: ' + self.state + \
           '\nApplication ID: ' + self.app_id + \
           '.\nTimestamp: ' + str(self.timestamp) + \
           '.\nEnd time: ' + str(self.endtime) + '.\n'

  def toPb(self, project_id, kind):
    """ Converts Entity object to datastore_v3_pb2.EntityProto.

    Args:
      project_id: Project id.
      kind: Value for creating keys.

    Returns:
      An object of datastore_v3_pb2.EntityProto.
    """

    entity_pb = datastore_v3_pb2.EntityProto()
    entity_pb.key.app = project_id
    element = entity_pb.key.path.element.add()
    element.type = kind
    element.name = self.key_name
    element_group = entity_pb.entity_group.element.add()
    element_group.CopyFrom(element)

    prop = entity_pb.property.add()
    prop.name = 'app_id'
    prop.value.stringValue = self.app_id
    prop.multiple = False

    prop = entity_pb.property.add()
    prop.name = 'endtime'
    if self.endtime is not None:
      prop.value.int64Value = self.endtime
    else:
      prop.value.Clear()

    prop.multiple = False

    prop = entity_pb.property.add()
    prop.name = 'queue'
    prop.value.stringValue = self.queue
    prop.multiple = False

    prop = entity_pb.property.add()
    prop.name = 'state'
    prop.value.stringValue = self.state
    prop.multiple = False

    prop = entity_pb.property.add()
    prop.name = 'timestamp'
    prop.value.int64Value = self.timestamp
    prop.multiple = False

    return entity_pb

  @classmethod
  def fromPb(cls, entity_pb):
    """ Converts datastore_v3_pb2.EntityProto object to Entity.

    Args:
      entity_pb: An object of datastore_v3_pb2.EntityProto object.

    Returns:
      An object of Entity.
    """
    key_name = entity_pb.entity_group.element[0].name
    app_id = entity_pb.property[0].value.stringValue
    if entity_pb.property[1].value.HasField('int64Value'):
      endtime = entity_pb.property[1].value.int64Value
    else:
      endtime = None
    queue = entity_pb.property[2].value.stringValue
    state = entity_pb.property[3].value.stringValue
    timestamp = entity_pb.property[4].value.int64Value

    return Entity(key_name=key_name, app_id=app_id, endtime=endtime,
                  queue=queue, state=state, timestamp=timestamp)


class DatastoreClient(object):
  """ Class provides connection between AppTaskQueue and datastore. """
  SERVICE_NAME = 'taskqueue'
  KIND = '__task_name__'
  _OPERATIONS = {
      '<': 1,
      '<=': 2,
      '>': 3,
      '>=': 4,
      '=': 5}

  def put(self, project_id, entities):
    """ Puts entities to datastore.

    Args:
      project_id: A str containing ID of project.
      entities: A list or a tuple of Entity class objects.
    """
    if not isinstance(entities, (list, tuple)):
      entities = [entities]

    request = datastore_v3_pb2.PutRequest()

    for entity in entities:
      pb_entity = request.entity.add()
      pb_entity.CopyFrom(entity.toPb(project_id, self.KIND))

    self._make_request(project_id, 'Put', request.SerializeToString())

  def get(self, project_id, key):
    """ Gets entities from datastore by key.

    Args:
      project_id: A str containing ID of project.
      key: Key object for query.
    """
    request = datastore_v3_pb2.GetRequest()
    req_key = request.key.add()
    req_key.app = project_id
    element = req_key.path.element.add()
    element.type = self.KIND
    element.name = key

    response = self._make_request(project_id, 'Get',
                                  request.SerializeToString())
    get_response = datastore_v3_pb2.GetResponse()
    get_response.ParseFromString(response)
    response_entity = get_response.entity[0].entity
    if not response_entity.HasField('key'):
      return

    return Entity.fromPb(response_entity)

  def fetch(self, project_id, limit=10):
    """ Gets all entities from datastore.

    Args:
      project_id: A str containing ID of object.
      limit: Number of returning entities.
    """
    query = datastore_v3_pb2.Query()
    query.app = project_id
    query.kind = self.KIND
    query.compile = True
    query.limit = limit

    encoded_response = self._make_request(project_id,
      'RunQuery', query.SerializeToString())
    results_pb = datastore_v3_pb2.QueryResult()
    results_pb.ParseFromString(encoded_response)
    return results_pb

  def query_count(self, project_id, filters=()):
    """ Gets count of specified by filters objects in datastore.

    Args:
      project_id: A str containing ID of project.
      filters: List of filters for query.
    """
    result = self._query(project_id, filters)
    return result.skipped_results

  def _query(self, project_id, filters=()):
    """ Sends query to datastore.

    Args:
      project_id: A str containing ID of project.
      filters: List of filters for query.
    """
    query = self._create_query(project_id, filters)

    encoded_response = self._make_request(project_id,
      'RunQuery', query.SerializeToString())
    results_pb = datastore_v3_pb2.QueryResult()
    results_pb.ParseFromString(encoded_response)
    return results_pb

  def _create_query(self, project_id, filters):
    """ Creates datastore_v3_pb2.Query object.

    Args:
      project_id: A str containing ID of project.
      filters: List of filters for query.
    Returns:
       datastore_v3_pb2.Query object.
    Raises:
      BadFilterConfiguration exception if filters configuration is invalid.
    """
    query = datastore_v3_pb2.Query()
    query.app = project_id
    query.kind = self.KIND
    query.compile = True
    query.limit = 0
    query.offset = 1000

    for f in filters:
      if len(f) != 2:
        raise BadFilterConfiguration('Filter should consist of two values!')
      filter_pb = query.filter.add()
      operands = f[0].split(' ')

      prop_name = operands[0]
      if len(operands) == 1:
        operation = self._OPERATIONS['=']
      else:
        try:
          operation = self._OPERATIONS[operands[1]]
        except KeyError:
          raise BadFilterConfiguration(
            'Operation {} not supported!'.format(operands[1]))

      filter_pb.op = operation
      prop = filter_pb.property.add()
      prop.name = prop_name
      prop.multiple = False
      prop.value.stringValue = f[1]

    return query

  def _make_request(self, project_id, method, body):
    """ Sends request to datastore using remote API.

    Args:
      project_id: A str containing ID of project.
      method: Method for remote API.
      body: Body of request for remote API.
    Returns:
      remote_api_pb2.Response object.
    Raises:
      DatastoreTransientError if some retry-able error occurred.
      DatastorePermanentError if some permanent error occurred.
    """
    request = remote_api_pb2.Request()
    request.service_name = self.SERVICE_NAME
    request.method = method
    request.request = body

    url = 'http://{}'.format(get_random_lb())
    headers = {'protocolbuffertype': 'Request', 'appdata': project_id}
    timeout = 3

    try:
      response = requests.post(url=url,
                               headers=headers,
                               data=request.SerializeToString(),
                               timeout=timeout)

      # If the response was successful, no Exception will be raised
      response.raise_for_status()
    except exceptions.ConnectionError as e:
      raise DatastoreTransientError(
        'Connection error occurred with message: {}'.format(e))
    except exceptions.Timeout:
      raise DatastoreTransientError(
        'Operation timed out after {} seconds.'.format(timeout))
    except exceptions.HTTPError as e:
      raise DatastoreTransientError(
        'HTTP error occurred with message: {}'.format(e))
    except socket.error as e:
      raise DatastoreTransientError(
        'Socket error occurred with message: {}'.format(e))

    api_response = remote_api_pb2.Response()
    api_response.ParseFromString(response.content)

    if api_response.HasField('application_error'):
      error = api_response.application_error

      error_code = error.code
      error_detail = error.detail
      error_name = datastore_v3_pb2.Error.ErrorCode.keys()[error_code]

      if error_code in PERMANENT_DS_ERRORS:
        error_msg = 'Bad request for datastore: {} ({})'.\
          format(error_name, error_detail)
        raise DatastorePermanentError(error_msg)

      error_msg = 'Datastore error: {} ({})'.format(error_name, error_detail)
      raise DatastoreTransientError(error_msg)

    if api_response.HasField('exception'):
      raise DatastoreTransientError(str(api_response.exception))

    return api_response.response
