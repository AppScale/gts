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
  APPSCALE_HOME, DB_SERVER_PORT, JAVA_APPSERVER, JAVA8, JAVA8_RUNTIME_DIR,
  PYTHON27_RUNTIME_DIR, SCRIPTS_DIR, UA_SERVER_PORT, VERSION_PATH_SEPARATOR)
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


def create_java_app_env(deployment_config, runtime, project_id):
  """ Returns the environment variables Java application servers uses.

  Args:
    deployment_config: A DeploymentConfig object.
    runtime: A string specifying which runtime to use (java or java8).
    project_id: A string specifying the project ID.
  Returns:
    A dictionary containing the environment variables
  """
  if runtime == JAVA8:
    env_vars = {
        'APPLICATION_ID': project_id,
        'APPNAME': project_id  # Used by API proxy xmpp/channel implementation
    }
  else:
    env_vars = {'APPSCALE_HOME': APPSCALE_HOME}

  gcs_config = {'scheme': 'https', 'port': 443}
  try:
    gcs_config.update(deployment_config.get_config('gcs'))
  except ConfigInaccessible:
    logger.warning('Unable to fetch GCS configuration.')

  if 'host' in gcs_config:
    env_vars['GCS_HOST'] = '{scheme}://{host}:{port}'.format(**gcs_config)

  return env_vars


def create_java_start_cmd(app_name, port, load_balancer_port, load_balancer_host,
                          max_heap, pidfile, revision_key, api_server_port,
                          runtime):
  """ Creates the start command to run the java application server.

  Args:
    app_name: The name of the application to run
    port: The local port the application server will bind to
    load_balancer_port: The port of the load balancer
    load_balancer_host: The host of the load balancer
    max_heap: An integer specifying the max heap size in MB.
    pidfile: A string specifying the pidfile location.
    revision_key: A string specifying the revision key.
    api_server_port: An integer specifying the port of the external API server.
    runtime: A string specifying which runtime to use (java or java8).
  Returns:
    A string of the start command.
  """
  if runtime == JAVA8:
    java_start_script = os.path.join(JAVA8_RUNTIME_DIR, 'bin',
                                     'appscale_java8_runtime.sh')
  else:
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
    "--address=" + options.private_ip,
    "--pidfile={}".format(pidfile)
  ]
  api_server_flags = []

  if runtime == JAVA8:
      cmd.extend(['--python_api_server_port={}'.format(api_server_port),
                  '--default_hostname={}:{}'.format(load_balancer_host,
                                                    load_balancer_port)])

      apis_using_external_server = ['app_identity_service', 'blobstore',
                                    'channel', 'datastore_v3', 'memcache',
                                    'search', 'taskqueue', 'xmpp']
  else:
      api_server = os.path.join(SCRIPTS_DIR,
                                'appscale_java_apiserver.sh')

      cmd.extend(['--path_to_python_api_server={}'.format(api_server),
                  '--disable_update_check',
                  '--APP_NAME={}'.format(app_name),
                  '--NGINX_ADDRESS={}'.format(load_balancer_host),
                  '--datastore_path={}'.format(options.db_proxy),
                  '--login_server={}'.format(load_balancer_host),
                  '--xmpp_path={}'.format(options.load_balancer_ip),
                  '--appscale_version=1'])

      api_server_flags = [
          '--application={}'.format(app_name),
          '--datastore_path={}'.format(
              ':'.join([options.db_proxy, str(DB_SERVER_PORT)])),
          '--login_server={}'.format(load_balancer_host),
          '--nginx_host={}'.format(load_balancer_host),
          '--xmpp_path={}'.format(load_balancer_host),
          '--uaserver_path={}'.format(
              ':'.join([options.db_proxy, str(UA_SERVER_PORT)])),
          '--external_api_port={}'.format(api_server_port)
      ]

      apis_using_external_server = ['app_identity_service', 'datastore_v3',
                                    'memcache', 'taskqueue']

  for flag in api_server_flags:
    cmd.append('--python_api_server_flag="{}"'.format(flag))

  for api in apis_using_external_server:
    cmd.append('--api_using_python_stub={}'.format(api))

  cmd.append(os.path.dirname(web_inf_directory))

  return ' '.join(cmd)


def create_python_api_start_cmd(app_name, login_ip, port, pidfile,
                                api_server_port):
  """ Creates the start command to run the python api server.

  Args:
    app_name: The name of the application to run
    login_ip: The public IP of this deployment
    port: The local port the api server will bind to
    pidfile: A string specifying the pidfile location.
    api_server_port: An integer specifying the port of the external API server.
  Returns:
    A string of the start command.
  """
  cmd = [
      '/usr/bin/python2', os.path.join(PYTHON27_RUNTIME_DIR, 'api_server.py'),
      '--api_port', str(port),
      '--application', app_name,
      '--login_server', login_ip,
      '--nginx_host', login_ip,
      '--enable_sendmail',
      '--xmpp_path', options.load_balancer_ip,
      '--uaserver_path', '{}:{}'.format(options.db_proxy, UA_SERVER_PORT),
      '--datastore_path', '{}:{}'.format(options.db_proxy, DB_SERVER_PORT),
      '--pidfile', pidfile,
      '--external_api_port', str(api_server_port)
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
    '/usr/bin/python2', os.path.join(PYTHON27_RUNTIME_DIR, 'dev_appserver.py'),
    '--application', app_name,
    '--port', str(port),
    '--login_server', login_ip,
    '--skip_sdk_update_check',
    '--nginx_host', login_ip,
    '--require_indexes',
    '--enable_sendmail',
    '--xmpp_path', options.load_balancer_ip,
    '--php_executable_path=' + str(PHP_CGI_LOCATION),
    '--max_module_instances', "{}:1".format(service_id),
    '--uaserver_path', '{}:{}'.format(options.db_proxy, UA_SERVER_PORT),
    '--datastore_path', '{}:{}'.format(options.db_proxy, DB_SERVER_PORT),
    '--host', options.private_ip,
    '--automatic_restart', 'no',
    '--pidfile', pidfile,
    '--external_api_port', str(api_server_port),
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
      return arg.rsplit('=', 1)[1]

    if arg == '--login_server':
      try:
        login_server = args[index + 1]
      except IndexError:
        return None

      return login_server

  return None
