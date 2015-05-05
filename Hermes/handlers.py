""" Handlers for accepting HTTP requests. """

import json
import logging
import Queue
import threading
from tornado.web import RequestHandler

import hermes_constants
import helper

# A set of required parameters that define a task.
REQUIRED_KEYS = ['type', 'bucket_name']

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
    node_info = helper.get_node_info()

    # Ensure that we bring down affected nodes before any action while doing a
    # restore.
    tasks = []
    if data['type'] == 'backup':
      tasks = [data['type']]
    elif data['type'] == 'restore':
      tasks = ['shutdown', 'restore']
    logging.info("Tasks to execute: {0}".format(tasks))

    for task in tasks:
      result_queue = Queue.Queue()
      threads = []
      for node in node_info:
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

      results = [result_queue.get() for _ in xrange(len(node_info))]
      logging.info("Results: {0}".format(results))

      # Update TASK_STATUS. TODO

    self.set_status(hermes_constants.HTTP_Codes.HTTP_OK)
