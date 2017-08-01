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
from cassandra import (
  InvalidRequest,
  OperationTimedOut
)
from cassandra.cluster import SimpleStatement
from cassandra.policies import FallthroughRetryPolicy
from .constants import InvalidTarget
from .queue import (
  InvalidLeaseRequest,
  PullQueue,
  PushQueue,
  TransientError
)
from .task import Task
from .utils import (
  get_celery_queue_name,
  get_queue_function_name,
  logger
)
from .queue_manager import GlobalQueueManager
from .service_manager import GlobalServiceManager

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_distributed
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.ext import db
from google.appengine.runtime import apiproxy_errors

# A policy that does not retry statements.
NO_RETRIES = FallthroughRetryPolicy()


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

  logger.info('Trying to create pull_queue_tasks_index')
  create_index_table = """
    CREATE TABLE IF NOT EXISTS pull_queue_tasks_index (
      app text,
      queue text,
      eta timestamp,
      id text,
      tag text,
      tag_exists boolean,
      PRIMARY KEY ((app, queue, eta), id)
    ) WITH gc_grace_seconds = 120
  """
  statement = SimpleStatement(create_index_table, retry_policy=NO_RETRIES)
  try:
    session.execute(statement, timeout=SCHEMA_CHANGE_TIMEOUT)
  except OperationTimedOut:
    logger.warning(
      'Encountered an operation timeout while creating pull_queue_tasks_index.'
      ' Waiting {} seconds for schema to settle.'
        .format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise

  logger.info('Trying to create pull_queue_tags index')
  create_index = """
    CREATE INDEX IF NOT EXISTS pull_queue_tags ON pull_queue_tasks_index (tag);
  """
  try:
    session.execute(create_index, timeout=SCHEMA_CHANGE_TIMEOUT)
  except (OperationTimedOut, InvalidRequest):
    logger.warning(
      'Encountered error while creating pull_queue_tags index. Waiting {} '
      'seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise

  # This additional index is needed for groupByTag=true,tag=None queries
  # because Cassandra can only do '=' queries on secondary indices.
  logger.info('Trying to create pull_queue_tag_exists index')
  create_index = """
    CREATE INDEX IF NOT EXISTS pull_queue_tag_exists
    ON pull_queue_tasks_index (tag_exists);
  """
  try:
    session.execute(create_index, timeout=SCHEMA_CHANGE_TIMEOUT)
  except (OperationTimedOut, InvalidRequest):
    logger.warning(
      'Encountered error while creating pull_queue_tag_exists index. '
      'Waiting {} seconds for schema to settle.'.format(SCHEMA_CHANGE_TIMEOUT))
    time.sleep(SCHEMA_CHANGE_TIMEOUT)
    raise

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


class TaskName(db.Model):
  """ A datastore model for tracking task names in order to prevent
  tasks with the same name from being enqueued repeatedly.
  
  Attributes:
    timestamp: The time the task was enqueued.
  """
  STORED_KIND_NAME = "__task_name__"
  timestamp = db.DateTimeProperty(auto_now_add=True)
  queue = db.StringProperty(required=True)
  state = db.StringProperty(required=True)
  endtime = db.DateTimeProperty()
  app_id = db.StringProperty(required=True)

  @classmethod
  def kind(cls):
    """ Kind name override. """
    return cls.STORED_KIND_NAME

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
    self.queue_manager = GlobalQueueManager(zk_client, db_access)
    self.service_manager = GlobalServiceManager(zk_client, db_access)

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
      return None

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
      queue = self.get_queue(app_id, queue_name)
      stats_response = response.add_queuestats()

      if isinstance(queue, PullQueue):
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

    queue = self.get_queue(app_id, request.queue_name())
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

    queue = self.get_queue(app_id, request.queue_name())
    for task_name in request.task_name_list():
      queue.delete_task(Task({'id': task_name}))
      response.add_result(taskqueue_service_pb.TaskQueueServiceError.OK)

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

    queue = self.get_queue(app_id, request.queue_name())
    tag = None
    if request.has_tag():
      tag = request.tag()

    try:
      tasks = queue.lease_tasks(request.max_tasks(), request.lease_seconds(),
                                group_by_tag=request.group_by_tag(), tag=tag)
    except TransientError as lease_error:
      pb_error = taskqueue_service_pb.TaskQueueServiceError.TRANSIENT_ERROR
      return response.Encode(), pb_error, str(lease_error)

    for task in tasks:
      task_pb = response.add_task()
      task_pb.MergeFrom(task.encode_lease_pb())

    return response.Encode(), 0, ""

  def add(self, app_id, http_data):
    """ Adds a single task to the task queue.

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    # Just call bulk add with one task.
    request = taskqueue_service_pb.TaskQueueAddRequest(http_data)
    request.set_app_id(app_id)
    response = taskqueue_service_pb.TaskQueueAddResponse()
    bulk_request = taskqueue_service_pb.TaskQueueBulkAddRequest()
    bulk_response = taskqueue_service_pb.TaskQueueBulkAddResponse()
    bulk_request.add_add_request().CopyFrom(request)

    self.__bulk_add(bulk_request, bulk_response)

    if bulk_response.taskresult_size() == 1:
      result = bulk_response.taskresult(0).result()
    else:
      err_code = taskqueue_service_pb.TaskQueueServiceError.INTERNAL_ERROR 
      return (response.Encode(), err_code, 
              "Task did not receive a task response.")

    if result != taskqueue_service_pb.TaskQueueServiceError.OK:
      return (response.Encode(), result, "Task did not get an OK status.")
    elif bulk_response.taskresult(0).has_chosen_task_name():
      response.set_chosen_task_name(
             bulk_response.taskresult(0).chosen_task_name())

    return (response.Encode(), 0, "")

  def bulk_add(self, app_id, http_data):
    """ Adds multiple tasks to the task queue.

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueBulkAddRequest(http_data)
    response = taskqueue_service_pb.TaskQueueBulkAddResponse()
    self.__bulk_add(request, response)
    return (response.Encode(), 0, "")

  def __bulk_add(self, request, response):
    """ Function for bulk adding tasks.
   
    Args:
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
        if not isinstance(queue, PullQueue):
          task_result.set_result(
            taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_MODE)
          error_found = True

        encoded_payload = base64.urlsafe_b64encode(add_request.body())
        task_info = {'payloadBase64': encoded_payload,
                     'leaseTimestamp': add_request.eta_usec()}
        if add_request.has_task_name():
          task_info['id'] = add_request.task_name()
        if add_request.has_tag():
          task_info['tag'] = add_request.tag()

        new_task = Task(task_info)
        queue.add_task(new_task)
        task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.OK)
        task_result.set_chosen_task_name(new_task.id)
        continue

      result = tq_lib.verify_task_queue_add_request(add_request.app_id(),
                                                    add_request, now)
      # Tasks go from SKIPPED to OK once they're run. If there are
      # any failures from other tasks then we pass this request 
      # back as skipped.
      if result == taskqueue_service_pb.TaskQueueServiceError.SKIPPED:
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
        self.__enqueue_push_task(add_request)
      except apiproxy_errors.ApplicationError as error:
        task_result.set_result(error.application_error)
      except InvalidTarget as e:
        logger.error(e.message)
        task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.INVALID_REQUEST)
      else:
        task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.OK)

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
    item = TaskName.get_by_key_name(task_name)
    logger.debug("Task name {0}".format(task_name))
    if item:
      logger.warning("Task already exists")
      raise apiproxy_errors.ApplicationError(
        taskqueue_service_pb.TaskQueueServiceError.TASK_ALREADY_EXISTS)
    else:
      new_name = TaskName(key_name=task_name, state=tq_lib.TASK_STATES.QUEUED,
        queue=request.queue_name(), app_id=request.app_id())
      logger.debug("Creating entity {0}".format(str(new_name)))
      try:
        db.put(new_name)
      except datastore_errors.InternalError, internal_error:
        logger.error(str(internal_error))
        raise apiproxy_errors.ApplicationError(
          taskqueue_service_pb.TaskQueueServiceError.DATASTORE_ERROR)

  def __enqueue_push_task(self, request):
    """ Enqueues a batch of push tasks.
  
    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    """
    self.__validate_push_task(request)
    self.__check_and_store_task_names(request)
    headers = self.get_task_headers(request)
    args = self.get_task_args(request, headers)
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

  def get_task_args(self, request, headers):
    """ Gets the task args used when making a task web request.
  
    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
      headers: The request headers, used to determine target.
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


    target_instance = appscale_info.get_login_ip()

    # Try to get the target from host (python sdk will set the target via
    # the Host header). Java sdk does not include Host header, so we catch
    # the KeyError.
    try:
      if not hasattr(self, '__version') and not hasattr(self, '__module'):
        self.set_module_version_source(headers['Version'], headers['Module'])
      target_url = self.get_target_from_host(app_id, target_instance,
                                             headers['Host'])
      args['url'] = "{0}{url}".format(target_url, url=request.url())
    except KeyError:
      target_url = None

    # Use queue defaults.
    queue = self.get_queue(app_id, queue_name)
    if queue is not None:
      if not isinstance(queue, PushQueue):
        raise Exception('Only push queues are implemented')

      args['max_retries'] = queue.task_retry_limit
      args['min_backoff_sec'] = queue.min_backoff_seconds
      args['max_backoff_sec'] = queue.max_backoff_seconds
      args['max_doublings'] = queue.max_doublings

      # If we could not get the target from the host, try to get it from the
      # queue config.
      if not target_url and queue.target:
        target_url = self.get_target_from_queue(app_id, target_instance,
                                                queue.target)
        args['url'] = "{0}{url}".format(target_url, url=request.url())
      # If we cannot get anything from the queue config, we use the module
      # and version from the request.
      elif not target_url:
        target_info = [self.__version, self.__module]
        args['url'] = "http://{0}:{1}{2}".format(target_instance,
           self.get_module_port(app_id, target_info), request.url())
      logger.debug("Old url: {0} New url: {1}".format(request.url(),
                                                     args['url']))

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
    return args

  def get_target_from_queue(self, app_id, target_instance, target):
    """ Gets the url for the target using the queue's target defined in the 
    configuration file. If target is None, target will be the current running
    version and module.
    
    Args:
      app_id: The application id, used to lookup module port.
      target_instance: The instance ip to use for the new url.
      target: A string containing the value of queue.target. 
    Returns:
       A url as a string for the given target.
    """
    target_info = target.split('.')
    return "http://{0}:{1}".format(target_instance, self.get_module_port(
      app_id, target_info))

  def get_target_from_host(self, app_id, target_instance, host):
    """ Gets the url for the target using the Host header.
    
    Args:
      app_id: The application id, used to lookup module port.
      target_instance: The instance ip to use for the new url.
      host: A string containing the value of the Task's host from target or 
        the HTTP_HOST (which would contain AppScale's login ip).
        
    Returns:
      A url as a string for the given target or None if target contains the 
        AppScale login ip because the Task did not specify a target. If this 
        method returns None the target will be determined by the queue or use 
        the current running version and module.
    """
    if target_instance in host:
      return None
    target_info = host.split('.')
    return "http://{0}:{1}".format(target_instance, self.get_module_port(
      app_id, target_info))

  def get_module_port(self, app_id, target_info):
    """ Gets the port for the desired version and module or uses the current 
    running version and module.
    
    Args:
     app_id: The application id, used to lookup port.
     target_info: A list containing [version, module]
    Returns:
      An int containing the port for the target.
    Raises:
      InvalidTarget if the app_id, module, and version cannot be found in 
        self.service_manager which maintains a dict of zookeeper info.
    """
    target_instance = appscale_info.get_login_ip()
    try:
      target_module = target_info.pop(-1)
    except IndexError:
      target_module = self.__module
    try:
      target_version = target_info.pop(-1)
    except IndexError:
      target_version = self.__version
    logger.info("app: {0} instance: {1} version: {2} module: {3}".format(
      app_id, target_instance, target_version, target_module))
    try:
      logger.info(self.service_manager)
      port = self.service_manager[app_id][target_module][target_version]
    except KeyError:
      err_msg = "target '{0}.{1}' does not exist".format(target_version,
                                                         target_module)
      raise InvalidTarget(err_msg)
    return port

  def set_module_version_source(self, version, module):
    """ Sets version and module defaults, should be used to set version and 
    module according to the request's running version and module.
    
    Args:
      version: A string containing the version from request.
      module: A string containing the module from request.
    """
    self.__version = version
    self.__module = module

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
              taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_NAME)
    if not request.has_task_name():
      raise apiproxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.INVALID_TASK_NAME)
    if not request.has_app_id():
      raise apiproxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
    if not request.has_url():
      raise apiproxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.INVALID_URL)
    if request.has_mode() and request.mode() == \
              taskqueue_service_pb.TaskQueueMode.PULL:
      raise apiproxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_MODE)
     
  def modify_task_lease(self, app_id, http_data):
    """ 

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueModifyTaskLeaseRequest(http_data)
    response = taskqueue_service_pb.TaskQueueModifyTaskLeaseResponse()

    queue = self.get_queue(app_id, request.queue_name())
    task_info = {'id': request.task_name()}
    try:
      # The Python AppServer sets eta_usec with a resolution of 1 second,
      # so update_lease can't be used. It checks with millisecond precision.
      task = queue.update_task(Task(task_info), request.lease_seconds())
    except InvalidLeaseRequest as lease_error:
      error = taskqueue_service_pb.TaskQueueServiceError.TASK_LEASE_EXPIRED
      # The response requires ETA to be set before encoding.
      response.set_updated_eta_usec(0)
      return response.Encode(), error, str(lease_error)

    epoch = datetime.datetime.utcfromtimestamp(0)
    updated_usec = int((task.leaseTimestamp - epoch).total_seconds() * 1000000)
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
