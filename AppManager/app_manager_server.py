""" This service starts and stops application servers of a given application. """

import errno
import logging
import math
import os
import re
import sys
import threading
import time
import urllib
import urllib2

import psutil
import tornado.web
from concurrent.futures import ThreadPoolExecutor
from kazoo.client import KazooClient
from tornado import gen
from tornado.escape import json_decode
from tornado.httpclient import HTTPClient
from tornado.httpclient import HTTPError
from tornado.ioloop import IOLoop
from tornado.options import options

from appscale.admin.constants import UNPACK_ROOT
from appscale.admin.instance_manager.constants import (
  APP_LOG_SIZE,
  DASHBOARD_LOG_SIZE,
  DASHBOARD_PROJECT_ID,
  DEFAULT_MAX_MEMORY,
  INSTANCE_CLASSES,
  LOGROTATE_CONFIG_DIR,
  MAX_BACKGROUND_WORKERS,
  MAX_INSTANCE_RESPONSE_TIME,
  MONIT_INSTANCE_PREFIX
)
from appscale.admin.instance_manager.projects_manager import (
  GlobalProjectsManager)
from appscale.admin.instance_manager.source_manager import SourceManager
from appscale.admin.instance_manager.stop_instance import stop_instance
from appscale.admin.instance_manager.utils import find_web_inf
from appscale.common import (
  appscale_info,
  constants,
  file_io,
  monit_app_configuration,
  monit_interface,
  misc
)
from appscale.common.constants import HTTPCodes
from appscale.common.constants import VERSION_PATH_SEPARATOR
from appscale.common.deployment_config import ConfigInaccessible
from appscale.common.deployment_config import DeploymentConfig
from appscale.common.monit_app_configuration import MONIT_CONFIG_DIR
from appscale.common.monit_interface import MonitOperator
from appscale.common.monit_interface import ProcessNotFound
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.appcontroller_client import AppControllerClient

# The amount of seconds to wait for an application to start up.
START_APP_TIMEOUT = 180

# The amount of seconds to wait between checking if an application is up.
BACKOFF_TIME = 1

# The PID number to return when a process did not start correctly
BAD_PID = -1

# Default hourly cron directory.
CRON_HOURLY = '/etc/cron.hourly'

# The web path to fetch to see if the application is up
FETCH_PATH = '/_ah/health_check'

# Apps which can access any application's data.
TRUSTED_APPS = ["appscaledashboard"]

# The flag to tell the application server that this application can access
# all application data.
TRUSTED_FLAG = "--trusted"

# The location on the filesystem where the PHP executable is installed.
PHP_CGI_LOCATION = "/usr/bin/php-cgi"

# The location of the App Engine SDK for Go.
GO_SDK = os.path.join('/', 'opt', 'go_appengine')

HTTP_OK = 200

# The amount of seconds to wait before retrying to add routing.
ROUTING_RETRY_INTERVAL = 5

PIDFILE_TEMPLATE = os.path.join('/', 'var', 'run', 'appscale',
                                'app___{revision}-{port}.pid')

# A DeploymentConfig accessor.
deployment_config = None

# A GlobalProjectsManager watch.
projects_manager = None

# An interface for working with Monit.
monit_operator = MonitOperator()

# Fetches, extracts, and keeps track of revision source code.
source_manager = None

# Allows synchronous code to be executed in the background.
thread_pool = None


class BadConfigurationException(Exception):
  """ An application is configured incorrectly. """
  def __init__(self, value):
    Exception.__init__(self, value)
    self.value = value

  def __str__(self):
    return repr(self.value)

class NoRedirection(urllib2.HTTPErrorProcessor):
  """ A url opener that does not automatically redirect. """
  def http_response(self, request, response):
    """ Processes HTTP responses.

    Args:
      request: An HTTP request object.
      response: An HTTP response object.
    Returns:
      The HTTP response object.
    """
    return response
  https_response = http_response


def add_routing(version_key, port):
  """ Tells the AppController to begin routing traffic to an AppServer.

  Args:
    version_key: A string that contains the version key.
    port: A string that contains the port that the AppServer listens on.
  """
  logging.info('Waiting for {}:{}'.format(version_key, port))
  if not wait_on_app(port):
    # In case the AppServer fails we let the AppController to detect it
    # and remove it if it still show in monit.
    logging.warning('{}:{} did not come up in time'.format(version_key, port))
    return

  acc = appscale_info.get_appcontroller_client()

  while True:
    result = acc.add_routing_for_appserver(version_key, options.private_ip,
                                           port)
    if result == AppControllerClient.NOT_READY:
      logging.info('AppController not yet ready to add routing.')
      time.sleep(ROUTING_RETRY_INTERVAL)
    else:
      break

  logging.info(
    'Successfully established routing for {}:{}'.format(version_key, port))

@gen.coroutine
def start_app(version_key, config):
  """ Starts a Google App Engine application on this machine. It
      will start it up and then proceed to fetch the main page.

  Args:
    version_key: A string specifying a version key.
    config: a dictionary that contains
      app_port: An integer specifying the port to use.
  """
  if 'app_port' not in config:
    raise BadConfigurationException('app_port is required')

  project_id, service_id, version_id = version_key.split(
    VERSION_PATH_SEPARATOR)

  if not misc.is_app_name_valid(project_id):
    raise BadConfigurationException(
      'Invalid project ID: {}'.format(project_id))

  try:
    service_manager = projects_manager[project_id][service_id]
    version_details = service_manager[version_id].version_details
  except KeyError:
    raise BadConfigurationException('Version not found')

  runtime = version_details['runtime']
  env_vars = version_details.get('envVariables', {})
  runtime_params = deployment_config.get_config('runtime_parameters')
  max_memory = runtime_params.get('max_memory', DEFAULT_MAX_MEMORY)
  if 'instanceClass' in version_details:
    max_memory = INSTANCE_CLASSES.get(version_details['instanceClass'],
                                      max_memory)

  version_key = VERSION_PATH_SEPARATOR.join(
    [project_id, service_id, version_id])
  revision_key = VERSION_PATH_SEPARATOR.join(
    [project_id, service_id, version_id, str(version_details['revision'])])
  source_archive = version_details['deployment']['zip']['sourceUrl']

  yield source_manager.ensure_source(revision_key, source_archive, runtime)

  logging.info('Starting {} application {}'.format(runtime, project_id))

  pidfile = PIDFILE_TEMPLATE.format(revision=revision_key,
                                    port=config['app_port'])

  if runtime == constants.GO:
    env_vars['GOPATH'] = os.path.join(UNPACK_ROOT, revision_key, 'gopath')
    env_vars['GOROOT'] = os.path.join(GO_SDK, 'goroot')

  watch = ''.join([MONIT_INSTANCE_PREFIX, revision_key])

  if runtime in (constants.PYTHON27, constants.GO, constants.PHP):
    start_cmd = create_python27_start_cmd(
      project_id,
      options.login_ip,
      config['app_port'],
      pidfile,
      revision_key)
    env_vars.update(create_python_app_env(
      options.login_ip,
      project_id))
  elif runtime == constants.JAVA:
    # Account for MaxPermSize (~170MB), the parent process (~50MB), and thread
    # stacks (~20MB).
    max_heap = max_memory - 250
    if max_heap <= 0:
      raise BadConfigurationException(
        'Memory for Java applications must be greater than 250MB')

    start_cmd = create_java_start_cmd(
      project_id,
      config['app_port'],
      options.login_ip,
      max_heap,
      pidfile,
      revision_key
    )

    env_vars.update(create_java_app_env(project_id))
  else:
    raise BadConfigurationException(
      'Unknown runtime {} for {}'.format(runtime, project_id))

  logging.info("Start command: " + str(start_cmd))
  logging.info("Environment variables: " + str(env_vars))

  monit_app_configuration.create_config_file(
    watch,
    start_cmd,
    pidfile,
    config['app_port'],
    env_vars,
    max_memory,
    options.syslog_server,
    check_port=True)

  # We want to tell monit to start the single process instead of the
  # group, since monit can get slow if there are quite a few processes in
  # the same group.
  full_watch = '{}-{}'.format(watch, config['app_port'])
  assert monit_interface.start(full_watch, is_group=False), (
    'Monit was unable to start {}:{}'.format(project_id, config['app_port']))

  # Since we are going to wait, possibly for a long time for the
  # application to be ready, we do it in a thread.
  threading.Thread(target=add_routing,
    args=(version_key, config['app_port'])).start()

  if project_id == DASHBOARD_PROJECT_ID:
    log_size = DASHBOARD_LOG_SIZE
  else:
    log_size = APP_LOG_SIZE

  if not setup_logrotate(project_id, log_size):
    logging.error("Error while setting up log rotation for application: {}".
      format(project_id))

def setup_logrotate(app_name, log_size):
  """ Creates a logrotate script for the logs that the given application
      will create.

  Args:
    app_name: A string, the application ID.
    log_size: An integer, the size of logs that are kept per application server.
      The size should be in bytes.
  Returns:
    True on success, False otherwise.
  """
  # Write application specific logrotation script.
  app_logrotate_script = "{0}/appscale-{1}".\
    format(LOGROTATE_CONFIG_DIR, app_name)

  log_prefix = ''.join([MONIT_INSTANCE_PREFIX, app_name])

  # Application logrotate script content.
  contents = """/var/log/appscale/{log_prefix}*.log {{
  size {size}
  missingok
  rotate 7
  compress
  delaycompress
  notifempty
  copytruncate
}}
""".format(log_prefix=log_prefix, size=log_size)
  logging.debug("Logrotate file: {} - Contents:\n{}".
    format(app_logrotate_script, contents))

  with open(app_logrotate_script, 'w') as app_logrotate_fd:
    app_logrotate_fd.write(contents)

  return True

def unmonitor(process_name, retries=5):
  """ Unmonitors a process.

  Args:
    process_name: A string specifying the process to stop monitoring.
    retries: An integer specifying the number of times to retry the operation.
  """
  client = HTTPClient()
  process_url = '{}/{}'.format(monit_operator.LOCATION, process_name)
  payload = urllib.urlencode({'action': 'unmonitor'})
  try:
    client.fetch(process_url, method='POST', body=payload)
  except HTTPError as error:
    if error.code == 404:
      raise ProcessNotFound('{} not listed by Monit'.format(process_name))

    if error.code == 503:
      retries -= 1
      if retries < 0:
        raise

      return unmonitor(process_name, retries)

    raise

@gen.coroutine
def clean_old_sources():
  """ Removes source code for obsolete revisions. """
  monit_entries = yield monit_operator.get_entries()
  active_revisions = {
    entry[len(MONIT_INSTANCE_PREFIX):].rsplit('-', 1)[0]
    for entry in monit_entries
    if entry.startswith(MONIT_INSTANCE_PREFIX)}

  for project_id, project_manager in projects_manager.items():
    for service_id, service_manager in project_manager.items():
      for version_id, version_manager in service_manager.items():
        revision_id = version_manager.version_details['revision']
        revision_key = VERSION_PATH_SEPARATOR.join(
          [project_id, service_id, version_id, str(revision_id)])
        active_revisions.add(revision_key)

  source_manager.clean_old_revisions(active_revisions=active_revisions)

@gen.coroutine
def unmonitor_and_terminate(watch):
  """ Unmonitors an instance and terminates it.

  Args:
    watch: A string specifying the Monit entry.
  """
  try:
    unmonitor(watch)
  except ProcessNotFound:
    # If Monit does not know about a process, assume it is already stopped.
    raise gen.Return()

  # Now that the AppServer is stopped, remove its monit config file so that
  # monit doesn't pick it up and restart it.
  monit_config_file = '{}/appscale-{}.cfg'.format(MONIT_CONFIG_DIR, watch)
  try:
    os.remove(monit_config_file)
  except OSError:
    logging.error("Error deleting {0}".format(monit_config_file))

  IOLoop.current().spawn_callback(stop_instance, watch,
                                  MAX_INSTANCE_RESPONSE_TIME)

@gen.coroutine
def stop_app_instance(version_key, port):
  """ Stops a Google App Engine application process instance on current
      machine.

  Args:
    version_key: A string, the name of version to stop.
    port: The port the application is running on.
  Returns:
    True on success, False otherwise.
  """
  project_id = version_key.split(VERSION_PATH_SEPARATOR)[0]

  if not misc.is_app_name_valid(project_id):
    raise BadConfigurationException(
      'Invalid project ID: {}'.format(project_id))

  logging.info('Stopping {}:{}'.format(version_key, port))

  # Discover revision key from version and port.
  instance_key_re = re.compile(
    '{}{}.*-{}'.format(MONIT_INSTANCE_PREFIX, version_key, port))
  monit_entries = yield monit_operator.get_entries()
  try:
    watch = next(entry for entry in monit_entries
                 if instance_key_re.match(entry))
  except StopIteration:
    message = 'No entries exist for {}:{}'.format(version_key, port)
    raise HTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

  yield unmonitor_and_terminate(watch)

  yield monit_operator.reload()
  yield clean_old_sources()

@gen.coroutine
def stop_app(version_key):
  """ Stops all process instances of a version on this machine.

  Args:
    version_key: Name of version to stop
  Returns:
    True on success, False otherwise
  """
  project_id = version_key.split(VERSION_PATH_SEPARATOR)[0]

  if not misc.is_app_name_valid(project_id):
    raise BadConfigurationException(
      'Invalid project ID: {}'.format(project_id))

  logging.info('Stopping {}'.format(version_key))

  version_group = ''.join([MONIT_INSTANCE_PREFIX, version_key])
  monit_entries = yield monit_operator.get_entries()
  version_entries = [entry for entry in monit_entries
                     if entry.startswith(version_group)]
  for entry in version_entries:
    yield unmonitor_and_terminate(entry)

  if project_id not in projects_manager and not remove_logrotate(project_id):
    logging.error("Error while removing log rotation for application: {}".
                  format(project_id))

  yield monit_operator.reload()
  yield clean_old_sources()

def remove_logrotate(app_name):
  """ Removes logrotate script for the given application.

  Args:
    app_name: A string, the name of the application to remove logrotate for.
  Returns:
    True on success, False otherwise.
  """
  app_logrotate_script = "{0}/appscale-{1}".\
    format(LOGROTATE_CONFIG_DIR, app_name)
  logging.debug("Removing script: {}".format(app_logrotate_script))

  try:
    os.remove(app_logrotate_script)
  except OSError:
    logging.error("Error deleting {0}".format(app_logrotate_script))
    return False

  return True

############################################
# Private Functions (but public for testing)
############################################
def wait_on_app(port):
  """ Waits for the application hosted on this machine, on the given port,
      to respond to HTTP requests.

  Args:
    port: Port where app is hosted on the local machine
  Returns:
    True on success, False otherwise
  """
  retries = math.ceil(START_APP_TIMEOUT / BACKOFF_TIME)

  url = "http://" + options.private_ip + ":" + str(port) + FETCH_PATH
  while retries > 0:
    try:
      opener = urllib2.build_opener(NoRedirection)
      response = opener.open(url)
      if response.code != HTTP_OK:
        logging.warning('{} returned {}. Headers: {}'.
          format(url, response.code, response.headers.headers))
      return True
    except IOError:
      retries -= 1

    time.sleep(BACKOFF_TIME)

  logging.error('Application did not come up on {} after {} seconds'.
    format(url, START_APP_TIMEOUT))
  return False

def create_python_app_env(public_ip, app_name):
  """ Returns the environment variables the python application server uses.

  Args:
    public_ip: The public IP of the load balancer
    app_name: The name of the application to be run
  Returns:
    A dictionary containing the environment variables
  """
  env_vars = {}
  env_vars['MY_IP_ADDRESS'] = public_ip
  env_vars['APPNAME'] = app_name
  env_vars['GOMAXPROCS'] = appscale_info.get_num_cpus()
  env_vars['APPSCALE_HOME'] = constants.APPSCALE_HOME
  env_vars['PYTHON_LIB'] = "{0}/AppServer/".format(constants.APPSCALE_HOME)
  return env_vars

def create_java_app_env(app_name):
  """ Returns the environment variables Java application servers uses.

  Args:
    app_name: A string containing the application ID.
  Returns:
    A dictionary containing the environment variables
  """
  env_vars = {'APPSCALE_HOME': constants.APPSCALE_HOME}

  gcs_config = {'scheme': 'https', 'port': 443}
  try:
    gcs_config.update(deployment_config.get_config('gcs'))
  except ConfigInaccessible:
    logging.warning('Unable to fetch GCS configuration.')

  if 'host' in gcs_config:
    env_vars['GCS_HOST'] = '{scheme}://{host}:{port}'.format(**gcs_config)

  return env_vars

def create_python27_start_cmd(app_name, login_ip, port, pidfile, revision_key):
  """ Creates the start command to run the python application server.

  Args:
    app_name: The name of the application to run
    login_ip: The public IP of this deployment
    port: The local port the application server will bind to
    pidfile: A string specifying the pidfile location.
    revision_key: A string specifying the revision key.
  Returns:
    A string of the start command.
  """
  source_directory = os.path.join(UNPACK_ROOT, revision_key, 'app')

  cmd = [
    "/usr/bin/python2",
    constants.APPSCALE_HOME + "/AppServer/dev_appserver.py",
    "--port " + str(port),
    "--admin_port " + str(port + 10000),
    "--login_server " + login_ip,
    "--skip_sdk_update_check",
    "--nginx_host " + str(login_ip),
    "--require_indexes",
    "--enable_sendmail",
    "--xmpp_path " + login_ip,
    "--php_executable_path=" + str(PHP_CGI_LOCATION),
    "--uaserver_path " + options.db_proxy + ":"\
      + str(constants.UA_SERVER_PORT),
    "--datastore_path " + options.db_proxy + ":"\
      + str(constants.DB_SERVER_PORT),
    source_directory,
    "--host " + options.private_ip,
    "--admin_host " + options.private_ip,
    "--automatic_restart", "no",
    "--pidfile", pidfile]

  if app_name in TRUSTED_APPS:
    cmd.extend([TRUSTED_FLAG])

  return ' '.join(cmd)

def locate_dir(path, dir_name):
  """ Locates a directory inside the given path.

  Args:
    path: The path to be searched
    dir_name: The directory we are looking for

  Returns:
    The absolute path of the directory we are looking for, None otherwise.
  """
  paths = []

  for root, sub_dirs, files in os.walk(path):
    for sub_dir in sub_dirs:
      if dir_name == sub_dir:
        result = os.path.abspath(os.path.join(root, sub_dir))
        if sub_dir == "WEB-INF":
          logging.info("Found WEB-INF/ at: {0}".format(result))
          paths.append(result)
        elif sub_dir == "lib" and result.count(os.sep) <= path.count(os.sep) + 2 \
            and result.endswith("/WEB-INF/{0}".format(sub_dir)):
          logging.info("Found lib/ at: {0}".format(result))
          paths.append(result)

  if len(paths) > 0:
    sorted_paths = sorted(paths, key = lambda s: len(s))
    return sorted_paths[0]
  else:
    return None

def create_java_start_cmd(app_name, port, load_balancer_host, max_heap,
                          pidfile, revision_key):
  """ Creates the start command to run the java application server.

  Args:
    app_name: The name of the application to run
    port: The local port the application server will bind to
    load_balancer_host: The host of the load balancer
    max_heap: An integer specifying the max heap size in MB.
    pidfile: A string specifying the pidfile location.
    revision_key: A string specifying the revision key.
  Returns:
    A string of the start command.
  """
  java_start_script = os.path.join(
    constants.JAVA_APPSERVER, 'appengine-java-sdk-repacked', 'bin',
    'dev_appserver.sh')
  revision_base = os.path.join(UNPACK_ROOT, revision_key)
  web_inf_directory = find_web_inf(revision_base)

  # The Java AppServer needs the NGINX_PORT flag set so that it will read the
  # local FS and see what port it's running on. The value doesn't matter.
  cmd = [
    java_start_script,
    "--port=" + str(port),
    #this jvm flag allows javax.email to connect to the smtp server
    "--jvm_flag=-Dsocket.permit_connect=true",
    '--jvm_flag=-Xmx{}m'.format(max_heap),
    '--jvm_flag=-Djava.security.egd=file:/dev/./urandom',
    "--disable_update_check",
    "--address=" + options.private_ip,
    "--datastore_path=" + options.db_proxy,
    "--login_server=" + load_balancer_host,
    "--appscale_version=1",
    "--APP_NAME=" + app_name,
    "--NGINX_ADDRESS=" + load_balancer_host,
    "--TQ_PROXY=" + options.tq_proxy,
    "--pidfile={}".format(pidfile),
    os.path.dirname(web_inf_directory)
  ]

  return ' '.join(cmd)


class VersionHandler(tornado.web.RequestHandler):
  """ Handles requests to start and stop instances for a project. """
  @gen.coroutine
  def post(self, version_key):
    """ Starts an AppServer instance on this machine.

    Args:
      version_key: A string specifying a version key.
    """
    try:
      config = json_decode(self.request.body)
    except ValueError:
      raise HTTPError(HTTPCodes.BAD_REQUEST, 'Payload must be valid JSON')

    try:
      yield start_app(version_key, config)
    except BadConfigurationException as error:
      raise HTTPError(HTTPCodes.BAD_REQUEST, error.message)

  @staticmethod
  @gen.coroutine
  def delete(version_key):
    """ Stops all instances on this machine for a version.

    Args:
      version_key: A string specifying a version key.
    """
    try:
      yield stop_app(version_key)
    except BadConfigurationException as error:
      raise HTTPError(HTTPCodes.BAD_REQUEST, error.message)


class InstanceHandler(tornado.web.RequestHandler):
  """ Handles requests to stop individual instances. """

  @staticmethod
  @gen.coroutine
  def delete(version_key, port):
    """ Stops an AppServer instance on this machine. """
    try:
      yield stop_app_instance(version_key, int(port))
    except BadConfigurationException as error:
      raise HTTPError(HTTPCodes.BAD_REQUEST, error.message)


################################
# MAIN
################################
if __name__ == "__main__":
  file_io.set_logging_format()
  logging.getLogger().setLevel(logging.INFO)

  zk_ips = appscale_info.get_zk_node_ips()
  zk_client = KazooClient(hosts=','.join(zk_ips))
  zk_client.start()
  deployment_config = DeploymentConfig(zk_client)
  projects_manager = GlobalProjectsManager(zk_client)
  thread_pool = ThreadPoolExecutor(MAX_BACKGROUND_WORKERS)
  source_manager = SourceManager(zk_client, thread_pool)

  options.define('private_ip', appscale_info.get_private_ip())
  options.define('login_ip', appscale_info.get_login_ip())
  options.define('syslog_server', appscale_info.get_headnode_ip())
  options.define('db_proxy', appscale_info.get_db_proxy())
  options.define('tq_proxy', appscale_info.get_tq_proxy())

  app = tornado.web.Application([
    ('/versions/([a-z0-9-_]+)', VersionHandler),
    ('/versions/([a-z0-9-_]+)/([0-9-]+)', InstanceHandler)
  ])

  app.listen(constants.APP_MANAGER_PORT)
  logging.info('Starting AppManager on {}'.format(constants.APP_MANAGER_PORT))
  IOLoop.current().start()
