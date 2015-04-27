""" Handlers for accepting HTTP requests. """

import json
import logging
import os
import sys
from tornado.web import RequestHandler

import constants
import helper

sys.path.append(os.path.join(os.path.dirname(__file__), "/root/appscale/lib/"))
import appscale_info

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
    url = "{0}{1}".format(constants.PORTAL_URL,
        constants.PORTAL_POLL_PATH)
    data = json.dumps({
      "secret": helper.get_deployment_id()
    })
    request = helper.create_request(url=url, method='POST', body=data)
    response = helper.urlfetch(request)
    if not response:
      self.set_status(constants.HTTP_Codes.HTTP_OK)
      return
    data = json.loads(response.body)

    # Verify all necessary fields are present in the request.
    if not set(data.keys()).issuperset(set(REQUIRED_KEYS)) or \
        None in data.values():
      logging.error("Missing args in request: " + self.request.body)
      return

    logging.info("Task to run: {0}".format(data))
    logging.info("Redirecting task request to TaskHandler.")
    url = "{0}{1}".format(constants.HERMES_URL, TaskHandler.PATH)
    request = helper.create_request(url, method='POST', body=data)
    # The poller can move forward without waiting for a response here.
    helper.urlfetch_async(request)

    self.set_status(constants.HTTP_Codes.HTTP_OK)

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
    node_info = [
      {
        'ip': appscale_info.get_db_master_ip(),
        'role': 'db_master',
        'type': data['type']
      }
    ]

    index = 0
    for node in appscale_info.get_db_slave_ips():
      node_info.append({
        'ip': node,
        'role': 'db_slave',
        'type': data['type'],
        'index': index
      })
      index += 1

    index = 0
    for node in appscale_info.get_zk_node_ips():
      node_info.append({
        'ip': node,
        'role': 'zk',
        'type': data['type'],
        'index': index
      })
      index += 1

    # TODO: create a thread and a backup_recovery_service request for each node.

    # Start one thread for each
    self.set_status(constants.HTTP_Codes.HTTP_OK)

def finalize_task():
  """ A function that marks a task as done and puts it into the queue of
  completed tasks.
  """
  # TODO
  logging.info("Task is completed successfully.")
