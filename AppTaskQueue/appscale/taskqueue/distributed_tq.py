#!/usr/bin/env python

""" A service for handling TaskQueue request from application servers.
It uses RabbitMQ and Celery to handle tasks. """

import base64
import datetime
import hashlib
import json
import os
import socket
import sys
import time
import tq_lib

from appscale.common import (
  appscale_info,
  constants
)
from appscale.common.constants import SCHEMA_CHANGE_TIMEOUT
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.cassandra_env.cassandra_interface import KEYSPACE
from appscale.datastore.cassandra_env.retry_policies import BASIC_RETRIES
from cassandra import OperationTimedOut
from cassandra.cluster import SimpleStatement
from cassandra.policies import FallthroughRetryPolicy
from .constants import (
  InvalidTarget,
  QueueNotFound,
  TaskNotFound,
  TARGET_REGEX,
  TRANSIENT_DS_ERRORS
)
from .queue import (
  InvalidLeaseRequest,
  PostgresPullQueue,
  PullQueue,
  PushQueue,
  TransientError
)
from .task import Task
from .task_name import TaskName
from .tq_lib import TASK_STATES
from .utils import (
  get_celery_queue_name,
  get_queue_function_name,
  logger
)
from .queue_manager import GlobalQueueManager
from .service_manager import GlobalServiceManager

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_distributed
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.api.taskqueue.taskqueue_service_pb import (
  TaskQueueServiceError)
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors

# A policy that does not retry statements.
NO_RETRIES = FallthroughRetryPolicy()


def rebuild_task_indexes(session):
  """ Creates index entries for all pull queue tasks.

  Args:
    session: A cassandra-driver session.
  """
  logger.info('Rebuilding task indexes')
  batch_size = 100
  total_tasks = 0
  app = ''
  queue = ''
  id_ = ''
  while True:
    results = session.execute("""
      SELECT app, queue, id, lease_expires, tag FROM pull_queue_tasks
      WHERE token(app, queue, id) > token(%(app)s, %(queue)s, %(id)s)
      LIMIT {}
    """.format(batch_size), {'app': app, 'queue': queue, 'id': id_})
    results_list = list(results)
    for result in results_list:
      parameters = {'app': result.app, 'queue': result.queue,
                    'eta': result.lease_expires, 'id': result.id,
                    'tag': result.tag or ''}

      insert_eta_index = SimpleStatement("""
        INSERT INTO pull_queue_eta_index (app, queue, eta, id, tag)
        VALUES (%(app)s, %(queue)s, %(eta)s, %(id)s, %(tag)s)
      """, retry_policy=BASIC_RETRIES)
      session.execute(insert_eta_index, parameters)

      insert_tag_index = SimpleStatement("""
        INSERT INTO pull_queue_tags_index (app, queue, tag, eta, id)
        VALUES (%(app)s, %(queue)s, %(tag)s, %(eta)s, %(id)s)
      """, retry_policy=BASIC_RETRIES)
      session.execute(insert_tag_index, parameters)

    total_tasks += len(results_list)
    if len(results_list) < batch_size:
      break

    app = results_list[-1].app
    queue = results_list[-1].queue
    id_ = results_list[-1].id

  logger.info('Created entries for {} tasks'.format(total_tasks))


def create_pull_queue_tables(cluster, session):
  """ Create the required tables for pull queues.

  Args:
    cluster: A cassandra-driver cluster.
    session: A cassandra-driver session.
  """
  logger.info('Trying to create pull_queue_tasks')
  create_table = """
    CREATE TABLE IF NOT EXISTS pull_queue_tasks (
      app text,
      queue text,
      id text,
      payload text,
      enqueued timestamp,
      lease_expires timestamp,
      retry_count int,
      tag text,
      op_id uuid,
      PRIMARY KEY ((app, queue, id))
    )
  """
  statement = SimpleStatement(create_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating pull_queue_tasks. '
      'Waiting {} seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise

  keyspace_metadata = cluster.metadata.keyspaces[KEYSPACE]
  if 'op_id' not in keyspace_metadata.tables['pull_queue_tasks'].columns:
    try:
      session.execute('ALTER TABLE pull_queue_tasks ADD op_id uuid',
                      timeout=SCHEMA_CHANGE_TIMEOUT)
    except OperationTimedOut:
      logger.warning(
        'Encountered a timeout when altering pull_queue_tasks. Waiting {} '
        'seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
      time.sleep(SCHEMA_CHANGE_TIMEOUT)
      raise

  rebuild_indexes = False
  if ('pull_queue_tasks_index' in keyspace_metadata.tables and
      'tag_exists' in keyspace_metadata.tables['pull_queue_tasks_index'].columns):
    rebuild_indexes = True
    logger.info('Dropping outdated pull_queue_tags index')
    session.execute('DROP INDEX IF EXISTS pull_queue_tags',
                    timeout=SCHEMA_CHANGE_TIMEOUT)

    logger.info('Dropping outdated pull_queue_tag_exists index')
    session.execute('DROP INDEX IF EXISTS pull_queue_tag_exists',
                    timeout=SCHEMA_CHANGE_TIMEOUT)

    logger.info('Dropping outdated pull_queue_tasks_index table')
    session.execute('DROP TABLE pull_queue_tasks_index',
                    timeout=SCHEMA_CHANGE_TIMEOUT)

  logger.info('Trying to create pull_queue_eta_index')
  create_index_table = """
    CREATE TABLE IF NOT EXISTS pull_queue_eta_index (
      app text,
      queue text,
      eta timestamp,
      id text,
      tag text,
      PRIMARY KEY ((app, queue, eta, id))
    ) WITH gc_grace_seconds = 120
  """
  statement = SimpleStatement(create_index_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating pull_queue_eta_index.'
      ' Waiting {} seconds for schema to settle.'
        .format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise

  logger.info('Trying to create pull_queue_tags_index')
  create_tags_index_table = """
    CREATE TABLE IF NOT EXISTS pull_queue_tags_index (
      app text,
      queue text,
      tag text,
      eta timestamp,
      id text,
      PRIMARY KEY ((app, queue, tag, eta, id))
    ) WITH gc_grace_seconds = 120
  """
  statement = SimpleStatement(create_tags_index_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating pull_queue_tags_index.'
      ' Waiting {} seconds for schema to settle.'
        .format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise

  if rebuild_indexes:
    rebuild_task_indexes(session)

  logger.info('Trying to create pull_queue_leases')
  create_leases_table = """
    CREATE TABLE IF NOT EXISTS pull_queue_leases (
      app text,
      queue text,
      leased timestamp,
      PRIMARY KEY ((app, queue, leased))
    ) WITH gc_grace_seconds = 120
  """
  statement = SimpleStatement(create_leases_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating pull_queue_leases. '
      'Waiting {} seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise


def setup_env():
  """ Sets required environment variables for GAE datastore library. """
  os.environ['AUTH_DOMAIN'] = "appscale.com"
  os.environ['USER_EMAIL'] = ""
  os.environ['USER_NICKNAME'] = ""
  os.environ['APPLICATION_ID'] = ""

class DistributedTaskQueue():
  """ AppScale taskqueue layer for the TaskQueue API. """

  # The longest a task is allowed to run in days.
  DEFAULT_EXPIRATION = 30

  # The default maximum number to retry a task, where 0 or None is unlimited.
  DEFAULT_MAX_RETRIES = 0

  # The default amount of min/max time we wait before retrying a task
  # in seconds.
  DEFAULT_MIN_BACKOFF = 1
  DEFAULT_MAX_BACKOFF = 3600.0

  # Default number of times we double the backoff value.
  DEFAULT_MAX_DOUBLINGS = 1000

  # Kind used for storing task names.
  TASK_NAME_KIND = "__task_name__"

  def __init__(self, db_access, zk_client):
    """ DistributedTaskQueue Constructor.

    Args:
      db_access: A DatastoreProxy object.
      zk_client: A KazooClient.
    """
    setup_env()

    db_proxy = appscale_info.get_db_proxy()
    connection_str = '{}:{}'.format(db_proxy, str(constants.DB_SERVER_PORT))
    ds_distrib = datastore_distributed.DatastoreDistributed(
      constants.DASHBOARD_APP_ID, connection_str, require_indexes=False)
    apiproxy_stub_map.apiproxy.RegisterStub('datastore_v3', ds_distrib)
    os.environ['APPLICATION_ID'] = constants.DASHBOARD_APP_ID

    self.db_access = db_access
    self.load_balancers = appscale_info.get_load_balancer_ips()
    self.queue_manager = GlobalQueueManager(zk_client, db_access)
    self.service_manager = GlobalServiceManager(zk_client)

  def get_queue(self, app, queue):
    """ Fetches a Queue object.

    Args:
      app: A string containing the application ID.
      queue: A string specifying the name of the queue.
    Returns:
      A Queue object or None.
    """
    try:
      return self.queue_manager[app][queue]
    except KeyError:
      raise QueueNotFound(
        'The queue {} is not defined for {}'.format(queue, app))

  def __parse_json_and_validate_tags(self, json_request, tags):
    """ Parses JSON and validates that it contains the proper tags.

    Args:
      json_request: A JSON string.
      tags: The tags to validate if they are in the JSON string.
    Returns:
      A dictionary dumped from the JSON string.
    """
    try:
      json_response = json.loads(json_request)
    except ValueError:
      json_response = {"error": True,
                       "reason": "Badly formed JSON"}
      return json_response

    for tag in tags:
      if tag  not in json_response:
        json_response = {'error': True,
                         'reason': 'Missing ' + tag + ' tag'}
        break
    return json_response

  def fetch_queue_stats(self, app_id, http_data):
    """ Gets statistics about tasks in queues.

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    epoch = datetime.datetime.utcfromtimestamp(0)
    request = taskqueue_service_pb.TaskQueueFetchQueueStatsRequest(http_data)
    response = taskqueue_service_pb.TaskQueueFetchQueueStatsResponse()

    for queue_name in request.queue_name_list():
      try:
        queue = self.get_queue(app_id, queue_name)
      except QueueNotFound as error:
        return '', TaskQueueServiceError.UNKNOWN_QUEUE, str(error)

      stats_response = response.add_queuestats()

      if isinstance(queue, (PullQueue, PostgresPullQueue)):
        num_tasks = queue.total_tasks()
        oldest_eta = queue.oldest_eta()
      else:
        num_tasks = TaskName.all().\
          filter("state =", tq_lib.TASK_STATES.QUEUED).\
          filter("queue =", queue_name).\
          filter("app_id =", app_id).count()

        # This is not supported for push queues yet.
        oldest_eta = None

      # -1 is used to indicate an absence of a value.
      oldest_eta_usec = (int((oldest_eta - epoch).total_seconds() * 1000000)
                         if oldest_eta else -1)

      stats_response.set_num_tasks(num_tasks)
      stats_response.set_oldest_eta_usec(oldest_eta_usec)

    return response.Encode(), 0, ""

  def purge_queue(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueuePurgeQueueRequest(http_data)
    response = taskqueue_service_pb.TaskQueuePurgeQueueResponse()

    try:
      queue = self.get_queue(app_id, request.queue_name())
    except QueueNotFound as error:
      return '', TaskQueueServiceError.UNKNOWN_QUEUE, str(error)

    queue.purge()
    return (response.Encode(), 0, "")

  def delete(self, app_id, http_data):
    """ Delete a task.

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueDeleteRequest(http_data)
    response = taskqueue_service_pb.TaskQueueDeleteResponse()

    try:
      queue = self.get_queue(app_id, request.queue_name())
    except QueueNotFound as error:
      return '', TaskQueueServiceError.UNKNOWN_QUEUE, str(error)

    for task_name in request.task_name_list():
      queue.delete_task(Task({'id': task_name}))
      response.add_result(TaskQueueServiceError.OK)

    return response.Encode(), 0, ""

  def query_and_own_tasks(self, app_id, http_data):
    """ Lease pull queue tasks.

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueQueryAndOwnTasksRequest(http_data)
    response = taskqueue_service_pb.TaskQueueQueryAndOwnTasksResponse()

    try:
      queue = self.get_queue(app_id, request.queue_name())
    except QueueNotFound as error:
      return '', TaskQueueServiceError.UNKNOWN_QUEUE, str(error)

    tag = None
    if request.has_tag():
      tag = request.tag()

    try:
      tasks = queue.lease_tasks(request.max_tasks(), request.lease_seconds(),
                                group_by_tag=request.group_by_tag(), tag=tag)
    except TransientError as lease_error:
      pb_error = TaskQueueServiceError.TRANSIENT_ERROR
      return response.Encode(), pb_error, str(lease_error)

    for task in tasks:
      task_pb = response.add_task()
      task_pb.MergeFrom(task.encode_lease_pb())

    return response.Encode(), 0, ""

  def add(self, source_info, http_data):
    """ Adds a single task to the task queue.

    Args:
      source_info: A dictionary containing the application, module, and version
       ID that is sending this request.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # Just call bulk add with one task.
    request = taskqueue_service_pb.TaskQueueAddRequest(http_data)
    request.set_app_id(source_info['app_id'])
    response = taskqueue_service_pb.TaskQueueAddResponse()
    bulk_request = taskqueue_service_pb.TaskQueueBulkAddRequest()
    bulk_response = taskqueue_service_pb.TaskQueueBulkAddResponse()
    bulk_request.add_add_request().CopyFrom(request)

    try:
      self.__bulk_add(source_info, bulk_request, bulk_response)
    except TransientError as error:
      return '', TaskQueueServiceError.TRANSIENT_ERROR, str(error)
    except QueueNotFound as error:
      return '', TaskQueueServiceError.UNKNOWN_QUEUE, str(error)

    if bulk_response.taskresult_size() == 1:
      result = bulk_response.taskresult(0).result()
    else:
      return (response.Encode(), TaskQueueServiceError.INTERNAL_ERROR,
              "Task did not receive a task response.")

    if result != TaskQueueServiceError.OK:
      return (response.Encode(), result, "Task did not get an OK status.")
    elif bulk_response.taskresult(0).has_chosen_task_name():
      response.set_chosen_task_name(
             bulk_response.taskresult(0).chosen_task_name())

    return (response.Encode(), 0, "")

  def bulk_add(self, source_info, http_data):
    """ Adds multiple tasks to the task queue.

    Args:
      source_info: A dictionary containing the application, module, and version
       ID that is sending this request.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueBulkAddRequest(http_data)
    response = taskqueue_service_pb.TaskQueueBulkAddResponse()

    try:
      self.__bulk_add(source_info, request, response)
    except QueueNotFound as error:
      return '', TaskQueueServiceError.UNKNOWN_QUEUE, str(error)
    except TransientError as error:
      return '', TaskQueueServiceError.TRANSIENT_ERROR, str(error)

    return (response.Encode(), 0, "")

  def __bulk_add(self, source_info, request, response):
    """ Function for bulk adding tasks.

    Args:
      source_info: A dictionary containing the application, module, and version
       ID that is sending this request.
      request: taskqueue_service_pb.TaskQueueBulkAddRequest.
      response: taskqueue_service_pb.TaskQueueBulkAddResponse.
    Raises:
      apiproxy_error.ApplicationError.
    """
    if request.add_request_size() == 0:
      return

    now = datetime.datetime.utcfromtimestamp(time.time())

    # Assign names if needed and validate tasks.
    error_found = False
    for add_request in request.add_request_list():
      task_result = response.add_taskresult()

      if (add_request.has_mode() and
          add_request.mode() == taskqueue_service_pb.TaskQueueMode.PULL):
        queue = self.get_queue(add_request.app_id(), add_request.queue_name())
        if not isinstance(queue, (PullQueue, PostgresPullQueue)):
          task_result.set_result(TaskQueueServiceError.INVALID_QUEUE_MODE)
          error_found = True
          continue

        encoded_payload = base64.urlsafe_b64encode(add_request.body())
        task_info = {'payloadBase64': encoded_payload,
                     'leaseTimestamp': add_request.eta_usec()}
        if add_request.has_task_name():
          task_info['id'] = add_request.task_name()
        if add_request.has_tag():
          task_info['tag'] = add_request.tag()

        new_task = Task(task_info)
        queue.add_task(new_task)
        task_result.set_result(TaskQueueServiceError.OK)
        task_result.set_chosen_task_name(new_task.id)
        continue

      result = tq_lib.verify_task_queue_add_request(add_request.app_id(),
                                                    add_request, now)
      # Tasks go from SKIPPED to OK once they're run. If there are
      # any failures from other tasks then we pass this request
      # back as skipped.
      if result == TaskQueueServiceError.SKIPPED:
        task_name = None
        if add_request.has_task_name():
          task_name = add_request.task_name()

        namespaced_name = tq_lib.choose_task_name(add_request.app_id(),
                                                  add_request.queue_name(),
                                                  user_chosen=task_name)
        add_request.set_task_name(namespaced_name)
        task_result.set_chosen_task_name(namespaced_name)
      else:
        error_found = True
        task_result.set_result(result)
    if error_found:
      return

    for add_request, task_result in zip(request.add_request_list(),
                                        response.taskresult_list()):
      if (add_request.has_mode() and
          add_request.mode() == taskqueue_service_pb.TaskQueueMode.PULL):
        continue

      try:
        self.__enqueue_push_task(source_info, add_request)
      except apiproxy_errors.ApplicationError as error:
        task_result.set_result(error.application_error)
      except InvalidTarget as e:
        logger.error(e.message)
        task_result.set_result(TaskQueueServiceError.INVALID_REQUEST)
      else:
        task_result.set_result(TaskQueueServiceError.OK)

  def __method_mapping(self, method):
    """ Maps an int index to a string.

    Args:
      method: int representing a http method.
    Returns:
      A string version of the method.
   """
    if method == taskqueue_service_pb.TaskQueueQueryTasksResponse_Task.GET:
      return 'GET'
    elif method == taskqueue_service_pb.TaskQueueQueryTasksResponse_Task.POST:
      return  'POST'
    elif method == taskqueue_service_pb.TaskQueueQueryTasksResponse_Task.HEAD:
      return  'HEAD'
    elif method == taskqueue_service_pb.TaskQueueQueryTasksResponse_Task.PUT:
      return 'PUT'
    elif method == taskqueue_service_pb.TaskQueueQueryTasksResponse_Task.DELETE:
      return 'DELETE'

  def __get_task_name(self, task_name, retries=3):
    """ Checks if a given TaskName entity exists.

    Args:
      task_name: A string specifying the TaskName key.
      retries: An integer specifying how many times to retry the get.
    """
    try:
      return TaskName.get_by_key_name(task_name)
    except TRANSIENT_DS_ERRORS as error:
      retries -= 1
      if retries >= 0:
        logger.warning('Error while checking task name: {}. '
                       'Retrying'.format(error))
        return self.__get_task_name(task_name, retries)

      raise

  def __create_task_name(self, project_id, queue_name, task_name, retries=3):
    """ Creates a new TaskName entity.

    Args:
      project_id: A string specifying a project ID.
      queue_name: A string specifying a queue name.
      task_name: A string specifying the TaskName key.
      retries: An integer specifying how many times to retry the create.
    """
    entity = TaskName(key_name=task_name, state=tq_lib.TASK_STATES.QUEUED,
                      queue=queue_name, app_id=project_id)
    try:
      db.put(entity)
      return
    except TRANSIENT_DS_ERRORS as error:
      retries -= 1
      if retries >= 0:
        logger.warning('Error creating task name: {}. Retrying'.format(error))
        return self.__create_task_name(project_id, queue_name, task_name,
                                       retries)

      raise

  def __check_and_store_task_names(self, request):
    """ Tries to fetch the taskqueue name, if it exists it will raise an
    exception.

    We store a receipt of each enqueued task in the datastore. If we find that
    task in the datastore, we will raise an exception. If the task is not
    in the datastore, then it is assumed this is the first time seeing the
    tasks and we create a receipt of the task in the datastore to prevent
    a duplicate task from being enqueued.

    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    Raises:
      A apiproxy_errors.ApplicationError of TASK_ALREADY_EXISTS.
    """
    task_name = request.task_name()

    try:
      item = self.__get_task_name(task_name)
    except TRANSIENT_DS_ERRORS:
      logger.exception('Unable to check task name')
      raise apiproxy_errors.ApplicationError(
        taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR)

    logger.debug("Task name {0}".format(task_name))
    if item:
      if item.state == TASK_STATES.QUEUED:
        logger.warning("Task already exists")
        raise apiproxy_errors.ApplicationError(
          TaskQueueServiceError.TASK_ALREADY_EXISTS)
      else:
        # If a task with the same name has already been processed, it should
        # be tombstoned for some time to prevent a duplicate task.
        raise apiproxy_errors.ApplicationError(
          TaskQueueServiceError.TOMBSTONED_TASK)

    logger.debug('Creating task name {}'.format(task_name))
    try:
      self.__create_task_name(request.app_id(), request.queue_name(),
                              task_name)
    except TRANSIENT_DS_ERRORS:
      logger.exception('Unable to create task name')
      raise apiproxy_errors.ApplicationError(
        TaskQueueServiceError.INTERNAL_ERROR)

  def __enqueue_push_task(self, source_info, request):
    """ Enqueues a batch of push tasks.

    Args:
      source_info: A dictionary containing the application, module, and version
       ID that is sending this request.
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    """
    self.__validate_push_task(request)
    self.__check_and_store_task_names(request)
    headers = self.get_task_headers(request)
    args = self.get_task_args(source_info, headers, request)
    countdown = int(headers['X-AppEngine-TaskETA']) - \
                int(datetime.datetime.now().strftime("%s"))

    push_queue = self.get_queue(request.app_id(), request.queue_name())
    task_func = get_queue_function_name(push_queue.name)
    celery_queue = get_celery_queue_name(request.app_id(), push_queue.name)

    push_queue.celery.send_task(
      task_func,
      kwargs={'headers': headers, 'args': args},
      expires=args['expires'],
      acks_late=True,
      countdown=countdown,
      queue=celery_queue,
      routing_key=celery_queue,
    )

  def get_task_args(self, source_info, headers, request):
    """ Gets the task args used when making a task web request.

    Args:
      source_info: A dictionary containing the application, module, and version
       ID that is sending this request.
      headers: The request headers, used to determine target.
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    Returns:
      A dictionary used by a task worker.
    """
    args = {}
    args['task_name'] = request.task_name()
    args['app_id'] = request.app_id()
    args['queue_name'] = request.queue_name()
    args['method'] = self.__method_mapping(request.method())
    args['body'] = request.body()
    args['payload'] = request.payload()
    args['description'] = request.description()

    # Set defaults.
    args['max_retries'] = self.DEFAULT_MAX_RETRIES
    args['expires'] = self.__when_to_expire(request)
    args['max_retries'] = self.DEFAULT_MAX_RETRIES
    args['max_backoff_sec'] = self.DEFAULT_MAX_BACKOFF
    args['min_backoff_sec'] = self.DEFAULT_MIN_BACKOFF
    args['max_doublings'] = self.DEFAULT_MAX_DOUBLINGS

    # Load queue info into cache.
    app_id = self.__cleanse(request.app_id())
    queue_name = request.queue_name()

    # Use queue defaults.
    queue = self.get_queue(app_id, queue_name)
    if queue is not None:
      if not isinstance(queue, PushQueue):
        raise Exception('Only push queues are implemented')

      args['max_retries'] = queue.task_retry_limit
      args['min_backoff_sec'] = queue.min_backoff_seconds
      args['max_backoff_sec'] = queue.max_backoff_seconds
      args['max_doublings'] = queue.max_doublings

    # Override defaults.
    if request.has_retry_parameters():
      retry_params = request.retry_parameters()
      if retry_params.has_retry_limit():
        args['max_retries'] = retry_params.retry_limit()
      if retry_params.has_min_backoff_sec():
        args['min_backoff_sec'] = request.\
                                  retry_parameters().min_backoff_sec()
      if retry_params.has_max_backoff_sec():
        args['max_backoff_sec'] = request.\
                                  retry_parameters().max_backoff_sec()
      if retry_params.has_max_doublings():
        args['max_doublings'] = request.\
                                  retry_parameters().max_doublings()

    target_url = "http://{ip}:{port}".format(
      ip=self.load_balancers[0],
      port=self.get_module_port(app_id, source_info, target_info=[]))

    try:
      host = headers['Host']
    except KeyError:
      host = None
    else:
      host =  host if TARGET_REGEX.match(host) else None

    # Try to set target based on queue config.
    if queue.target:
      target_url = self.get_target_url(app_id, source_info, queue.target)
    # If we cannot get anything from the queue config, we try the target from
    # the request (python sdk will set the target via the Host header). Java
    # sdk does not include Host header, so we catch the KeyError.
    elif host:
      target_url = self.get_target_url(app_id, source_info, host)


    args['url'] = "{target}{url}".format(target=target_url, url=request.url())
    return args

  def get_target_url(self, app_id, source_info, target):
    """ Gets the url for the target using the queue's target defined in the
    configuration file or the request's host header.

    Args:
      app_id: The application id, used to lookup module port.
      source_info: A dictionary containing the source version and module ids.
      target: A string containing the value of queue.target or the host header.
    Returns:
       A url as a string for the given target.
    """
    target_info = target.split('.')
    return "http://{ip}:{port}".format(
      ip=self.load_balancers[0],
      port=self.get_module_port(app_id, source_info, target_info))

  def get_module_port(self, app_id, source_info, target_info):
    """ Gets the port for the desired version and module or uses the current
    running version and module.

    Args:
     app_id: The application id, used to lookup port.
     source_info: A dictionary containing the source version and module ids.
     target_info: A list containing [version, module]
    Returns:
      An int containing the port for the target.
    Raises:
      InvalidTarget if the app_id, module, and version cannot be found in
        self.service_manager which maintains a dict of zookeeper info.
    """
    try:
      target_module = target_info.pop()
    except IndexError:
      target_module = source_info['module_id']
    try:
      target_version = target_info.pop()
    except IndexError:
      target_version = source_info['version_id']
    try:
      port = self.service_manager[app_id][target_module][target_version]
    except KeyError:
      err_msg = "target '{version}.{module}' does not exist".format(
        version=target_version, module=target_module)
      raise InvalidTarget(err_msg)
    return port

  def get_task_headers(self, request):
    """ Gets the task headers used for a task web request.

    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest
    Returns:
      A dictionary of key/values for a web request.
    """
    headers = {}
    for header in request.header_list():
      headers[header.key()] = header.value()

    eta = self.__when_to_run(request)

    # This header is how we authenticate that it's an internal request
    secret = appscale_info.get_secret()
    secret_hash = hashlib.sha1(request.app_id() + '/' + \
                      secret).hexdigest()
    headers['X-AppEngine-Fake-Is-Admin'] = secret_hash
    headers['X-AppEngine-QueueName'] = request.queue_name()
    headers['X-AppEngine-TaskName'] = request.task_name()
    headers['X-AppEngine-TaskRetryCount'] = '0'
    headers['X-AppEngine-TaskExecutionCount'] = '0'
    headers['X-AppEngine-TaskETA'] = str(int(eta.strftime("%s")))
    return headers

  def __when_to_run(self, request):
    """ Returns a datetime object of when a task should execute.

    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    Returns:
      A datetime object for when the nearest time to run the
     task is.
    """
    if request.has_eta_usec():
      eta = request.eta_usec()
      return datetime.datetime.fromtimestamp(eta/1000000)
    else:
      return datetime.datetime.now()

  def __when_to_expire(self, request):
    """ Returns a datetime object of when a task should expire.

    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    Returns:
      A datetime object of when the task should expire.
    """
    if request.has_retry_parameters() and \
           request.retry_parameters().has_age_limit_sec():
      limit = request.retry_parameters().age_limit_sec()
      return datetime.datetime.now() + datetime.timedelta(seconds=limit)
    else:
      return datetime.datetime.now() + \
                   datetime.timedelta(days=self.DEFAULT_EXPIRATION)

  def __validate_push_task(self, request):
    """ Checks to make sure the task request is valid.

    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    Raises:
      apiproxy_errors.ApplicationError upon invalid tasks.
    """
    if not request.has_queue_name():
      raise apiproxy_errors.ApplicationError(
        TaskQueueServiceError.INVALID_QUEUE_NAME)
    if not request.has_task_name():
      raise apiproxy_errors.ApplicationError(
        TaskQueueServiceError.INVALID_TASK_NAME)
    if not request.has_app_id():
      raise apiproxy_errors.ApplicationError(
        TaskQueueServiceError.UNKNOWN_QUEUE)
    if not request.has_url():
      raise apiproxy_errors.ApplicationError(TaskQueueServiceError.INVALID_URL)
    if (request.has_mode() and
        request.mode() == taskqueue_service_pb.TaskQueueMode.PULL):
      raise apiproxy_errors.ApplicationError(
        TaskQueueServiceError.INVALID_QUEUE_MODE)

  def modify_task_lease(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueModifyTaskLeaseRequest(http_data)

    try:
      queue = self.get_queue(app_id, request.queue_name())
    except QueueNotFound as error:
      return '', TaskQueueServiceError.UNKNOWN_QUEUE, str(error)

    task_info = {'id': request.task_name(),
                 'leaseTimestamp': request.eta_usec()}
    try:
      # The Python AppServer sets eta_usec with a resolution of 1 second,
      # so update_lease can't be used. It checks with millisecond precision.
      task = queue.update_task(Task(task_info), request.lease_seconds())
    except InvalidLeaseRequest as lease_error:
      return '', TaskQueueServiceError.TASK_LEASE_EXPIRED, str(lease_error)
    except TaskNotFound as error:
      return '', TaskQueueServiceError.TASK_LEASE_EXPIRED, str(error)

    epoch = datetime.datetime.utcfromtimestamp(0)
    updated_usec = int((task.leaseTimestamp - epoch).total_seconds() * 1000000)
    response = taskqueue_service_pb.TaskQueueModifyTaskLeaseResponse()
    response.set_updated_eta_usec(updated_usec)
    return response.Encode(), 0, ""

  def fetch_queue(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # TODO implement.
    request = taskqueue_service_pb.TaskQueueFetchQueuesRequest(http_data)
    response = taskqueue_service_pb.TaskQueueFetchQueuesResponse()
    return (response.Encode(), 0, "")

  def query_tasks(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # TODO implement.
    request = taskqueue_service_pb.TaskQueueQueryTasksRequest(http_data)
    response = taskqueue_service_pb.TaskQueueQueryTasksResponse()
    return (response.Encode(), 0, "")

  def fetch_task(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # TODO implement.
    request = taskqueue_service_pb.TaskQueueFetchTaskRequest(http_data)
    response = taskqueue_service_pb.TaskQueueFetchTaskResponse()
    return (response.Encode(), 0, "")

  def force_run(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # TODO implement.
    request = taskqueue_service_pb.TaskQueueForceRunRequest(http_data)
    response = taskqueue_service_pb.TaskQueueForceRunResponse()
    return (response.Encode(), 0, "")

  def pause_queue(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # TODO implement.
    request = taskqueue_service_pb.TaskQueuePauseQueueRequest(http_data)
    response = taskqueue_service_pb.TaskQueuePauseQueueResponse()
    return (response.Encode(), 0, "")

  def delete_group(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # TODO implement.
    request = taskqueue_service_pb.TaskQueueDeleteGroupRequest(http_data)
    response = taskqueue_service_pb.TaskQueueDeleteGroupResponse()
    return (response.Encode(), 0, "")

  def update_storage_limit(self, app_id, http_data):
    """

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # TODO implement.
    request = taskqueue_service_pb.TaskQueueUpdateStorageLimitRequest(http_data)
    response = taskqueue_service_pb.TaskQueueUpdateStorageLimitResponse()
    return (response.Encode(), 0, "")

  def __cleanse(self, str_input):
    """ Removes any questionable characters which might be apart of a remote
    attack.

    Args:
      str_input: The string to cleanse.
    Returns:
      A string which has questionable characters replaced.
    """
    for char in "~./\\!@#$%&*()]\+=|":
      str_input = str_input.replace(char, "_")
    return str_input

  def __is_localhost(self, hostname):
    """ Determines if the hostname is that of the current host.

    Args:
      hostname: A string representing the hostname.
    Returns:
      True if its the localhost, false otherwise.
    """
    if socket.gethostname() == hostname:
      return True
    elif socket.gethostbyname(socket.gethostname()) == hostname:
      return True
    else:
      return False
