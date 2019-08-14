import asyncio
import itertools

import aiohttp
import attr

from helpers import taskqueue_service_pb2, remote_api_pb2


def sync_version(async_coroutine):
  """ Decorates asyncio coroutine in order to make it synchronous.

  Args:
    async_coroutine: asyncio coroutine to wrap.
  Returns:
    Synchronous version of the method.
  """
  def sync(*args, **kwargs):
    event_loop = asyncio.get_event_loop()
    result = event_loop.run_until_complete(async_coroutine(*args, **kwargs))
    return result
  return sync


class TaskQueueError(Exception):
  pass


class HTTPError(TaskQueueError):
  def __init__(self, status, reason, body):
    super().__init__(f'HTTP {status}: {reason}\n{body}')
    self.status = status
    self.reason = reason
    self.body = body


class ProtobufferError(TaskQueueError):
  pass


class ProtobufferAppError(ProtobufferError):
  def __init__(self, msg, code, detail):
    super().__init__(msg)
    self.code = code
    self.detail = detail


class ProtobufferException(ProtobufferError):
  def __init__(self, exception):
    super().__init__(exception)
    self.exception = exception


def timed(coroutine):
  async def decorated(*args, **kwargs):
    ioloop = asyncio.get_event_loop()
    start = ioloop.time()
    result = await coroutine(*args, **kwargs)
    delay = ioloop.time() - start
    return result, delay * 1_000_000
  return decorated


class TaskQueue(object):
  """
  Helper class for making HTTP REST and HTTP Protobuffer requests.
  """

  SERVICE_NAME = 'taskqueue'

  @attr.s(cmp=False, hash=False, slots=True, frozen=True)
  class RESTResponse(object):
    """
    REST response container. It is used as aiohttp.ClientResponse
    forces client await json.
    """
    status = attr.ib()
    reason = attr.ib()
    json = attr.ib()
    headers = attr.ib()

  def __init__(self, tcp_addresses, project_id):
    self._locations = itertools.cycle(tcp_addresses)
    self._project_id = project_id
    self.rest_sync = sync_version(self.rest)
    self.protobuf_sync = sync_version(self.protobuf)
    self.timed_rest = timed(self.rest)
    self.timed_protobuf = timed(self.protobuf)

  async def rest(self, method, *, path_suffix, params=None, json=None,
                 raise_for_status=True):
    """ Provides simplified interface for sending REST requests
    to the TaskQueue service.

    Args:
      method: a str representing HTTP method.
      path_suffix: a str to use in URL:
        http://<TCP_ADDR>/taskqueue/v1beta2/projects/<PROJECT>/taskqueues/<PATH_PREFIX>.
      params: a dict containing request parameters.
      json: an object to serialise as JSON body.
      raise_for_status: a bool indicating if error should be raised for
        error in response.
    Returns:
      an instance of Taskqueue.RESTResponse.
    """
    url = (
      f'http://{next(self._locations)}/taskqueue/v1beta2/'
      f'projects/{self._project_id}/taskqueues{path_suffix}'
    )
    async with aiohttp.ClientSession() as session:
      async with session.request(method, url, params=params, json=json) as resp:
        if raise_for_status:
          try:
            resp.raise_for_status()
          except aiohttp.ClientResponseError:
            body = await resp.text()
            raise HTTPError(status=resp.status, reason=resp.reason, body=body)

        return self.RESTResponse(
          status=resp.status,
          reason=resp.reason,
          json=await resp.json(content_type=None),
          headers=resp.headers
        )

  async def protobuf(self, method, request, raise_for_status=True):
    """ Provides simplified interface for sending Protobuffer
    requests to the TaskQueue service.

    Args:
      method: a str representing name of TaskQueue method.
      request: an instance of ProtobufferMessage representing request.
      raise_for_status: a bool indicating if error should be raised for
        error in response.
    Returns:
      an instance of corresponding ProtobufferMessage (response).
    """
    remote_api_request = remote_api_pb2.Request()
    remote_api_request.service_name = self.SERVICE_NAME
    remote_api_request.method = method
    remote_api_request.request = request.SerializeToString()

    url = f'http://{next(self._locations)}'
    headers = {
      'protocolbuffertype': 'Request',
      'appdata': self._project_id,
      'Module': '',
      'Version': ''
    }
    body = remote_api_request.SerializeToString()
    async with aiohttp.ClientSession() as session:
      async with session.request('POST', url, data=body, headers=headers) as resp:
        try:
          # We won't be able to parse PB response if status != 200
          resp.raise_for_status()
        except aiohttp.ClientResponseError:
          body = await resp.text()
          raise HTTPError(status=resp.status, reason=resp.reason, body=body)

        response_body = await resp.read()
        api_response = remote_api_pb2.Response()
        api_response.ParseFromString(response_body)

        if raise_for_status:
          if api_response.HasField('application_error'):
            err = api_response.application_error
            raise ProtobufferAppError(f'{err.code}: {err.detail}',
                                      code=err.code, detail=err.detail)
          if api_response.HasField('exception'):
            raise ProtobufferException(api_response.exception)

        resp_cls_name = f'TaskQueue{method}Response'
        resp_cls = getattr(taskqueue_service_pb2, resp_cls_name)
        resp = resp_cls()
        resp.ParseFromString(api_response.response)
        return resp

  async def remote_time_usec(self):
    """ Provides current time according to taskqueue server.

    Returns:
      an integer representing usec timestamp.
    """
    url = f'http://{next(self._locations)}/service-stats'
    async with aiohttp.ClientSession() as session:
      async with session.get(url) as resp:
        stats = await resp.json(content_type=None)
        return stats['cumulative_counters']['to'] * 1000
