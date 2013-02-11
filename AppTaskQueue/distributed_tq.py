#!/usr/bin/env python

""" 
A service for handling TaskQueue request from application servers.
It uses RabbitMQ and celery to task handling. 
"""

import datetime
import hashlib
import json
import logging
import os
import socket
import sys
import time
import urllib2
 
import taskqueue_server
import tq_lib

from tq_config import TaskQueueConfig

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import appscale_info
import file_io
import god_app_interface
import god_interface
import remote

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.runtime import apiproxy_errors
#from google.appengine.api import datastore_distributed
#from google.appengine.api import datastore

from google.appengine.api.taskqueue import taskqueue_service_pb

sys.path.append(TaskQueueConfig.CELERY_WORKER_DIR)

class DistributedTaskQueue():
  """ AppScale taskqueue layer for the TaskQueue API. """

  # Valid commands on queues.
  VALID_QUEUE_COMMANDS = ['reload', 'update', 'stop']

  # Run queue operation required tag
  RUN_QUEUE_OP_TAGS = ['app_id', 'command']

  # Required start worker name tags.
  SETUP_WORKERS_TAGS = ['app_id']

  # Required stop worker name tags.
  STOP_WORKERS_TAGS = ['app_id']

  # Autoscale argument for max/min amounds of concurrent for a 
  # celery worker.
  MIN_MAX_CONCURRENCY = "10,1"

  # The location of where celery logs go
  LOG_DIR = "/var/log/appscale/celery_workers/"

  # The hard time limit of a running task in seconds, extra
  # time over the soft limit allows it to catch up to interrupts.
  HARD_TIME_LIMIT = 610

  # The soft time limit of a running task.
  TASK_SOFT_TIME_LIMIT = 600

  # The location where celery tasks place their PID file. Prevents
  # the same worker from being started if it is already running.
  PID_FILE_LOC = "/etc/appscale/"

  # A port number given to God for the watch, but not actually used.
  CELERY_PORT = 9999

  # The longest a task is allowed to run in days.
  DEFAULT_EXPIRATION = 30

  # The default maximum number to retry task, where 0 or None is unlimited.
  DEFAULT_MAX_RETRIES = 0

  # The default amount of minimum/max time we wait before retrying 
  # a task in seconds.
  DEFAULT_MIN_BACKOFF = 1
  DEFAULT_MAX_BACKOFF = 3600.0

  # Default number of times we double the backoff value.
  DEFAULT_MAX_DOUBLINGS = 1000

  def __init__(self):
    """ DistributedTaskQueue Constructor. """
    file_io.set_logging_format()
    file_io.mkdir(self.LOG_DIR)

  def __parse_json_and_validate_tags(self, json_request, tags):
    """ Parses JSON and validates that it contains the 
        proper tags.

    Args: 
      json_request: A JSON string.
      tags: The tags to validate if they are in the json.
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

  def run_queue_operation(self, json_request):
    """ Runs queue operations such as setting up a new app's
        queues, reloading them, or shutting them down.

    Args:
      json_request: A JSON string containing the app_id and 
                    the location of the queue.yaml file.
    Returns:
      A JSON string of the result which depends on the type
      of command which was issued.
    """
    logging.info("Request: %s" % str(json_request))
    request = self.__parse_json_and_validate_tags(json_request,  
                                         self.RUN_QUEUE_OP_TAGS)
    if 'error' in request:
      return json.dumps(request)

    app_id = self.__cleanse(request['app_id'])
    command = self.__cleanse(request['command'])

    config = TaskQueueConfig(TaskQueueConfig.RABBITMQ, app_id)

    if command not in self.VALID_QUEUE_COMMANDS:
      response = {'error': True, 'reason': 'Unknown command %s' % \
                  command}
      return json.dumps(response) 

    # Load the queue info
    config_file = None
    if 'reload' == command:
      #TODO correctly reload the new configurations
      #if 'queue_yaml' not in request:
      #  return json.dumps({'error': True, 'reason': 'Missing queue_yaml tag'})
      # queue_yaml = request['queue_yaml'] 
      #config.load_queues_from_db()
      #config_file = config.create_celery_file(TaskQueueConfig.QUEUE_INFO_FILE) 
      #worker_file = config.create_celery_worker_scripts(
      #                  TaskQueueConfig.QUEUE_INFO_FILE)
      #result = self.copy_config_files(config_file, worker_file) 
      #json_response = self.start_all_workers(app_id, result)
      #return json.dumps(json_response) 
      return json.dumps({'error': True, 'reason': 'Reload not implemented'})
    elif 'update' == command:
      if 'queue_yaml' not in request:
        return json.dumps({'error': True, 'reason': 'Missing queue_yaml tag'})
      queue_yaml = request['queue_yaml'] 
      config.load_queues_from_file(queue_yaml)
      config_file = config.create_celery_file(TaskQueueConfig.QUEUE_INFO_FILE) 
      worker_file = config.create_celery_worker_scripts(
                        TaskQueueConfig.QUEUE_INFO_FILE)
      result = self.copy_config_files(config_file, worker_file) 
      json_response = self.start_all_workers(app_id, result)
      return json.dumps(json_response)
    elif 'stop' == command:
      return json.dumps(self.stop_queue(app_id))

  def stop_queue(self, app_id):
    """ Stops queue workers on all TaskQueue nodes.
  
    Args:
      app_id: The applicaiton ID.
    Returns:
      A dictionary of the status on each node for the shutdown.
    """
    result = {}
    taskqueue_nodes = appscale_info.get_taskqueue_nodes()
    for node in taskqueue_nodes:
      url = 'http://' + node + ':' + \
            str(taskqueue_server.SERVER_PORT) + "/stopworker"
      values = {}
      values['app_id'] = app_id
      payload = json.dumps(values)
      if self.__is_localhost(node):
        result[node] = json.loads(self.stop_worker(payload))
      else:
        result[node] = self.send_remote_command( 
                            url, payload, "stop_queue")
    return result

  def send_remote_command(self, url, payload, stage):
    """ Sends a remote command for slave nodes.
   
    Args:
      url: A URL destination where a taskqueue server is.
      payload: A payload string.
      stage: The caller description as a string.
    Returns:
      A dictionary with the status of the request.
    """ 
    try:
      request = urllib2.Request(url)
      request.add_header('Content-Type', 'application/json')
      request.add_header("Content-Length", "%d" % len(payload))
      response = urllib2.urlopen(request, payload)
      if response.getcode()!= 200:
        return {'error': True,
                'reason': "Response code of %d" % response.getcode(),
                'stage': stage}
      json_response = response.read()
      json_response = json.loads(json_response)
      if 'error' in json_response and json_response['error']:
        return {'error': True,
                'reason': "Reponse code of %d" % json_response['reason'],
                'stage': stage}
    except ValueError, value_error:
      return {'error': True,
              'reason': 
              str("Badly formed json response from worker: %s" % \
                                         str(value_error)),
              'stage': stage}
    except urllib2.URLError, url_error:
      return {'error': True,
              'reason': str("URLError: %s" % str(url_error)),
              'stage': stage}
    except IOError, io_error:
      return {'error': True,
              'reason': str(io_error),
              'stage': stage}
    except Exception, exception:
      return {'error': True,
              'reason': str(exception.__class__) + "  " + str(exception),
              'stage': stage}
    return {'error': False}

  def start_all_workers(self, 
                       app_id,  
                       result):
    """ Starts the task workers for each queue on each node. The
        result passed in has status of the previous scps done, 
        and if they failed, those nodes are skipped over. 
        Note: Only the master taskqueue node should call this.
 
    Args:
      app_id: The application ID.
      result: A dictionary of nodes to errors, and error reasons.
    Returns:
      A dictionary of status of workers on each node which is 
      dependent on the result previous passed in.
    """
    for node in result:
      if 'error' in result and result[node]['error'] == True:
        continue
      url = 'http://' + node + ':' + \
            str(taskqueue_server.SERVER_PORT) + "/startworkers"
      values = {}
      values['app_id'] = app_id
      payload = json.dumps(values)
      if self.__is_localhost(node):
        result[node] = self.start_worker(payload)
      else:
        result[node] = self.send_remote_command(
                          url, payload, "start_all_workers")
    return result 

  def stop_worker(self, json_request):
    """ Stops the god watch for queues of an application on the current
        node.
   
    Args:
      json_request: A JSON string with the queue name for which we're 
                    stopping its queues.
    Returns:
      A JSON string with the result.
    """
    request = self.__parse_json_and_validate_tags(json_request,  
                                         self.STOP_WORKERS_TAGS)
    if 'error' in request:
      return json.dumps(request)

    app_id = request['app_id']
    watch = "celery-" + str(app_id)
    try:
      if god_interface.stop(watch):
        stop_command = self.get_worker_stop_command(app_id)
        os.system(stop_command) 
        TaskQueueConfig.remove_config_files(app_id)
        result = {'error': False}
      else:
        result = {'error': True, 'reason': "Unable to stop watch %s" % watch}
    except OSError, os_error:
      result = {'error': True, 'reason' : str(os_error)}

    return json.dumps(result)
    
  def copy_config_files(self, config_file, worker_file):
    """ Copies the configuration and worker scripts to all other
        task queue nodes.
   
    Args:
      config_file:
      worker_file:
    Returns:
      Dictionary of status of copying to each node.
    """
    result = {}
    taskqueue_nodes = appscale_info.get_taskqueue_nodes()
    for node in taskqueue_nodes:
      try:
        if not self.__is_localhost(node):
          remote.scp(node, config_file, config_file)
          remote.scp(node, worker_file, worker_file)
        result[node] = {'error': False, 'reason': ""}
      except remote.ShellException, shell_exception:
        result[node] = {'error': True, 'stage': 'copy_config_files',
                        'reason': str(shell_exception)}
    return result 

  def get_worker_stop_command(self, app_id):
    """ Returns the command to run to stop celery workers for
        a given application.
  
    Args:
      app_id: The application identifier.
    Returns:
      A string which, if run, will kill celery workers for a 
      given application id.
    """
    stop_command = "ps auxww | grep 'celery worker ' | grep '"+ \
                   str(app_id) + \
                   "' | awk '{print $2}' | xargs kill -9"
    return stop_command

  def start_worker(self, json_request):
    """ Starts taskqueue workers if they are not already running.
        A worker can be started on both a master and slave node.
 
    Args:
      json_request: A JSON string with the application id and  
                    location of queue configurations.
    Returns:
      A JSON string with the error status and error reason.
    """
    request = self.__parse_json_and_validate_tags(json_request,  
                                         self.SETUP_WORKERS_TAGS)
    if 'error' in request:
      return json.dumps(request)

    app_id = self.__cleanse(request['app_id'])

    hostname = socket.gethostbyname(socket.gethostname())

    log_file = self.LOG_DIR + app_id + ".log"
    command = ["celery",
               "worker",
               "--app=" + \
                    TaskQueueConfig.get_celery_worker_module_name(app_id),
               "--autoscale=" + self.MIN_MAX_CONCURRENCY,
               "--hostname=" + hostname + "." + app_id,
               "--workdir=" + TaskQueueConfig.CELERY_WORKER_DIR,
               "--logfile=" + log_file,
               "--time-limit=" + str(self.HARD_TIME_LIMIT),
               "--soft-time-limit=" + str(self.TASK_SOFT_TIME_LIMIT),
               "--pidfile=" + self.PID_FILE_LOC + 'celery___' + \
                             app_id + ".pid",
               "--autoreload"]
    start_command = str(' '.join(command))
    stop_command = self.get_worker_stop_command(app_id)
    watch = "celery-" + str(app_id)
    god_config = god_app_interface.create_config_file(watch,
                                                      start_command, 
                                                      stop_command, 
                                                      [self.CELERY_PORT])
    if god_interface.start(god_config, watch):
      json_response = {'error': False}
    else:
      json_response = {'error': True, 
                       'reason': "Start of god watch for %s failed" % watch}
    return json.dumps(json_response)

  def fetch_queue_stats(self, app_id, http_data):
    """ 

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.\
               TaskQueueFetchQueueStatsRequest(http_data)
    response = taskqueue_service_pb.\
               TaskQueueFetchQueueStatsResponse_QueueStats()
    return (response.Encode(), 0, "")

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
    return (response.Encode(), 0, "")

  def delete(self, app_id, http_data):
    """ 

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueDeleteRequest(http_data)
    response = taskqueue_service_pb.TaskQueueDeleteResponse()
    return (response.Encode(), 0, "")

  def query_and_own_tasks(self, app_id, http_data):
    """ 

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueQueryAndOwnTasksRequest(http_data)
    response = taskqueue_service_pb.TaskQueueQueryAndOwnTasksResponse()
    return (response.Encode(), 0, "")

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
      request: taskqueue_service_pb.TaskQueueBulkAddRequest
      response: taskqueue_service_pb.TaskQUeueBulkAddResponse
    Raises:
      apiproxy_error.ApplicationError
    """
    if request.add_request_size() == 0:
      return
   
    now = datetime.datetime.utcfromtimestamp(time.time())

    # Assign names if needed and validate tasks
    error_found = False
    for add_request in request.add_request_list(): 
      task_result = response.add_taskresult()
      result = tq_lib.verify_task_queue_add_request(add_request.app_id(),
                                                    add_request, now)
      # Tasks go from SKIPPED to OK once its run. If there are 
      # any failures from other tasks then we pass this request 
      # back as skipped.
      if result == taskqueue_service_pb.TaskQueueServiceError.SKIPPED:
        task_name = None       
        if not add_request.has_task_name():
          task_name = add_request.task_name()
        chosen_name = tq_lib.choose_task_name(add_request.app_id(),
                                              add_request.queue_name(),
                                              user_chosen=task_name)
        add_request.set_task_name(chosen_name)
        task_result.set_chosen_task_name(chosen_name)
      else:
        error_found = True
        task_result.set_result(result)
    if error_found:
      return

    for add_request, task_result in zip(request.add_request_list(),
                                        response.taskresult_list()):
      if add_request.has_transaction():
        # TODO make sure transactional tasks are handled first at the AppServer
        # level, and not at the taskqueue server level
        task_result.set_result(
            apiproxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED))
        continue
      
      try:  
        self.__enqueue_push_task(add_request)
      except apiproxy_errors.ApplicationError, e:
        task_result.set_result(e.application_error)
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

  def __enqueue_push_task(self, request):
    """ Enqueues a batch of push tasks.
  
    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    """
    self.__validate_push_task(request)

    args = self.get_task_args(request)

    headers = self.get_task_headers(request)

    task_func = self.__get_task_function(request)

    result = task_func.apply_async(kwargs={'headers':headers,
                    'args':args},
                    expires=args['expires'],
                    acks_late=True,
                    eta=self.__when_to_run(request),
                    queue=TaskQueueConfig.get_celery_queue_name(
                              request.app_id(), request.queue_name()),
                    routing_key=TaskQueueConfig.get_celery_queue_name(
                              request.app_id(), request.queue_name()))

  def __get_task_function(self, request):
    """ Returns a function pointer to a celery task.
        Load the module for the app/queue.
    
    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    Returns:
      A function pointer to a celery task.
    Raises:
      taskqueue_service_pb.TaskQueueServiceError
    """
    try:
      task_module = __import__(TaskQueueConfig.\
                  get_celery_worker_module_name(request.app_id()))
      task_func = getattr(task_module, 
        TaskQueueConfig.get_queue_function_name(request.queue_name()))
      return task_func
    except ImportError, import_error:
      raise apiproxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
     

  def get_task_args(self, request):
    """ Gets the task args used when making a task web request.
  
    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest
    Returns:
      A dictionary used by a task worker.
    """
    args = {}
    args['task_name'] = request.task_name()
    args['url'] = request.url()
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
    headers['X-AppEngine-Development-Payload'] = secret_hash
    headers['X-AppEngine-QueueName'] = request.queue_name()
    headers['X-AppEngine-TaskName'] = request.task_name()
    headers['X-AppEngine-TaskRetryCount'] = '0'
    headers['X-AppEngine-TaskExecutionCount'] = '0'
    headers['X-AppEngine-TaskETA'] = int(eta.strftime("%s")) * 1000  
    return headers

  def __when_to_run(self, request):
    """ Returns a datetime object of when a task should 
        execute.
    
    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest
    Returns:
      A datetime object for when the nearest time to run the 
     task is.
    """
    if request.has_eta_usec():
      eta = request.eta_usec()
      return datetime.datetime.now() + datetime.timedelta(microseconds=eta)
    else:
      return datetime.datetime.now() 

  def __when_to_expire(self, request):
    """ Returns a datetime object of when a task should 
        expire.
    
    Args:
      A taskqueue_service_pb.TaskQueueAddRequest
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
    return (response.Encode(), 0, "")

  def update_queue(self, app_id, http_data):
    """ Creates a queue entry in the database.

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueUpdateQueueRequest(http_data)
    response = taskqueue_service_pb.TaskQueueUpdateQueueResponse()
    return (response.Encode(), 0, "")

  def fetch_queue(self, app_id, http_data):
    """ 

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
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
    request = taskqueue_service_pb.TaskQueueForceRunRequest(http_data)
    response = taskqueue_service_pb.TaskQueueForceRunResponse()
    return (response.Encode(), 0, "")

  def delete_queue(self, app_id, http_data):
    """ 

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
    request = taskqueue_service_pb.TaskQueueDeleteQueueRequest(http_data)
    response = taskqueue_service_pb.TaskQueueDeleteQueueResponse()
    return (response.Encode(), 0, "")

  def pause_queue(self, app_id, http_data):
    """ 

    Args:
      app_id: The application ID.
      http_data: The payload containing the protocol buffer request.
    Returns:
      A tuple of a encoded response, error code, and error detail.
    """
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
    request = taskqueue_service_pb.TaskQueueUpdateStorageLimitRequest(http_data)
    response = taskqueue_service_pb.TaskQueueUpdateStorageLimitResponse()
    return (response.Encode(), 0, "")

  def __cleanse(self, str_input):
    """ Removes any questionable characters which might be apart of 
        a remote attack.
   
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
