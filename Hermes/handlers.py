""" Handlers for accepting HTTP requests. """

import Queue
import json
import logging
import os
import sys
import threading

from tornado.ioloop import IOLoop
from tornado.web import RequestHandler

import helper
import hermes_constants
from helper import JSONTags
from helper import NodeInfoTags
from helper import TASK_STATUS
from helper import TASK_STATUS_LOCK
from lib.stats_collector import StatsCollector

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

STATS = {}

class TaskStatus(object):
  """ A class containing all possible task states. """
  PENDING = 'pending'
  FAILED = 'failed'
  COMPLETE = 'complete'

class MainHandler(RequestHandler):
  """ Main handler class. """

  def get(self):
    """ Main GET method. Reports the status of the server. """
    self.write(json.dumps({'status': 'up'}))

class TaskHandler(RequestHandler):
  """ Handler that starts operations to complete a task. """

  def post(self):
    """ POST method that sends a request for action to the
    corresponding deployment components. """
    logging.debug("Task request received: {0}, {1}".format(str(self.request),
      str(self.request.body)))

    if not self.request.body:
      logging.info("Response from the AppScale Portal empty. No tasks to run.")
      self.set_status(hermes_constants.HTTP_Codes.HTTP_OK)
      return

    try:
      data = json.loads(self.request.body)
    except (TypeError, ValueError) as error:
      logging.exception(error)
      logging.error("Unable to parse: {0}".format(self.request.body))
      self.set_status(hermes_constants.HTTP_Codes.HTTP_BAD_REQUEST)
      return

    # Verify all necessary fields are present in request.body.
    logging.debug("Verifying all necessary parameters are present.")
    if not set(data.keys()).issuperset(set(hermes_constants.REQUIRED_KEYS)):
      logging.error("Missing args in request: " + self.request.body)
      self.set_status(hermes_constants.HTTP_Codes.HTTP_BAD_REQUEST)
      return

    # Gather information for sending the requests to start off the current
    # task at hand.
    nodes = helper.get_node_info()

    if data[JSONTags.TYPE] not in hermes_constants.SUPPORTED_TASKS:
      logging.error("Unsupported task type: '{0}'".format(data[JSONTags.TYPE]))
      self.set_status(hermes_constants.HTTP_Codes.HTTP_BAD_REQUEST)
      return

    tasks = [data[JSONTags.TYPE]]
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
          node[NodeInfoTags.INDEX], data[JSONTags.STORAGE])
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
      logging.debug("Task: {0}. Results: {1}.".format(task, results))

      # Backup source code.
      app_success = False
      if task == 'backup':
        app_success = helper.\
          backup_apps(data[JSONTags.STORAGE], data[JSONTags.BUCKET_NAME])
      elif task == 'restore':
        app_success = helper.\
          restore_apps(data[JSONTags.STORAGE], data[JSONTags.BUCKET_NAME])

      # Update TASK_STATUS.
      successful_nodes = 0
      for result in results:
        if result[JSONTags.SUCCESS]:
          successful_nodes += 1

      TASK_STATUS_LOCK.acquire(True)
      all_nodes = TASK_STATUS[data[JSONTags.TASK_ID]]\
          [NodeInfoTags.NUM_NODES]
      if successful_nodes < all_nodes or not app_success:
        TASK_STATUS[data[JSONTags.TASK_ID]][JSONTags.STATUS] = \
          TaskStatus.FAILED
      else:
        TASK_STATUS[data[JSONTags.TASK_ID]][JSONTags.STATUS] = \
          TaskStatus.COMPLETE

      logging.info("Task: {0}. Status: {1}.".format(task,
        TASK_STATUS[data[JSONTags.TASK_ID]][JSONTags.STATUS]))
      IOLoop.instance().add_callback(callback=lambda:
        helper.report_status(task, data[JSONTags.TASK_ID],
        TASK_STATUS[data[JSONTags.TASK_ID]][JSONTags.STATUS]
      ))
      TASK_STATUS_LOCK.release()

    self.set_status(hermes_constants.HTTP_Codes.HTTP_OK)


class NodeStatsHandler(RequestHandler):
  """ Handler for getting current node stats
  """
  # TODO update djinn.rb to use new response structure
  def __init__(self, *args, **kwargs):
    super(NodeStatsHandler, self).__init__(*args, **kwargs)
    self.stats_collector = StatsCollector.instance()
    self.secret = appscale_info.get_secret()

  def get(self):
    if self.get_argument('secret') != self.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
    else:
      self.write(json.dumps(self.stats_collector.cluster_stats.my_node))


class ClusterStatsHandler(RequestHandler):
  """ Handler for getting cluster stats:
      Nodes stats + Services stats
  """
  # TODO update djinn.rb to use new response structure
  def __init__(self, *args, **kwargs):
    super(ClusterStatsHandler, self).__init__(*args, **kwargs)
    self.stats_collector = StatsCollector.instance()
    self.secret = appscale_info.get_secret()

  def get(self):
    if self.get_argument('secret') != self.secret:
      logging.warn("Received bad secret from {client}"
                   .format(client=self.request.remote_ip))
      self.set_status(401, "Bad secret")
    else:
      self.write(json.dumps({
        'nodes': self.stats_collector.cluster_stats.nodes,
        'services': self.stats_collector.cluster_stats.services
      }))
