""" Schedules servers to fulfill service assignments. """
import collections
import errno
import functools
import json
import logging
import monotonic
import os
import psutil
import re
import socket
import subprocess

from builtins import range

from kazoo.protocol.states import KazooState
from psutil import NoSuchProcess
from tornado import gen, web
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.locks import Lock as AsyncLock
from tornado.options import options

from appscale.admin.constants import BOOKED_PORTS, NoPortsAvailable
from appscale.common.async_retrying import retry_data_watch_coroutine
from appscale.common.constants import (ASSIGNMENTS_PATH, CGROUP_DIR, HTTPCodes,
                                       LOG_DIR, VAR_DIR)

# The characters allowed in a service identifier (eg. datastore)
SERVICE_ID_CHARS = '[a-z_]'

logger = logging.getLogger(__name__)


class ServiceTypes(object):
  """ Services recognized by the ServiceManager. """
  DATASTORE = 'datastore'
  SEARCH = 'search'


class ServerStates(object):
  """ Possible states for a server. """
  FAILED = 'failed'
  NEW = 'new'
  RUNNING = 'running'
  STARTING = 'starting'
  STOPPED = 'stopped'
  STOPPING = 'stopping'


class BadRequest(Exception):
  """ Indicates a problem with the client request. """
  pass


class ProcessStopped(Exception):
  """ Indicates that the server process is no longer running. """
  pass


class StartTimeout(Exception):
  """ Indicates that a server took too long to start. """
  pass


def slice_path(slice_name):
  """ Retrieves the file system path for a slice.

  Args:
    slice_name: A string specifying the slice name.
  Returns:
    A string specifying the location of the slice.
  """
  path = [CGROUP_DIR, 'systemd']
  slice_parts = slice_name.split('-')
  for index in range(len(slice_parts)):
    slice_part = '-'.join(slice_parts[:index + 1])
    path.append('.'.join([slice_part, 'slice']))

  return os.path.join(*path)


def pids_in_slice(slice_name):
  """ Retrieves the PIDs running in a slice.

  Args:
    slice_name: A string specifying the slice name.
  Returns:
    A list of integers specifying the running PIDs.
  """
  pids = []
  for root, _, files in os.walk(slice_path(slice_name)):
    for file_ in files:
      if not file_ == 'cgroup.procs':
        continue

      with open(os.path.join(root, file_)) as procs_file:
        for line in procs_file:
          pid_str = line.strip()
          if pid_str:
            pids.append(int(pid_str))

  return pids


def cpu_multiple_count_supplier(cpu_multiplier, cpu_multiple_fallback=1):
  """
  A function returning a multiple of the cpu count.

  Use with functools.partial for Services count_supplier

  Args:
    cpu_multiplier: A float multiplier for the count calculation
    cpu_multiple_fallback: Result to return when cpu count not available
  """
  cpu_count = psutil.cpu_count()
  if cpu_count is None:
    return cpu_multiple_fallback
  return int(cpu_count * cpu_multiplier)


class Service(object):
  """
  A container for service specific properties
  and functions to use in ServerManager.
  """
  def __init__(self, type_, slice_, start_cmd_matcher, start_cmd_builder,
               health_probe, min_port, max_port,
               start_timeout=30, status_timeout=10, stop_timeout=5,
               monit_name_fmt='{type}_server-{port}',
               log_filename_fmt='{type}_server-{port}.log',
               count_supplier=None):
    """ Initializes instance of Service.

    Args:
      type_: A str - name of the service.
      slice_: A str - name of cgroup slice to use for the service.
      start_cmd_matcher: A func getting cmd args list and returning port.
      start_cmd_builder: A func building args from port and assignment options.
      health_probe: A func getting port and returning True if server is healthy.
      min_port: An int - minimal port to use for the service.
      max_port: An int - maximal port to use for the service.
      start_timeout: An int - max time to wait for server to start (in seconds).
      status_timeout: An int - max time to wait for server status (in seconds).
      stop_timeout: An int - max time to wait for server to stop (in seconds).
      monit_name_fmt: A format str containing 'type' and 'port' keywords.
      log_filename_fmt: A format str containing 'type' and 'port' keywords.
      count_supplier: A func supplying the default service count.
    """
    self.type = type_
    self.slice = slice_
    self.port_from_start_cmd = start_cmd_matcher
    self.get_start_cmd = start_cmd_builder
    self.health_probe = health_probe
    self.min_port = min_port
    self.max_port = max_port
    self.start_timeout = start_timeout
    self.status_timeout = status_timeout
    self.stop_timeout = stop_timeout
    self._monit_name_fmt = monit_name_fmt
    self._log_filename_fmt = log_filename_fmt
    self.count_supplier = count_supplier

  def monit_name(self, port):
    """ Renders a monit name to use in Hermes stats.

    Args:
      port: An int - port where server is listening on.
    Returns:
      A string representing name to use in Hermes as monit name.
    """
    return self._monit_name_fmt.format(type=self.type, port=port)

  def log_filename(self, port):
    """ Renders a filename to use for logs.

    Args:
      port: An int - port where server is listening on.
    Returns:
      A string representing filename (not a full path, just name).
    """
    return self._log_filename_fmt.format(type=self.type, port=port)

  def default_count(self):
    """ Calculate the default service count for this host.

    Returns:
      An int value for the default service count.
    """
    if self.count_supplier:
      return max(1, int(self.count_supplier()))
    else:
      return 1


# =============================
#    Datastore service info:
# -----------------------------

def port_from_datastore_start_cmd(args):
  """ Extracts appscale-datastore server port from command line arguments.

  Args:
    args: A list representing command line arguments of server process.
  Returns:
    An integer representing port where server is listening on.
  Raises:
    ValueError if args doesn't correspond to appscale-datastore.
  """
  if len(args) < 2 or not args[1].endswith('appscale-datastore'):
    raise ValueError('Not a datastore start command')
  return int(args[args.index('--port') + 1])


def datastore_start_cmd(port, assignment_options):
  """ Prepares command line arguments for starting a new datastore server.

  Args:
    port: An int - tcp port to start datastore server on.
    assignment_options: A dict containing assignment options from ZK.
  Returns:
    A list of command line arguments.
  """
  start_cmd = ['appscale-datastore',
               '--type', assignment_options.get('backend', 'cassandra'),
               '--port', str(port)]
  if assignment_options.get('verbose'):
    start_cmd.append('--verbose')
  return start_cmd


@gen.coroutine
def datastore_health_probe(base_url):
  """ Verifies if datastore server is responsive.

  Args:
    base_url: A str - datastore server base URL to test.
  Returns:
    True if the serve is responsive and False otherwise.
  """
  http_client = AsyncHTTPClient()
  try:
    response = yield http_client.fetch(base_url)
    raise gen.Return(response.code == 200)
  except socket.error as error:
    if error.errno != errno.ECONNREFUSED:
      raise
    raise gen.Return(False)


datastore_service = Service(
  type_='datastore', slice_='appscale-datastore',
  start_cmd_matcher=port_from_datastore_start_cmd,
  start_cmd_builder=datastore_start_cmd, health_probe=datastore_health_probe,
  min_port=4000, max_port=5999,
  start_timeout=30, status_timeout=10, stop_timeout=5,
  monit_name_fmt='datastore_server-{port}',
  log_filename_fmt='datastore_server-{port}.log',
  count_supplier=functools.partial(cpu_multiple_count_supplier, 1,
                                   cpu_multiple_fallback=3)
)


# ==========================
#    Search service info:
# --------------------------

class SearchServiceFunctions(object):

  def __init__(self):
    self.latest_health_status = None

  @staticmethod
  def port_from_search_start_cmd(args):
    """ Extracts appscale-search server port from command line arguments.

    Args:
      args: A list representing command line arguments of server process.
    Returns:
      An integer representing port where server is listening on.
    Raises:
      ValueError if args doesn't correspond to appscale-search.
    """
    search_executable = '/opt/appscale_venvs/search2/bin/appscale-search2'
    if len(args) < 2 or not args[1].endswith(search_executable):
      raise ValueError('Not a search start command')
    return int(args[args.index('--port') + 1])

  @staticmethod
  def search_start_cmd(port, assignment_options):
    """ Prepares command line arguments for starting a new search server.

    Args:
      port: An int - tcp port to start search server on.
      assignment_options: A dict containing assignment options from ZK.
    Returns:
      A list of command line arguments.
    """
    start_cmd = ['/opt/appscale_venvs/search2/bin/appscale-search2',
                 '--zk-locations'] + options.zk_locations + [
                 '--host', options.private_ip,
                 '--port', str(port)]
    if assignment_options.get('verbose'):
      start_cmd.append('--verbose')
    return start_cmd

  @gen.coroutine
  def search_health_probe(self, base_url):
    """ Verifies if search server is responsive.
    It also writes warning to logs if the server is responsive
    but reported issues with connection to ZooKeeper or Solr.

    Args:
      base_url: A str - search server base URL to test.
    Returns:
      True if the serve is responsive and False otherwise.
    """
    http_client = AsyncHTTPClient()
    try:
      response = yield http_client.fetch('{}/_health'.format(base_url))
      if response.code != 200:
        raise gen.Return(False)
      health_status = json.loads(response.body.decode('utf-8'))
      if health_status != self.latest_health_status:
        logger.debug('Search service reported new status: {}'
                     .format(health_status))
        self.latest_health_status = health_status
      if health_status['zookeeper_state'] != KazooState.CONNECTED:
        logger.warning('Zookeeper client state at search service is {}'
                       .format(health_status['zookeeper_state']))
      if not health_status['solr_live_nodes']:
        logger.warning('There are no Solr live nodes available')
      raise gen.Return(True)
    except socket.error as error:
      if error.errno != errno.ECONNREFUSED:
        raise
      raise gen.Return(False)


_search_service_functions = SearchServiceFunctions()
search_service = Service(
  type_='search', slice_='appscale-search',
  start_cmd_matcher=_search_service_functions.port_from_search_start_cmd,
  start_cmd_builder=_search_service_functions.search_start_cmd,
  health_probe=_search_service_functions.search_health_probe,
  min_port=31000, max_port=31999,
  start_timeout=30, status_timeout=10, stop_timeout=5,
  monit_name_fmt='search_server-{port}',
  log_filename_fmt='search_server-{port}.log'
)


class ServerManager(object):
  """ Keeps track of the status and location of a specific server. """

  KNOWN_SERVICES = [datastore_service, search_service]

  # The number of seconds to keep track of failed servers.
  FAILED_SERVER_RETENTION = 60

  def __init__(self, service, port, assignment_options=None, start_cmd=None):
    """ Creates a new Server.
    It accepts either assignment_options argument (to build start_cmd)
    or start_cmd of existing process.

    Args:
      service: An instance of Service.
      port: An integer specifying the port to use.
      assignment_options: A dict representing assignment options from zookeeper.
      start_cmd: A list of command line arguments used for starting server.
    """
    self.service = service
    self.failure = None
    # This is for compatibility with Hermes, which expects a monit name.
    self.monit_name = self.service.monit_name(port)
    self.port = port
    self.process = None
    self.state = ServerStates.NEW
    self.type = self.service.type
    if assignment_options is None and start_cmd is None:
      raise TypeError('assignment_options or start_cmd should be specified')
    self._assignment_options = assignment_options
    # A value from the monotonic clock indicating when a server failed.
    self._failure_time = None
    self._start_cmd = start_cmd
    self._stdout = None

    # Serializes start, stop, and monitor operations.
    self._management_lock = AsyncLock()

  @property
  def outdated(self):
    if self.state == ServerStates.FAILED:
      if (monotonic.monotonic() >
          self._failure_time + self.FAILED_SERVER_RETENTION):
        return True

    if self.state == ServerStates.STOPPED:
      return True

    return False

  @gen.coroutine
  def ensure_running(self):
    """ Checks to make sure the server is still running. """
    with (yield self._management_lock.acquire()):
      yield self._wait_for_service(timeout=self.service.status_timeout)

  @staticmethod
  def from_pid(pid, service):
    """ Creates a new ServerManager from an existing process.

    Args:
      pid: An integers specifying a process ID.
      service: An instance of Service.
    """
    process = psutil.Process(pid)
    args = process.cmdline()
    try:
      port = service.port_from_start_cmd(args)
    except ValueError:
      raise ValueError('Process #{} ({}) is not recognized'.format(args, pid))

    server = ServerManager(service, port, start_cmd=args)
    server.process = process
    server.state = ServerStates.RUNNING
    return server

  @gen.coroutine
  def restart(self):
    yield self.stop()
    yield self.start()

  @gen.coroutine
  def start(self):
    """ Starts a new server process. """
    with (yield self._management_lock.acquire()):
      if self.state == ServerStates.RUNNING:
        return

      self.state = ServerStates.STARTING
      if not self._start_cmd:
        self._start_cmd = self.service.get_start_cmd(
          self.port, self._assignment_options
        )
      log_filename = self.service.log_filename(self.port)

      log_file = os.path.join(LOG_DIR, log_filename)
      self._stdout = open(log_file, 'a')

      # With systemd-run, it's possible to start the process within the slice.
      # To keep things simple and maintain backwards compatibility with
      # pre-systemd distros, move the process after starting it.
      self.process = psutil.Popen(self._start_cmd, stdout=self._stdout,
                                  stderr=subprocess.STDOUT)
      logger.info('Started process #{} using command {}'
                  .format(self.process.pid, self._start_cmd))

      tasks_location = os.path.join(slice_path(self.service.slice), 'tasks')
      with open(tasks_location, 'w') as tasks_file:
        tasks_file.write(str(self.process.pid))

      yield self._wait_for_service(timeout=self.service.start_timeout)
      self.state = ServerStates.RUNNING

  @gen.coroutine
  def stop(self):
    """ Stops an existing server process. """
    with (yield self._management_lock.acquire()):
      if self.state == ServerStates.STOPPED:
        return

      self.state = ServerStates.STOPPING
      try:
        yield self._cleanup()
      finally:
        self.state = ServerStates.STOPPED

  @gen.coroutine
  def _cleanup(self):
    """ Cleans up process and file descriptor. """
    if self.process is not None:
      try:
        self.process.terminate()
      except NoSuchProcess:
        logger.info('Can\'t terminate process {pid} as it no longer exists'
                    .format(pid=self.process.pid))
        return

      deadline = monotonic.monotonic() + self.service.stop_timeout
      while True:
        if monotonic.monotonic() > deadline:
          self.process.kill()
          break

        try:
          self.process.wait(timeout=0)
          break
        except psutil.TimeoutExpired:
          yield gen.sleep(1)

    if self._stdout is not None:
      self._stdout.close()

  @gen.coroutine
  def _wait_for_service(self, timeout):
    """ Query server until it responds.

    Args:
      timeout: A integer specifying the number of seconds to wait.
    Raises:
      StartTimeout if start time exceeds given timeout.
    """
    base_url = 'http://{}:{}'.format(options.private_ip, self.port)
    deadline = monotonic.monotonic() + timeout
    try:
      while True:
        if not self.process.is_running():
          raise ProcessStopped('{} is no longer running'.format(self))

        if monotonic.monotonic() > deadline:
          raise StartTimeout('{} took too long to start'.format(self))

        try:
          health_result = self.service.health_probe(base_url)
          if isinstance(health_result, gen.Future):
            health_result = yield health_result
          if health_result:
            break
        except Exception as error:
          logger.error('Failed to make a health check for {} ({})'
                       .format(self.monit_name, error))

        yield gen.sleep(1)
    except Exception as error:
      self._cleanup()
      self._failure_time = monotonic.monotonic()
      self.failure = error
      self.state = ServerStates.FAILED
      raise

  def __repr__(self):
    """ Represents the server details.

    Returns:
      A string representing the server.
    """
    return '<Server: {}:{}, {}>'.format(self.type, self.port, self.state)


class ServiceManager(object):
  """ Schedules servers to fulfill service assignments. """

  # States that satisfy the assignment.
  SCHEDULED_STATES = (ServerStates.STARTING, ServerStates.RUNNING)

  # Associates service names with server classes.
  SERVICE_MAP = collections.OrderedDict([
    ('datastore', datastore_service),
    ('search', search_service),
  ])

  # The number of seconds to wait between cleaning up servers.
  GROOMING_INTERVAL = 10

  def __init__(self, zk_client):
    """ Creates new ServiceManager.

    Args:
      zk_client: A KazooClient.
    """
    self.assignments = {}
    self.state = []

    self._assignments_path = '/'.join([ASSIGNMENTS_PATH, options.private_ip])
    self._http_client = AsyncHTTPClient()
    self._zk_client = zk_client

  @staticmethod
  def get_state():
    """ Collects a list of running servers from cgroup process IDs.

    Returns:
      A list of Server objects.
    """
    state = []
    for service in ServiceManager.SERVICE_MAP.values():
      for pid in pids_in_slice(service.slice):
        server = ServerManager.from_pid(pid, service)
        state.append(server)

    return state

  def start(self):
    """ Begin watching for assignments. """
    logger.info('Starting ServiceManager')

    # Ensure cgroup process containers exist.
    for service in self.SERVICE_MAP.values():
      try:
        os.makedirs(slice_path(service.slice))
      except OSError as error:
        if error.errno != errno.EEXIST:
          raise

    self.state = self.get_state()
    self._zk_client.DataWatch(self._assignments_path,
                              self._update_services_watch)
    PeriodicCallback(self._groom_servers,
                     self.GROOMING_INTERVAL * 1000).start()

  @gen.coroutine
  def restart_service(self, service_id):
    if service_id not in self.SERVICE_MAP:
      raise BadRequest('Unrecognized service: {}'.format(service_id))

    logger.info('Restarting {} servers'.format(service_id))
    yield [server.restart() for server in self.state
           if server.type == service_id]

  @gen.coroutine
  def restart_server(self, service_id, port):
    if service_id not in self.SERVICE_MAP:
      raise BadRequest('Unrecognized service: {}'.format(service_id))

    try:
      server = next(server for server in self.state
                    if server.type == service_id and server.port == port)
    except StopIteration:
      raise BadRequest('Server not found')

    yield server.restart()

  @gen.coroutine
  def _groom_servers(self):
    """ Forgets about outdated servers and fulfills assignments. """
    self.state = [server for server in self.state if not server.outdated]
    futures = []
    for service_type, assignment_options in self.assignments.items():
      futures.append(self._schedule_service(service_type, assignment_options))

    unassigned_services = {server.type for server in self.state
                           if server.type not in self.assignments}
    for service_type in unassigned_services:
      futures.append(self._schedule_service(service_type, {'count': 0}))

    yield futures

    yield [server.ensure_running() for server in self.state
           if server.state == ServerStates.RUNNING]

  def _get_open_port(self, service):
    """ Selects an available port for a server to use.

    Returns:
      An integer specifying a port.
    """
    assigned_ports = BOOKED_PORTS | set(service.port for service in self.state)
    for port in range(service.min_port, service.max_port):
      # Skip ports that have been assigned.
      if port not in assigned_ports:
        return port
    raise NoPortsAvailable(
      'Exhausted available port for {} in range from {} to {}'
      .format(service.type, service.min_port, service.max_port)
    )

  @gen.coroutine
  def _schedule_service(self, service_type, assignment_options):
    """ Schedules servers to fulfill service assignment.

    Args:
      service_type: A string specifying the service type.
      assignment_options: A dictionary specifying options
                          to use when starting servers.
    """
    service = self.SERVICE_MAP[service_type]
    scheduled = [server for server in self.state
                 if server.type == service_type and
                 server.state in self.SCHEDULED_STATES]
    default_count = service.default_count()
    to_start = assignment_options.get('count', default_count) - len(scheduled)
    futures = []
    if to_start < 0:
      stopped = 0
      for server in reversed(scheduled):
        if stopped >= abs(to_start):
          break

        logger.info('Stopping {}'.format(server))
        futures.append(server.stop())
        stopped += 1

      return

    for _ in range(to_start):
      port = self._get_open_port(service)
      server = ServerManager(service, port, assignment_options)
      self.state.append(server)
      logger.info('Starting {}'.format(server))
      futures.append(server.start())

    yield futures

  @gen.coroutine
  def _update_services(self, assignments):
    """ Updates service schedules to fulfill assignments.

    Args:
      assignments: A dictionary specifying service assignments.
    """
    self.assignments = assignments
    yield self._groom_servers()

  def _update_services_watch(self, encoded_assignments, _):
    """ Updates service schedules to fulfill assignments.

    Args:
      encoded_assignments: A JSON-encoded string specifying service
        assignments.
    """
    persistent_update_services = retry_data_watch_coroutine(
      self._assignments_path, self._update_services)
    assignments = json.loads(encoded_assignments) if encoded_assignments else {}

    IOLoop.instance().add_callback(persistent_update_services, assignments)


class ServiceManagerHandler(web.RequestHandler):
  # The unix socket to use for receiving management requests.
  SOCKET_PATH = os.path.join(VAR_DIR, 'service_manager.sock')

  # An expression that matches server instances.
  SERVER_RE = re.compile(r'^({}+)-(\d+)$'.format(SERVICE_ID_CHARS))

  # An expression that matches service IDs.
  SERVICE_RE = re.compile('^{}+$'.format(SERVICE_ID_CHARS))

  def initialize(self, service_manager):
    """ Defines required resources to handle requests.

    Args:
      service_manager: A ServiceManager object.
    """
    self._service_manager = service_manager

  @gen.coroutine
  def post(self):
    command = self.get_argument('command')
    if command != 'restart':
      raise web.HTTPError(HTTPCodes.BAD_REQUEST,
                          '"restart" is the only supported command')

    args = self.get_arguments('arg')
    for arg in args:
      match = self.SERVER_RE.match(arg)
      if match:
        service_id = match.group(1)
        port = int(match.group(2))
        try:
          yield self._service_manager.restart_server(service_id, port)
          return
        except BadRequest as error:
          raise web.HTTPError(HTTPCodes.BAD_REQUEST, str(error))

      if self.SERVICE_RE.match(arg):
        try:
          yield self._service_manager.restart_service(arg)
          return
        except BadRequest as error:
          raise web.HTTPError(HTTPCodes.BAD_REQUEST, str(error))

      raise web.HTTPError(HTTPCodes.BAD_REQUEST,
                          'Unrecognized argument: {}'.format(arg))
