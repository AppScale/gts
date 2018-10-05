""" Fulfills AppServer instance assignments from the scheduler. """
import logging
import math
import json
import os
import psutil
import signal
import time
import urllib2

from kazoo.exceptions import NoNodeError
from tornado import gen
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.locks import Event as AsyncEvent

from appscale.admin.constants import UNPACK_ROOT
from appscale.admin.instance_manager.constants import (
  API_SERVER_LOCATION, API_SERVER_PREFIX, APP_LOG_SIZE, BACKOFF_TIME,
  BadConfigurationException, DASHBOARD_LOG_SIZE, DASHBOARD_PROJECT_ID,
  DEFAULT_MAX_APPSERVER_MEMORY, FETCH_PATH, GO_SDK, INSTANCE_CLASSES,
  INSTANCE_CLEANUP_INTERVAL, JAVA_APPSERVER_CLASS, MAX_API_SERVER_PORT,
  MAX_INSTANCE_RESPONSE_TIME, MONIT_INSTANCE_PREFIX, NoRedirection,
  PIDFILE_TEMPLATE, PYTHON_APPSERVER, START_APP_TIMEOUT,
  STARTING_INSTANCE_PORT, VERSION_REGISTRATION_NODE)
from appscale.admin.instance_manager.instance import (
  Instance, create_java_app_env, create_java_start_cmd, create_python_app_env,
  create_python27_start_cmd)
from appscale.admin.instance_manager.stop_instance import stop_instance
from appscale.admin.instance_manager.utils import setup_logrotate
from appscale.common import appscale_info, monit_app_configuration
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
  GROOMING_INTERVAL = 60

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
    self._last_cleanup_time = time.time()
    self._login_server = None
    self._grooming_trigger = PeriodicCallback(
      self._update_event.set, self.GROOMING_INTERVAL * 1000)

  def start(self):
    """ Begins processes needed to fulfill instance assignments. """

    # Update list of running instances in case the InstanceManager was
    # restarted.
    self._recover_state()
    self._last_cleanup_time = time.time()

    # Synchronously fetch assignments so that instances are not stopped before
    # the first time assignments are fetched.
    try:
      encoded_state = self._zk_client.get(self.CONTROLLER_STATE_NODE)[0]
    except NoNodeError:
      encoded_state = None

    self._update_assignments(encoded_state)

    # Trigger fulfillment work on a regular interval.
    self._grooming_trigger.start()

    # Subscribe to changes in controller state, which includes assignments and
    # the 'login' property.
    self._zk_client.DataWatch(self.CONTROLLER_STATE_NODE,
                              self._update_assignments_watch)

    # Subscribe to changes in project configuration, including relevant
    # versions.
    self._projects_manager.subscriptions.append(
      self._handle_configuration_update)

    # Begin the never-ending task of fulfilling assignments.
    IOLoop.current().spawn_callback(self._fulfillment_loop)

  @gen.coroutine
  def _start_instance(self, version, port):
    """ Starts a Google App Engine application on this machine. It
        will start it up and then proceed to fetch the main page.

    Args:
      version: A Version object.
      port: An integer specifying a port to use.
    """
    version_details = version.version_details
    runtime = version_details['runtime']
    env_vars = version_details.get('envVariables', {})
    runtime_params = self._deployment_config.get_config('runtime_parameters')
    max_memory = runtime_params.get('default_max_appserver_memory',
                                    DEFAULT_MAX_APPSERVER_MEMORY)
    if 'instanceClass' in version_details:
      max_memory = INSTANCE_CLASSES.get(version_details['instanceClass'],
                                        max_memory)

    source_archive = version_details['deployment']['zip']['sourceUrl']

    api_server_port = yield self._ensure_api_server(version.project_id)
    yield self._source_manager.ensure_source(
      version.revision_key, source_archive, runtime)

    logger.info('Starting {}'.format(version))

    pidfile = PIDFILE_TEMPLATE.format(revision=version.revision_key, port=port)

    if runtime == GO:
      env_vars['GOPATH'] = os.path.join(UNPACK_ROOT, version.revision_key,
                                        'gopath')
      env_vars['GOROOT'] = os.path.join(GO_SDK, 'goroot')

    watch = ''.join([MONIT_INSTANCE_PREFIX, version.revision_key])
    if runtime in (PYTHON27, GO, PHP):
      start_cmd = create_python27_start_cmd(
        version.project_id,
        self._login_server,
        port,
        pidfile,
        version.revision_key,
        api_server_port)
      env_vars.update(create_python_app_env(self._login_server,
                                            version.project_id))
    elif runtime == JAVA:
      # Account for MaxPermSize (~170MB), the parent process (~50MB), and thread
      # stacks (~20MB).
      max_heap = max_memory - 250
      if max_heap <= 0:
        raise BadConfigurationException(
          'Memory for Java applications must be greater than 250MB')

      start_cmd = create_java_start_cmd(
        version.project_id,
        port,
        self._login_server,
        max_heap,
        pidfile,
        version.revision_key,
        api_server_port
      )

      env_vars.update(create_java_app_env(self._deployment_config))
    else:
      raise BadConfigurationException(
        'Unknown runtime {} for {}'.format(runtime, version.project_id))

    logging.info("Start command: " + str(start_cmd))
    logging.info("Environment variables: " + str(env_vars))

    monit_app_configuration.create_config_file(
      watch,
      start_cmd,
      pidfile,
      port,
      env_vars,
      max_memory,
      self._syslog_server,
      check_port=True,
      kill_exceeded_memory=True)

    full_watch = '{}-{}'.format(watch, port)

    yield self._monit_operator.reload(self._thread_pool)
    yield self._monit_operator.send_command_retry_process(full_watch, 'start')

    # Make sure the version registration node exists.
    self._zk_client.ensure_path(
      '/'.join([VERSION_REGISTRATION_NODE, version.version_key]))

    instance = Instance(version.revision_key, port)
    yield self._add_routing(instance)

    if version.project_id == DASHBOARD_PROJECT_ID:
      log_size = DASHBOARD_LOG_SIZE
    else:
      log_size = APP_LOG_SIZE

    if not setup_logrotate(version.project_id, log_size):
      logging.error("Error while setting up log rotation for application: {}".
                    format(version.project_id))

  @gen.coroutine
  def stop_failed_instances(self):
    """ Stops AppServer instances that HAProxy considers to be unavailable. """
    failed_instances = yield self._routing_client.get_failed_instances()
    for instance in self._running_instances:
      if (instance.version_key, instance.port) in failed_instances:
        yield self._stop_app_instance(instance)

    self._last_cleanup_time = time.time()

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

    stop_instance(watch, MAX_INSTANCE_RESPONSE_TIME)

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
  def _stop_app_instance(self, instance):
    """ Stops a Google App Engine application process instance on current
        machine.

    Args:
      instance: An Instance object.
    """
    logger.info('Stopping {}'.format(instance))

    monit_watch = ''.join(
      [MONIT_INSTANCE_PREFIX, instance.revision_key, '-', str(instance.port)])

    self._routing_client.unregister_instance(instance)
    try:
      self._running_instances.remove(instance)
    except KeyError:
      logging.info(
        'unregister_instance: non-existent instance {}'.format(instance))

    yield self._unmonitor_and_terminate(monit_watch)

    project_instances = [instance_ for instance_ in self._running_instances
                         if instance_.project_id == instance.project_id]
    if not project_instances:
      yield self._stop_api_server(instance.project_id)

    yield self._monit_operator.reload(self._thread_pool)
    yield self._clean_old_sources()

  def _get_lowest_port(self):
    """ Determines the lowest usuable port for a new instance.

    Returns:
      An integer specifying a free port.
    """
    existing_ports = {instance.port for instance in self._running_instances}
    port = STARTING_INSTANCE_PORT
    while True:
      if port in existing_ports:
        port += 1
        continue

      return port

  def _get_login_server(self, instance):
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

  @gen.coroutine
  def _fulfill_assignments(self):
    """ Starts and stops instances in order to fulfill assignments. """

    # Wait until one of the following conditions has been met:
    #  - The grooming interval has passed
    #  - The machine's assignments have been updated
    #  - The deployment's "login" property has been updated
    #  - The details of an assigned version have been updated
    #  - The details of a running version have been updated
    yield self._update_event.wait()
    self._update_event.clear()

    # Occasionally, a router will mark an instance as "down". This cleanup
    # manually stops the unrouted processes.
    if time.time() > self._last_cleanup_time + INSTANCE_CLEANUP_INTERVAL:
      yield self.stop_failed_instances()

    # Stop versions that aren't assigned.
    to_stop = [instance for instance in self._running_instances
               if instance.version_key not in self._assignments]
    for instance in to_stop:
      yield self._stop_app_instance(instance)

    for version_key, assigned_ports in self._assignments.items():
      project_id, service_id, version_id = version_key.split(
        VERSION_PATH_SEPARATOR)
      version_instances = [instance for instance in self._running_instances
                           if instance.version_key == version_key]
      try:
        version = self._projects_manager[project_id][service_id][version_id]
      except KeyError:
        # If the version node no longer exists, stop any running instances.
        for instance in version_instances:
          yield self._stop_app_instance(instance)

        continue

      # Stop instances that aren't assigned.
      for instance in version_instances:
        if instance.port not in assigned_ports:
          yield self._stop_app_instance(instance)

      # Start assigned instances that aren't running.
      for port in assigned_ports:
        if port == -1:
          port = self._get_lowest_port()

        instance = Instance(version.revision_key, port)
        if instance not in version_instances:
          self._start_instance(version, instance.port)

      # Restart instances with an outdated revision or login server.
      for instance in version_instances:
        if (instance.revision_key != version.revision_key or
            self._get_login_server(instance) != self._login_server):
          yield self._stop_app_instance(instance)
          yield self._start_instance(version, instance.port)

  @gen.coroutine
  def _fulfillment_loop(self):
    """ Continually tries to fulfill assignments. """
    while True:
      try:
        yield self._fulfill_assignments()
      # The above shouldn't raise an exception, but if for some reason it does,
      # it's crucial that the manager keeps trying to fulfill assignments.
      except Exception:
        logger.exception('Unexpected error when scheduling instances')

  def _update_assignments(self, encoded_controller_state):
    """ Updates the list of instances this machine should run.

    Args:
      encoded_controller_state: A JSON-encoded string containing controller
        state.
    """
    if encoded_controller_state is None:
      self._assignments = {}
      return

    controller_state = json.loads(encoded_controller_state)
    def version_assignments(data):
      return [int(server.split(':')[1]) for server in data['appservers']
              if server.split(':')[0] == self._private_ip]

    new_assignments = {
      version_key: version_assignments(data)
      for version_key, data in controller_state['@app_info_map'].items()
      if version_assignments(data)}

    login_server = controller_state['@options']['login']

    if (new_assignments != self._assignments or
        login_server != self._login_server):
      self._assignments = new_assignments
      self._login_server = login_server
      self._update_event.set()

  def _update_assignments_watch(self, encoded_controller_state, _):
    """ Handles updates to controller state.

    Args:
      encoded_controller_state: A JSON-encoded string containing controller
        state.
    """
    IOLoop.instance().add_callback(
      self._update_assignments, encoded_controller_state)

  def _handle_configuration_update(self, event):
    """ Triggers fulfillment work when an assigned version has been updated. """
    running_versions = {instance.version_key
                        for instance in self._running_instances}
    assigned_versions = set(self._assignments.keys())
    for relevant_version in running_versions | assigned_versions:
      if event.affects_version(relevant_version):
        self._update_event.set()
        break
