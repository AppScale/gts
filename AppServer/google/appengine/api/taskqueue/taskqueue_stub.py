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




"""Stub version of the Task Queue API.

This stub stores tasks and runs them via dev_appserver's AddEvent capability.
It also validates the tasks by checking their queue name against the queue.yaml.

As well as implementing Task Queue API functions, the stub exposes various other
functions that are used by the dev_appserver's admin console to display the
application's queues and tasks.
"""













import StringIO
import base64
import calendar
import bisect
import datetime
import logging
import os
import random
import string
import time

import taskqueue_service_pb

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import queueinfo
from google.appengine.runtime import apiproxy_errors




DEFAULT_RATE = '5.00/s'





DEFAULT_BUCKET_SIZE = 5


MAX_ETA = datetime.timedelta(days=30)




MAX_TASK_SIZE = 10 * 1024



BUILT_IN_HEADERS = set(['x-appengine-queuename',
                        'x-appengine-taskname',
                        'x-appengine-taskretrycount',
                        'x-appengine-development-payload',
                        'content-length'])



DEFAULT_QUEUE_NAME = 'default'

AUTOMATIC_QUEUES = {
    DEFAULT_QUEUE_NAME: (0.2, DEFAULT_BUCKET_SIZE, DEFAULT_RATE),


    '__cron': (1, 1, '1/s')}


def _GetAppId(request):
  """Returns the app id to use for the given request.

  Args:
    request: A protocol buffer that has an app_id field.

  Returns:
    A string containing the app id or None if no app id was specified.
  """
  if request.has_app_id():
    return request.app_id()
  else:
    return None


def _SecToUsec(t):
  """Converts a time in seconds since the epoch to usec since the epoch.

  Args:
    t: Time in seconds since the unix epoch

  Returns:
    A float containing the number of usec since the unix epoch.
  """
  return t * 1e6


def _UsecToSec(t):
  """Converts a time in usec since the epoch to seconds since the epoch.

  Args:
    t: Time in usec since the unix epoch

  Returns:
    A float containing the number of seconds since the unix epoch.
  """
  return t / 1e6


class _Group(object):
  """A taskqueue group.

  This class contains all of the queues for an application.
  """

  def __init__(self, queue_yaml_parser=None, app_id=None,
               _all_queues_valid=False, _enqueue_automatic_run_task=None):
    """Constructor.

    Args:
      queue_yaml_parser: A function that takes no parameters and returns the
          parsed results of the queue.yaml file. If this queue is not based on a
          queues.yaml file use None.
      app_id: The app id this Group is representing or None if it is the
        currently running application.
      _all_queues_valid: Automatically generate queues on first access.
      _enqueue_automatic_run_task: Callable for automatically executing tasks.
        Takes the ETA of the task in seconds since the epoch, the queue_name and
        a task name. May be None if automatic task running is disabled.
    """


    self._queues = {}
    self._queue_yaml_parser = queue_yaml_parser
    self._all_queues_valid = _all_queues_valid
    self._next_task_id = 1
    self._app_id = app_id
    self._enqueue_automatic_run_task = _enqueue_automatic_run_task




  def GetQueuesAsDicts(self):
    """Gets all the applications's queues.

    Returns:
      A list of dictionaries, where each dictionary contains one queue's
      attributes. E.g.:
        [{'name': 'some-queue',
          'max_rate': '1/s',
          'bucket_size': 5,
          'oldest_task': '2009/02/02 05:37:42',
          'eta_delta': '0:00:06.342511 ago',
          'tasks_in_queue': 12}, ...]
      The list of queues always includes the default queue.
    """
    self._ReloadQueuesFromYaml()
    now = datetime.datetime.utcnow()

    queues = []
    for queue_name, queue in sorted(self._queues.items()):
      queue_dict = {}
      queues.append(queue_dict)

      queue_dict['name'] = queue_name
      queue_dict['max_rate'] = queue.user_specified_rate
      queue_dict['bucket_size'] = queue.bucket_capacity
      if queue.Oldest():
        queue_dict['oldest_task'] = _FormatEta(queue.Oldest())
        queue_dict['eta_delta'] = _EtaDelta(queue.Oldest(), now)
      else:
        queue_dict['oldest_task'] = ''
        queue_dict['eta_delta'] = ''
      queue_dict['tasks_in_queue'] = queue.Count()

    return queues

  def HasQueue(self, queue_name):
    """Check if the specified queue_name references a valid queue.

    Args:
      queue_name: The name of the queue to check.

    Returns:
      True if the queue exists, False otherwise.
    """
    self._ReloadQueuesFromYaml()
    return queue_name in self._queues and (
        self._queues[queue_name] is not None)

  def GetQueue(self, queue_name):
    """Gets the _Queue instance for the specified queue.

    Args:
      queue_name: The name of the queue to fetch.

    Returns:
      The _Queue instance for the specified queue.

    Raises:
      KeyError if the queue does not exist.
    """
    self._ReloadQueuesFromYaml()
    return self._queues[queue_name]

  def _ConstructQueue(self, queue_name, *args, **kwargs):
    self._queues[queue_name] = _Queue(
        queue_name, *args, **kwargs)

  def _ConstructAutomaticQueue(self, queue_name):
    if queue_name in AUTOMATIC_QUEUES:
      queue = _Queue(queue_name, *AUTOMATIC_QUEUES[queue_name])
    else:


      assert self._all_queues_valid
      queue =  _Queue(queue_name)
    self._queues[queue_name] = queue

  def _ReloadQueuesFromYaml(self):
    """Update the queue map with the contents of the queue.yaml file.

    This function will remove queues that no longer exist in the queue.yaml
    file.

    If no queue yaml parser has been defined, this function is a no-op.
    """
    if not self._queue_yaml_parser:
      return

    queue_info = self._queue_yaml_parser()

    if queue_info and queue_info.queue:
      queues = queue_info.queue
    else:
      queues = []

    old_queues = set(self._queues)
    new_queues = set()

    for entry in queues:
      queue_name = entry.name
      new_queues.add(queue_name)


      max_rate = entry.rate
      if entry.bucket_size:
        bucket_size = entry.bucket_size
      else:
        bucket_size = DEFAULT_BUCKET_SIZE

      if self._queues.get(queue_name) is None:

        self._ConstructQueue(queue_name, bucket_capacity=bucket_size,
                             user_specified_rate=max_rate)
      else:


        self._queues[queue_name].bucket_size = bucket_size
        self._queues[queue_name].user_specified_rate = max_rate

    if DEFAULT_QUEUE_NAME not in self._queues:
      self._ConstructAutomaticQueue(DEFAULT_QUEUE_NAME)


    new_queues.add(DEFAULT_QUEUE_NAME)
    if not self._all_queues_valid:

      for queue_name in old_queues-new_queues:



        del self._queues[queue_name]




  def _ValidateQueueName(self, queue_name):
    """Tests if the specified queue exists and creates it if needed.

    This function replicates the behaviour of the taskqueue service by
    automatically creating the 'automatic' queues when they are first accessed.

    Args:
      queue_name: The name queue of the queue to check.

    Returns:
      If there are no problems, returns TaskQueueServiceError.OK. Otherwise
          returns the correct constant from TaskQueueServiceError.
    """
    if not queue_name:
      return taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_NAME
    elif queue_name not in self._queues:
      if queue_name in AUTOMATIC_QUEUES or self._all_queues_valid:

        self._ConstructAutomaticQueue(queue_name)
      else:
        return taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE
    elif self._queues[queue_name] is None:
      return taskqueue_service_pb.TaskQueueServiceError.TOMBSTONED_QUEUE

    return taskqueue_service_pb.TaskQueueServiceError.OK

  def _CheckQueueForRpc(self, queue_name):
    """Ensures the specified queue exists and creates it if needed.

    This function replicates the behaviour of the taskqueue service by
    automatically creating the 'automatic' queues when they are first accessed.

    Args:
      queue_name: The name queue of the queue to check

    Raises:
      ApplicationError: If the queue name is invalid, tombstoned or does not
          exist.
    """
    self._ReloadQueuesFromYaml()

    response = self._ValidateQueueName(queue_name)

    if response != taskqueue_service_pb.TaskQueueServiceError.OK:
      raise apiproxy_errors.ApplicationError(response)

  def _ChooseTaskName(self):
    """Returns a string containing a unique task name."""




    self._next_task_id += 1
    return 'task%d' % (self._next_task_id - 1)

  def _VerifyTaskQueueAddRequest(self, request, now):
    """Checks that a TaskQueueAddRequest is valid.

    Checks that a TaskQueueAddRequest specifies a valid eta and a valid queue.

    Args:
      request: The taskqueue_service_pb.TaskQueueAddRequest to validate.
      now: A datetime.datetime object containing the current time in UTC.

    Returns:
      A taskqueue_service_pb.TaskQueueServiceError indicating any problems with
      the request or taskqueue_service_pb.TaskQueueServiceError.OK if it is
      valid.
    """
    if request.eta_usec() < 0:
      return taskqueue_service_pb.TaskQueueServiceError.INVALID_ETA

    eta = datetime.datetime.utcfromtimestamp(_UsecToSec(request.eta_usec()))
    max_eta = now + MAX_ETA
    if eta > max_eta:
      return taskqueue_service_pb.TaskQueueServiceError.INVALID_ETA


    queue_name_response = self._ValidateQueueName(request.queue_name())
    if queue_name_response != taskqueue_service_pb.TaskQueueServiceError.OK:
      return queue_name_response


    if request.has_crontimetable() and self.app_id is None:
      return taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED

    if request.ByteSize() > MAX_TASK_SIZE:
      return taskqueue_service_pb.TaskQueueServiceError.TASK_TOO_LARGE

    return taskqueue_service_pb.TaskQueueServiceError.OK




  def BulkAdd_Rpc(self, request, response):
    """Add many tasks to a queue using a single request.

    Args:
      request: The taskqueue_service_pb.TaskQueueBulkAddRequest. See
          taskqueue_service.proto.
      response: The taskqueue_service_pb.TaskQueueBulkAddResponse. See
          taskqueue_service.proto.
    """
    self._ReloadQueuesFromYaml()


    if not request.add_request(0).queue_name():
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)

    error_found = False
    task_results_with_chosen_names = set()
    now = datetime.datetime.utcnow()


    for add_request in request.add_request_list():
      task_result = response.add_taskresult()
      result = self._VerifyTaskQueueAddRequest(add_request, now)
      if result == taskqueue_service_pb.TaskQueueServiceError.OK:
        if not add_request.task_name():
          chosen_name = self._ChooseTaskName()
          add_request.set_task_name(chosen_name)
          task_results_with_chosen_names.add(id(task_result))



        task_result.set_result(
            taskqueue_service_pb.TaskQueueServiceError.SKIPPED)
      else:
        error_found = True
        task_result.set_result(result)

    if error_found:
      return


    if request.add_request(0).has_transaction():
      self._TransactionalBulkAdd(request)
    else:
      self._NonTransactionalBulkAdd(request, response, now)


    for add_request, task_result in zip(request.add_request_list(),
                                        response.taskresult_list()):
      if (task_result.result() ==
          taskqueue_service_pb.TaskQueueServiceError.SKIPPED):
        task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.OK)
      if id(task_result) in task_results_with_chosen_names:
        task_result.set_chosen_task_name(add_request.task_name())

  def _TransactionalBulkAdd(self, request):
    """Uses datastore.AddActions to associate tasks with a transaction.

    Args:
      request: The taskqueue_service_pb.TaskQueueBulkAddRequest containing the
        tasks to add. N.B. all tasks in the request have been validated and
        assigned unique names.
    """
    try:
      apiproxy_stub_map.MakeSyncCall(
          'datastore_v3', 'AddActions', request, api_base_pb.VoidProto())
    except apiproxy_errors.ApplicationError, e:
      raise apiproxy_errors.ApplicationError(
          e.application_error +
          taskqueue_service_pb.TaskQueueServiceError.DATASTORE_ERROR,
          e.error_detail)

  def _NonTransactionalBulkAdd(self, request, response, now):
    """Adds tasks to the appropriate _Queue instance.

    Args:
      request: The taskqueue_service_pb.TaskQueueBulkAddRequest containing the
        tasks to add. N.B. all tasks in the request have been validated and
        those with empty names have been assigned unique names.
      response: The taskqueue_service_pb.TaskQueueBulkAddResponse to populate
        with the results. N.B. the chosen_task_name field in the response will
        not be filled-in.
      now: A datetime.datetime object containing the current time in UTC.
    """

    queue_name = request.add_request(0).queue_name()

    store = self._queues[queue_name]
    for add_request, task_result in zip(request.add_request_list(),
                                        response.taskresult_list()):
      try:
        store.Add(add_request, now)
      except apiproxy_errors.ApplicationError, e:
        task_result.set_result(e.application_error)
      else:
        task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.OK)



        if self._enqueue_automatic_run_task:
          self._enqueue_automatic_run_task(
              _UsecToSec(add_request.eta_usec()),
              queue_name, add_request.task_name())

  def UpdateQueue_Rpc(self, request, response):
    """Implementation of the UpdateQueue RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateQueueRequest.
      response: A taskqueue_service_pb.TaskQueueUpdateQueueResponse.
    """
    queue_name = request.queue_name()

    response = self._ValidateQueueName(queue_name)
    is_unknown_queue = (
        response == taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
    if response != taskqueue_service_pb.TaskQueueServiceError.OK and (
        not is_unknown_queue):
      raise apiproxy_errors.ApplicationError(response)

    if is_unknown_queue:
      self._queues[queue_name] = _Queue(request.queue_name())



      if self._app_id is not None:
        self._queues[queue_name].Populate(random.randint(10, 100))

    self._queues[queue_name].UpdateQueue_Rpc(request, response)

  def FetchQueues_Rpc(self, request, response):
    """Implementation of the FetchQueues RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueuesRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueuesResponse.
    """
    for queue_name in sorted(self._queues):
      if response.queue_size() > request.max_rows():
        break


      if self._queues[queue_name] is None:
        continue


      self._queues[queue_name].FetchQueues_Rpc(request, response)

  def FetchQueueStats_Rpc(self, request, response):
    """Implementation of the FetchQueueStats rpc which returns 'random' data.

    This implementation loads some stats from the task store, the rest are
    random numbers.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueueStatsRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueueStatsResponse.
    """
    for queue_name in request.queue_name_list():
      stats = response.add_queuestats()
      if queue_name not in self._queues:

        stats.set_num_tasks(0)
        stats.set_oldest_eta_usec(-1)
        continue
      store = self._queues[queue_name]

      stats.set_num_tasks(store.Count())
      if stats.num_tasks() == 0:
        stats.set_oldest_eta_usec(-1)
      else:
        stats.set_oldest_eta_usec(store.Oldest())


      if random.randint(0, 9) > 0:
        scanner_info = stats.mutable_scanner_info()
        scanner_info.set_executed_last_minute(random.randint(0, 10))
        scanner_info.set_executed_last_hour(scanner_info.executed_last_minute()
                                            + random.randint(0, 100))
        scanner_info.set_sampling_duration_seconds(random.random() * 10000.0)
        scanner_info.set_requests_in_flight(random.randint(0, 10))

  def QueryTasks_Rpc(self, request, response):
    """Implementation of the QueryTasks RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueQueryTasksRequest.
      response: A taskqueue_service_pb.TaskQueueQueryTasksResponse.
    """
    self._CheckQueueForRpc(request.queue_name())
    self._queues[request.queue_name()].QueryTasks_Rpc(request, response)

  def Delete_Rpc(self, request, response):
    """Implementation of the Delete RPC.

    Deletes tasks from the task store. A 1/20 chance of a transient error.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteResponse.
    """
    def _AddResultForAll(result):
      for _ in request.task_name_list():
        response.add_result(result)
    if request.queue_name() not in self._queues:
      _AddResultForAll(taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
    elif self._queues[request.queue_name()] is None:
      _AddResultForAll(
          taskqueue_service_pb.TaskQueueServiceError.TOMBSTONED_QUEUE)
    else:
      self._queues[request.queue_name()].Delete(request, response)

  def DeleteQueue_Rpc(self, request, response):
    """Implementation of the DeleteQueue RPC.

    Tombstones the queue.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteQueueRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteQueueResponse.
    """
    self._CheckQueueForRpc(request.queue_name())


    self._queues[request.queue_name()] = None

  def PauseQueue_Rpc(self, request, response):
    """Implementation of the PauseQueue RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueuePauseQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePauseQueueResponse.
    """
    self._CheckQueueForRpc(request.queue_name())
    self._queues[request.queue_name()].paused = request.pause()

  def PurgeQueue_Rpc(self, request, response):
    """Implementation of the PurgeQueue RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueuePurgeQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePurgeQueueResponse.
    """
    self._CheckQueueForRpc(request.queue_name())
    self._queues[request.queue_name()].PurgeQueue()


class _Queue(object):
  """A Taskqueue Queue.

  This class contains all of the properties of a queue and a sorted list of
  tasks.
  """
  def __init__(self, queue_name, bucket_refill_per_second=DEFAULT_RATE,
               bucket_capacity=DEFAULT_BUCKET_SIZE,
               user_specified_rate=DEFAULT_RATE, retry_parameters=None,
               max_concurrent_requests=None, paused=False):


    self.queue_name = queue_name
    self.bucket_refill_per_second = bucket_refill_per_second
    self.bucket_capacity = bucket_capacity
    self.user_specified_rate = user_specified_rate
    self.retry_parameters = retry_parameters
    self.max_concurrent_requests = max_concurrent_requests
    self.paused = paused


    self._sorted_by_name = []

    self._sorted_by_eta = []




  def UpdateQueue_Rpc(self, request, response):
    """Implementation of the UpdateQueue RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateQueueRequest.
      response: A taskqueue_service_pb.TaskQueueUpdateQueueResponse.
    """
    assert request.queue_name() == self.queue_name

    self.bucket_refill_per_second = request.bucket_refill_per_second()
    self.bucket_capacity = request.bucket_capacity()
    if request.has_user_specified_rate():
      self.user_specified_rate = request.user_specified_rate()
    else:
      self.user_specified_rate = None
    if request.has_retry_parameters():
      self.retry_parameters = request.retry_parameters()
    else:
      self.retry_parameters = None
    if request.has_max_concurrent_requests():
      self.max_concurrent_requests = request.max_concurrent_requests()
    else:
      self.max_concurrent_requests = None

  def FetchQueues_Rpc(self, request, response):
    """Fills out a queue message on the provided TaskQueueFetchQueuesResponse.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueuesRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueuesResponse.
    """
    response_queue = response.add_queue()

    response_queue.set_queue_name(self.queue_name)
    response_queue.set_bucket_refill_per_second(
        self.bucket_refill_per_second)
    response_queue.set_bucket_capacity(self.bucket_capacity)
    if self.user_specified_rate is not None:
      response_queue.set_user_specified_rate(self.user_specified_rate)
    if self.max_concurrent_requests is not None:
      response_queue.set_max_concurrent_requests(
          self.max_concurrent_requests)
    if self.retry_parameters is not None:
      response_queue.retry_parameters().CopyFrom(self.retry_parameters)
    response_queue.set_paused(self.paused)

  def QueryTasks_Rpc(self, request, response):
    """Implementation of the QueryTasks RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueQueryTasksRequest.
      response: A taskqueue_service_pb.TaskQueueQueryTasksResponse.
    """
    if request.has_start_eta_usec():
      tasks = self.Lookup(request.max_rows(), name=request.start_task_name(),
                          eta=request.start_eta_usec())
    else:
      tasks = self.Lookup(request.max_rows(), name=request.start_task_name())
    for task in tasks:
      response.add_task().MergeFrom(task)

  def Delete_Rpc(self, request, response):
    """Implementation of the Delete RPC.

    Deletes tasks from the task store. A 1/20 chance of a transient error.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteResponse.
    """
    for taskname in request.task_name_list():
      if random.random() <= 0.05:
        response.add_result(
            taskqueue_service_pb.TaskQueueServiceError.TRANSIENT_ERROR)
      else:
        response.add_result(self.Delete(taskname))




  def GetTasksAsDicts(self):
    """Gets all of the tasks in this queue.

    Returns:
      A list of dictionaries, where each dictionary contains one task's
      attributes. E.g.
        [{'name': 'task-123',
          'queue_name': 'default',
          'url': '/update',
          'method': 'GET',
          'eta': '2009/02/02 05:37:42',
          'eta_delta': '0:00:06.342511 ago',
          'body': '',
          'headers': [('user-header', 'some-value')
                      ('X-AppEngine-QueueName': 'update-queue'),
                      ('X-AppEngine-TaskName': 'task-123'),
                      ('X-AppEngine-TaskRetryCount': '0'),
                      ('X-AppEngine-Development-Payload': '1'),
                      ('Content-Length': 0),
                      ('Content-Type': 'application/octet-stream')]

    Raises:
      ValueError: A task request contains an unknown HTTP method type.
    """
    tasks = []
    now = datetime.datetime.utcnow()

    for _, _, task_request in self._sorted_by_eta:
      tasks.append(self._GetTaskAsDictInternal(task_request, now))
    return tasks

  def GetTaskAsDict(self, task_name):
    """Gets a specific task from this queue.

    Returns:
      A dictionary containing one task's attributes. E.g.
        [{'name': 'task-123',
          'queue_name': 'default',
          'url': '/update',
          'method': 'GET',
          'eta': '2009/02/02 05:37:42',
          'eta_delta': '0:00:06.342511 ago',
          'body': '',
          'headers': [('user-header', 'some-value')
                      ('X-AppEngine-QueueName': 'update-queue'),
                      ('X-AppEngine-TaskName': 'task-123'),
                      ('X-AppEngine-TaskRetryCount': '0'),
                      ('X-AppEngine-Development-Payload': '1'),
                      ('Content-Length': 0),
                      ('Content-Type': 'application/octet-stream')]

    Raises:
      ValueError: A task request contains an unknown HTTP method type.
    """
    task_requests = self.Lookup(maximum=1, name=task_name)
    if not task_requests:
      return
    task_request, = task_requests
    if task_request.task_name() != task_name:
      return

    now = datetime.datetime.utcnow()
    return self._GetTaskAsDictInternal(task_request, now)

  def _GetTaskAsDictInternal(self, task_request, now):
    """Converts a TaskQueueAddRequest protocol buffer into a dict.

    Args:
      task_request: An instance of TaskQueueAddRequest.
      now: A datetime.datetime object containing the current time in UTC.

    Returns:
      A dict containing the fields used by the dev appserver's admin console.

    Raises:
      ValueError: A task request contains an unknown HTTP method type.
    """
    task = {}

    task['name'] = task_request.task_name()
    task['queue_name'] = self.queue_name
    task['url'] = task_request.url()
    method = task_request.method()
    if method == taskqueue_service_pb.TaskQueueAddRequest.GET:
      task['method'] = 'GET'
    elif method == taskqueue_service_pb.TaskQueueAddRequest.POST:
      task['method'] = 'POST'
    elif method == taskqueue_service_pb.TaskQueueAddRequest.HEAD:
      task['method'] = 'HEAD'
    elif method == taskqueue_service_pb.TaskQueueAddRequest.PUT:
      task['method'] = 'PUT'
    elif method == taskqueue_service_pb.TaskQueueAddRequest.DELETE:
      task['method'] = 'DELETE'
    else:
      raise ValueError('Unexpected method: %d' % method)

    task['eta'] = _FormatEta(task_request.eta_usec())
    task['eta_delta'] = _EtaDelta(task_request.eta_usec(), now)
    task['body'] = base64.b64encode(task_request.body())



    headers = [(header.key(), header.value())
               for header in task_request.header_list()
               if header.key().lower() not in BUILT_IN_HEADERS]


    headers.append(('X-AppEngine-QueueName', self.queue_name))
    headers.append(('X-AppEngine-TaskName', task['name']))
    headers.append(('X-AppEngine-TaskRetryCount', '0'))
    headers.append(('X-AppEngine-Development-Payload', '1'))
    headers.append(('Content-Length', len(task['body'])))
    if 'content-type' not in frozenset(key.lower() for key, _ in headers):
      headers.append(('Content-Type', 'application/octet-stream'))
    task['headers'] = headers

    return task

  def PurgeQueue(self):
    """Removes all content from the queue."""
    self._sorted_by_name = []
    self._sorted_by_eta = []

  def _GetTasks(self):
    """Helper method for tests returning all tasks sorted by eta.

    Returns:
      A list of taskqueue_service_pb.TaskQueueQueryTasksResponse_Task objects
        sorted by eta.
    """
    tasks = []
    for eta, task_name, task in self._sorted_by_eta:
      tasks.append(task)
    return tasks

  def _InsertTask(self, task):
    """Insert a task into the store, keeps lists sorted.

    Args:
      task: the new task.
    """
    eta = task.eta_usec()
    name = task.task_name()
    bisect.insort_left(self._sorted_by_eta, (eta, name, task))
    bisect.insort_left(self._sorted_by_name, (name, task))

  def Lookup(self, maximum, name=None, eta=None):
    """Lookup a number of sorted tasks from the store.

    If 'eta' is specified, the tasks are looked up in a list sorted by 'eta',
    then 'name'. Otherwise they are sorted by 'name'. We need to be able to
    sort by 'eta' and 'name' because tasks can have identical eta. If you had
    20 tasks with the same ETA, you wouldn't be able to page past them, since
    the 'next eta' would give the first one again. Names are unique, though.

    Args:
      maximum: the maximum number of tasks to return.
      name: a task name to start with.
      eta: an eta to start with.

    Returns:
      A list of up to 'maximum' tasks.

    Raises:
      ValueError: if the task store gets corrupted.
    """
    if eta is None:

      pos = bisect.bisect_left(self._sorted_by_name, (name,))

      tasks = (x[1] for x in self._sorted_by_name[pos:pos + maximum])
      return list(tasks)
    if name is None:
      raise ValueError('must supply name or eta')

    pos = bisect.bisect_left(self._sorted_by_eta, (eta, name))

    tasks = (x[2] for x in self._sorted_by_eta[pos:pos + maximum])
    return list(tasks)

  def Count(self):
    """Returns the number of tasks in the store."""
    return len(self._sorted_by_name)

  def Oldest(self):
    """Returns the oldest eta in the store, or None if no tasks."""
    if self._sorted_by_eta:
      return self._sorted_by_eta[0][0]
    return None

  def Add(self, request, now):
    """Inserts a new task into the store.

    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
      now: A datetime.datetime object containing the current time in UTC.

    Raises:
      apiproxy_errors.ApplicationError: If a task with the same name is already
      in the store.
    """

    pos = bisect.bisect_left(self._sorted_by_name, (request.task_name(),))
    if (pos < len(self._sorted_by_name) and
        self._sorted_by_name[pos][0] == request.task_name()):
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.TASK_ALREADY_EXISTS)

    now_sec = calendar.timegm(now.utctimetuple())
    task = taskqueue_service_pb.TaskQueueQueryTasksResponse_Task()
    task.set_task_name(request.task_name())
    task.set_eta_usec(request.eta_usec())
    task.set_creation_time_usec(_SecToUsec(now_sec))
    task.set_url(request.url())
    task.set_method(request.method())
    for keyvalue in request.header_list():
      header = task.add_header()
      header.set_key(keyvalue.key())
      header.set_value(keyvalue.value())
    if request.has_description():
      task.set_description(request.description())
    if request.has_body():
      task.set_body(request.body())
    if request.has_crontimetable():
      task.mutable_crontimetable().set_schedule(
          request.crontimetable().schedule())
      task.mutable_crontimetable().set_timezone(
          request.crontimetable().timezone())
    self._InsertTask(task)

  def Delete(self, name):
    """Deletes a task from the store by name.

    Args:
      name: the name of the task to delete.

    Returns:
      TaskQueueServiceError.UNKNOWN_TASK: if the task is unknown.
      TaskQueueServiceError.INTERNAL_ERROR: if the store is corrupted.
      TaskQueueServiceError.OK: otherwise.
    """
    pos = bisect.bisect_left(self._sorted_by_name, (name,))
    if pos >= len(self._sorted_by_name):

      return taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_TASK
    if self._sorted_by_name[pos][1].task_name() != name:
      logging.info('looking for task name %s, got task name %s', name,
                   self._sorted_by_name[pos][1].task_name())
      return taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_TASK
    old_task = self._sorted_by_name.pop(pos)[1]

    eta = old_task.eta_usec()
    pos = bisect.bisect_left(self._sorted_by_eta, (eta, name, None))
    if self._sorted_by_eta[pos][2] is not old_task:
      logging.error('task store corrupted')
      return taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERRROR
    self._sorted_by_eta.pop(pos)
    return taskqueue_service_pb.TaskQueueServiceError.OK

  def Populate(self, num_tasks):
    """Populates the store with a number of tasks.

    Args:
      num_tasks: the number of tasks to insert.
    """
    now = datetime.datetime.utcnow()
    now_sec = calendar.timegm(now.utctimetuple())
    now_usec = int(_SecToUsec(now_sec))

    def RandomTask():
      """Creates a new task and randomly populates values."""
      task = taskqueue_service_pb.TaskQueueQueryTasksResponse_Task()
      task.set_task_name(''.join(random.choice(string.ascii_lowercase)
                                 for x in range(20)))

      task.set_eta_usec(now_usec + random.randint(_SecToUsec(-10),
                                                  _SecToUsec(600)))



      task.set_creation_time_usec(min(now_usec, task.eta_usec()) -
                                  random.randint(0, _SecToUsec(20)))

      task.set_url(random.choice(['/a', '/b', '/c', '/d']))
      if random.random() < 0.2:
        task.set_method(
            taskqueue_service_pb.TaskQueueQueryTasksResponse_Task.POST)
        task.set_body('A' * 2000)
      else:
        task.set_method(
            taskqueue_service_pb.TaskQueueQueryTasksResponse_Task.GET)
      task.set_retry_count(max(0, random.randint(-10, 5)))
      if random.random() < 0.3:
        random_headers = [('nexus', 'one'),
                          ('foo', 'bar'),
                          ('content-type', 'text/plain'),
                          ('from', 'user@email.com')]
        for _ in xrange(random.randint(1, 4)):
          elem = random.randint(0, len(random_headers)-1)
          key, value = random_headers.pop(elem)
          header_proto = task.add_header()
          header_proto.set_key(key)
          header_proto.set_value(value)
      return task

    for _ in range(num_tasks):
      self._InsertTask(RandomTask())



def _FormatEta(eta_usec):
  """Formats a task ETA as a date string in UTC."""
  eta = datetime.datetime.utcfromtimestamp(_UsecToSec(eta_usec))
  return eta.strftime('%Y/%m/%d %H:%M:%S')


def _EtaDelta(eta_usec, now):
  """Formats a task ETA as a relative time string."""
  eta = datetime.datetime.utcfromtimestamp(_UsecToSec(eta_usec))
  if eta > now:
    return str(eta - now) + ' from now'
  else:
    return str(now - eta) + ' ago'


class TaskQueueServiceStub(apiproxy_stub.APIProxyStub):
  """Python only task queue service stub.

  This stub executes tasks when enabled by using the dev_appserver's AddEvent
  capability. When task running is disabled this stub will store tasks for
  display on a console, where the user may manually execute the tasks.
  """

  def __init__(self,
               service_name='taskqueue',
               root_path=None,
               auto_task_running=False,
               task_retry_seconds=30,
               _all_queues_valid=False):
    """Constructor.

    Args:
      service_name: Service name expected for all calls.
      root_path: Root path to the directory of the application which may contain
        a queue.yaml file. If None, then it's assumed no queue.yaml file is
        available.
      auto_task_running: When True, the dev_appserver should automatically
        run tasks after they are enqueued.
      task_retry_seconds: How long to wait between task executions after a
        task fails.
    """
    super(TaskQueueServiceStub, self).__init__(service_name)


    self._queues = {}





    self._all_queues_valid = _all_queues_valid

    self._root_path = root_path


    self._queues[None] = _Group(
        self._ParseQueueYaml, app_id=None,
        _all_queues_valid=_all_queues_valid,
        _enqueue_automatic_run_task=self._EnqueueRunTask)






    self._add_event = None
    self._auto_task_running = auto_task_running
    self._task_retry_seconds = task_retry_seconds

  def _ParseQueueYaml(self):
    """Loads the queue.yaml file and parses it.

    Returns:
      None if queue.yaml doesn't exist, otherwise a queueinfo.QueueEntry object
      populated from the queue.yaml.
    """
    if hasattr(self, 'queue_yaml_parser'):

      return self.queue_yaml_parser(self._root_path)



    if self._root_path is None:
      return None
    for queueyaml in ('queue.yaml', 'queue.yml'):
      try:
        fh = open(os.path.join(self._root_path, queueyaml), 'r')
      except IOError:
        continue
      try:
        queue_info = queueinfo.LoadSingleQueue(fh)
        return queue_info
      finally:
        fh.close()
    return None

  def _EnqueueRunTask(self, callback_time, queue_name, task_name):
    """Enqueue a task to be automatically scheduled.

    Note: If auto task running is disabled, this function is a no-op.

    Args:
      callback_time: The earliest time this task may be run, in seconds since
        the epoch.
      queue_name: The name of the queue.
      task_name: The name of the task to run.
    """
    def _Callback():
      return self._RunTask(queue_name, task_name)


    if self._add_event and self._auto_task_running:
      self._add_event(callback_time, _Callback)

  def _GetGroup(self, app_id=None):
    """Get the _Group instance for app_id, creating a new one if needed.

    Args:
      app_id: The app id in question. Note: This field is not validated.
    """
    if app_id not in self._queues:
      self._queues[app_id] = _Group(
          app_id=app_id, _all_queues_valid=self._all_queues_valid)
    return self._queues[app_id]

  def _Dynamic_Add(self, request, response):
    """Add a single task to a queue.

    This method is a wrapper around the BulkAdd RPC request.

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
    """











    assert request.add_request_size(), 'taskqueue should prevent empty requests'
    self._GetGroup(_GetAppId(request.add_request(0))).BulkAdd_Rpc(
        request, response)

  def _RunTask(self, queue_name, task_name):
    """Returns a fake request for running a task in the dev_appserver.

    Args:
      queue_name: The queue the task is in.
      task_name: The name of the task to run.

    Returns:
      None if this task no longer exists or tuple (connection, addrinfo) of
      a fake connection and address information used to run this task. The
      task will be deleted after it runs or re-enqueued in the future on
      failure.
    """
    if not self._GetGroup().HasQueue(queue_name):
      return None

    task = self._GetGroup().GetQueue(queue_name).GetTaskAsDict(task_name)
    if not task:
      return None

    class FakeConnection(object):
      def __init__(self, input_buffer):
        self.rfile = StringIO.StringIO(input_buffer)
        self.wfile = StringIO.StringIO()
        self.wfile_close = self.wfile.close
        self.wfile.close = self.connection_done

      def connection_done(myself):
        result = myself.wfile.getvalue()
        myself.wfile_close()


        first_line, rest = (result.split('\n', 1) + ['', ''])[:2]
        version, code, rest = (first_line.split(' ', 2) + ['', '500', ''])[:3]


        try:
          code = int(code)
        except ValueError:
          code = 500

        if 200 <= int(code) <= 299:
          self.DeleteTask(queue_name, task_name)
          return

        logging.warning('Task named "%s" on queue "%s" failed with code %s; '
                        'will retry in %d seconds',
                        task_name, queue_name, code, self._task_retry_seconds)
        self._EnqueueRunTask(time.time() + self._task_retry_seconds,
                             queue_name,
                             task_name)

      def close(self):
        pass

      def makefile(self, mode, buffsize):
        if mode.startswith('w'):
          return self.wfile
        else:
          return self.rfile

    payload = StringIO.StringIO()
    payload.write('%s %s HTTP/1.1\r\n' % (task['method'], task['url']))
    for key, value in task['headers']:
      payload.write('%s: %s\r\n' % (key, value))
    payload.write('\r\n')
    payload.write(task['body'])

    return FakeConnection(payload.getvalue()), ('0.1.0.2', 80)

  def GetQueues(self):
    """Gets all the application's queues.

    Returns:
      A list of dictionaries, where each dictionary contains one queue's
      attributes. E.g.:
        [{'name': 'some-queue',
          'max_rate': '1/s',
          'bucket_size': 5,
          'oldest_task': '2009/02/02 05:37:42',
          'eta_delta': '0:00:06.342511 ago',
          'tasks_in_queue': 12}, ...]
      The list of queues always includes the default queue.
    """
    return self._GetGroup().GetQueuesAsDicts()

  def GetTasks(self, queue_name):
    """Gets a queue's tasks.

    Args:
      queue_name: Queue's name to return tasks for.

    Returns:
      A list of dictionaries, where each dictionary contains one task's
      attributes. E.g.
        [{'name': 'task-123',
          'queue_name': 'default',
          'url': '/update',
          'method': 'GET',
          'eta': '2009/02/02 05:37:42',
          'eta_delta': '0:00:06.342511 ago',
          'body': '',
          'headers': [('user-header', 'some-value')
                      ('X-AppEngine-QueueName': 'update-queue'),
                      ('X-AppEngine-TaskName': 'task-123'),
                      ('X-AppEngine-TaskRetryCount': '0'),
                      ('X-AppEngine-Development-Payload': '1'),
                      ('Content-Length': 0),
                      ('Content-Type': 'application/octet-stream')]

    Raises:
      ValueError: A task request contains an unknown HTTP method type.
      KeyError: An invalid queue name was specified.
    """
    return self._GetGroup().GetQueue(queue_name).GetTasksAsDicts()

  def DeleteTask(self, queue_name, task_name):
    """Deletes a task from a queue.

    Args:
      queue_name: the name of the queue to delete the task from.
      task_name: the name of the task to delete.
    """
    if self._GetGroup().HasQueue(queue_name):
      self._GetGroup().GetQueue(queue_name).Delete(task_name)

  def FlushQueue(self, queue_name):
    """Removes all tasks from a queue.

    Args:
      queue_name: the name of the queue to remove tasks from.
    """
    if self._GetGroup().HasQueue(queue_name):
      self._GetGroup().GetQueue(queue_name).PurgeQueue()

  def _Dynamic_UpdateQueue(self, request, unused_response):
    """Local implementation of the UpdateQueue RPC in TaskQueueService.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateQueueRequest.
      unused_response: A taskqueue_service_pb.TaskQueueUpdateQueueResponse.
                       Not used.
    """
    app_id = _GetAppId(request)
    if app_id is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)
    self._GetGroup(app_id).UpdateQueue_Rpc(request, unused_response)

  def _Dynamic_FetchQueues(self, request, response):
    """Local implementation of the FetchQueues RPC in TaskQueueService.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueuesRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueuesResponse.
    """
    app_id = _GetAppId(request)
    if app_id is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)
    self._GetGroup(app_id).FetchQueues_Rpc(request, response)

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
    app_id = _GetAppId(request)
    if app_id is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)
    self._GetGroup(app_id).FetchQueueStats_Rpc(request, response)

  def _Dynamic_QueryTasks(self, request, response):
    """Local implementation of the TaskQueueService.QueryTasks RPC.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueQueryTasksRequest.
      response: A taskqueue_service_pb.TaskQueueQueryTasksResponse.
    """
    app_id = _GetAppId(request)
    if app_id is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)
    self._GetGroup(app_id).QueryTasks_Rpc(request, response)

  def _Dynamic_Delete(self, request, response):
    """Local delete implementation of TaskQueueService.Delete.

    Deletes tasks from the task store. A 1/20 chance of a transient error.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteResponse.
    """

    self._GetGroup(_GetAppId(request)).Delete_Rpc(request, response)

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
    if _GetAppId(request) is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)


    if random.random() <= 0.05:
      response.set_result(
          taskqueue_service_pb.TaskQueueServiceError.TRANSIENT_ERROR)
    elif random.random() <= 0.052:
      response.set_result(
          taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR)
    else:
      response.set_result(
          taskqueue_service_pb.TaskQueueServiceError.OK)

  def _Dynamic_DeleteQueue(self, request, response):
    """Local delete implementation of TaskQueueService.DeleteQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteQueueRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteQueueResponse.
    """
    app_id = _GetAppId(request)
    if app_id is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)
    self._GetGroup(app_id).DeleteQueue_Rpc(request, response)

  def _Dynamic_PauseQueue(self, request, response):
    """Local pause implementation of TaskQueueService.PauseQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueuePauseQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePauseQueueResponse.
    """
    app_id = _GetAppId(request)
    if app_id is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)
    self._GetGroup(app_id).PauseQueue_Rpc(request, response)

  def _Dynamic_PurgeQueue(self, request, response):
    """Local purge implementation of TaskQueueService.PurgeQueue.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueuePurgeQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePurgeQueueResponse.
    """

    self._GetGroup(_GetAppId(request)).PurgeQueue_Rpc(request, response)

  def _Dynamic_DeleteGroup(self, request, response):
    """Local delete implementation of TaskQueueService.DeleteGroup.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteGroupRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteGroupResponse.
    """
    app_id = _GetAppId(request)
    if app_id is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)


    del self._queues[app_id]

  def _Dynamic_UpdateStorageLimit(self, request, response):
    """Local implementation of TaskQueueService.UpdateStorageLimit.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateStorageLimitRequest.
      response: A taskqueue_service_pb.TaskQueueUpdateStorageLimitResponse.
    """
    if _GetAppId(request) is None:
      raise apiproxy_errors.ApplicationError(
         taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED)

    if request.limit() < 0 or request.limit() > 1000 * (1024 ** 4):
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.INVALID_REQUEST)

    response.set_new_limit(request.limit())
