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
import bisect
import datetime
import logging
import os
import random
import string
import time


from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import queueinfo
from google.appengine.api.labs.taskqueue import taskqueue_service_pb
from google.appengine.runtime import apiproxy_errors




DEFAULT_RATE = '5.00/s'





DEFAULT_BUCKET_SIZE = 5


MAX_ETA_DELTA_DAYS = 30


admin_console_dummy_tasks = {}



BUILT_IN_HEADERS = set(['x-appengine-queuename',
                        'x-appengine-taskname',
                        'x-appengine-taskretrycount',
                        'x-appengine-development-payload',
                        'content-length'])



DEFAULT_QUEUE_NAME = 'default'


CRON_QUEUE_NAME = '__cron'


class _DummyTaskStore(object):
  """A class that encapsulates a sorted store of tasks.

  Used for testing the admin console.
  """

  def __init__(self):
    """Constructor."""

    self._sorted_by_name = []

    self._sorted_by_eta = []

  def _InsertTask(self, task):
    """Insert a task into the dummy store, keeps lists sorted.

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

  def Add(self, request):
    """Inserts a new task into the store.

    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.

    Raises:
      apiproxy_errors.ApplicationError: If a task with the same name is already
      in the store.
    """

    pos = bisect.bisect_left(self._sorted_by_name, (request.task_name(),))
    if (pos < len(self._sorted_by_name) and
        self._sorted_by_name[pos][0] == request.task_name()):
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.TASK_ALREADY_EXISTS)

    now = datetime.datetime.utcnow()
    now_sec = time.mktime(now.timetuple())
    task = taskqueue_service_pb.TaskQueueQueryTasksResponse_Task()
    task.set_task_name(request.task_name())
    task.set_eta_usec(request.eta_usec())
    task.set_creation_time_usec(now_sec * 1e6)
    task.set_url(request.url())
    task.set_method(request.method())
    for keyvalue in task.header_list():
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
    now_sec = time.mktime(now.timetuple())

    def RandomTask():
      """Creates a new task and randomly populates values."""
      task = taskqueue_service_pb.TaskQueueQueryTasksResponse_Task()
      task.set_task_name(''.join(random.choice(string.ascii_lowercase)
                                 for x in range(20)))

      task.set_eta_usec(int(now_sec * 1e6) + random.randint(-10e6, 600e6))



      task.set_creation_time_usec(min(now_sec * 1e6, task.eta_usec()) -
                                  random.randint(0, 2e7))

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


def _ParseQueueYaml(unused_self, root_path):
  """Loads the queue.yaml file and parses it.

  Args:
    unused_self: Allows this function to be bound to a class member. Not used.
    root_path: Directory containing queue.yaml. Not used.

  Returns:
    None if queue.yaml doesn't exist, otherwise a queueinfo.QueueEntry object
    populated from the queue.yaml.
  """
  if root_path is None:
    return None
  for queueyaml in ('queue.yaml', 'queue.yml'):
    try:
      fh = open(os.path.join(root_path, queueyaml), 'r')
    except IOError:
      continue
    try:
      queue_info = queueinfo.LoadSingleQueue(fh)
      return queue_info
    finally:
      fh.close()
  return None


def _CompareTasksByEta(a, b):
  """Python sort comparator for tasks by estimated time of arrival (ETA).

  Args:
    a: A taskqueue_service_pb.TaskQueueAddRequest.
    b: A taskqueue_service_pb.TaskQueueAddRequest.

  Returns:
    Standard 1/0/-1 comparison result.
  """
  if a.eta_usec() > b.eta_usec():
    return 1
  if a.eta_usec() < b.eta_usec():
    return -1
  return 0



def _FormatEta(eta_usec):
  """Formats a task ETA as a date string in UTC."""
  eta = datetime.datetime.fromtimestamp(eta_usec/1000000)
  return eta.strftime('%Y/%m/%d %H:%M:%S')


def _EtaDelta(eta_usec):
  """Formats a task ETA as a relative time string."""
  eta = datetime.datetime.fromtimestamp(eta_usec/1000000)
  now = datetime.datetime.utcnow()
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


  queue_yaml_parser = _ParseQueueYaml

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

    self._taskqueues = {}
    self._next_task_id = 1
    self._root_path = root_path



    self._all_queues_valid = _all_queues_valid






    self._add_event = None
    self._auto_task_running = auto_task_running
    self._task_retry_seconds = task_retry_seconds







    self._app_queues = {}

  class _QueueDetails(taskqueue_service_pb.TaskQueueUpdateQueueRequest):
    def __init__(self, paused=False):
      self.paused = paused

  def _ChooseTaskName(self):
    """Returns a string containing a unique task name."""
    self._next_task_id += 1
    return 'task%d' % (self._next_task_id - 1)

  def _VerifyTaskQueueAddRequest(self, request):
    """Checks that a TaskQueueAddRequest is valid.

    Checks that a TaskQueueAddRequest specifies a valid eta and a valid queue.

    Args:
      request: The taskqueue_service_pb.TaskQueueAddRequest to validate.

    Returns:
      A taskqueue_service_pb.TaskQueueServiceError indicating any problems with
      the request or taskqueue_service_pb.TaskQueueServiceError.OK if it is
      valid.
    """
    if request.eta_usec() < 0:
      return taskqueue_service_pb.TaskQueueServiceError.INVALID_ETA

    eta = datetime.datetime.utcfromtimestamp(request.eta_usec() / 1e6)
    max_eta = (datetime.datetime.utcnow() +
               datetime.timedelta(days=MAX_ETA_DELTA_DAYS))
    if eta > max_eta:
      return taskqueue_service_pb.TaskQueueServiceError.INVALID_ETA

    return taskqueue_service_pb.TaskQueueServiceError.OK

  def _Dynamic_Add(self, request, response):
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

    Args:
      request: The taskqueue_service_pb.TaskQueueBulkAddRequest. See
          taskqueue_service.proto.
      response: The taskqueue_service_pb.TaskQueueBulkAddResponse. See
          taskqueue_service.proto.
    """










    assert request.add_request_size(), 'taskqueue should prevent empty requests'
    app_id = None
    if request.add_request(0).has_app_id():
      app_id = request.add_request(0).app_id()

    if not self._IsValidQueue(request.add_request(0).queue_name(), app_id):
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)

    error_found = False
    task_results_with_chosen_names = []


    for add_request in request.add_request_list():
      task_result = response.add_taskresult()
      error = self._VerifyTaskQueueAddRequest(add_request)
      if error == taskqueue_service_pb.TaskQueueServiceError.OK:
        if not add_request.task_name():
          chosen_name = self._ChooseTaskName()
          add_request.set_task_name(chosen_name)
          task_results_with_chosen_names.append(task_result)



        task_result.set_result(
            taskqueue_service_pb.TaskQueueServiceError.SKIPPED)
      else:
        error_found = True
        task_result.set_result(error)

    if error_found:
      return


    if request.add_request(0).has_transaction():
      self._TransactionalBulkAdd(request)
    elif request.add_request(0).has_app_id():


      self._DummyTaskStoreBulkAdd(request, response)
    else:
      self._NonTransactionalBulkAdd(request, response)


    for add_request, task_result in zip(request.add_request_list(),
                                        response.taskresult_list()):
      if (task_result.result() ==
          taskqueue_service_pb.TaskQueueServiceError.SKIPPED):
        task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.OK)
        if task_result in task_results_with_chosen_names:
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

  def _DummyTaskStoreBulkAdd(self, request, response):
    """Adds tasks to the appropriate DummyTaskStore.

    Args:
      request: The taskqueue_service_pb.TaskQueueBulkAddRequest containing the
        tasks to add. N.B. all tasks in the request have been validated and
        those with empty names have been assigned unique names.
      response: The taskqueue_service_pb.TaskQueueBulkAddResponse to populate
        with the results. N.B. the chosen_task_name field in the response will
        not be filled-in.
    """
    store = self.GetDummyTaskStore(request.add_request(0).app_id(),
                                   request.add_request(0).queue_name())
    for add_request, task_result in zip(request.add_request_list(),
                                        response.taskresult_list()):
      try:
        store.Add(add_request)
      except apiproxy_errors.ApplicationError, e:
        task_result.set_result(e.application_error)
      else:
        task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.OK)

  def _NonTransactionalBulkAdd(self, request, response):
    """Adds tasks to the appropriate list in in self._taskqueues.

    Args:
      request: The taskqueue_service_pb.TaskQueueBulkAddRequest containing the
        tasks to add. N.B. all tasks in the request have been validated and
        those with empty names have been assigned unique names.
      response: The taskqueue_service_pb.TaskQueueBulkAddResponse to populate
        with the results. N.B. the chosen_task_name field in the response will
        not be filled-in.
    """
    existing_tasks = self._taskqueues.setdefault(
        request.add_request(0).queue_name(), [])
    existing_task_names = set(task.task_name() for task in existing_tasks)


    def DefineCallback(queue_name, task_name):
      return lambda: self._RunTask(queue_name, task_name)

    for add_request, task_result in zip(request.add_request_list(),
                                        response.taskresult_list()):
      if add_request.task_name() in existing_task_names:
        task_result.set_result(
            taskqueue_service_pb.TaskQueueServiceError.TASK_ALREADY_EXISTS)
      else:
        existing_tasks.append(add_request)


      if self._add_event and self._auto_task_running:
        self._add_event(
            add_request.eta_usec() / 1000000.0,
            DefineCallback(add_request.queue_name(), add_request.task_name()))

    existing_tasks.sort(_CompareTasksByEta)

  def _IsValidQueue(self, queue_name, app_id):
    """Determines whether a queue is valid, i.e. tasks can be added to it.

    Valid queues are the 'default' queue, plus any queues in the queue.yaml
    file.

    Args:
      queue_name: the name of the queue to validate.
      app_id: the app_id. Can be None.

    Returns:
      True iff queue is valid.
    """
    if self._all_queues_valid:
      return True
    if queue_name == DEFAULT_QUEUE_NAME or queue_name == CRON_QUEUE_NAME:
      return True
    queue_info = self.queue_yaml_parser(self._root_path)
    if queue_info and queue_info.queue:
      for entry in queue_info.queue:
        if entry.name == queue_name:
          return True

    if app_id is not None:
      queues = self._app_queues.get(app_id, {})
      return queues.get(queue_name, None) is not None
    return False

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
    task_list = self.GetTasks(queue_name)
    for task in task_list:
      if task['name'] == task_name:
        break
    else:
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
        self._add_event(
            time.time() + self._task_retry_seconds,
            lambda: self._RunTask(queue_name, task_name))

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
    queues = []
    queue_info = self.queue_yaml_parser(self._root_path)
    has_default = False
    if queue_info and queue_info.queue:
      for entry in queue_info.queue:
        if entry.name == DEFAULT_QUEUE_NAME:
          has_default = True
        queue = {}
        queues.append(queue)
        queue['name'] = entry.name
        queue['max_rate'] = entry.rate
        if entry.bucket_size:
          queue['bucket_size'] = entry.bucket_size
        else:
          queue['bucket_size'] = DEFAULT_BUCKET_SIZE

        tasks = self._taskqueues.setdefault(entry.name, [])
        if tasks:
          queue['oldest_task'] = _FormatEta(tasks[0].eta_usec())
          queue['eta_delta'] = _EtaDelta(tasks[0].eta_usec())
        else:
          queue['oldest_task'] = ''
        queue['tasks_in_queue'] = len(tasks)


    if not has_default:
      queue = {}
      queues.append(queue)
      queue['name'] = DEFAULT_QUEUE_NAME
      queue['max_rate'] = DEFAULT_RATE
      queue['bucket_size'] = DEFAULT_BUCKET_SIZE

      tasks = self._taskqueues.get(DEFAULT_QUEUE_NAME, [])
      if tasks:
        queue['oldest_task'] = _FormatEta(tasks[0].eta_usec())
        queue['eta_delta'] = _EtaDelta(tasks[0].eta_usec())
      else:
        queue['oldest_task'] = ''
      queue['tasks_in_queue'] = len(tasks)
    return queues

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
    """
    tasks = self._taskqueues.get(queue_name, [])
    result_tasks = []
    for task_request in tasks:
      task = {}
      result_tasks.append(task)
      task['name'] = task_request.task_name()
      task['queue_name'] = queue_name
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
      task['eta_delta'] = _EtaDelta(task_request.eta_usec())
      task['body'] = base64.b64encode(task_request.body())



      headers = [(header.key(), header.value())
                 for header in task_request.header_list()
                 if header.key().lower() not in BUILT_IN_HEADERS]


      headers.append(('X-AppEngine-QueueName', queue_name))
      headers.append(('X-AppEngine-TaskName', task['name']))
      headers.append(('X-AppEngine-TaskRetryCount', '0'))
      headers.append(('X-AppEngine-Development-Payload', '1'))
      headers.append(('Content-Length', len(task['body'])))
      if 'content-type' not in frozenset(key.lower() for key, _ in headers):
        headers.append(('Content-Type', 'application/octet-stream'))
      task['headers'] = headers

    return result_tasks

  def DeleteTask(self, queue_name, task_name):
    """Deletes a task from a queue.

    Args:
      queue_name: the name of the queue to delete the task from.
      task_name: the name of the task to delete.
    """
    tasks = self._taskqueues.get(queue_name, [])
    for task in tasks:
      if task.task_name() == task_name:
        tasks.remove(task)
        return

  def FlushQueue(self, queue_name):
    """Removes all tasks from a queue.

    Args:
      queue_name: the name of the queue to remove tasks from.
    """
    self._taskqueues[queue_name] = []

  def _Dynamic_UpdateQueue(self, request, unused_response):
    """Local implementation of the UpdateQueue RPC in TaskQueueService.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateQueueRequest.
      unused_response: A taskqueue_service_pb.TaskQueueUpdateQueueResponse.
                       Not used.
    """
    queues = self._app_queues.setdefault(request.app_id(), {})
    if request.queue_name() in queues and queues[request.queue_name()] is None:
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.TOMBSTONED_QUEUE)

    defensive_copy = self._QueueDetails()
    defensive_copy.CopyFrom(request)

    queues[request.queue_name()] = defensive_copy

  def _Dynamic_FetchQueues(self, request, response):
    """Local implementation of the FetchQueues RPC in TaskQueueService.

    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueuesRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueuesResponse.
    """
    queues = self._app_queues.get(request.app_id(), {})
    for unused_key, queue in sorted(queues.items()):
      if request.max_rows() == response.queue_size():
        break

      if queue is None:
        continue

      response_queue = response.add_queue()
      response_queue.set_queue_name(queue.queue_name())
      response_queue.set_bucket_refill_per_second(
          queue.bucket_refill_per_second())
      response_queue.set_bucket_capacity(queue.bucket_capacity())
      response_queue.set_user_specified_rate(queue.user_specified_rate())
      if queue.has_max_concurrent_requests():
        response_queue.set_max_concurrent_requests(
            queue.max_concurrent_requests())
      response_queue.set_paused(queue.paused)

  def _Dynamic_FetchQueueStats(self, request, response):
    """Local 'random' implementation of the TaskQueueService.FetchQueueStats.

    This implementation loads some stats from the dummy store,
    the rest with random numbers.
    Must adhere to the '_Dynamic_' naming convention for stubbing to work.
    See taskqueue_service.proto for a full description of the RPC.

    Args:
      request: A taskqueue_service_pb.TaskQueueFetchQueueStatsRequest.
      response: A taskqueue_service_pb.TaskQueueFetchQueueStatsResponse.
    """
    for queue in request.queue_name_list():
      store = self.GetDummyTaskStore(request.app_id(), queue)
      stats = response.add_queuestats()
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

  def GetDummyTaskStore(self, app_id, queue_name):
    """Get the dummy task store for this app_id/queue_name pair.

    Creates an entry and populates it, if there's not already an entry.

    Args:
      app_id: the app_id.
      queue_name: the queue_name.

    Returns:
      the existing or the new dummy store.
    """
    task_store_key = (app_id, queue_name)
    if task_store_key not in admin_console_dummy_tasks:
      store = _DummyTaskStore()
      if not self._all_queues_valid and queue_name != CRON_QUEUE_NAME:
        store.Populate(random.randint(10, 100))
      admin_console_dummy_tasks[task_store_key] = store
    else:
      store = admin_console_dummy_tasks[task_store_key]
    return store

  def _Dynamic_QueryTasks(self, request, response):
    """Local implementation of the TaskQueueService.QueryTasks RPC.

    Uses the dummy store, creating tasks if this is the first time the
    queue has been seen.

    Args:
      request: A taskqueue_service_pb.TaskQueueQueryTasksRequest.
      response: A taskqueue_service_pb.TaskQueueQueryTasksResponse.
    """
    store = self.GetDummyTaskStore(request.app_id(), request.queue_name())

    if request.has_start_eta_usec():
      tasks = store.Lookup(request.max_rows(), name=request.start_task_name(),
                           eta=request.start_eta_usec())
    else:
      tasks = store.Lookup(request.max_rows(), name=request.start_task_name())
    for task in tasks:
      response.add_task().MergeFrom(task)

  def _Dynamic_Delete(self, request, response):
    """Local delete implementation of TaskQueueService.Delete.

    Deletes tasks from the dummy store. A 1/20 chance of a transient error.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteResponse.
    """
    task_store_key = (request.app_id(), request.queue_name())
    if task_store_key not in admin_console_dummy_tasks:
      for _ in request.task_name_list():
        response.add_result(
            taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
        return

    store = admin_console_dummy_tasks[task_store_key]
    for taskname in request.task_name_list():
      if random.random() <= 0.05:
        response.add_result(
            taskqueue_service_pb.TaskQueueServiceError.TRANSIENT_ERROR)
      else:
        response.add_result(store.Delete(taskname))

  def _Dynamic_ForceRun(self, request, response):
    """Local force run implementation of TaskQueueService.ForceRun.

    Forces running of a task in a queue. This is a no-op here.
    This will fail randomly for testing.

    Args:
      request: A taskqueue_service_pb.TaskQueueForceRunRequest.
      response: A taskqueue_service_pb.TaskQueueForceRunResponse.
    """
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

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteQueueRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteQueueResponse.
    """
    if not request.queue_name():
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_NAME)

    queues = self._app_queues.get(request.app_id(), {})
    if request.queue_name() not in queues:
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
    elif queues[request.queue_name()] is None:
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.TOMBSTONED_QUEUE)

    queues[request.queue_name()] = None

  def _Dynamic_PauseQueue(self, request, response):
    """Local pause implementation of TaskQueueService.PauseQueue.

    Args:
      request: A taskqueue_service_pb.TaskQueuePauseQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePauseQueueResponse.
    """
    if not request.queue_name():
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_NAME)

    queues = self._app_queues.get(request.app_id(), {})
    if request.queue_name() != DEFAULT_QUEUE_NAME:
      if request.queue_name() not in queues:
        raise apiproxy_errors.ApplicationError(
            taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
      elif queues[request.queue_name()] is None:
        raise apiproxy_errors.ApplicationError(
            taskqueue_service_pb.TaskQueueServiceError.TOMBSTONED_QUEUE)

    queues[request.queue_name()].paused = request.pause()

  def _Dynamic_PurgeQueue(self, request, response):
    """Local purge implementation of TaskQueueService.PurgeQueue.

    Args:
      request: A taskqueue_service_pb.TaskQueuePurgeQueueRequest.
      response: A taskqueue_service_pb.TaskQueuePurgeQueueResponse.
    """
    if not request.queue_name():
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_NAME)

    if request.has_app_id():
      queues = self._app_queues.get(request.app_id(), {})
      if request.queue_name() != DEFAULT_QUEUE_NAME:
        if request.queue_name() not in queues:
          raise apiproxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
        elif queues[request.queue_name()] is None:
          raise apiproxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.TOMBSTONED_QUEUE)

      store = self.GetDummyTaskStore(request.app_id(), request.queue_name())
      for task in store.Lookup(store.Count()):
        store.Delete(task.task_name())
    elif (not self._IsValidQueue(request.queue_name(), None)
          and not request.queue_name() in self._taskqueues):


      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)

    self.FlushQueue(request.queue_name())

  def _Dynamic_DeleteGroup(self, request, response):
    """Local delete implementation of TaskQueueService.DeleteGroup.

    Args:
      request: A taskqueue_service_pb.TaskQueueDeleteGroupRequest.
      response: A taskqueue_service_pb.TaskQueueDeleteGroupResponse.
    """
    queues = self._app_queues.get(request.app_id(), {})


    for queue in queues.iterkeys():
      store = self.GetDummyTaskStore(request.app_id(), queue)
      for task in store.Lookup(store.Count()):
        store.Delete(task.task_name())
      self.FlushQueue(queue)

    self._app_queues[request.app_id()] = {}

  def _Dynamic_UpdateStorageLimit(self, request, response):
    """Local implementation of TaskQueueService.UpdateStorageLimit.
    Args:
      request: A taskqueue_service_pb.TaskQueueUpdateStorageLimitRequest.
      response: A taskqueue_service_pb.TaskQueueUpdateStorageLimitResponse.
    """
    if request.limit() < 0 or request.limit() > 1000 * (1024 ** 4):
      raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.INVALID_REQUEST)

    response.set_new_limit(request.limit())
