""" This service starts and stops application servers of a given application. """

import fnmatch
import glob
import logging
import math
import os
import shutil
import subprocess
import sys
import threading
import time
import urllib
import urllib2
from xml.etree import ElementTree

import psutil
import tornado.web
from kazoo.client import KazooClient
from tornado.escape import json_decode
from tornado.httpclient import HTTPClient
from tornado.httpclient import HTTPError
from tornado.ioloop import IOLoop
from tornado.options import options

from appscale.common import (
  appscale_info,
  constants,
  file_io,
  monit_app_configuration,
  monit_interface,
  misc
)
from appscale.common.constants import HTTPCodes
from appscale.common.deployment_config import ConfigInaccessible
from appscale.common.deployment_config import DeploymentConfig
from appscale.common.monit_app_configuration import MONIT_CONFIG_DIR
from appscale.common.monit_interface import MonitOperator
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

# Default logrotate configuration directory.
LOGROTATE_CONFIG_DIR = '/etc/logrotate.d'

# Max log size for AppScale Dashboard servers.
DASHBOARD_LOG_SIZE = 10 * 1024 * 1024

# Max application server log size in bytes.
APP_LOG_SIZE = 250 * 1024 * 1024

# Required configuration fields for starting an application
REQUIRED_CONFIG_FIELDS = [
  'app_name',
  'app_port',
  'language',
  'login_ip',
  'env_vars',
  'max_memory']

# The web path to fetch to see if the application is up
FETCH_PATH = '/_ah/health_check'

# The app ID of the AppScale Dashboard.
APPSCALE_DASHBOARD_ID = "appscaledashboard"

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
                                'app___{project}-{port}.pid')

# The number of seconds an instance is allowed to finish serving requests after
# it receives a shutdown signal.
MAX_INSTANCE_RESPONSE_TIME = 600

# A DeploymentConfig accessor.
deployment_config = None

# An interface for working with Monit.
monit_operator = MonitOperator()


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


def add_routing(app, port):
  """ Tells the AppController to begin routing traffic to an AppServer.

  Args:
    app: A string that contains the application ID.
    port: A string that contains the port that the AppServer listens on.
  """
  logging.info("Waiting for application {} on port {} to be active.".
    format(str(app), str(port)))
  if not wait_on_app(port):
    # In case the AppServer fails we let the AppController to detect it
    # and remove it if it still show in monit.
    logging.warning("AppServer did not come up in time, for {}:{}.".
      format(str(app), str(port)))
    return

  acc = appscale_info.get_appcontroller_client()

  while True:
    result = acc.add_routing_for_appserver(app, options.private_ip, port)
    if result == AppControllerClient.NOT_READY:
      logging.info('AppController not yet ready to add routing.')
      time.sleep(ROUTING_RETRY_INTERVAL)
    else:
      break

  logging.info('Successfully established routing for {} on port {}'.
    format(app, port))

def start_app(project_id, config):
  """ Starts a Google App Engine application on this machine. It
      will start it up and then proceed to fetch the main page.

  Args:
    project_id: A string specifying a project ID.
    config: a dictionary that contains
       app_port: Port to start on
       language: What language the app is written in
       login_ip: Public ip of deployment
       env_vars: A dict of environment variables that should be passed to the
        app.
       max_memory: An int that names the maximum amount of memory that this
        App Engine app is allowed to consume before being restarted.
       syslog_server: The IP of the syslog server to send the application
         logs to. Usually it's the login private IP.
  Returns:
    PID of process on success, -1 otherwise
  """
  required_params = ('app_port', 'language', 'login_ip', 'env_vars',
                     'max_memory')
  for param in required_params:
    if param not in config:
      logging.error('Missing parameter: {}'.format(param))
      return BAD_PID

  if not misc.is_app_name_valid(project_id):
    logging.error("Invalid app name for application: " + project_id)
    return BAD_PID
  logging.info("Starting %s application %s" % (
    config['language'], project_id))

  env_vars = config['env_vars']
  pidfile = PIDFILE_TEMPLATE.format(project=project_id,
                                    port=config['app_port'])

  if config['language'] == constants.GO:
    env_vars['GOPATH'] = os.path.join('/var', 'apps', project_id, 'gopath')
    env_vars['GOROOT'] = os.path.join(GO_SDK, 'goroot')

  watch = "app___" + project_id
  match_cmd = ""

  if config['language'] == constants.PYTHON27 or \
      config['language'] == constants.GO or \
      config['language'] == constants.PHP:
    start_cmd = create_python27_start_cmd(
      project_id,
      config['login_ip'],
      config['app_port'],
      pidfile)
    stop_cmd = create_python27_stop_cmd(config['app_port'])
    env_vars.update(create_python_app_env(
      config['login_ip'],
      project_id))
  elif config['language'] == constants.JAVA:
    remove_conflicting_jars(project_id)
    copy_successful = copy_modified_jars(project_id)
    if not copy_successful:
      return BAD_PID

    # Account for MaxPermSize (~170MB), the parent process (~50MB), and thread
    # stacks (~20MB).
    max_heap = config['max_memory'] - 250
    if max_heap <= 0:
      return BAD_PID
    start_cmd = create_java_start_cmd(
      project_id,
      config['app_port'],
      config['login_ip'],
      max_heap,
      pidfile
    )
    match_cmd = "java -ea -cp.*--port={}.*{}".format(str(config['app_port']),
      os.path.dirname(locate_dir("/var/apps/" + project_id + "/app/",
      "WEB-INF")))

    stop_cmd = create_java_stop_cmd(config['app_port'])
    env_vars.update(create_java_app_env(project_id))
  else:
    logging.error("Unknown application language %s for appname %s" \
      % (config['language'], project_id))
    return BAD_PID

  logging.info("Start command: " + str(start_cmd))
  logging.info("Stop command: " + str(stop_cmd))
  logging.info("Environment variables: " + str(env_vars))

  # Set the syslog_server is specified.
  syslog_server = ""
  if 'syslog_server' in config:
    syslog_server = config['syslog_server']
  monit_app_configuration.create_config_file(
    watch,
    start_cmd,
    pidfile,
    config['app_port'],
    env_vars,
    config['max_memory'],
    syslog_server,
    check_port=True)

  # We want to tell monit to start the single process instead of the
  # group, since monit can get slow if there are quite a few processes in
  # the same group.
  full_watch = "{}-{}".format(str(watch), str(config['app_port']))
  if not monit_interface.start(full_watch, is_group=False):
    logging.warning("Monit was unable to start {}:{}".
      format(project_id, config['app_port']))
    return BAD_PID

  # Since we are going to wait, possibly for a long time for the
  # application to be ready, we do it in a thread.
  threading.Thread(target=add_routing,
    args=(project_id, config['app_port'])).start()

  if 'log_size' in config.keys():
    log_size = config['log_size']
  else:
    if project_id == APPSCALE_DASHBOARD_ID:
      log_size = DASHBOARD_LOG_SIZE
    else:
      log_size = APP_LOG_SIZE

  if not setup_logrotate(project_id, watch, log_size):
    logging.error("Error while setting up log rotation for application: {}".
      format(project_id))

  return 0

def setup_logrotate(app_name, watch, log_size):
  """ Creates a logrotate script for the logs that the given application
      will create.

  Args:
    app_name: A string, the application ID.
    watch: A string of the form 'app___<app_ID>'.
    log_size: An integer, the size of logs that are kept per application server.
      The size should be in bytes.
  Returns:
    True on success, False otherwise.
  """
  # Write application specific logrotation script.
  app_logrotate_script = "{0}/appscale-{1}".\
    format(LOGROTATE_CONFIG_DIR, app_name)

  # Application logrotate script content.
  contents = """/var/log/appscale/{watch}*.log {{
  size {size}
  missingok
  rotate 7
  compress
  delaycompress
  notifempty
  copytruncate
}}
""".format(watch=watch, size=log_size)
  logging.debug("Logrotate file: {} - Contents:\n{}".
    format(app_logrotate_script, contents))

  with open(app_logrotate_script, 'w') as app_logrotate_fd:
    app_logrotate_fd.write(contents)

  return True

def kill_instance(watch, instance_pid):
  """ Stops an AppServer process.

  Args:
    watch: A string specifying the monit entry for the process.
    instance_pid: An integer specifying the process ID.
  """
  process = psutil.Process(instance_pid)
  process.terminate()
  try:
    process.wait(MAX_INSTANCE_RESPONSE_TIME)
  except psutil.TimeoutExpired:
    process.kill()

  logging.info('Finished stopping {}'.format(watch))

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
    if error.code == 503:
      retries -= 1
      if retries < 0:
        raise

      return unmonitor(process_name, retries)

    raise

def stop_app_instance(app_name, port):
  """ Stops a Google App Engine application process instance on current
      machine.

  Args:
    app_name: A string, the name of application to stop.
    port: The port the application is running on.
  Returns:
    True on success, False otherwise.
  """
  if not misc.is_app_name_valid(app_name):
    logging.error("Unable to kill app process %s on port %d because of " \
      "invalid name for application" % (app_name, int(port)))
    return False

  logging.info("Stopping application %s" % app_name)
  watch = "app___" + app_name + "-" + str(port)

  pid_location = os.path.join(constants.PID_DIR, '{}.pid'.format(watch))
  try:
    with open(pid_location) as pidfile:
      instance_pid = int(pidfile.read().strip())
  except IOError:
    logging.error('{} does not exist'.format(pid_location))
    return False

  unmonitor(watch)

  # Now that the AppServer is stopped, remove its monit config file so that
  # monit doesn't pick it up and restart it.
  monit_config_file = '{}/appscale-{}.cfg'.format(MONIT_CONFIG_DIR, watch)
  try:
    os.remove(monit_config_file)
  except OSError as os_error:
    logging.error("Error deleting {0}".format(monit_config_file))

  monit_interface.run_with_retry([monit_interface.MONIT, 'reload'])
  threading.Thread(target=kill_instance, args=(watch, instance_pid)).start()
  return True


def stop_app(app_name):
  """ Stops all process instances of a Google App Engine application on this
      machine.

  Args:
    app_name: Name of application to stop
  Returns:
    True on success, False otherwise
  """
  if not misc.is_app_name_valid(app_name):
    logging.error("Unable to kill app process %s on because of " \
      "invalid name for application" % (app_name))
    return False

  logging.info("Stopping application %s" % app_name)
  watch = "app___" + app_name
  monit_result = monit_interface.stop(watch)

  if not monit_result:
    logging.error("Unable to shut down monit interface for watch %s" % watch)
    return False

  # Remove the monit config files for the application.
  # TODO: Reload monit to pick up config changes.
  config_files = glob.glob('{}/appscale-{}-*.cfg'.format(MONIT_CONFIG_DIR, watch))
  for config_file in config_files:
    try:
      os.remove(config_file)
    except OSError:
      logging.exception('Error removing {}'.format(config_file))

  if not remove_logrotate(app_name):
    logging.error("Error while setting up log rotation for application: {}".
      format(app_name))

  return True

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

def find_web_xml(app_name):
  """ Returns the location of a Java application's appengine-web.xml file.

  Args:
    app_name: A string containing the application ID.
  Returns:
    A string containing the location of the file.
  Raises:
    BadConfigurationException if the file is not found or multiple candidates
    are found.

  """
  app_dir = '/var/apps/{}/app'.format(app_name)
  file_name = 'appengine-web.xml'
  matches = []
  for root, dirs, files in os.walk(app_dir):
    if file_name in files and root.endswith('/WEB-INF'):
      matches.append(os.path.join(root, file_name))

  if len(matches) < 1:
    raise BadConfigurationException(
      'Unable to find {} file for {}'.format(file_name, app_name))
  if len(matches) > 1:
    # Use the shortest path. If there are any ties, use the first after
    # sorting alphabetically.
    matches.sort()
    match_to_use = matches[0]
    for match in matches:
      if len(match) < len(match_to_use):
        match_to_use = match
    return match_to_use
  return matches[0]

def extract_env_vars_from_xml(xml_file):
  """ Returns any custom environment variables defined in appengine-web.xml.

  Args:
    xml_file: A string containing the location of the xml file.
  Returns:
    A dictionary containing the custom environment variables.
  """
  custom_vars = {}
  tree = ElementTree.parse(xml_file)
  root = tree.getroot()
  for child in root:
    if not child.tag.endswith('env-variables'):
      continue

    for env_var in child:
      var_dict = env_var.attrib
      custom_vars[var_dict['name']] = var_dict['value']

  return custom_vars

def create_java_app_env(app_name):
  """ Returns the environment variables Java application servers uses.

  Args:
    app_name: A string containing the application ID.
  Returns:
    A dictionary containing the environment variables
  """
  env_vars = {'APPSCALE_HOME': constants.APPSCALE_HOME}

  config_file = find_web_xml(app_name)
  custom_env_vars = extract_env_vars_from_xml(config_file)
  env_vars.update(custom_env_vars)

  gcs_config = {'scheme': 'https', 'port': 443}
  try:
    gcs_config.update(deployment_config.get_config('gcs'))
  except ConfigInaccessible:
    logging.warning('Unable to fetch GCS configuration.')

  if 'host' in gcs_config:
    env_vars['GCS_HOST'] = '{scheme}://{host}:{port}'.format(**gcs_config)

  return env_vars

def create_python27_start_cmd(app_name, login_ip, port, pidfile):
  """ Creates the start command to run the python application server.

  Args:
    app_name: The name of the application to run
    login_ip: The public IP of this deployment
    port: The local port the application server will bind to
    pidfile: A string specifying the pidfile location.
  Returns:
    A string of the start command.
  """
  db_proxy = appscale_info.get_db_proxy()

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
    "--uaserver_path " + db_proxy + ":"\
      + str(constants.UA_SERVER_PORT),
    "--datastore_path " + db_proxy + ":"\
      + str(constants.DB_SERVER_PORT),
    "/var/apps/" + app_name + "/app",
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

def remove_conflicting_jars(app_name):
  """ Removes jars uploaded which may conflict with AppScale jars.

  Args:
    app_name: The name of the application to run.
  """
  app_dir = "/var/apps/" + app_name + "/app/"
  lib_dir = locate_dir(app_dir, "lib")
  if not lib_dir:
    logging.warn("Lib directory not found in app code while updating.")
    return
  logging.info("Removing jars from {0}".format(lib_dir))
  conflicting_jars_pattern = ['appengine-api-1.0-sdk-*.jar', 'appengine-api-stubs-*.jar',
                  'appengine-api-labs-*.jar', 'appengine-jsr107cache-*.jar',
                  'jsr107cache-*.jar', 'appengine-mapreduce*.jar',
                  'appengine-pipeline*.jar', 'appengine-gcs-client*.jar']
  for file in os.listdir(lib_dir):
    for pattern in conflicting_jars_pattern:
      if fnmatch.fnmatch(file, pattern):
        os.remove(lib_dir + os.sep + file)

def copy_modified_jars(app_name):
  """ Copies the changes made to the Java SDK
  for AppScale into the apps lib folder.

  Args:
    app_name: The name of the application to run

  Returns:
    False if there were any errors, True if success
  """
  appscale_home = constants.APPSCALE_HOME

  app_dir = "/var/apps/" + app_name + "/app/"
  lib_dir = locate_dir(app_dir, "lib")

  if not lib_dir:
    web_inf_dir = locate_dir(app_dir, "WEB-INF")
    lib_dir = web_inf_dir + os.sep + "lib"
    logging.info("Creating lib directory at: {0}".format(lib_dir))
    mkdir_result = subprocess.call("mkdir " + lib_dir, shell=True)

    if mkdir_result != 0:
      logging.error("Failed to create missing lib directory in: {0}.".
        format(web_inf_dir))
      return False
  try:
    copy_files_matching_pattern(appscale_home + "/AppServer_Java/" +\
                "appengine-java-sdk-repacked/lib/user/*.jar", lib_dir)
    copy_files_matching_pattern(appscale_home + "/AppServer_Java/" +\
                "appengine-java-sdk-repacked/lib/impl/appscale-*.jar", lib_dir)
    copy_files_matching_pattern("/usr/share/appscale/ext/*", lib_dir)
  except IOError as io_error:
    logging.error("Failed to copy modified jar files to lib directory of " + app_name +\
                  " due to:" + str(io_error))
    return False
  return True

def copy_files_matching_pattern(file_path_pattern, dest):
  """ Copies files matching the specified pattern to the destination directory.
  Args:
      file_path_pattern: The pattern of the files to be copied over.
      dest: The destination directory.
  """
  for file in glob.glob(file_path_pattern):
    shutil.copy(file, dest)

def create_java_start_cmd(app_name, port, load_balancer_host, max_heap,
                          pidfile):
  """ Creates the start command to run the java application server.

  Args:
    app_name: The name of the application to run
    port: The local port the application server will bind to
    load_balancer_host: The host of the load balancer
    max_heap: An integer specifying the max heap size in MB.
    pidfile: A string specifying the pidfile location.
  Returns:
    A string of the start command.
  """
  db_proxy = appscale_info.get_db_proxy()
  tq_proxy = appscale_info.get_tq_proxy()
  java_start_script = os.path.join(
    constants.JAVA_APPSERVER, 'appengine-java-sdk-repacked', 'bin',
    'dev_appserver.sh')

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
    "--datastore_path=" + db_proxy,
    "--login_server=" + load_balancer_host,
    "--appscale_version=1",
    "--APP_NAME=" + app_name,
    "--NGINX_ADDRESS=" + load_balancer_host,
    "--TQ_PROXY=" + tq_proxy,
    "--pidfile={}".format(pidfile),
    os.path.dirname(locate_dir("/var/apps/" + app_name + "/app/", "WEB-INF"))
  ]

  return ' '.join(cmd)

def create_python27_stop_cmd(port):
  """ This creates the stop command for an application which is
  uniquely identified by a port number. Additional portions of the
  start command are included to prevent the termination of other
  processes.

  Args:
    port: The port which the application server is running
  Returns:
    A string of the stop command.
  """
  stop_cmd = "/usr/bin/python2 {0}/scripts/stop_service.py " \
    "dev_appserver.py {1}".format(constants.APPSCALE_HOME, port)
  return stop_cmd

def create_java_stop_cmd(port):
  """ This creates the stop command for an application which is
  uniquely identified by a port number. Additional portions of the
  start command are included to prevent the termination of other
  processes.

  Args:
    port: The port which the application server is running
  Returns:
    A string of the stop command.
  """
  stop_cmd = "/usr/bin/python2 {0}/scripts/stop_service.py " \
    "java {1}".format(constants.APPSCALE_HOME, port)
  return stop_cmd

def is_config_valid(config):
  """ Takes a configuration and checks to make sure all required properties
    are present.

  Args:
    config: The dictionary to validate
  Returns:
    True if valid, False otherwise
  """
  for ii in REQUIRED_CONFIG_FIELDS:
    try:
      if config[ii]:
        pass
    except KeyError:
      logging.error("Unable to find " + str(ii) + " in configuration")
      return False
  return True


class AppHandler(tornado.web.RequestHandler):
  """ Handles requests to start and stop instances for a project. """
  def post(self, project_id):
    """ Starts an AppServer instance on this machine.

    Args:
      project_id: A string specifying a project ID.
    """
    try:
      config = json_decode(self.request.body)
    except ValueError:
      raise HTTPError(HTTPCodes.BAD_REQUEST, 'Payload must be valid JSON')

    if not start_app(project_id, config):
      raise HTTPError(HTTPCodes.INTERNAL_ERROR, 'Unable to start application')

  @staticmethod
  def delete(project_id):
    """ Stops all instances on this machine for a project.

    Args:
      project_id: A string specifying a project ID.
    """
    if not stop_app(project_id):
      raise HTTPError(HTTPCodes.INTERNAL_ERROR, 'Unable to stop application')


class InstanceHandler(tornado.web.RequestHandler):
  """ Handles requests to stop individual instances. """

  @staticmethod
  def delete(project_id, port):
    """ Stops an AppServer instance on this machine. """
    if not stop_app_instance(project_id, int(port)):
      raise HTTPError(HTTPCodes.INTERNAL_ERROR, 'Unable to stop instance')


################################
# MAIN
################################
if __name__ == "__main__":
  file_io.set_logging_format()

  zk_ips = appscale_info.get_zk_node_ips()
  zk_client = KazooClient(hosts=','.join(zk_ips))
  zk_client.start()
  deployment_config = DeploymentConfig(zk_client)

  options.define('private_ip', appscale_info.get_private_ip())
  app = tornado.web.Application([
    ('/projects/([a-z0-9-]+)', AppHandler),
    ('/projects/([a-z0-9-]+)/([0-9-]+)', InstanceHandler)
  ])

  app.listen(constants.APP_MANAGER_PORT)
  IOLoop.current().start()
