""" Web server/client that polls the AppScale Portal for new tasks and
initiates actions accordingly. """

import json
import logging
import signal
import socket
import datetime
import tornado.escape
import tornado.httpclient
import tornado.web
import urllib

from tornado.ioloop import IOLoop
from tornado.ioloop import PeriodicCallback
from tornado.options import define
from tornado.options import options
from tornado.options import parse_command_line

import hermes_constants
import helper
from handlers import MainHandler
from handlers import TaskHandler
from helper import JSONTags

# Tornado web server options.
define("port", default=hermes_constants.HERMES_PORT, type=int)

def poll():
  """ Callback function that polls for new tasks based on a schedule. """
  deployment_id = helper.get_deployment_id()
  # If the deployment is not registered, skip.
  if not deployment_id:
    return

  # If we can't reach the backup and recovery services, skip.
  nodes = helper.get_node_info()
  http_client = tornado.httpclient.HTTPClient()
  for node in nodes:
    br_host = node[helper.NodeInfoTags.HOST]
    request = tornado.httpclient.HTTPRequest(br_host)
    try:
      response = http_client.fetch(request)
      if json.loads(response.body)['status'] != 'up':
        logging.warn('Backup and Recovery service at {} is not up.'
          .format(br_host))
        return
    except (socket.error, ValueError):
      logging.exception('Backup and Recovery service at {} is not up.'
        .format(br_host))
      return

  logging.info("Polling for new task.")

  # Send request to AppScale Portal.
  url = "{0}{1}".format(hermes_constants.PORTAL_URL,
      hermes_constants.PORTAL_POLL_PATH)
  data = urllib.urlencode({JSONTags.DEPLOYMENT_ID: deployment_id})
  request = helper.create_request(url=url, method='POST', body=data)
  response = helper.urlfetch(request)

  if not response[JSONTags.SUCCESS]:
    logging.error("Inaccessible resource: {}".format(url))
    return

  try:
    data = json.loads(response[JSONTags.BODY])
  except (TypeError, ValueError) as error:
    logging.error("Cannot parse response from url '{0}'. Error: {1}".
      format(url, str(error)))
    return

  if data == {}:  # If there's no task to perform.
    return

  # Verify all necessary fields are present in the request.
  if not set(data.keys()).issuperset(set(hermes_constants.REQUIRED_KEYS)):
    logging.error("Missing args in response: {0}".format(response))
    return

  logging.debug("Task to run: {0}".format(data))
  logging.info("Redirecting task request to TaskHandler.")
  url = "{0}{1}".format(hermes_constants.HERMES_URL, TaskHandler.PATH)
  request = helper.create_request(url, method='POST', body=json.dumps(data))

  # The poller can move forward without waiting for a response here.
  helper.urlfetch_async(request)

def send_all_stats():
  """ Calls get_all_stats and sends the deployment monitoring stats to the
  AppScale Portal. """
  deployment_id = helper.get_deployment_id()
  # If the deployment is not registered, skip.
  if not deployment_id:
    return

  # Get all stats from this deployment.
  logging.debug("Getting all stats from every deployment node.")
  all_stats = helper.get_all_stats()

  # Send request to AppScale Portal.
  url = "{0}{1}".format(hermes_constants.PORTAL_URL,
      hermes_constants.PORTAL_STATS_PATH)
  data = {
    JSONTags.DEPLOYMENT_ID: deployment_id,
    JSONTags.TIMESTAMP: datetime.datetime.utcnow(),
    JSONTags.ALL_STATS: all_stats
  }
  logging.debug("Sending all stats to the AppScale Portal. Data: \n{}".
    format(data))

  request = helper.create_request(url=url, method='POST',
    body=urllib.urlencode(data))
  response = helper.urlfetch(request)

  if not response[JSONTags.SUCCESS]:
    logging.error("Inaccessible resource: {}".format(url))
    return

def signal_handler(signal, frame):
  """ Signal handler for graceful shutdown. """
  logging.warning("Caught signal: {0}".format(signal))
  IOLoop.instance().add_callback(shutdown)

def shutdown():
  """ Shuts down the server. """
  logging.warning("Hermes is shutting down.")
  IOLoop.instance().stop()

def main():
  """ Main. """

  logging_level = logging.INFO
  if hermes_constants.DEBUG:
    logging_level = logging.DEBUG
  logging.getLogger().setLevel(logging_level)

  signal.signal(signal.SIGTERM, signal_handler)
  signal.signal(signal.SIGINT, signal_handler)

  parse_command_line()

  app = tornado.web.Application([
    (MainHandler.PATH, MainHandler),
    (TaskHandler.PATH, TaskHandler),
  ], debug=False)

  try:
    app.listen(options.port)
  except socket.error:
    logging.error("ERROR on Hermes initialization: Port {0} already in use.".
      format(options.port))
    shutdown()
    return

  logging.info("Hermes is up and listening on port: {0}.".
    format(options.port))

  # Periodically check with the portal for new tasks.
  # Note: Currently, any active handlers from the tornado app will block
  # polling until they complete.
  PeriodicCallback(poll, hermes_constants.POLLING_INTERVAL).start()

  # Periodically send all available stats from each deployment node to the
  # AppScale Portal.
  PeriodicCallback(send_all_stats, hermes_constants.STATS_INTERVAL).start()

  # Start loop for accepting http requests.
  IOLoop.instance().start()

if __name__ == "__main__":
  main()
