""" Handlers for accepting HTTP requests. """

import json
import logging
import Queue
import threading
from tornado.web import RequestHandler

import hermes_constants
import helper

# Structure for keeping status of tasks.
TASK_STATUS = {}

# Lock for accessing TASK_STATUS.
TASK_STATUS_LOCK = threading.Lock()

# A list of required parameters that define a task.
REQUIRED_KEYS = ['task_id', 'type', 'bucket_name']

# A list of tasks that we report status for.
REPORT_TASKS = ['backup', 'restore']

class TaskStatus(object):
  """ A class containing all possible task states. """
  PENDING = 'pending'
  FAILED = 'failed'
  SUCCESSFUL = 'successful'

class MainHandler(RequestHandler):
  """ Main handler class. """

  # The path for this handler.
  PATH = "/"

  def get(self):
    """ Main GET method. Reports the status of the server. """
    self.write(json.dumps({'status': 'up'}))

class PollHandler(RequestHandler):
  """ Handler that polls for new tasks. """

  # The path for this handler.
  PATH = "/poll"

  def get(self):
    """ GET method that polls for a new task. """

    # Send request to AppScale Portal.
    logging.info("Sending request to AppScale Portal.")
    url = "{0}{1}".format(hermes_constants.PORTAL_URL,
        hermes_constants.PORTAL_POLL_PATH)
    data = json.dumps({
      "secret": helper.get_deployment_id()
    })
    request = helper.create_request(url=url, method='POST', body=data)
    response = helper.urlfetch(request)
    if not response['success']:
      self.set_status(hermes_constants.HTTP_Codes.HTTP_OK)
      return
    data = json.loads(response.body)

    # Verify all necessary fields are present in the request.
    if not set(data.keys()).issuperset(set(REQUIRED_KEYS)) or \
        None in data.values():
      logging.error("Missing args in request: " + self.request.body)
      return

    logging.info("Task to run: {0}".format(data))
    logging.info("Redirecting task request to TaskHandler.")
    url = "{0}{1}".format(hermes_constants.HERMES_URL, TaskHandler.PATH)
    request = helper.create_request(url, method='POST', body=data)
    # The poller can move forward without waiting for a response here.
    helper.urlfetch_async(request)

    self.set_status(hermes_constants.HTTP_Codes.HTTP_OK)

class TaskHandler(RequestHandler):
  """ Handler that starts operations to complete a task. """

  # The path for this handler.
  PATH = "/do_task"

  def post(self):
    """ POST method that sends a request for action to the
    corresponding deployment components. """
    logging.info("Task request received: {0}, {1}".format(str(self.request),
      str(self.request.body)))

    try:
      data = json.loads(self.request.body)
    except (TypeError, ValueError) as error:
      logging.exception(error)
      logging.error("Unable to parse: {0}".format(self.request.body))
      return

    # Verify all necessary fields are present in request.body.
    logging.info("Verifying all necessary parameters are present.")
    if not set(data.keys()).issuperset(set(REQUIRED_KEYS)) or \
        None in data.values():
      logging.error("Missing args in request: " + self.request.body)
      return

    # Gather information for sending the requests to start off the current
    # task at hand.
    nodes = helper.get_node_info()

    # Ensure that we bring down affected nodes before any action while doing a
    # restore.
    tasks = []
    if data['type'] == 'backup':
      tasks = [data['type']]
    elif data['type'] == 'restore':
      tasks = ['shutdown', 'restore']
    logging.info("Tasks to execute: {0}".format(tasks))

    for task in tasks:
      # Initiate the task as pending.
      TASK_STATUS_LOCK.acquire(True)
      TASK_STATUS[data['task_id']] = {
        'type': task, 'num_nodes': len(nodes), 'status': TaskStatus.PENDING
      }
      TASK_STATUS_LOCK.release()

      result_queue = Queue.Queue()
      threads = []
      for node in nodes:
        # Create a br_service compatible JSON object.
        json_data = helper.create_br_json_data(node['role'], task,
          data['bucket_name'], node['index'])
        request = helper.create_request(url=node['host'], method='POST',
          body=json_data)

        # Start a thread for the request.
        thread = threading.Thread(target=helper.send_remote_request,
          name='{0}{1}'.format(data['type'], node['host']),
          args=(request, result_queue,))
        threads.append(thread)
        thread.start()

      # Wait for threads to finish.
      for thread in threads:
        thread.join()
      # Harvest results.
      results = [result_queue.get() for _ in xrange(len(nodes))]
      logging.info("Task: {0}. Results: {1}".format(task, results))

      # Update TASK_STATUS.
      successful_nodes = 0
      for result in results:
        if result['success']:
          successful_nodes += 1

      TASK_STATUS_LOCK.acquire(True)
      if successful_nodes < TASK_STATUS[data['task_id']]['num_nodes']:
        TASK_STATUS[data['task_id']]['status'] = TaskStatus.FAILED
      else:
        TASK_STATUS[data['task_id']]['status'] = TaskStatus.SUCCESSFUL

      # Report status.
      if task in REPORT_TASKS:
        url = '{0}{1}'.format(hermes_constants.PORTAL_URL,
          hermes_constants.PORTAL_STATUS_PATH)
        data = json.dumps({
          'task_id': data['task_id'],
          'deployment_id': helper.get_deployment_id(),
          'status': TASK_STATUS[data['task_id']]['status']
        })
        TASK_STATUS_LOCK.release()
        request = helper.create_request(url=url, method='POST', body=data)
        helper.urlfetch(request)

    self.set_status(hermes_constants.HTTP_Codes.HTTP_OK)
