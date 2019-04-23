""" Resources related to starting AppServer instances. """
import logging
import os

import psutil
from tornado.options import options

from appscale.admin.constants import UNPACK_ROOT
from appscale.admin.instance_manager.constants import (
  PHP_CGI_LOCATION, PIDFILE_TEMPLATE, TRUSTED_APPS)
from appscale.admin.instance_manager.utils import find_web_inf
from appscale.common import appscale_info
from appscale.common.constants import (
  APPSCALE_HOME, DB_SERVER_PORT, JAVA_APPSERVER, UA_SERVER_PORT,
  VERSION_PATH_SEPARATOR)
from appscale.common.deployment_config import ConfigInaccessible

logger = logging.getLogger(__name__)


class Instance(object):
  """ Represents an AppServer instance. """
  __slots__ = ['revision_key', 'port']
  def __init__(self, revision_key, port):
    self.revision_key = revision_key
    self.port = port

  @property
  def version_key(self):
    revision_parts = self.revision_key.split(VERSION_PATH_SEPARATOR)
    return VERSION_PATH_SEPARATOR.join(revision_parts[:3])

  @property
  def project_id(self):
    revision_parts = self.revision_key.split(VERSION_PATH_SEPARATOR)
    return revision_parts[0]

  @property
  def revision(self):
    return self.revision_key.split(VERSION_PATH_SEPARATOR)[-1]

  def __eq__(self, other):
    return self.revision_key == other.revision_key and self.port == other.port

  def __repr__(self):
    return '<Instance: {}:{}>'.format(self.revision_key, self.port)

  def __hash__(self):
    return hash((self.revision_key, self.port))


def create_java_app_env(deployment_config):
  """ Returns the environment variables Java application servers uses.

  Args:
    deployment_config: A DeploymentConfig object.
  Returns:
    A dictionary containing the environment variables
  """
  env_vars = {'APPSCALE_HOME': APPSCALE_HOME}

  gcs_config = {'scheme': 'https', 'port': 443}
  try:
    gcs_config.update(deployment_config.get_config('gcs'))
  except ConfigInaccessible:
    logger.warning('Unable to fetch GCS configuration.')

  if 'host' in gcs_config:
    env_vars['GCS_HOST'] = '{scheme}://{host}:{port}'.format(**gcs_config)

  return env_vars


def create_java_start_cmd(app_name, port, load_balancer_host, max_heap,
                          pidfile, revision_key, api_server_port):
  """ Creates the start command to run the java application server.

  Args:
    app_name: The name of the application to run
    port: The local port the application server will bind to
    load_balancer_host: The host of the load balancer
    max_heap: An integer specifying the max heap size in MB.
    pidfile: A string specifying the pidfile location.
    revision_key: A string specifying the revision key.
    api_server_port: An integer specifying the port of the external API server.
  Returns:
    A string of the start command.
  """
  java_start_script = os.path.join(
    JAVA_APPSERVER, 'appengine-java-sdk-repacked', 'bin',
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
    '--jvm_flag=-Djdk.tls.client.protocols=TLSv1.1,TLSv1.2',
    "--disable_update_check",
    "--address=" + options.private_ip,
    "--datastore_path=" + options.db_proxy,
    "--login_server=" + load_balancer_host,
    "--appscale_version=1",
    "--APP_NAME=" + app_name,
    "--NGINX_ADDRESS=" + load_balancer_host,
    "--TQ_PROXY=" + options.tq_proxy,
    "--xmpp_path=" + options.load_balancer_ip,
    "--pidfile={}".format(pidfile),
    "--external_api_port={}".format(api_server_port),
    "--api_using_python_stub=app_identity_service",
    os.path.dirname(web_inf_directory)
  ]

  return ' '.join(cmd)


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
  env_vars['APPSCALE_HOME'] = APPSCALE_HOME
  env_vars['PYTHON_LIB'] = "{0}/AppServer/".format(APPSCALE_HOME)
  return env_vars


def create_python27_start_cmd(app_name, login_ip, port, pidfile, revision_key,
                              api_server_port):
  """ Creates the start command to run the python application server.

  Args:
    app_name: The name of the application to run
    login_ip: The public IP of this deployment
    port: The local port the application server will bind to
    pidfile: A string specifying the pidfile location.
    revision_key: A string specifying the revision key.
    api_server_port: An integer specifying the port of the external API server.
  Returns:
    A string of the start command.
  """
  service_id = revision_key.split(VERSION_PATH_SEPARATOR)[1]

  # When deploying the service, the tools rename the service yaml to app.yaml.
  config_file = os.path.join(UNPACK_ROOT, revision_key, 'app', 'app.yaml')

  cmd = [
    "/usr/bin/python2", APPSCALE_HOME + "/AppServer/dev_appserver.py",
    "--application", app_name,
    "--port " + str(port),
    "--admin_port " + str(port + 10000),
    "--login_server " + login_ip,
    "--skip_sdk_update_check",
    "--nginx_host " + str(login_ip),
    "--require_indexes",
    "--enable_sendmail",
    "--xmpp_path " + options.load_balancer_ip,
    "--php_executable_path=" + str(PHP_CGI_LOCATION),
    "--max_module_instances", "{}:1".format(service_id),
    "--uaserver_path " + options.db_proxy + ":" + str(UA_SERVER_PORT),
    "--datastore_path " + options.db_proxy + ":" + str(DB_SERVER_PORT),
    "--host " + options.private_ip,
    "--admin_host " + options.private_ip,
    "--automatic_restart", "no",
    "--pidfile", pidfile,
    "--external_api_port", str(api_server_port),
    config_file
  ]

  if app_name in TRUSTED_APPS:
    cmd.append('--trusted')

  return ' '.join(cmd)


def get_login_server(instance):
  """ Returns the configured login server for a running instance.

  Args:
    instance: An Instance object.
  Returns:
    A string containing the instance's login server value or None.
  """
  pidfile_location = PIDFILE_TEMPLATE.format(revision=instance.revision_key,
                                             port=instance.port)
  try:
    with open(pidfile_location) as pidfile:
      pid_str = pidfile.read().strip()
  except IOError:
    return None

  try:
    pid = int(pid_str)
  except ValueError:
    logger.warning('Invalid pidfile for {}: {}'.format(instance, pid_str))
    return None

  try:
    args = psutil.Process(pid).cmdline()
  except psutil.NoSuchProcess:
    return None

  for index, arg in enumerate(args):
    if '--login_server=' in arg:
      return arg.split('=', 1)[1]

    if arg == '--login_server':
      try:
        login_server = args[index + 1]
      except IndexError:
        return None

      return login_server

  return None
