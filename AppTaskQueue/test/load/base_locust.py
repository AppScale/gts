import logging
import threading
import os
import time
from contextlib import contextmanager

import locust
from locust.exception import LocustError
from locust.clients import HttpSession
from requests import RequestException

from helpers import api_helper, remote_api_pb2, taskqueue_service_pb2

LOGS_DIR = os.environ['VALIDATION_LOG']
TEST_PROJECT = os.environ['TEST_PROJECT']


class TaskqueueClient(object):
  """
  Decorates Locust HttpSession with protobuffer and REST request
  preparation and response processing for communication with TaskQueue.
  Encapsulates TaskQueue host and ProjectID.
  """

  SERVICE_NAME = 'taskqueue'

  def __init__(self, tq_location):
    self.tq_location = tq_location
    self.http_session = HttpSession(base_url=f'http://{tq_location}')

  @contextmanager
  def protobuf(self, pb_method, pb_request):
    """ Provides simplified interface for sending Protobuffer
    requests to the TaskQueue service.

    Args:
      pb_method: a str representing name of TaskQueue method.
      pb_request: an instance of ProtobufferMessage representing request.
    Returns:
      an instance of corresponding ProtobufferMessage (response).
    """
    remote_api_request = remote_api_pb2.Request()
    remote_api_request.service_name = self.SERVICE_NAME
    remote_api_request.method = pb_method
    remote_api_request.request = pb_request.SerializeToString()
    headers = {
      'protocolbuffertype': 'Request',
      'appdata': TEST_PROJECT,
      'Module': '',
      'Version': ''
    }
    body = remote_api_request.SerializeToString()
    locust_wrapped_response = self.http_session.request(
      'POST', f'http://{self.tq_location}', headers=headers, data=body,
      name=pb_method, catch_response=True
    )
    with locust_wrapped_response as resp:
      if resp.status_code >= 400:
        resp.failure(f'TaskQueue responded '
                     f'"HTTP {resp.status_code}: {resp.reason}"')
        raise api_helper.HTTPError(resp.status_code, resp.reason, resp.content)
      api_response = remote_api_pb2.Response()
      api_response.ParseFromString(resp.content)
      if api_response.HasField('application_error'):
        err = api_response.application_error
        msg = f'{err.code}: {err.detail}'
        resp.failure(msg)
        raise api_helper.ProtobufferAppError(
            msg, code=err.code, detail=err.detail)
      if api_response.HasField('exception'):
        resp.failure(api_response.exception)
        raise api_helper.ProtobufferException(api_response.exception)

      pb_resp_cls_name = f'TaskQueue{pb_method}Response'
      pb_resp_cls = getattr(taskqueue_service_pb2, pb_resp_cls_name)
      pb_resp = pb_resp_cls()
      pb_resp.ParseFromString(api_response.response)

      try:
        yield pb_resp
      finally:
        resp.success()

  @contextmanager
  def rest(self, method, *, path_suffix, params=None, json=None):
    """ Provides simplified interface for sending REST requests
    to the TaskQueue service.

    Args:
      method: a str representing HTTP method.
      path_suffix: a str to use in URL:
        http://<HOST>/taskqueue/v1beta2/projects/<PROJECT>/taskqueues/<PATH_PREFIX>.
      params: a dict containing request parameters.
      json: an object to serialise as JSON body.
    Returns:
      an instance of Taskqueue.RESTResponse.
    """
    url = f'/taskqueue/v1beta2/projects/{TEST_PROJECT}/taskqueues{path_suffix}'
    locust_wrapped_response = self.http_session.request(
      method, url, params=params, json=json,
      name=path_suffix, catch_response=True
    )
    with locust_wrapped_response as resp:
      try:
        resp.raise_for_status()
      except RequestException as err:
        resp.failure(err)
        raise
      else:
        try:
          yield resp
        finally:
          resp.success()


class TaskQueueLocust(locust.Locust):
  """
  Base class for virtual TaskQueue users run by Locust.
  """

  # Dict containing loggers for every process running different TQ users
  LOGGERS = {}
  LOGGERS_LOCK = threading.Lock()

  @classmethod
  def get_logger(cls):
    """ Thread-safe method returning instance of logger
    reporting TaskQueue actions for further validation.

    Returns:
      an instance of Python logger
    """
    pid = os.getpid()
    logger_name = f'{cls.__name__}s-{pid}'
    if logger_name in cls.LOGGERS:
      return cls.LOGGERS[logger_name]
    with cls.LOGGERS_LOCK:
      if logger_name in cls.LOGGERS:
        return cls.LOGGERS[logger_name]
      formatter = logging.Formatter("%(message)s")
      handler = logging.FileHandler(f'{LOGS_DIR}/{logger_name}.log')
      handler.setFormatter(formatter)
      logger = logging.Logger(logger_name)
      logger.addHandler(handler)
      cls.LOGGERS[logger_name] = logger
      return logger

  def __init__(self):
    super().__init__()
    if self.host is None:
      raise LocustError(
        "You must specify the base host. "
        "Either in the host attribute in the Locust class, "
        "or on the command line using the --host option.")
    self.client = TaskqueueClient(tq_location=self.host)
    self.actions_logger = self.get_logger()

  def log_action(self, status, task_id, action_description):
    """ Reports TaskQueue action to validation log.
    """
    timestamp_ms = int(time.time() * 1000)
    self.actions_logger.info(
      f'{timestamp_ms} {status} {task_id} {action_description}'
    )
