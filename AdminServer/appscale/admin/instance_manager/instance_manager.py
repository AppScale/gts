""" Fulfills AppServer instance assignments from the scheduler. """
import hashlib
import httplib
import logging
import json
import os
import psutil
import signal
import time
import urllib2

from tornado import gen
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.locks import Lock as AsyncLock

from appscale.admin.constants import CONTROLLER_STATE_NODE, UNPACK_ROOT
from appscale.admin.instance_manager.constants import (
  API_SERVER_LOCATION, API_SERVER_PREFIX, APP_LOG_SIZE, BACKOFF_TIME,
  BadConfigurationException, DASHBOARD_LOG_SIZE, DASHBOARD_PROJECT_ID,
  DEFAULT_MAX_APPSERVER_MEMORY, FETCH_PATH, GO_SDK, HEALTH_CHECK_TIMEOUT,
  INSTANCE_CLASSES, JAVA_APPSERVER_CLASS, MAX_API_SERVER_PORT,
  MAX_INSTANCE_RESPONSE_TIME, MONIT_INSTANCE_PREFIX, NoRedirection,
  PIDFILE_TEMPLATE, PYTHON_APPSERVER, START_APP_TIMEOUT,
  STARTING_INSTANCE_PORT, VERSION_REGISTRATION_NODE)
from appscale.admin.instance_manager.instance import (
  create_java_app_env, create_java_start_cmd, create_python_api_start_cmd,
  create_python_app_env, create_python27_start_cmd, get_login_server, Instance)
from appscale.admin.instance_manager.stop_instance import stop_instance
from appscale.admin.instance_manager.utils import setup_logrotate, \
  remove_logrotate
from appscale.common import appscale_info, monit_app_configuration
from appscale.common.async_retrying import retry_data_watch_coroutine
from appscale.common.constants import (
  APPS_PATH, GO, HTTPCodes, JAVA, JAVA8, MonitStates, PHP, PYTHON27, VAR_DIR,
  VERSION_PATH_SEPARATOR)
from appscale.common.monit_interface import DEFAULT_RETRIES, ProcessNotFound
from appscale.common.retrying import retry

logger = logging.getLogger(__name__)


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

  logger.info('Killing {} unmonitored instances'.format(len(to_stop)))
  for process in to_stop:
    group = os.getpgid(process.pid)
    os.killpg(group, signal.SIGKILL)


class InstanceManager(object):
  """ Fulfills AppServer instance assignments from the scheduler. """

  # The seconds to wait between performing health checks.
  HEALTH_CHECK_INTERVAL = 60

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
    self._zk_client = zk_client

    # Ensures only one process tries to make changes at a time.
    self._work_lock = AsyncLock()

    self._health_checker = PeriodicCallback(
      self._ensure_health, self.HEALTH_CHECK_INTERVAL * 1000)

    # Instances that this machine should run.
    # For example, {guestbook_default_v1: [20000, -1]}
    self._assignments = None
    # List of API server ports by project id. There may be an api server and
    # a python runtime api server per project.
    self._api_servers = {}
    self._running_instances = set()
    self._login_server = None

  def start(self):
    """ Begins processes needed to fulfill instance assignments. """

    # Update list of running instances in case the InstanceManager was
    # restarted.
    self._recover_state()

    # Subscribe to changes in controller state, which includes assignments and
    # the 'login' property.
    self._zk_client.DataWatch(CONTROLLER_STATE_NODE,
                              self._controller_state_watch)

    # Subscribe to changes in project configuration, including relevant
    # versions.
    self._projects_manager.subscriptions.append(
      self._handle_configuration_update)

    # Start the regular health check.
    self._health_checker.start()

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
    http_port = version_details['appscaleExtensions']['httpPort']

    api_server_port = yield self._ensure_api_server(version.project_id, runtime)
    yield self._source_manager.ensure_source(
      version.revision_key, source_archive, runtime)

    logger.info('Starting {}:{}'.format(version, port))

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
    elif runtime in (JAVA, JAVA8):
      # Account for MaxPermSize (~170MB), the parent process (~50MB), and thread
      # stacks (~20MB).
      max_heap = max_memory - 250
      if max_heap <= 0:
        raise BadConfigurationException(
          'Memory for Java applications must be greater than 250MB')

      start_cmd = create_java_start_cmd(
        version.project_id,
        port,
        http_port,
        self._login_server,
        max_heap,
        pidfile,
        version.revision_key,
        api_server_port,
        runtime
      )

      env_vars.update(create_java_app_env(self._deployment_config, runtime,
                                          version.project_id))
    else:
      raise BadConfigurationException(
        'Unknown runtime {} for {}'.format(runtime, version.project_id))

    logger.info("Start command: " + str(start_cmd))
    logger.info("Environment variables: " + str(env_vars))

    base_version = version.revision_key.rsplit(VERSION_PATH_SEPARATOR, 1)[0]
    log_tag = "app_{}".format(hashlib.sha1(base_version).hexdigest()[:28])

    monit_app_configuration.create_config_file(
      watch,
      start_cmd,
      pidfile,
      port,
      env_vars,
      max_memory,
      self._syslog_server,
      check_port=True,
      kill_exceeded_memory=True,
      log_tag=log_tag,
    )

    full_watch = '{}-{}'.format(watch, port)

    yield self._monit_operator.reload(self._thread_pool)

    # The reload command does not block, and we don't have a good way to check
    # if Monit is ready with its new configuration yet. If the daemon begins
    # reloading while it is handling the 'start', it can end up in a state
    # where it never starts the process. As a temporary workaround, this
    # small period allows it to finish reloading. This can be removed if
    # instances are started inside a cgroup.
    yield gen.sleep(1)
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
      logger.error("Error while setting up log rotation for application: {}".
                    format(version.project_id))

  @gen.coroutine
  def populate_api_servers(self):
    """ Find running API servers. """

    def api_server_info(entry):
      prefix, port = entry.rsplit('-', 1)
      index = 0
      project_id = prefix[len(API_SERVER_PREFIX):]
      index_and_id = project_id.split('_', 1)
      if len(index_and_id) > 1:
        index = int(index_and_id[0])
        project_id = index_and_id[1]
      return project_id, index, int(port)

    monit_entries = yield self._monit_operator.get_entries()
    monit_entry_list = [entry for entry in monit_entries
                        if entry.startswith(API_SERVER_PREFIX)]
    monit_entry_list.sort()
    server_entries = [api_server_info(entry) for entry in monit_entry_list]

    for project_id, index, port in server_entries:
      ports =  (self._api_servers[project_id] if project_id in
                                                 self._api_servers else [])
      if not ports:
        ports = [port]
        self._api_servers[project_id] = ports
      else:
        ports.insert(index, port)

  def _recover_state(self):
    """ Establishes current state from Monit entries. """
    logger.info('Getting current state')
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
  def _ensure_api_server(self, project_id, runtime):
    """ Make sure there is a running API server for a project.

    Args:
      project_id: A string specifying the project ID.
      runtime: The runtime for the project
    Returns:
      An integer specifying the API server port.
    """
    ensure_app_server_api = runtime==JAVA8
    if project_id in self._api_servers:
      api_server_ports = self._api_servers[project_id]
      if not ensure_app_server_api:
        raise gen.Return(api_server_ports[0])
      elif len(api_server_ports) > 1:
          raise gen.Return(api_server_ports[1])

    server_port = MAX_API_SERVER_PORT
    for ports in self._api_servers.values():
      for port in ports:
        if port <= server_port:
          server_port = port - 1

    full_watch = None
    if not project_id in self._api_servers:
      watch = ''.join([API_SERVER_PREFIX, project_id])
      full_watch = '-'.join([watch, str(server_port)])
      pidfile = os.path.join(VAR_DIR, '{}.pid'.format(full_watch))
      zk_locations = appscale_info.get_zk_node_ips()
      start_cmd = ' '.join([API_SERVER_LOCATION,
                          '--port', str(server_port),
                          '--project-id', project_id,
                          '--zookeeper-locations', ' '.join(zk_locations)])
      monit_app_configuration.create_config_file(
        watch,
        start_cmd,
        pidfile,
        server_port,
        max_memory=DEFAULT_MAX_APPSERVER_MEMORY,
        check_port=True,
        check_host='127.0.0.1')
      api_server_port = server_port
    else:
      api_server_port = self._api_servers[project_id][0]

    full_watch_app = None
    if ensure_app_server_api:
      # Start an Python 27 runtime API server
      if api_server_port==server_port:
        server_port -= 1
      watch = ''.join([API_SERVER_PREFIX, '1_', project_id])
      full_watch_app = '-'.join([watch, str(server_port)])
      pidfile = os.path.join(VAR_DIR, '{}.pid'.format(full_watch_app))
      start_cmd = create_python_api_start_cmd(project_id,
                                              self._login_server,
                                              server_port,
                                              pidfile,
                                              api_server_port)
      monit_app_configuration.create_config_file(
        watch,
        start_cmd,
        pidfile,
        server_port,
        max_memory=DEFAULT_MAX_APPSERVER_MEMORY,
        check_port=True,
        check_host='127.0.0.1',
        group='api-server')
      self._api_servers[project_id] = [api_server_port, server_port]
    else:
      self._api_servers[project_id] = [server_port]

    yield self._monit_operator.reload(self._thread_pool)
    if full_watch:
      yield self._monit_operator.send_command_retry_process(full_watch, 'start')
    if full_watch_app:
      yield self._monit_operator.send_command_retry_process(full_watch_app, 'start')

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

  def _instance_healthy(self, port):
    """ Determines the health of an instance with an HTTP request.

    Args:
      port: An integer specifying the port the instance is listening on.
    Returns:
      A boolean indicating whether or not the instance is healthy.
    """
    url = "http://" + self._private_ip + ":" + str(port) + FETCH_PATH
    try:
      opener = urllib2.build_opener(NoRedirection)
      response = opener.open(url, timeout=HEALTH_CHECK_TIMEOUT)
      if response.code == httplib.SERVICE_UNAVAILABLE:
        return False
    except IOError:
      return False

    return True

  @gen.coroutine
  def _wait_for_app(self, port):
    """ Waits for the application hosted on this machine, on the given port,
        to respond to HTTP requests.

    Args:
      port: Port where app is hosted on the local machine
    Returns:
      True on success, False otherwise
    """
    deadline = time.time() + START_APP_TIMEOUT

    while time.time() < deadline:
      if self._instance_healthy(port):
        raise gen.Return(True)

      logger.debug('Instance at port {} is not ready yet'.format(port))
      yield gen.sleep(BACKOFF_TIME)

    raise gen.Return(False)

  @gen.coroutine
  def _add_routing(self, instance):
    """ Tells the AppController to begin routing traffic to an AppServer.

    Args:
      instance: An Instance.
    """
    logger.info('Waiting for {}'.format(instance))
    start_successful = yield self._wait_for_app(instance.port)
    if not start_successful:
      monit_watch = ''.join(
        [MONIT_INSTANCE_PREFIX, instance.revision_key, '-',
         str(instance.port)])
      yield self._unmonitor_and_terminate(monit_watch)
      yield self._monit_operator.reload(self._thread_pool)
      logger.warning('{} did not come up in time'.format(instance))
      return

    self._routing_client.register_instance(instance)
    self._running_instances.add(instance)

  @gen.coroutine
  def _stop_api_server(self, project_id):
    """ Make sure there are no running API servers for a project.

    Args:
      project_id: A string specifying the project ID.
    """
    if project_id not in self._api_servers:
      return

    ports = self._api_servers[project_id]
    for index, port in enumerate(ports):
      index_str = '' if index==0 else '{}_'.format(index)
      watch = '{}{}{}-{}'.format(API_SERVER_PREFIX, index_str, project_id, port)
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
      logger.info(
        'unregister_instance: non-existent instance {}'.format(instance))

    yield self._unmonitor_and_terminate(monit_watch)

    project_instances = [instance_ for instance_ in self._running_instances
                         if instance_.project_id == instance.project_id]
    if not project_instances:
      yield self._stop_api_server(instance.project_id)
      remove_logrotate(instance.project_id)

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

  @gen.coroutine
  def _restart_unrouted_instances(self):
    """ Restarts instances that the router considers offline. """
    with (yield self._work_lock.acquire()):
      failed_instances = yield self._routing_client.get_failed_instances()
      for version_key, port in failed_instances:
        try:
          instance = next(instance for instance in self._running_instances
                          if instance.version_key == version_key
                          and instance.port == port)
        except StopIteration:
          # If the manager has no recored of that instance, remove routing.
          self._routing_client.unregister_instance(Instance(version_key, port))
          continue

        try:
          version = self._projects_manager.version_from_key(
            instance.version_key)
        except KeyError:
          # If the version no longer exists, avoid doing any work. The
          # scheduler should remove any assignments for it.
          continue

        logger.warning('Restarting failed instance: {}'.format(instance))
        yield self._stop_app_instance(instance)
        yield self._start_instance(version, instance.port)

  @gen.coroutine
  def _restart_unavailable_instances(self):
    """ Restarts instances that fail health check requests. """
    with (yield self._work_lock.acquire()):
      for instance in self._running_instances:
        # TODO: Add a threshold to avoid restarting on a transient error.
        if not self._instance_healthy(instance.port):
          try:
            version = self._projects_manager.version_from_key(
              instance.version_key)
          except KeyError:
            # If the version no longer exists, avoid doing any work. The
            # scheduler should remove any assignments for it.
            continue

          logger.warning('Restarting failed instance: {}'.format(instance))
          yield self._stop_app_instance(instance)
          yield self._start_instance(version, instance.port)

  @gen.coroutine
  def _ensure_health(self):
    """ Checks to make sure all required instances are running and healthy. """
    yield self._restart_unrouted_instances()
    yield self._restart_unavailable_instances()

    # Just as an infrequent sanity check, fulfill assignments and enforce
    # instance details.
    yield self._fulfill_assignments()
    yield self._enforce_instance_details()

  @gen.coroutine
  def _fulfill_assignments(self):
    """ Starts and stops instances in order to fulfill assignments. """

    # If the manager has not been able to retrieve a valid set of assignments,
    # don't do any work.
    if self._assignments is None:
      return

    if self._login_server is None:
      return

    with (yield self._work_lock.acquire()):
      # Stop versions that aren't assigned.
      to_stop = [instance for instance in self._running_instances
                 if instance.version_key not in self._assignments]
      for version_key in {instance.version_key for instance in to_stop}:
        logger.info('{} is no longer assigned'.format(version_key))

      for instance in to_stop:
        yield self._stop_app_instance(instance)

      for version_key, assigned_ports in self._assignments.items():
        try:
          version = self._projects_manager.version_from_key(version_key)
        except KeyError:
          # If the version no longer exists, avoid doing any work. The
          # scheduler should remove any assignments for it.
          continue

        # The number of required instances that don't have an assigned port.
        new_assignment_count = sum(port == -1 for port in assigned_ports)

        # Stop instances that aren't assigned. If the assignment list includes
        # any -1s, match them to running instances that aren't in the assigned
        # ports list.
        candidates = [instance for instance in self._running_instances
                      if instance.version_key == version_key
                      and instance.port not in assigned_ports]
        unmatched_instances = candidates[new_assignment_count:]
        for running_instance in unmatched_instances:
          logger.info('{} is no longer assigned'.format(running_instance))
          yield self._stop_app_instance(running_instance)

        # Start defined ports that aren't running.
        running_ports = [instance.port for instance in self._running_instances
                         if instance.version_key == version_key]
        for port in assigned_ports:
          if port != -1 and port not in running_ports:
            yield self._start_instance(version, port)

        # Start new assignments that don't have a match.
        candidates = [instance for instance in self._running_instances
                      if instance.version_key == version_key
                      and instance.port not in assigned_ports]
        to_start = max(new_assignment_count - len(candidates), 0)
        for _ in range(to_start):
          yield self._start_instance(version, self._get_lowest_port())

  @gen.coroutine
  def _enforce_instance_details(self):
    """ Ensures all running instances are configured correctly. """
    with (yield self._work_lock.acquire()):
      # Restart instances with an outdated revision or login server.
      for instance in self._running_instances:
        try:
          version = self._projects_manager.version_from_key(instance.version_key)
        except KeyError:
          # If the version no longer exists, avoid doing any work. The
          # scheduler should remove any assignments for it.
          continue

        instance_login_server = get_login_server(instance)
        login_server_changed = (
          instance_login_server is not None and
          self._login_server is not None and
          self._login_server != instance_login_server)
        if (instance.revision_key != version.revision_key or
            login_server_changed):
          logger.info('Configuration changed for {}'.format(instance))
          yield self._stop_app_instance(instance)
          yield self._start_instance(version, instance.port)

  def _assignments_from_state(self, controller_state):
    """ Extracts the current machine's assignments from controller state.

    Args:
      controller_state: A dictionary containing controller state.
    """
    def version_assignments(data):
      return [int(server.split(':')[1]) for server in data['appservers']
              if server.split(':')[0] == self._private_ip]

    return {
      version_key: version_assignments(data)
      for version_key, data in controller_state['@app_info_map'].items()
      if version_assignments(data)}

  @gen.coroutine
  def _update_controller_state(self, encoded_controller_state):
    """ Handles updates to controller state.

    Args:
      encoded_controller_state: A JSON-encoded string containing controller
        state.
    """
    try:
      controller_state = json.loads(encoded_controller_state)
    except (TypeError, ValueError):
      # If the controller state isn't usable, don't do any work.
      logger.warning(
        'Invalid controller state: {}'.format(encoded_controller_state))
      return

    new_assignments = self._assignments_from_state(controller_state)
    login_server = controller_state['@options']['login']

    if new_assignments != self._assignments:
      logger.info('New assignments: {}'.format(new_assignments))
      self._assignments = new_assignments
      yield self._fulfill_assignments()

    if login_server != self._login_server:
      logger.info('New login server: {}'.format(login_server))
      self._login_server = login_server
      yield self._enforce_instance_details()

  def _controller_state_watch(self, encoded_controller_state, _):
    """ Handles updates to controller state.

    Args:
      encoded_controller_state: A JSON-encoded string containing controller
        state.
    """
    persistent_update_controller_state = retry_data_watch_coroutine(
      CONTROLLER_STATE_NODE, self._update_controller_state)
    IOLoop.instance().add_callback(
      persistent_update_controller_state, encoded_controller_state)

  @gen.coroutine
  def _handle_configuration_update(self, event):
    """ Handles updates to a project's configuration details.

    Args:
      event: An appscale.admin.instance_manager.projects_manager.Event object.
    """
    relevant_versions = {instance.version_key
                         for instance in self._running_instances}
    if self._assignments is not None:
      relevant_versions |= set(self._assignments.keys())

    for version_key in relevant_versions:
      if event.affects_version(version_key):
        logger.info('New revision for version: {}'.format(version_key))
        yield self._enforce_instance_details()
        break
