#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

""" AppScale version of TaskQueue stub. Client to the TaskQueue server.  """

from __future__ import with_statement

import time

__all__ = []

import datetime
import errno
import logging
import os.path
import random
import socket
import string

import taskqueue_service_pb

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext.remote_api import remote_api_pb
from google.net.proto import ProtocolBuffer

DEFAULT_RATE = '5.00/s'

DEFAULT_RATE_FLOAT = 5.0

DEFAULT_BUCKET_SIZE = 5

MAX_ETA = datetime.timedelta(days=30)

MAX_PULL_TASK_SIZE_BYTES = 2 ** 20

MAX_PUSH_TASK_SIZE_BYTES = 100 * (2 ** 10)

MAX_TASK_SIZE = MAX_PUSH_TASK_SIZE_BYTES

MAX_REQUEST_SIZE = 32 << 20

BUILT_IN_HEADERS = set(['x-appengine-queuename',
                        'x-appengine-taskname',
                        'x-appengine-taskexecutioncount',
                        'x-appengine-taskpreviousresponse',
                        'x-appengine-taskretrycount',
                        'x-appengine-tasketa',
                        'x-appengine-development-payload',
                        'content-length'])

DEFAULT_QUEUE_NAME = 'default'

INF = 1e500

QUEUE_MODE = taskqueue_service_pb.TaskQueueMode

AUTOMATIC_QUEUES = {
    DEFAULT_QUEUE_NAME: (0.2, DEFAULT_BUCKET_SIZE, DEFAULT_RATE),
    '__cron': (1, 1, '1/s')}

# The location the SSL certificate is placed for encrypted communication.
CERT_LOCATION = "/etc/appscale/certs/mycert.pem"

# The location the SSL private key is placed for encrypted communication.
KEY_LOCATION = "/etc/appscale/certs/mykey.pem"

TASKQUEUE_PROXY_FILE = "/etc/appscale/load_balancer_ips"
TASKQUEUE_SERVER_PORT = 17446

class TaskQueueServiceStub(apiproxy_stub.APIProxyStub):
  """Python only task queue service stub.

  This stub executes tasks when enabled by using the dev_appserver's AddEvent
  capability.
  """
  THREADSAFE = True

  _ACCEPTS_REQUEST_ID = True

  def __init__(self, app_id, host, service_name='taskqueue'):
    """Constructor.

    Args:
      app_id: The application ID.
      host: The nginx host.
      service_name: Service name expected for all calls.
    """
    super(TaskQueueServiceStub, self).__init__(
        service_name, max_request_size=MAX_REQUEST_SIZE)
    self.__app_id = app_id
    self.__nginx_host = host
    self.__tq_locations = self._GetTQLocations()

  def _GetTQLocations(self):
    """ Gets a list of TaskQueue proxies. """
    if os.path.exists(TASKQUEUE_PROXY_FILE):
      try:
        with open(TASKQUEUE_PROXY_FILE) as tq_file:
          ips = [ip for ip in tq_file.read().split('\n') if ip]
      except IOError:
        raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR)
    else:
      raise apiproxy_errors.ApplicationError(
        taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR)

    locations = ["{ip}:{port}".format(ip=ip, port=TASKQUEUE_SERVER_PORT)
                 for ip in ips]
    return locations

  def _ChooseTaskName(self):
    """ Creates a task name that the system can use to address
        tasks from different apps and queues.

    Returns:
      A randomized string representing a task name.
    """
    RAND_LENGTH_SIZE = 32
    alphabet = string.ascii_uppercase + string.digits
    return ''.join(random.choice(alphabet) for _ in range(RAND_LENGTH_SIZE))

  def _AddTransactionalBulkTask(self, request, response):
    """ Add a transactional task.

    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
      response: A taskqueue_service_pb.TaskQueueAddResponse.
    Returns:
      The taskqueue response.
    """
    for add_request in request.add_request_list():
      task_result = response.add_taskresult()

      task_name = None
      if add_request.has_task_name():
        task_name = add_request.task_name()

      if not task_name:
        task_name = self._ChooseTaskName()

      namespaced_name = '_'.join(['task', self.__app_id,
                                  add_request.queue_name(), task_name])

      add_request.set_task_name(task_name)
      task_result.set_chosen_task_name(namespaced_name)

    for add_request, task_result in zip(request.add_request_list(),
                                        response.taskresult_list()):
      task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.OK)

    # All task should have been validated and assigned a unique name by this point.
    try:
      apiproxy_stub_map.MakeSyncCall(
          'datastore_v3', 'AddActions', request, api_base_pb.VoidProto())
    except apiproxy_errors.ApplicationError, e:
      raise apiproxy_errors.ApplicationError(
          e.application_error +
          taskqueue_service_pb.TaskQueueServiceError.DATASTORE_ERROR,
          e.error_detail)

    return response

  def _Dynamic_Add(self, request, response, request_id=None):
    """Add a single task to a queue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: The taskqueue_service_pb.TaskQueueAddRequest. See
          taskqueue_service.proto.
      response: The taskqueue_service_pb.TaskQueueAddResponse. See
          taskqueue_service.proto.
      request_id: A string specifying the request ID.
    """
    bulk_request = taskqueue_service_pb.TaskQueueBulkAddRequest()
    bulk_response = taskqueue_service_pb.TaskQueueBulkAddResponse()

    bulk_request.add_add_request().CopyFrom(request)
    self._Dynamic_BulkAdd(bulk_request, bulk_response, request_id)

    assert bulk_response.taskresult_size() == 1
    result = bulk_response.taskresult(0).result()

    if result != taskqueue_service_pb.TaskQueueServiceError.OK:
      raise apiproxy_errors.ApplicationError(result)
    elif bulk_response.taskresult(0).has_chosen_task_name():
      response.set_chosen_task_name(
          bulk_response.taskresult(0).chosen_task_name())

  def _Dynamic_BulkAdd(self, request, response, request_id=None):
    """Add many tasks to a queue using a single request.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: The taskqueue_service_pb.TaskQueueBulkAddRequest. See
          taskqueue_service.proto.
      response: The taskqueue_service_pb.TaskQueueBulkAddResponse. See
          taskqueue_service.proto.
      request_id: A string specifying the request ID.
    Returns:
      The response object.
    """
    assert request.add_request_size(), 'taskqueue should prevent empty requests'

    if request.add_request(0).has_transaction():
      self._AddTransactionalBulkTask(request, response)
      return response

    for add_request in request.add_request_list():
      add_request.set_app_id(self.__app_id)

    self._RemoteSend(request, response, "BulkAdd", request_id)
    return response

  def _Dynamic_UpdateQueue(self, request, unused_response, request_id=None):
    """Local implementation of the UpdateQueue RPC in TaskQueueService.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateQueueRequest.
      unused_response: A taskqueue_service_pb.TaskQueueUpdateQueueResponse.
                       Not used.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, unused_response, "UpdateQueue", request_id)
    return unused_response

  def _Dynamic_FetchQueues(self, request, response, request_id=None):
    """Local implementation of the FetchQueues RPC in TaskQueueService.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueuesRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueuesResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "FetchQueues", request_id)
    return response

  def _Dynamic_FetchQueueStats(self, request, response, request_id=None):
    """Local 'random' implementation of the TaskQueueService.FetchQueueStats.

    This implementation loads some stats from the task store, the rest with
    random numbers.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueueStatsRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueueStatsResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "FetchQueueStats", request_id)
    return response

  def _Dynamic_QueryTasks(self, request, response, request_id=None):
    """Local implementation of the TaskQueueService.QueryTasks RPC.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueQueryTasksRequest.
      response: A taskqueue_service_pb.TaskQueueQueryTasksResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "QueryTasks", request_id)
    return response

  def _Dynamic_FetchTask(self, request, response, request_id=None):
    """Local implementation of the TaskQueueService.FetchTask RPC.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchTaskRequest.
      response: A taskqueue_service_pb.TaskQueueFetchTaskResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "FetchTask", request_id)
    return response

  def _Dynamic_Delete(self, request, response, request_id=None):
    """Local delete implementation of TaskQueueService.Delete.

    Deletes tasks from the task store. A 1/20 chance of a transient error.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "Delete", request_id)
    return response

  def _Dynamic_ForceRun(self, request, response, request_id=None):
    """Local force run implementation of TaskQueueService.ForceRun.

    Forces running of a task in a queue. This is a no-op here.
    This will fail randomly for testing.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueForceRunRequest.
      response: A taskqueue_service_pb.TaskQueueForceRunResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "ForceRun", request_id)
    return response

  def _Dynamic_DeleteQueue(self, request, response, request_id=None):
    """Local delete implementation of TaskQueueService.DeleteQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteQueueRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteQueueResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "DeleteQueue", request_id)
    return response

  def _Dynamic_PauseQueue(self, request, response, request_id=None):
    """Remote pause implementation of TaskQueueService.PauseQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueuePauseQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePauseQueueResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "PauseQueue", request_id)
    return response

  def _Dynamic_PurgeQueue(self, request, response, request_id=None):
    """Remote purge implementation of TaskQueueService.PurgeQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueuePurgeQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePurgeQueueResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "PurgeQueue", request_id)
    return response

  def _Dynamic_DeleteGroup(self, request, response, request_id=None):
    """Remote delete implementation of TaskQueueService.DeleteGroup.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteGroupRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteGroupResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "DeleteGroup", request_id)

  def _Dynamic_UpdateStorageLimit(self, request, response, request_id=None):
    """Remote implementation of TaskQueueService.UpdateStorageLimit.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateStorageLimitRequest.
      response: A taskqueue_service_pb.TaskQueueUpdateStorageLimitResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "UpdateStorageLimit", request_id)

  def _Dynamic_QueryAndOwnTasks(self, request, response, request_id=None):
    """Local implementation of TaskQueueService.QueryAndOwnTasks.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueQueryAndOwnTasksRequest.
      response: A taskqueue_service_pb.TaskQueueQueryAndOwnTasksResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "QueryAndOwnTasks", request_id)

  def _Dynamic_ModifyTaskLease(self, request, response, request_id=None):
    """Local implementation of TaskQueueService.ModifyTaskLease.

    Args:
      request: A taskqueue_service_pb.TaskQueueModifyTaskLeaseRequest.
      response: A taskqueue_service_pb.TaskQueueModifyTaskLeaseResponse.
      request_id: A string specifying the request ID.
    """
    self._RemoteSend(request, response, "ModifyTaskLease", request_id)

  def _RemoteSend(self, request, response, method, request_id=None,
                  service_id=None, version_id=None):
    """Sends a request remotely to the taskqueue server.

    Args:
      request: A protocol buffer request.
      response: A protocol buffer response.
      method: The function which is calling the remote server.
      request_id: A string specifying a request ID.
      service_id: A string specifying the client service ID.
      version_id: A string specifying the client version ID.
    Raises:
      taskqueue_service_pb.InternalError:
    """
    tag = self.__app_id
    api_request = remote_api_pb.Request()
    api_request.set_method(method)
    api_request.set_service_name("taskqueue")
    api_request.set_request(request.Encode())
    if request_id is not None:
      api_request.set_request_id(request_id)

    api_response = remote_api_pb.Response()

    retry_count = 0
    max_retries = 3
    location = random.choice(self.__tq_locations)
    while True:
      try:
        api_request.sendCommand(location,
          tag,
          api_response,
          1,
          False,
          KEY_LOCATION,
          CERT_LOCATION)
        break
      except socket.error as socket_error:
        if socket_error.errno in (errno.ECONNREFUSED, errno.EHOSTUNREACH):
          backoff_ms = 500 * 3**retry_count   # 0.5s, 1.5s, 4.5s
          retry_count += 1
          if retry_count > max_retries:
            raise

          logging.warning(
            'Failed to call {} method of TaskQueue ({}). Retry #{} in {}ms.'
            .format(method, socket_error, retry_count, backoff_ms))
          time.sleep(float(backoff_ms) / 1000)
          location = random.choice(self.__tq_locations)
          api_response = remote_api_pb.Response()
          continue

        if socket_error.errno == errno.ETIMEDOUT:
          raise apiproxy_errors.ApplicationError(
            taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR,
            'Connection timed out when making taskqueue request')
        raise
      # AppScale: Interpret ProtocolBuffer.ProtocolBufferReturnError as
      # datastore_errors.InternalError
      except ProtocolBuffer.ProtocolBufferReturnError as e:
        raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR, str(e))

    if not api_response or not api_response.has_response():
      raise apiproxy_errors.ApplicationError(
        taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR)

    if api_response.has_application_error():
      error_pb = api_response.application_error()
      logging.error(error_pb.detail())
      raise apiproxy_errors.ApplicationError(error_pb.code(),
                                             error_pb.detail())

    if api_response.has_exception():
      raise api_response.exception()

    response.ParseFromString(api_response.response())

