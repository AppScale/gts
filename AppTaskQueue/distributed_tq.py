""" 
A service for handling TaskQueue request from application servers.
It uses RabbitMQ and celery to task handling. 
"""

import celery
import httplib
import json
import logging
import new
import os
import socket
import sys
import urllib2
 
import taskqueue_server
import tq_lib

from tq_config import TaskQueueConfig

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import file_io
import god_app_interface
import god_interface
import remote

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api.taskqueue import taskqueue_service_pb
from google.appengine.api import datastore_distributed
from google.appengine.api import datastore

sys.path.append(TaskQueueConfig.CELERY_CONFIG_DIR)

class DistributedTaskQueue():
  """ AppScale taskqueue layer for the TaskQueue API. """

  # The file location which has all taskqueue nodes listed.
  TASKQUEUE_NODE_FILE = "/etc/appscale/taskqueue_nodes"

  # Required setup queues name tags.
  SETUP_QUEUE_TAGS = ['queue_yaml', 'app_id', 'command']

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

  def setup_queues(self, json_request):
    """ Creates a configuration file for an application's queues

    Args:
      json_request: A JSON string containing the app_id and 
                    the location of the queue.yaml file.
    Returns:
      A JSON string of the location of the queue config file, 
      along with an error status and string if there was an 
      error. 
    """
    logging.info("Request: %s" % str(json_request))
    request = self.__parse_json_and_validate_tags(json_request,  
                                         self.SETUP_QUEUE_TAGS)
    if 'error' in request:
      return json.dumps(request)

    app_id = self.__cleanse(request['app_id'])
    command = self.__cleanse(request['command'])
    queue_yaml = request['queue_yaml'] 

    config = TaskQueueConfig(TaskQueueConfig.RABBITMQ, app_id)

    # Load the queue info
    config_file = None
    if 'reload' == command:
      config.load_queues_from_db()
      config_file = config.create_celery_file(TaskQueueConfig.QUEUE_INFO_FILE) 
      worker_file = config.create_celery_worker_scripts(
                        TaskQueueConfig.QUEUE_INFO_FILE)
    elif 'update' == command:
      config.load_queues_from_file(queue_yaml)
      config_file = config.create_celery_file(TaskQueueConfig.QUEUE_INFO_FILE) 
      worker_file = config.create_celery_worker_scripts(
                        TaskQueueConfig.QUEUE_INFO_FILE)
    else:
      response = {'error': True, 'reason': 'Unknown command %s' % \
                  command}
      return json.dumps(response) 

    # Copy over files and start the workers  
    result = self.copy_config_files(config_file, worker_file) 
    json_response = self.start_workers(app_id, result)
    return json.dumps(json_response)

  def start_workers(self, 
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
      values = json.dumps(values)
      if self.__is_localhost(node):
        result[node] = self.setup_workers(values)
        continue
      try:
        print "Sending request to %s" % url
        request = urllib2.Request(url)
        request.add_header('Content-Type', 'application/json')
        request.add_header("Content-Length", "%d" % len(values))
        response = urllib2.urlopen(request, values)
        if response.getcode()!= 200:
          result[node] = {'error': True,
                'reason': "Response code of %d" % response.getcode(),
                'stage': 'start_workers'}
        print "Getting response"
        json_response = response.read()
        print json_response
        json_response = json.loads(json_response)
        if 'error' in json_response and json_response['error']:
          result[node] = {'error': True,
                'reason': "Reponse code of %d" % json_response['reason'],
                'stage': 'start_workers'}
        print "Sent request to %s" % url
      except ValueError:
        result[node] = {'error': True,
                'reason': 
                str("Badly formed json response from worker: %s" % values),
                'stage': 'start_workers'}
      except httplib.InvalidURL, http_error:
        result[node] = {'error': True,
                'reason': str(http_error),
                'stage': 'start_workers'}
      except httplib.NotConnected, http_error:
        result[node] = {'error': True,
                'reason': str(http_error),
                'stage': 'start_workers'}
      except httplib.HTTPException, http_error:
        result[node] = {'error': True,
                'reason': str(http_error),
                'stage': 'start_workers'}
      except IOError, io_error:
        result[node] = {'error': True,
                'reason': str(io_error),
                'stage': 'start_workers'}
      except Exception, exception:
        result[node] = {'error': True,
                'reason': str(exception.__class__) + \
                          "  " + str(exception),
                'stage': 'start_workers'}
       
    return result 

  def stop_workers(self, json_request):
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
    if god_interface.stop(watch):
      self.remove_config_files(app_id)
      result = {'error':False}
    else:
      result = {'error':True, 'reason':"Unable to stop watch %s" % watch}
    return json.dumps(result)

  def remove_config_files(self, app_id):
    """ Removed celery worker and config files.
  
    Args:
      app_id: The application identifer.
    """  
    worker_file = TaskQueueConfig.get_celery_worker_script_path(app_id)
    config_file = TaskQueueConfig.get_celery_configuration_path(app_id)
    file_io.delete(worker_file)
    file_io.delete(config_file)
    
  def get_taskqueue_nodes(self):
    """ Returns a list of all the taskqueue nodes (including the master). 
        Strips off any empty lines

    Returns:
      A list of taskqueue nodes.
    """
    nodes = file_io.read(self.TASKQUEUE_NODE_FILE)
    nodes = nodes.split('\n') 
    if nodes[-1] == '':
      nodes = nodes[:-1]
    return nodes

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
    taskqueue_nodes = self.get_taskqueue_nodes()
    for node in taskqueue_nodes:
      try:
        remote.scp(node, config_file, config_file)
        remote.scp(node, worker_file, worker_file)
        result[node] = {'error': False, 'reason': ""}
      except remote.ShellException, shell_exception:
        result[node] = {'error': True, 'stage': 'copy_config_files',
                        'reason': str(shell_exception)}
    return result 

  def setup_workers(self, json_request):
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

    #config_name = app_id + "." + queue_name
    log_file = self.LOG_DIR + app_id + ".log"
    command = ["celery",
               "worker",
               "--app=app__" + app_id,
               "--autoscale=" + self.MIN_MAX_CONCURRENCY,
               "--hostname=" + hostname + "." + app_id,
               "--workdir=" + TaskQueueConfig.CELERY_WORKER_DIR,
               "--logfile=" + log_file,
               "--time-limit=" + str(self.HARD_TIME_LIMIT),
               "--soft-time-limit=" + str(self.TASK_SOFT_TIME_LIMIT),
               "--pidfile=" + self.PID_FILE_LOC + app_id + ".pid",
               "--autoreload"]
    start_command = str(' '.join(command))
    print start_command
    stop_command = "ps auxww | grep 'celery worker ' | grep '"+ str(app_id) + \
                   "' | awk '{print $2}' | xargs kill -9"
    watch = "celery-" + str(app_id)
    god_config = god_app_interface.create_config_file(watch,
                                                      start_command, 
                                                      stop_command, 
                                                      [self.CELERY_PORT])
    if god_interface.start(god_config, watch):
    #ret = os.system("nohup " + start_command + " &")
    #if ret == 0:
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
      api_proxy_error.ApplicationError
    """
    if request.add_request_size() == 0:
      return

    now = datetime.datetime.utcfromtimestamp(time.time())

    # Assign names if needed.
    for add_request in rquest.add_request_list(): 
      task_result = response.add_taskresult()
      result = tq_lib.verify_task_queue_add_request(add_request, now)
      if result == taskqueue_service_pb.TaskQueueServiceError.OK:
        if not add_request.task_name():
          chosen_name = tq_lib.choose_task_name()
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
            api_proxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.PERMISSION_DENIED))
        continue
      
      try:  
        self.__enqueue_push_task(add_request, now)
      except apiproxy_error.ApplicationError, e:
        task_result.set_result(e.application_error)
      else:
        task_result.set_result(taskqueue_service_pb.TaskQueueServiceError.OK)

  def __enqueue_push_task(self, request):
    """ Enqueues a batch of push tasks.
  
    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest.
    """
    self.__validate_push_task(request)
    queue_name = request.queue_name()
    method = request.method()
    app_id = request.app_id()
    url = request.url()
    # Load the module for the app/queue 
    task_module = __import__(TaskQueueConfig.\
                  get_celery_worker_module_name(app_id))
    task_func = getattr(task_modele, 
                 TaskQueueConfig.get_queue_function_name(queue_name))
  
    task_func.delay(headers=headers,
                    args=args,
                    retry_dict=retry_dict,
                    name=request.task_name(),
                    eta=self.__when_to_run(request),
                    expires=self.__when_to_expire(request))

  def __when_to_run(self, request):
    """ Returns a datetime object of when a task should 
        execute.
    
    Args:
      A taskqueue_service_pb.TaskQueueAddRequest
    """
    # TODO calculate offsets
    return datetime.now() 

  def __when_to_expire(self, request):
    """ Returns a datetime object of when a task should 
        expire.
    
    Args:
      A taskqueue_service_pb.TaskQueueAddRequest
    """
    # TODO calculate offsets
    return datetime.now() + datetime.timedelta(days=30)

  def __validate_push_task(self, request):
    """ Checks to make sure the task request is valid.
    
    Args:
      request: A taskqueue_service_pb.TaskQueueAddRequest. 
    Raises:
      api_proxy_errors.ApplicationError upon invalid tasks.
    """ 
    if not request.has_queue_name():
      raise api_proxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.INVALID_QUEUE_NAME)
    if not request.has_task_name():
      raise api_proxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.INVALID_TASK_NAME)
    if not request.has_app_id():
      raise api_proxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.UNKNOWN_QUEUE)
    if not request.has_url():
      raise api_proxy_errors.ApplicationError(
              taskqueue_service_pb.TaskQueueServiceError.INVALID_URL)
    if request.has_mode() and request.mode() == TaskQueueMode.PULL:
      raise api_proxy_errors.ApplicationError(
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
