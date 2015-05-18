""" Handlers for accepting HTTP requests. """

import json
import logging
import Queue
import threading
from tornado.ioloop import IOLoop
from tornado.web import RequestHandler

import hermes_constants
import helper
from helper import JSONTags
from helper import NodeInfoTags
from helper import TASK_STATUS
from helper import TASK_STATUS_LOCK

# A list of required parameters that define a task.
REQUIRED_KEYS = ['task_id', 'type', 'bucket_name']

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
      JSONTags.DEPLOYMENT_ID: helper.get_deployment_id()
    })
    request = helper.create_request(url=url, method='POST', body=data)
    response = helper.urlfetch(request)
    if not response[JSONTags.DEPLOYMENT_ID]:
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
    if data[JSONTags.TYPE] == 'backup':
      tasks = [data[JSONTags.TYPE]]
    elif data[JSONTags.TYPE] == 'restore':
      tasks = ['restore']
    logging.info("Tasks to execute: {0}".format(tasks))

    for task in tasks:
      # Initiate the task as pending.
      TASK_STATUS_LOCK.acquire(True)
      TASK_STATUS[data[JSONTags.TASK_ID]] = {
        JSONTags.TYPE: task, NodeInfoTags.NUM_NODES: len(nodes),
        JSONTags.STATUS: TaskStatus.PENDING
      }
      TASK_STATUS_LOCK.release()

      result_queue = Queue.Queue()
      threads = []
      for node in nodes:
        # Create a br_service compatible JSON object.
        json_data = helper.create_br_json_data(
          node[NodeInfoTags.ROLE],
          task, data[JSONTags.BUCKET_NAME],
          node[NodeInfoTags.INDEX])
        request = helper.create_request(url=node[NodeInfoTags.HOST],
          method='POST', body=json_data)

        # Start a thread for the request.
        thread = threading.Thread(
          target=helper.send_remote_request,
          name='{0}{1}'.
            format(data[JSONTags.TYPE], node[NodeInfoTags.HOST]),
          args=(request, result_queue,))
        threads.append(thread)
        thread.start()

      # Wait for threads to finish.
      for thread in threads:
        thread.join()
      # Harvest results.
      results = [result_queue.get() for _ in xrange(len(nodes))]
      logging.warn("Task: {0}. Results: {1}.".format(task, results))

      # Update TASK_STATUS.
      successful_nodes = 0
      for result in results:
        if result[JSONTags.SUCCESS]:
          successful_nodes += 1

      TASK_STATUS_LOCK.acquire(True)
      all_nodes = TASK_STATUS[data[JSONTags.TASK_ID]]\
          [NodeInfoTags.NUM_NODES]
      if successful_nodes < all_nodes:
        TASK_STATUS[data[JSONTags.TASK_ID]][JSONTags.STATUS] = \
          TaskStatus.FAILED
      else:
        TASK_STATUS[data[JSONTags.TASK_ID]][JSONTags.STATUS] = \
          TaskStatus.SUCCESSFUL
      logging.info("Task: {0}. Status: {1}.".format(task,
        TASK_STATUS[data[JSONTags.TASK_ID]][JSONTags.STATUS]))
      IOLoop.instance().add_callback(callback=lambda:
        helper.report_status(task, data[JSONTags.TASK_ID],
        TASK_STATUS[data[JSONTags.TASK_ID]][JSONTags.STATUS]
      ))
      TASK_STATUS_LOCK.release()

    self.set_status(hermes_constants.HTTP_Codes.HTTP_OK)
