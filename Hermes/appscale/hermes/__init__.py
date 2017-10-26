""" Web server/client that polls the AppScale Portal for new tasks and
initiates actions accordingly. """

import argparse
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
from appscale.admin.constants import DEFAULT_SERVICE
from appscale.admin.constants import DEFAULT_VERSION
from appscale.common import appscale_info, appscale_utils
from appscale.common.constants import LOG_FORMAT, ZK_PERSISTENT_RECONNECTS
from appscale.common.ua_client import UAClient, UAException
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from kazoo.client import KazooClient
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.options import options

from appscale.hermes import constants, helper
from appscale.hermes.handlers import MainHandler, TaskHandler, Respond404Handler
from appscale.hermes.helper import JSONTags
from appscale.hermes.stats import stats_app
from appscale.hermes.stats import constants as stats_constants


sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.appcontroller_client import AppControllerException

# A KazooClient for detecting configuration changes.
zk_client = None


class SensorDeployer(object):
  """ Uploads the sensor app for registered deployments. """
  def __init__(self, zk_client):
    """ Creates new SensorDeployer object.

    Args:
      zk_client: A KazooClient.
    """
    self.zk_client = zk_client

  def deploy(self):
    """ Uploads the sensor app for registered deployments. """
    deployment_id = helper.get_deployment_id()
    # If deployment is not registered, then do nothing.
    if not deployment_id:
      return

    ua_client = UAClient(appscale_info.get_db_master_ip(), options.secret)

    # If the appscalesensor app is already running, then do nothing.
    version_node = '/appscale/projects/{}/services/{}/versions/{}'.format(
      constants.APPSCALE_SENSOR, DEFAULT_SERVICE, DEFAULT_VERSION)
    if self.zk_client.exists(version_node) is not None:
      return

    pwd = appscale_utils.encrypt_password(constants.USER_EMAIL,
                                          appscale_utils.random_password_generator())
    if create_appscale_user(pwd, ua_client) and create_xmpp_user(pwd,
                                                                 ua_client):
      logging.debug("Created new user and now tarring app to be deployed.")
      file_path = os.path.join(os.path.dirname(__file__), '../Apps/sensor')
      app_dir_location = os.path.join(constants.APP_DIR_LOCATION,
                                      constants.APPSCALE_SENSOR)
      archive = tarfile.open(app_dir_location, "w|gz")
      archive.add(file_path, arcname=constants.APPSCALE_SENSOR)
      archive.close()

      try:
        logging.info("Deploying the sensor app for registered deployments.")
        acc = appscale_info.get_appcontroller_client()
        acc.upload_app(app_dir_location, constants.FILE_SUFFIX)
      except AppControllerException:
        logging.exception("AppControllerException while trying to deploy "
                          "appscalesensor app.")
    else:
      logging.error("Error while creating or accessing the user to deploy "
                    "appscalesensor app.")


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
  url = "http://localhost:{}{}".format(constants.HERMES_PORT, '/do_task')
  request = helper.create_request(url, method='POST', body=json.dumps(data))

  # The poller can move forward without waiting for a response here.
  helper.urlfetch_async(request)


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
  zk_client.stop()
  IOLoop.instance().add_callback(shutdown)


def shutdown():
  """ Shuts down the server. """
  logging.warning("Hermes is shutting down.")
  IOLoop.instance().stop()


def main():
  """ Main. """
  parser = argparse.ArgumentParser()
  parser.add_argument(
    '-v', '--verbose', action='store_true',
    help='Output debug-level logging')
  args = parser.parse_args()

  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  if args.verbose:
    logging.getLogger().setLevel(logging.DEBUG)

  options.define('secret', appscale_info.get_secret())

  signal.signal(signal.SIGTERM, signal_handler)
  signal.signal(signal.SIGINT, signal_handler)

  my_ip = appscale_info.get_private_ip()
  is_master = (my_ip == appscale_info.get_headnode_ip())
  is_lb = (my_ip in appscale_info.get_load_balancer_ips())

  if is_master:
    # Periodically check with the portal for new tasks.
    # Note: Currently, any active handlers from the tornado app will block
    # polling until they complete.
    PeriodicCallback(poll, constants.POLLING_INTERVAL).start()

    # Only master Hermes node handles /do_task route
    task_route = ('/do_task', TaskHandler)

    global zk_client
    zk_client = KazooClient(
      hosts=','.join(appscale_info.get_zk_node_ips()),
      connection_retry=ZK_PERSISTENT_RECONNECTS)
    zk_client.start()
    # Start watching profiling configs in ZooKeeper
    stats_app.ProfilingManager(zk_client)

    # Periodically checks if the deployment is registered and uploads the
    # appscalesensor app for registered deployments.
    sensor_deployer = SensorDeployer(zk_client)
    PeriodicCallback(sensor_deployer.deploy,
                     constants.UPLOAD_SENSOR_INTERVAL).start()
  else:
    task_route = ('/do_task', Respond404Handler,
                  dict(reason='Hermes slaves do not manage tasks from Portal'))

  app = tornado.web.Application([
      ("/", MainHandler),
      task_route,
    ]
    + stats_app.get_local_stats_api_routes(is_lb)
    + stats_app.get_cluster_stats_api_routes(is_master),
    debug=False
  )
  app.listen(constants.HERMES_PORT)

  # Start loop for accepting http requests.
  IOLoop.instance().start()

  logging.info("Hermes is up and listening on port: {}."
               .format(constants.HERMES_PORT))
