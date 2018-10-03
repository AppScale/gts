""" Fulfills AppServer instance assignments from the scheduler. """
import logging
import math
import os
import psutil
import re
import signal
import urllib2

from tornado import gen
from tornado.httpclient import HTTPError
from tornado.ioloop import IOLoop
from tornado.locks import Event as AsyncEvent

from appscale.admin.constants import UNPACK_ROOT
from appscale.admin.instance_manager.constants import (
  API_SERVER_LOCATION, API_SERVER_PREFIX, APP_LOG_SIZE, BACKOFF_TIME,
  BadConfigurationException, DASHBOARD_LOG_SIZE, DASHBOARD_PROJECT_ID,
  DEFAULT_MAX_APPSERVER_MEMORY, FETCH_PATH, GO_SDK, JAVA_APPSERVER_CLASS,
  INSTANCE_CLASSES, MAX_API_SERVER_PORT, MAX_INSTANCE_RESPONSE_TIME,
  MONIT_INSTANCE_PREFIX, NoRedirection, PIDFILE_TEMPLATE, PYTHON_APPSERVER,
  START_APP_TIMEOUT, VERSION_REGISTRATION_NODE)
from appscale.admin.instance_manager.instance import (
  Instance, create_java_app_env, create_java_start_cmd, create_python_app_env,
  create_python27_start_cmd)
from appscale.admin.instance_manager.stop_instance import stop_instance
from appscale.admin.instance_manager.utils import (
  remove_logrotate, setup_logrotate)
from appscale.common import appscale_info, misc, monit_app_configuration
from appscale.common.constants import (
  APPS_PATH, GO, HTTPCodes, JAVA, MonitStates, PHP, PYTHON27, VAR_DIR,
  VERSION_PATH_SEPARATOR)
from appscale.common.monit_interface import DEFAULT_RETRIES, ProcessNotFound
from appscale.common.retrying import retry

logger = logging.getLogger('appscale-instance-manager')


def clean_up_instances(entries_to_keep):
  """ Terminates instances that aren't accounted for.

  Args:
    entries_to_keep: A list of dictionaries containing instance details.
  """
  monitored = {(entry['revision'], entry['port']) for entry in entries_to_keep}
  to_stop = []
  for process in psutil.process_iter():
    cmd = process.cmdline()
    if len(cmd) < 2:
      continue

    if JAVA_APPSERVER_CLASS in cmd:
      revision = cmd[-1].split(os.sep)[-2]
      port_arg = next(arg for arg in cmd if arg.startswith('--port='))
      port = int(port_arg.split('=')[-1])
    elif cmd[1] == PYTHON_APPSERVER:
      source_arg = next(arg for arg in cmd if arg.startswith(APPS_PATH))
      revision = source_arg.split(os.sep)[-2]
      port = int(cmd[cmd.index('--port') + 1])
    else:
      continue

    if (revision, port) not in monitored:
      to_stop.append(process)

  if not to_stop:
    return

  logging.info('Killing {} unmonitored instances'.format(len(to_stop)))
  for process in to_stop:
    group = os.getpgid(process.pid)
    os.killpg(group, signal.SIGKILL)


class InstanceManager(object):
  """ Fulfills AppServer instance assignments from the scheduler. """

  # The seconds to wait between ensuring that assignments are fulfilled.
  GROOMING_INTERVAL = 10

  # The ZooKeeper node that keeps track of the head node's state.
  CONTROLLER_STATE_NODE = '/appcontroller/state'

  def __init__(self, zk_client, monit_operator, routing_client,
               projects_manager, deployment_config, source_manager,
               syslog_server, thread_pool, private_ip):
    """ Creates a new InstanceManager.

    Args:
      zk_client: A kazoo.client.KazooClient object.
      monit_operator: An appscale.common.monit_interface.MonitOperator object.
      routing_client: An instance_manager.routing_client.RoutingClient object.
      projects_manager: A ProjectsManager object.
      deployment_config: A common.deployment_config.DeploymentConfig object.
      source_manager: An instance_manager.source_manager.SourceManager object.
      syslog_server: A string specifying the location of the syslog process
        that generates the combined app logs.
      thread_pool: A ThreadPoolExecutor.
      private_ip: A string specifying the current machine's private IP address.
    """
    self._monit_operator = monit_operator
    self._routing_client = routing_client
    self._private_ip = private_ip
    self._syslog_server = syslog_server
    self._projects_manager = projects_manager
    self._deployment_config = deployment_config
    self._source_manager = source_manager
    self._thread_pool = thread_pool
    self._update_event = AsyncEvent()
    self._zk_client = zk_client

    # Instances that this machine should run.
    # For example, {guestbook_default_v1: [20000, -1]}
    self._assignments = {}
    self._api_servers = {}
    self._running_instances = set()

  def start(self):
    """ Begins processes needed to fulfill instance assignments. """
    self._recover_state()

  @gen.coroutine
  def start_app(self, version_key, config):
    """ Starts a Google App Engine application on this machine. It
        will start it up and then proceed to fetch the main page.

    Args:
      version_key: A string specifying a version key.
      config: a dictionary that contains
        app_port: An integer specifying the port to use.
        login_server: The server address the AppServer will use for login urls.
    """
    if 'app_port' not in config:
      raise BadConfigurationException('app_port is required')
    if 'login_server' not in config or not config['login_server']:
      raise BadConfigurationException('login_server is required')

    login_server = config['login_server']

    project_id, service_id, version_id = version_key.split(
      VERSION_PATH_SEPARATOR)

    if not misc.is_app_name_valid(project_id):
      raise BadConfigurationException(
        'Invalid project ID: {}'.format(project_id))

    try:
      service_manager = self._projects_manager[project_id][service_id]
      version_details = service_manager[version_id].version_details
    except KeyError:
      raise BadConfigurationException('Version not found')

    runtime = version_details['runtime']
    env_vars = version_details.get('envVariables', {})
    runtime_params = self._deployment_config.get_config('runtime_parameters')
    max_memory = runtime_params.get('default_max_appserver_memory',
                                    DEFAULT_MAX_APPSERVER_MEMORY)
    if 'instanceClass' in version_details:
      max_memory = INSTANCE_CLASSES.get(version_details['instanceClass'],
                                        max_memory)

    revision_key = VERSION_PATH_SEPARATOR.join(
      [project_id, service_id, version_id, str(version_details['revision'])])
    source_archive = version_details['deployment']['zip']['sourceUrl']

    api_server_port = yield self._ensure_api_server(project_id)
    yield self._source_manager.ensure_source(revision_key, source_archive,
                                             runtime)

    logging.info('Starting {} application {}'.format(runtime, project_id))

    pidfile = PIDFILE_TEMPLATE.format(revision=revision_key,
                                      port=config['app_port'])

    if runtime == GO:
      env_vars['GOPATH'] = os.path.join(UNPACK_ROOT, revision_key, 'gopath')
      env_vars['GOROOT'] = os.path.join(GO_SDK, 'goroot')

    watch = ''.join([MONIT_INSTANCE_PREFIX, revision_key])
    if runtime in (PYTHON27, GO, PHP):
      start_cmd = create_python27_start_cmd(
        project_id,
        login_server,
        config['app_port'],
        pidfile,
        revision_key,
        api_server_port)
      env_vars.update(create_python_app_env(
        login_server,
        project_id))
    elif runtime == JAVA:
      # Account for MaxPermSize (~170MB), the parent process (~50MB), and thread
      # stacks (~20MB).
      max_heap = max_memory - 250
      if max_heap <= 0:
        raise BadConfigurationException(
          'Memory for Java applications must be greater than 250MB')

      start_cmd = create_java_start_cmd(
        project_id,
        config['app_port'],
        login_server,
        max_heap,
        pidfile,
        revision_key,
        api_server_port
      )

      env_vars.update(create_java_app_env(self._deployment_config))
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
      self._syslog_server,
      check_port=True,
      kill_exceeded_memory=True)

    full_watch = '{}-{}'.format(watch, config['app_port'])

    yield self._monit_operator.reload(self._thread_pool)
    yield self._monit_operator.send_command_retry_process(full_watch, 'start')

    # Make sure the version node exists.
    self._zk_client.ensure_path(
      '/'.join([VERSION_REGISTRATION_NODE, version_key]))

    # Since we are going to wait, possibly for a long time for the
    # application to be ready, we do it later.
    IOLoop.current().spawn_callback(self._add_routing,
                                    Instance(revision_key, config['app_port']))

    if project_id == DASHBOARD_PROJECT_ID:
      log_size = DASHBOARD_LOG_SIZE
    else:
      log_size = APP_LOG_SIZE

    if not setup_logrotate(project_id, log_size):
      logging.error("Error while setting up log rotation for application: {}".
                    format(project_id))

  @gen.coroutine
  def stop_app(self, version_key):
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
    monit_entries = yield self._monit_operator.get_entries()
    version_entries = [entry for entry in monit_entries
                       if entry.startswith(version_group)]
    for entry in version_entries:
      revision_key, port = entry[len(MONIT_INSTANCE_PREFIX):].rsplit('-', 1)
      port = int(port)
      instance = Instance(revision_key, port)
      self._routing_client.unregister_instance(instance)
      try:
        self._running_instances.remove(instance)
      except KeyError:
        logging.info(
          'unregister_instance: non-existent instance {}'.format(instance))

      yield self._unmonitor_and_terminate(entry)

    project_prefix = ''.join([MONIT_INSTANCE_PREFIX, project_id])
    remaining_instances = [entry for entry in monit_entries
                           if entry.startswith(project_prefix)
                           and entry not in version_entries]
    if not remaining_instances:
      yield self._stop_api_server(project_id)

    if (project_id not in self._projects_manager and
        not remove_logrotate(project_id)):
      logging.error("Error while removing log rotation for application: {}".
                    format(project_id))

    yield self._monit_operator.reload(self._thread_pool)
    yield self._clean_old_sources()

  @gen.coroutine
  def stop_failed_instances(self):
    """ Stops AppServer instances that HAProxy considers to be unavailable. """
    failed_instances = yield self._routing_client.get_failed_instances()
    for instance in self._running_instances:
      if (instance.version_key, instance.port) in failed_instances:
        yield self._stop_app_instance(instance.version_key, instance.port)

  @gen.coroutine
  def populate_api_servers(self):
    """ Find running API servers. """

    def api_server_info(entry):
      prefix, port = entry.rsplit('-', 1)
      project_id = prefix[len(API_SERVER_PREFIX):]
      return project_id, int(port)

    monit_entries = yield self._monit_operator.get_entries()
    server_entries = [api_server_info(entry) for entry in monit_entries
                      if entry.startswith(API_SERVER_PREFIX)]

    for project_id, port in server_entries:
      self._api_servers[project_id] = port

  def _recover_state(self):
    """ Establishes current state from Monit entries. """
    logging.info('Getting current state')
    monit_entries = self._monit_operator.get_entries_sync()
    instance_entries = {entry: state for entry, state in monit_entries.items()
                        if entry.startswith(MONIT_INSTANCE_PREFIX)}

    # Remove all unmonitored entries.
    removed = []
    for entry, state in instance_entries.items():
      if state == MonitStates.UNMONITORED:
        self._monit_operator.remove_configuration(entry)
        removed.append(entry)

    for entry in removed:
      del instance_entries[entry]

    if removed:
      self._monit_operator.reload_sync()

    instance_details = []
    for entry, state in instance_entries.items():
      revision, port = entry[len(MONIT_INSTANCE_PREFIX):].rsplit('-', 1)
      instance_details.append(
        {'revision': revision, 'port': int(port), 'state': state})

    clean_up_instances(instance_details)

    # Ensure version nodes exist.
    running_versions = {'_'.join(instance['revision'].split('_')[:3])
                        for instance in instance_details}
    self._zk_client.ensure_path(VERSION_REGISTRATION_NODE)
    for version_key in running_versions:
      self._zk_client.ensure_path(
        '/'.join([VERSION_REGISTRATION_NODE, version_key]))

    # Account for monitored instances.
    running_instances = {
      Instance(instance['revision'], instance['port'])
      for instance in instance_details}
    self._routing_client.declare_instance_nodes(running_instances)
    self._running_instances = running_instances

  @gen.coroutine
  def _ensure_api_server(self, project_id):
    """ Make sure there is a running API server for a project.

    Args:
      project_id: A string specifying the project ID.
    Returns:
      An integer specifying the API server port.
    """
    if project_id in self._api_servers:
      raise gen.Return(self._api_servers[project_id])

    server_port = MAX_API_SERVER_PORT
    for port in self._api_servers.values():
      if port <= server_port:
        server_port = port - 1

    zk_locations = appscale_info.get_zk_node_ips()
    start_cmd = ' '.join([API_SERVER_LOCATION,
                          '--port', str(server_port),
                          '--project-id', project_id,
                          '--zookeeper-locations', ' '.join(zk_locations)])

    watch = ''.join([API_SERVER_PREFIX, project_id])
    full_watch = '-'.join([watch, str(server_port)])
    pidfile = os.path.join(VAR_DIR, '{}.pid'.format(full_watch))
    monit_app_configuration.create_config_file(
      watch,
      start_cmd,
      pidfile,
      server_port,
      max_memory=DEFAULT_MAX_APPSERVER_MEMORY,
      check_port=True)

    yield self._monit_operator.reload(self._thread_pool)
    yield self._monit_operator.send_command_retry_process(full_watch, 'start')

    self._api_servers[project_id] = server_port
    raise gen.Return(server_port)

  @gen.coroutine
  def _unmonitor_and_terminate(self, watch):
    """ Unmonitors an instance and terminates it.

    Args:
      watch: A string specifying the Monit entry.
    """
    try:
      monit_retry = retry(max_retries=5, retry_on_exception=DEFAULT_RETRIES)
      send_w_retries = monit_retry(self._monit_operator.send_command_sync)
      send_w_retries(watch, 'unmonitor')
    except ProcessNotFound:
      # If Monit does not know about a process, assume it is already stopped.
      return

    # Now that the AppServer is stopped, remove its monit config file so that
    # monit doesn't pick it up and restart it.
    self._monit_operator.remove_configuration(watch)

    yield stop_instance(watch, MAX_INSTANCE_RESPONSE_TIME)

  @gen.coroutine
  def _wait_for_app(self, port):
    """ Waits for the application hosted on this machine, on the given port,
        to respond to HTTP requests.

    Args:
      port: Port where app is hosted on the local machine
    Returns:
      True on success, False otherwise
    """
    retries = math.ceil(START_APP_TIMEOUT / BACKOFF_TIME)

    url = "http://" + self._private_ip + ":" + str(port) + FETCH_PATH
    while retries > 0:
      try:
        opener = urllib2.build_opener(NoRedirection)
        response = opener.open(url)
        if response.code != HTTPCodes.OK:
          logging.warning('{} returned {}. Headers: {}'.
                          format(url, response.code, response.headers.headers))
        raise gen.Return(True)
      except IOError:
        retries -= 1

      yield gen.sleep(BACKOFF_TIME)

    logging.error('Application did not come up on {} after {} seconds'.
                  format(url, START_APP_TIMEOUT))
    raise gen.Return(False)

  @gen.coroutine
  def _add_routing(self, instance):
    """ Tells the AppController to begin routing traffic to an AppServer.

    Args:
      instance: An Instance.
    """
    logging.info('Waiting for {}'.format(instance))
    start_successful = yield self._wait_for_app(instance.port)
    if not start_successful:
      # In case the AppServer fails we let the AppController to detect it
      # and remove it if it still show in monit.
      logging.warning('{} did not come up in time'.format(instance))
      raise gen.Return()

    self._routing_client.register_instance(instance)
    self._running_instances.add(instance)

  @gen.coroutine
  def _stop_api_server(self, project_id):
    """ Make sure there is not a running API server for a project.

    Args:
      project_id: A string specifying the project ID.
    """
    if project_id not in self._api_servers:
      return

    port = self._api_servers[project_id]
    watch = '{}{}-{}'.format(API_SERVER_PREFIX, project_id, port)
    yield self._unmonitor_and_terminate(watch)
    del self._api_servers[project_id]

  @gen.coroutine
  def _clean_old_sources(self):
    """ Removes source code for obsolete revisions. """
    monit_entries = yield self._monit_operator.get_entries()
    active_revisions = {
      entry[len(MONIT_INSTANCE_PREFIX):].rsplit('-', 1)[0]
      for entry in monit_entries
      if entry.startswith(MONIT_INSTANCE_PREFIX)}

    for project_id, project_manager in self._projects_manager.items():
      for service_id, service_manager in project_manager.items():
        for version_id, version_manager in service_manager.items():
          revision_id = version_manager.version_details['revision']
          revision_key = VERSION_PATH_SEPARATOR.join(
            [project_id, service_id, version_id, str(revision_id)])
          active_revisions.add(revision_key)

    self._source_manager.clean_old_revisions(active_revisions=active_revisions)

  @gen.coroutine
  def _stop_app_instance(self, version_key, port):
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
    monit_entries = yield self._monit_operator.get_entries()
    try:
      watch = next(entry for entry in monit_entries
                   if instance_key_re.match(entry))
    except StopIteration:
      message = 'No entries exist for {}:{}'.format(version_key, port)
      raise HTTPError(HTTPCodes.INTERNAL_ERROR, message=message)

    revision_key, port = watch[len(MONIT_INSTANCE_PREFIX):].rsplit('-', 1)
    port = int(port)
    instance = Instance(revision_key, port)
    self._routing_client.unregister_instance()
    try:
      self._running_instances.remove(instance)
    except KeyError:
      logging.info(
        'unregister_instance: non-existent instance {}'.format(instance))

    yield self._unmonitor_and_terminate(watch)

    project_prefix = ''.join([MONIT_INSTANCE_PREFIX, project_id])
    remaining_instances = [entry for entry in monit_entries
                           if entry.startswith(project_prefix)
                           and not instance_key_re.match(entry)]
    if not remaining_instances:
      yield self._stop_api_server(project_id)

    yield self._monit_operator.reload(self._thread_pool)
    yield self._clean_old_sources()
