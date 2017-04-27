""" Web server/client that polls the AppScale Portal for new tasks and
initiates actions accordingly. """

import json
import logging
import os
import re
import signal
import socket
import sys
import tarfile
import urllib

import tornado.escape
import tornado.httpclient
import tornado.web
from appscale.common import appscale_info
from appscale.common import appscale_utils
from appscale.common.ua_client import UAClient
from appscale.common.ua_client import UAException
from tornado.ioloop import IOLoop
from tornado.ioloop import PeriodicCallback
from tornado.options import define
from tornado.options import options
from tornado.options import parse_command_line

import helper
from appscale.hermes.constants import WRITE_PROFILE_LOG, TRACK_PROCESSES_STATS, \
  MINIMIZE_CLUSTER_STATS, HERMES_PORT
from handlers import MainHandler, TaskHandler
from helper import JSONTags

sys.path.append('../../../AppServer')
from google.appengine.api.appcontroller_client import AppControllerException

# Tornado web server options.
define("port", default=HERMES_PORT, type=int)
# Determines whether this node is a master node (head node is master by default)
define("master", default=None, type=bool)
# Determines whether profile log should be written (only for master node)
define("write-profile-log", default=WRITE_PROFILE_LOG, type=bool)
# Determines whether processes stats should be collected
define("track-processes-stats", default=TRACK_PROCESSES_STATS, type=bool)
# Determines whether processes stats should be collected
define("minimize-cluster-stats", default=MINIMIZE_CLUSTER_STATS, type=bool)

# Statistics cache.


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
  url = "{0}{1}".format(constants.PORTAL_URL,
                        constants.PORTAL_POLL_PATH)
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
  if not set(data.keys()).issuperset(set(constants.REQUIRED_KEYS)):
    logging.error("Missing args in response: {0}".format(response))
    return

  logging.debug("Task to run: {0}".format(data))
  logging.info("Redirecting task request to TaskHandler.")
  url = "{0}{1}".format(constants.HERMES_URL, TaskHandler.PATH)
  request = helper.create_request(url, method='POST', body=json.dumps(data))

  # The poller can move forward without waiting for a response here.
  helper.urlfetch_async(request)


def deploy_sensor_app():
  """ Uploads the sensor app for registered deployments. """

  deployment_id = helper.get_deployment_id()
  #If deployment is not registered, then do nothing.
  if not deployment_id:
    return

  secret = appscale_info.get_secret()
  ua_client = UAClient(appscale_info.get_db_master_ip(), secret)

  # If the appscalesensor app is already running, then do nothing.
  if ua_client.is_app_enabled(constants.APPSCALE_SENSOR):
    return

  pwd = appscale_utils.encrypt_password(constants.USER_EMAIL,
                                        appscale_utils.random_password_generator())
  if create_appscale_user(pwd, ua_client) and create_xmpp_user(pwd, ua_client):
    logging.debug("Created new user and now tarring app to be deployed.")
    file_path = os.path.join(os.path.dirname(__file__), '../Apps/sensor')
    app_dir_location = os.path.join(constants.APP_DIR_LOCATION,
                                    constants.APPSCALE_SENSOR)
    archive = tarfile.open(app_dir_location, "w|gz")
    archive.add(file_path, arcname= constants.APPSCALE_SENSOR)
    archive.close()

    try:
      logging.info("Deploying the sensor app for registered deployments.")
      acc = appscale_info.get_appcontroller_client()
      acc.upload_app(app_dir_location, constants.FILE_SUFFIX,
                     constants.USER_EMAIL)
    except AppControllerException:
      logging.exception("AppControllerException while trying to deploy "
        "appscalesensor app.")
  else:
    logging.error("Error while creating or accessing the user to deploy "
      "appscalesensor app.")


def create_appscale_user(password, uaserver):
  """ Creates the user account with the email address and password provided. """
  if uaserver.does_user_exist(constants.USER_EMAIL):
    logging.debug("User {0} already exists, so not creating it again.".
                  format(constants.USER_EMAIL))
    return True

  try:
    uaserver.commit_new_user(constants.USER_EMAIL, password,
                             constants.ACCOUNT_TYPE)
    return True
  except UAException as error:
    logging.error('Error while creating an Appscale user: {}'.format(error))
    return False


def create_xmpp_user(password, uaserver):
  """ Creates the XMPP account. If the user's email is a@a.com, then that
  means their XMPP account name is a@login_ip. """
  username_regex = re.compile('\A(.*)@')
  username = username_regex.match(constants.USER_EMAIL).groups()[0]
  xmpp_user = "{0}@{1}".format(username, appscale_info.get_login_ip())
  xmpp_pass = appscale_utils.encrypt_password(xmpp_user, password)
  if uaserver.does_user_exist(xmpp_user):
    logging.debug("XMPP User {0} already exists, so not creating it again.".
      format(xmpp_user))
    return True

  try:
    uaserver.commit_new_user(xmpp_user, xmpp_pass,
                             constants.ACCOUNT_TYPE)
    logging.info("XMPP username is {0}".format(xmpp_user))
    return True
  except UAException as error:
    logging.error('Error while creating an XMPP user: {}'.format(error))
    return False


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
  if constants.DEBUG:
    logging_level = logging.DEBUG
  logging.getLogger().setLevel(logging_level)

  signal.signal(signal.SIGTERM, signal_handler)
  signal.signal(signal.SIGINT, signal_handler)

  parse_command_line()

  logging.info("Hermes is up and listening on port: {0}.".
    format(options.port))

  master = appscale_info.get_private_ip() == appscale_info.get_headnode_ip()

  if master:
    # Periodically checks if the deployment is registered and uploads the
    # appscalesensor app for registered deployments.
    PeriodicCallback(deploy_sensor_app,
                     constants.UPLOAD_SENSOR_INTERVAL).start()

    # Periodically check with the portal for new tasks.
    # Note: Currently, any active handlers from the tornado app will block
    # polling until they complete.
    PeriodicCallback(poll, constants.POLLING_INTERVAL).start()

  app = tornado.web.Application([
    ("/", MainHandler),
    ("/do_task", TaskHandler),
  ], debug=False)

  try:
    app.listen(options.port)
  except socket.error:
    logging.error("ERROR on Hermes initialization: Port {0} already in use.".
      format(options.port))
    shutdown()
    return

  # Start loop for accepting http requests.
  IOLoop.instance().start()

if __name__ == "__main__":
  main()
