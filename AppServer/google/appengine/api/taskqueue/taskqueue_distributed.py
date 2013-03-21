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
__all__ = []

import datetime
import logging
import random
import string

import taskqueue_service_pb

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.runtime import apiproxy_errors
from google.appengine.ext.remote_api import remote_api_pb

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

TASKQUEUE_LOCATION_FILE = "/etc/appscale/rabbitmq_ip"
TASKQUEUE_SERVER_PORT = 64839

class TaskQueueServiceStub(apiproxy_stub.APIProxyStub):
  """Python only task queue service stub.

  This stub executes tasks when enabled by using the dev_appserver's AddEvent
  capability. 
  """
  def __init__(self, app_id, host, port, service_name='taskqueue'):
    """Constructor.

    Args:
      app_id: The application ID.
      host: The nginx host.
      port: The nginx port.
      service_name: Service name expected for all calls.
    """
    super(TaskQueueServiceStub, self).__init__(
        service_name, max_request_size=MAX_REQUEST_SIZE)
    self.__app_id = app_id
    self.__nginx_host = host
    self.__nginx_port = port
    self.__tq_location = self.__GetTQLocation()

  def __GetTQLocation(self):
    """ Gets the nearest AppScale TaskQueue server. """
    tq_file = open(TASKQUEUE_LOCATION_FILE)
    location = tq_file.read() 
    location += ":" + str(TASKQUEUE_SERVER_PORT)
    return location

  def _ChooseTaskName(self, app_name, queue_name, user_chosen=None):
    """ Creates a task name that the system can use to address
        tasks from different apps and queues.
 
    Args:
      app_name: The application name.
      queue_name: The queue 
      user_chosen: A string name the user selected for their applicaiton.
    Returns:
      A randomized string representing a task name.
    """
    RAND_LENGTH_SIZE = 32
    if not user_chosen:
      user_chosen = ''.join(random.choice(string.ascii_uppercase + \
        string.digits) for x in range(RAND_LENGTH_SIZE))
    return 'task_%s_%s_%s' % (app_name, queue_name, user_chosen)


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
      namespaced_name = self._ChooseTaskName(add_request.app_id(),
                                            add_request.queue_name(),
                                            user_chosen=task_name)
      add_request.set_task_name(namespaced_name)
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

  def _Dynamic_Add(self, request, response):
    """Add a single task to a queue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: The taskqueue_service_pb.TaskQueueAddRequest. See
          taskqueue_service.proto.
      response: The taskqueue_service_pb.TaskQueueAddResponse. See
          taskqueue_service.proto.
    """
    bulk_request = taskqueue_service_pb.TaskQueueBulkAddRequest()
    bulk_response = taskqueue_service_pb.TaskQueueBulkAddResponse()

    bulk_request.add_add_request().CopyFrom(request)
    self._Dynamic_BulkAdd(bulk_request, bulk_response)

    assert bulk_response.taskresult_size() == 1
    result = bulk_response.taskresult(0).result()

    if result != taskqueue_service_pb.TaskQueueServiceError.OK:
      raise apiproxy_errors.ApplicationError(result)
    elif bulk_response.taskresult(0).has_chosen_task_name():
      response.set_chosen_task_name(
          bulk_response.taskresult(0).chosen_task_name())

  def _Dynamic_BulkAdd(self, request, response):
    """Add many tasks to a queue using a single request.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: The taskqueue_service_pb.TaskQueueBulkAddRequest. See
          taskqueue_service.proto.
      response: The taskqueue_service_pb.TaskQueueBulkAddResponse. See
          taskqueue_service.proto.
    Returns:
      The response object.
    """
    assert request.add_request_size(), 'taskqueue should prevent empty requests'

    if request.add_request(0).has_transaction():
      self._AddTransactionalBulkTask(request, response)
      return response

    for add_request in request.add_request_list():
      add_request.set_app_id(self.__app_id)
      url = add_request.url()
      url = "http://" + self.__nginx_host + ":" + str(self.__nginx_port) + url
      add_request.set_url(url)

    self._RemoteSend(request, response, "BulkAdd")
    return response

  def _Dynamic_UpdateQueue(self, request, unused_response):
    """Local implementation of the UpdateQueue RPC in TaskQueueService.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateQueueRequest.
      unused_response: A taskqueue_service_pb.TaskQueueUpdateQueueResponse.
                       Not used.
    """
    self._RemoteSend(request, unused_response, "UpdateQueue")
    return unused_response

  def _Dynamic_FetchQueues(self, request, response):
    """Local implementation of the FetchQueues RPC in TaskQueueService.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueuesRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueuesResponse.
    """
    self._RemoteSend(request, response, "FetchQueues")
    return response

  def _Dynamic_FetchQueueStats(self, request, response):
    """Local 'random' implementation of the TaskQueueService.FetchQueueStats.

    This implementation loads some stats from the task store, the rest with
    random numbers.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueueStatsRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueueStatsResponse.
    """
    self._RemoteSend(request, response, "FetchQueueStats")
    return response

  def _Dynamic_QueryTasks(self, request, response):
    """Local implementation of the TaskQueueService.QueryTasks RPC.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueQueryTasksRequest.
      response: A taskqueue_service_pb.TaskQueueQueryTasksResponse.
    """
    self._RemoteSend(request, response, "QueryTasks")
    return response

  def _Dynamic_FetchTask(self, request, response):
    """Local implementation of the TaskQueueService.FetchTask RPC.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchTaskRequest.
      response: A taskqueue_service_pb.TaskQueueFetchTaskResponse.
    """
    self._RemoteSend(request, response, "FetchTask")
    return response 

  def _Dynamic_Delete(self, request, response):
    """Local delete implementation of TaskQueueService.Delete.

    Deletes tasks from the task store. A 1/20 chance of a transient error.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteResponse.
    """
    self._RemoteSend(request, response, "Delete")
    return response 

  def _Dynamic_ForceRun(self, request, response):
    """Local force run implementation of TaskQueueService.ForceRun.

    Forces running of a task in a queue. This is a no-op here.
    This will fail randomly for testing.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueForceRunRequest.
      response: A taskqueue_service_pb.TaskQueueForceRunResponse.
    """
    self._RemoteSend(request, response, "ForceRun")
    return response
 
  def _Dynamic_DeleteQueue(self, request, response):
    """Local delete implementation of TaskQueueService.DeleteQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteQueueRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteQueueResponse.
    """
    self._RemoteSend(request, response, "DeleteQueue")
    return response

  def _Dynamic_PauseQueue(self, request, response):
    """Remote pause implementation of TaskQueueService.PauseQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueuePauseQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePauseQueueResponse.
    """
    self._RemoteSend(request, response, "PauseQueue")
    return response

  def _Dynamic_PurgeQueue(self, request, response):
    """Remote purge implementation of TaskQueueService.PurgeQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueuePurgeQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePurgeQueueResponse.
    """
    self._RemoteSend(request, response, "PurgeQueue")
    return response

  def _Dynamic_DeleteGroup(self, request, response):
    """Remote delete implementation of TaskQueueService.DeleteGroup.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteGroupRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteGroupResponse.
    """
    self._RemoteSend(request, response, "DeleteGroup")
 
  def _Dynamic_UpdateStorageLimit(self, request, response):
    """Remote implementation of TaskQueueService.UpdateStorageLimit.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateStorageLimitRequest.
      response: A taskqueue_service_pb.TaskQueueUpdateStorageLimitResponse.
    """
    self._RemoteSend(request, response, "UpdateStorageLimit")

  def _Dynamic_QueryAndOwnTasks(self, request, response):
    """Local implementation of TaskQueueService.QueryAndOwnTasks.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueQueryAndOwnTasksRequest.
      response: A taskqueue_service_pb.TaskQueueQueryAndOwnTasksResponse.
    """
    self._RemoteSend(request, response, "QueryAndOwnTasks")

  def _Dynamic_ModifyTaskLease(self, request, response):
    """Local implementation of TaskQueueService.ModifyTaskLease.

    Args:
      request: A taskqueue_service_pb.TaskQueueModifyTaskLeaseRequest.
      response: A taskqueue_service_pb.TaskQueueModifyTaskLeaseResponse.
    """
    self._RemoteSend(request, response, "ModifyTaskLease")

  def _RemoteSend(self, request, response, method):
    """Sends a request remotely to the taskqueue server. 
 
    Args:
      request: A protocol buffer request.
      response: A protocol buffer response.
      method: The function which is calling the remote server.
    Raises:
      taskqueue_service_pb.InternalError: 
    """
    tag = self.__app_id
    api_request = remote_api_pb.Request()
    api_request.set_method(method)
    api_request.set_service_name("taskqueue")
    api_request.set_request(request.Encode())

    api_response = remote_api_pb.Response()
    api_response = api_request.sendCommand(self.__tq_location,
      tag,
      api_response,
      1,
      False,
      KEY_LOCATION,
      CERT_LOCATION)

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

