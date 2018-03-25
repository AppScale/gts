""" Schedules servers to fulfill service assignments. """

import errno
import json
import logging
import os
import psutil
import socket
import subprocess
import time

from tornado import gen
from tornado.httpclient import AsyncHTTPClient
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.options import options

from appscale.common.async_retrying import retry_data_watch_coroutine
from appscale.common.constants import ASSIGNMENTS_PATH, CGROUP_DIR, LOG_DIR

# The cgroup used to start datastore server processes.
DATASTORE_CGROUP = ['memory', 'appscale-datastore']

logger = logging.getLogger('appscale-admin')


class ServiceTypes(object):
  """ Services recognized by the ServiceManager. """
  DATASTORE = 'datastore'


class ServerStates(object):
  """ Possible states for a server. """
  FAILED = 'failed'
  NEW = 'new'
  RUNNING = 'running'
  STARTING = 'starting'
  STOPPED = 'stopped'
  STOPPING = 'stopping'


class ProcessStopped(Exception):
  """ Indicates that the server process is no longer running. """
  pass


class StartTimeout(Exception):
  """ Indicates that a server took too long to start. """
  pass


class Server(object):
  """ Keeps track of the status and location of a specific server. """
  def __init__(self, service_type, port):
    """ Creates a new Server.

    Args:
      service_type: A string specifying the service type.
      port: An integer specifying the port to use.
    """
    self.failure = None
    self.failure_time = None
    # This is for compatibility with Hermes, which expects a monit name.
    self.monit_name = None
    self.port = port
    self.process = None
    self.state = ServerStates.NEW
    self.type = service_type

  @gen.coroutine
  def start(self):
    raise NotImplementedError()

  @gen.coroutine
  def stop(self):
    raise NotImplementedError()

  def __repr__(self):
    """ Represents the service details.

    Returns:
      A string representing the service.
    """
    return '<Service: {}:{}, {}>'.format(self.type, self.port, self.state)


class DatastoreServer(Server):
  """ Keeps track of the status and location of a datastore server. """

  # The datastore backend.
  DATASTORE_TYPE = 'cassandra'

  # The number of seconds to wait for the server to start.
  START_TIMEOUT = 30

  # The number of seconds to wait for a status check.
  STATUS_TIMEOUT = 10

  # The number of seconds to wait for the server to stop.
  STOP_TIMEOUT = 5

  def __init__(self, port, http_client, verbose):
    """ Creates a new DatastoreServer.

    Args:
      port: An integer specifying the port to use.
      http_client: An AsyncHTTPClient
      verbose: A boolean that sets logging level to debug.
    """
    super(DatastoreServer, self).__init__(ServiceTypes.DATASTORE, port)
    self.monit_name = 'datastore_server-{}'.format(port)
    self._http_client = http_client
    self._stdout = None
    self._verbose = verbose

  @gen.coroutine
  def ensure_running(self):
    """ Checks to make sure the server is still running. """
    yield self._wait_for_service(timeout=self.STATUS_TIMEOUT)

  @classmethod
  def from_pid(cls, pid, http_client):
    """ Creates a new DatastoreServer from an existing process.

    Args:
      pid: An integers specifying a process ID.
      http_client: An AsyncHTTPClient.
    """
    process = psutil.Process(pid)
    args = process.cmdline()
    port = int(args[args.index('--port') + 1])
    verbose = '--verbose' in args
    server = cls(port, http_client, verbose)
    server.process = process
    server.state = ServerStates.RUNNING
    return server

  @gen.coroutine
  def start(self):
    """ Starts a new datastore server. """
    if self.state in (ServerStates.STARTING, ServerStates.RUNNING):
      raise gen.Return()

    self.state = ServerStates.STARTING
    start_cmd = ['appscale-datastore',
                 '--type', self.DATASTORE_TYPE,
                 '--port', str(self.port)]
    if self._verbose:
      start_cmd.append('--verbose')

    log_file = os.path.join(LOG_DIR,
                            'datastore_server-{}.log'.format(self.port))
    self._stdout = open(log_file, 'a')
    self.process = psutil.Popen(
      ['cgexec', '-g', ':'.join(DATASTORE_CGROUP)] + start_cmd,
      stdout=self._stdout, stderr=subprocess.STDOUT)

    # Wait for server to bind to port before making HTTP requests.
    yield gen.sleep(1)
    yield self._wait_for_service(timeout=self.START_TIMEOUT)
    self.state = ServerStates.RUNNING

  @gen.coroutine
  def stop(self):
    """ Stops an existing datastore server. """
    if self.state in (ServerStates.STOPPING, ServerStates.STOPPED):
      raise gen.Return()

    self.state = ServerStates.STOPPING
    try:
      self._cleanup()
    finally:
      self.state = ServerStates.STOPPED

  @gen.coroutine
  def _cleanup(self):
    """ Cleans up process and file descriptor. """
    if self.process is not None:
      self.process.terminate()
      initial_stop_time = time.time()
      while True:
        if time.time() > initial_stop_time + self.STOP_TIMEOUT:
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
    server_url = 'http://localhost:{}'.format(self.port)
    start_time = time.time()
    try:
      while True:
        if not self.process.is_running():
          raise ProcessStopped('{} is no longer running'.format(self))

        if time.time() > start_time + timeout:
          raise StartTimeout('{} took too long to start'.format(self))

        try:
          response = yield self._http_client.fetch(server_url)
          if response.code == 200:
            break
        except socket.error as error:
          if error.errno != errno.ECONNREFUSED:
            raise

        yield gen.sleep(1)
    except Exception as error:
      self._cleanup()
      self.failure_time = time.time()
      self.failure = error
      self.state = ServerStates.FAILED
      raise error


class ServiceManager(object):
  """ Schedules servers to fulfill service assignments. """

  # States that satisfy the assignment.
  SCHEDULED_STATES = (ServerStates.STARTING, ServerStates.RUNNING)

  # Associates service names with server classes.
  SERVICE_MAP = {'datastore': {'server': DatastoreServer,
                               'cgroup': DATASTORE_CGROUP}}

  # The first port to use when starting a server.
  START_PORT = 4000

  # The number of seconds to wait between cleaning up servers.
  GROOMING_INTERVAL = 10

  # The number of seconds to keep track of failed servers.
  FAILED_SERVER_RETENTION = 60

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

  @classmethod
  def get_state(cls, http_client=None):
    """ Collects a list of running servers from cgroup process IDs.

    Args:
      http_client: An AsyncHTTPClient.
    Returns:
      A list of Server objects.
    """
    state = []
    for service_details in cls.SERVICE_MAP.values():
      server_class = service_details['server']
      path = [CGROUP_DIR] + service_details['cgroup'] + ['cgroup.procs']
      try:
        with open(os.path.join(*path)) as pid_list:
          for line in pid_list:
            try:
              pid = int(line)
            except ValueError:
              continue

            server = server_class.from_pid(pid, http_client)
            state.append(server)
      except IOError as error:
        if error.errno != errno.ENOENT:
          raise

    return state

  def start(self):
    """ Begin watching for assignments. """
    logger.info('Starting ServiceManager')

    # Ensure cgroup process containers exist.
    for service_details in self.SERVICE_MAP.values():
      cgroup_path = [CGROUP_DIR] + service_details['cgroup']
      try:
        os.makedirs(os.path.join(*cgroup_path))
      except OSError as error:
        if error.errno != errno.EEXIST:
          raise

    self.state = self.get_state(self._http_client)
    self._zk_client.DataWatch(self._assignments_path,
                              self._update_services_watch)
    PeriodicCallback(self._groom_servers,
                     self.GROOMING_INTERVAL * 1000).start()

  @gen.coroutine
  def _groom_servers(self):
    """ Forgets about outdated servers and fulfills assignments. """
    def outdated(server):
      if (server.state == ServerStates.FAILED and
          time.time() > server.failure_time + self.FAILED_SERVER_RETENTION):
        return True

      if server.state == ServerStates.STOPPED:
        return True

      return False

    self.state = [server for server in self.state if not outdated(server)]
    for service_type, options in self.assignments.items():
      yield self._schedule_service(service_type, options)

    for server in self.state:
      if server.state != ServerStates.RUNNING:
        continue

      IOLoop.current().spawn_callback(server.ensure_running)

  @gen.coroutine
  def _get_open_port(self):
    """ Selects an available port for a server to use.

    Returns:
      An integer specifying a port.
    """
    assigned_ports = set(service.port for service in self.state)
    port = self.START_PORT
    while True:
      # Skip ports that have been assigned.
      if port in assigned_ports:
        port += 1
        continue

      raise gen.Return(port)

  @gen.coroutine
  def _schedule_service(self, service_type, options):
    """ Schedules servers to fulfill service assignment.

    Args:
      service_type: A string specifying the service type.
      options: A dictionary specifying options to use when starting servers.
    """
    scheduled = [server for server in self.state
                 if server.type == service_type and
                 server.state in self.SCHEDULED_STATES]
    to_start = options['count'] - len(scheduled)
    if to_start < 0:
      stopped = 0
      for server in reversed(scheduled):
        if stopped >= abs(to_start):
          break

        logger.info('Stopping {}'.format(server))
        IOLoop.current().spawn_callback(server.stop)
        stopped += 1

      raise gen.Return()

    for _ in range(to_start):
      port = yield self._get_open_port()
      server_class = self.SERVICE_MAP[service_type]['server']
      server = server_class(port, self._http_client, options['verbose'])
      self.state.append(server)
      logger.info('Starting {}'.format(server))
      IOLoop.current().spawn_callback(server.start)

  @gen.coroutine
  def _update_services(self, assignments):
    """ Updates service schedules to fulfill assignments.

    Args:
      assignments: A dictionary specifying service assignments.
    """
    self.assignments = assignments
    for service_type, options in assignments.items():
      yield self._schedule_service(service_type, options)

  def _update_services_watch(self, encoded_assignments, _):
    """ Updates service schedules to fulfill assignments.

    Args:
      encoded_assignments: A JSON-encoded string specifying service
        assignments.
    """
    persistent_update_services = retry_data_watch_coroutine(
      self._assignments_path, self._update_services)
    try:
      assignments = json.loads(encoded_assignments)
    except (TypeError, ValueError):
      if encoded_assignments:
        raise

      assignments = {}

    IOLoop.instance().add_callback(persistent_update_services, assignments)
