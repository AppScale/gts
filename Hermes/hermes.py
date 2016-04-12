""" Web server/client that polls the AppScale Portal for new tasks and
initiates actions accordingly. """

import datetime
import hashlib
import json
import logging
import os
import random
import re
import signal
import SOAPpy
import socket
import string
import sys
import tarfile
import tornado.escape
import tornado.httpclient
import tornado.web
import urllib

from tornado.ioloop import IOLoop
from tornado.ioloop import PeriodicCallback
from tornado.options import define
from tornado.options import options
from tornado.options import parse_command_line

sys.path.append(os.path.join(os.path.dirname(__file__), '../AppServer'))
from google.appengine.api.appcontroller_client import AppControllerException
from google.appengine.api import users

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

import hermes_constants
import helper
from handlers import MainHandler
from handlers import TaskHandler
from helper import JSONTags

# Tornado web server options.
define("port", default=hermes_constants.HERMES_PORT, type=int)

# The port that the SOAP server listens to.
UA_SERVER_PORT = 4343

USER_EMAIL = "appscale_user@appscale.local"

DEFAULT_PASSWORD = "appscale"

ACCOUNT_TYPE = "user"

PASSWORD_SIZE = 6

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
  portal_path = hermes_constants.PORTAL_STATS_PATH.format(deployment_id)
  url = "{0}{1}".format(hermes_constants.PORTAL_URL, portal_path)
  data = {
    JSONTags.DEPLOYMENT_ID: deployment_id,
    JSONTags.TIMESTAMP: datetime.datetime.utcnow(),
    JSONTags.ALL_STATS: json.dumps(all_stats)
  }
  logging.debug("Sending all stats to the AppScale Portal. Data: \n{}".
    format(data))

  request = helper.create_request(url=url, method='POST',
    body=urllib.urlencode(data))
  response = helper.urlfetch(request)

  if not response[JSONTags.SUCCESS]:
    logging.error("Inaccessible resource: {}".format(url))
    return

def deploy_sensor_app():
  """ Uploads the sensor app for registered deployments."""

  deployment_id = helper.get_deployment_id()
  #If deployment is not registered, then do nothing.
  #if not deployment_id:
    #return

  uaserver = SOAPpy.SOAPProxy('https://{0}:{1}'.format(
    appscale_info.get_db_master_ip(), UA_SERVER_PORT))

  password = encrypt_password(USER_EMAIL, random_password_generator())
  if create_appscale_user(password, uaserver) and create_xmpp_user(password, uaserver):
    logging.warn("Created new users and now deploying app...")
    file_path = os.path.join(os.path.dirname(__file__), '../Apps/sensor')
    file_suffix = 'tar.gz'
    app_dir_location = os.path.join(hermes_constants.APP_DIR_LOCATION, 'sensor')

    archive = tarfile.open(app_dir_location, "w|gz")
    archive.add(file_path, arcname="sensor")
    archive.close()

    try:
      logging.warn("Deploying the sensor app for registered deployments.")
      acc = appscale_info.get_appcontroller_client()
      return acc.upload_app(app_dir_location, file_suffix, USER_EMAIL)

    except AppControllerException:
      logging.exception("AppControllerException while trying to upload "
        "sensor app.")
  else:
    logging.warn("Error while creating a new user or accessing existing user.")

def create_appscale_user(password, uaserver):
  does_user_exist = uaserver.does_user_exist(USER_EMAIL, appscale_info.get_secret())
  if does_user_exist == "true":
    logging.warn("User {0} already exists, so not creating it again.".
      format(USER_EMAIL))
    return True
  else:
    if uaserver.commit_new_user(USER_EMAIL, password, ACCOUNT_TYPE, appscale_info.get_secret()) == "true":
      return True
    else:
      logging.warn("Appscale user was not created.")
      return False

def create_xmpp_user(password, uaserver):
  # Create the XMPP account. If the user's email is a@a.com, then that
  # means their XMPP account name is a@login_ip
  username_regex = re.compile('\A(.*)@')
  username = username_regex.match(USER_EMAIL).groups()[0]
  xmpp_user = "{0}@{1}".format(username, appscale_info.get_login_ip())
  xmpp_pass = encrypt_password(xmpp_user, password)
  does_user_exist = uaserver.does_user_exist(xmpp_user, appscale_info.get_secret())
  if does_user_exist == "true":
    logging.warn("XMPP User {0} already exists, so not creating it again.".
      format(xmpp_user))
    return True
  else:
    if uaserver.commit_new_user(xmpp_user, xmpp_pass, ACCOUNT_TYPE, appscale_info.get_secret()) == "true":
      logging.warn("XMPP username is {0}".format(xmpp_user))
      return True
    else:
      logging.warn("XMPP user not created.")
      return False

def random_password_generator():
  """ Generates a random six character password with letters and digits. """
  characters = string.letters + string.digits
  pwdSize = PASSWORD_SIZE
  return ''.join((random.choice(characters)) for x in range(pwdSize))

def encrypt_password(username, password):
  return hashlib.sha1(username + password).hexdigest()

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
