""" Manages HAProxy operations. """
import errno
import logging
import monotonic
import os
import pkgutil
import signal
import subprocess

from tornado import gen

from appscale.common.appscale_info import get_private_ip

logger = logging.getLogger(__name__)

# The directory that contains HAProxy config files.
CONFIG_DIR = os.path.join('/', 'etc', 'haproxy')

# The location of the combined HAProxy config file for AppServer instances.
APP_CONFIG = os.path.join(CONFIG_DIR, 'app-haproxy.cfg')

# The location of the combined HAProxy config file for AppScale services.
SERVICE_CONFIG = os.path.join(CONFIG_DIR, 'service-haproxy.cfg')

# The location of the pidfile for instance-related HAProxy processes.
APP_PID = os.path.join('/', 'run', 'appscale', 'app-haproxy.pid')

# The location of the pidfile for service-related HAProxy processes.
SERVICE_PID = os.path.join('/', 'run', 'appscale', 'service-haproxy.pid')

# The location of the unix socket used for reporting application stats.
APP_STATS_SOCKET = os.path.join(CONFIG_DIR, 'stats')

# The location of the unix socket used for reporting service stats.
SERVICE_STATS_SOCKET = os.path.join(CONFIG_DIR, 'service-stats')


class InvalidConfig(Exception):
  """ Indicates that a given HAProxy configuration cannot be enforced. """
  pass


class HAProxyListenBlock(object):
  """ Represents an HAProxy configuration block. """

  # The template for a server config line.
  SERVER_TEMPLATE = ('server {block_id}-{location} {location} '
                     'maxconn {max_connections} check')

  # The template for a listen block.
  BLOCK_TEMPLATE = pkgutil.get_data('appscale.admin.routing',
                                    'templates/listen_block.cfg')

  def __init__(self, block_id, port, max_connections, servers=()):
    """ Creates a new HAProxyListenBlock instance.

    Args:
      block_id: A string specifying the name of the listen block.
      port: An integer specifying the listen port.
      max_connections: An integer specifying the max number of connections.
      servers: An iterable specifying server locations.
    """
    self.block_id = block_id
    self.port = port
    self.max_connections = max_connections
    self.servers = servers

    self._private_ip = get_private_ip()

  def __repr__(self):
    """ Returns a print-friendly representation of the version config. """
    return 'HAProxyListenBlock({!r}, {!r}, {!r}, {!r})'.format(
      self.block_id, self.port, self.max_connections, self.servers)

  @property
  def block(self):
    """ Generates the configuration block.

    Returns:
      A string containing the configuration block or None.
    """
    if not self.servers:
      return None

    server_lines = [
      self.SERVER_TEMPLATE.format(block_id=self.block_id, location=server,
                                  max_connections=self.max_connections)
      for server in self.servers]
    server_lines.sort()
    bind_location = ':'.join([self._private_ip, str(self.port)])
    return self.BLOCK_TEMPLATE.format(
      block_id=self.block_id, bind_location=bind_location,
      servers='\n  '.join(server_lines))


class HAProxy(object):
  """ Manages an HAProxy process. """

  # The template for the configuration file.
  BASE_TEMPLATE = pkgutil.get_data('appscale.admin.routing',
                                   'templates/base.cfg')

  # The seconds a request can wait in the queue before it fails with a 503.
  DEFAULT_CONNECT_TIMEOUT = 120

  # The seconds a client is allowed to remain inactive.
  DEFAULT_CLIENT_TIMEOUT = 50

  # The seconds a downstream server can hold onto a request.
  DEFAULT_SERVER_TIMEOUT = 600

  # The minimum number of seconds to wait between each reload operation.
  RELOAD_COOLDOWN = .1

  def __init__(self, config_location, pid_location, stats_socket):
    """ Creates a new HAProxy operator. """
    self.connect_timeout_ms = self.DEFAULT_CONNECT_TIMEOUT * 1000
    self.client_timeout_ms = self.DEFAULT_CLIENT_TIMEOUT * 1000
    self.server_timeout_ms = self.DEFAULT_SERVER_TIMEOUT * 1000
    self.blocks = {}
    self.reload_future = None

    self._config_location = config_location
    self._pid_location = pid_location
    self._stats_socket = stats_socket

    # Given the arbitrary base of the monotonic clock, it doesn't make sense
    # for outside functions to access this attribute.
    self._last_reload = monotonic.monotonic()

  @property
  def config(self):
    """ Represents the current state as an HAProxy configuration file.

    Returns:
      A string containing a complete HAProxy configuration.
    """
    unique_ports = set()
    for block in self.blocks.values():
      if block.port in unique_ports:
        raise InvalidConfig('Port {} is used by more than one '
                            'block'.format(block.port))

      unique_ports.add(block.port)

    listen_blocks = [self.blocks[key].block
                     for key in sorted(self.blocks.keys())
                     if self.blocks[key].block]
    if not listen_blocks:
      return None

    return self.BASE_TEMPLATE.format(
      stats_socket=self._stats_socket,
      connect_timeout=self.connect_timeout_ms,
      client_timeout=self.client_timeout_ms,
      server_timeout=self.server_timeout_ms,
      listen_blocks='\n'.join(listen_blocks))

  @gen.coroutine
  def reload(self):
    """ Groups closely-timed reload operations. """
    if self.reload_future is None or self.reload_future.done():
      self.reload_future = self._reload()

    yield self.reload_future

  def _get_pid(self):
    try:
      with open(self._pid_location) as pid_file:
        pid = int(pid_file.read())
    except IOError as error:
      if error.errno != errno.ENOENT:
        raise

      pid = None

    # Check if the process is running.
    if pid is not None:
      try:
        os.kill(pid, 0)
      except OSError:
        pid = None

    return pid

  def _stop(self):
    pid = self._get_pid()
    if pid is not None:
      os.kill(pid, signal.SIGUSR1)

    try:
      os.remove(self._config_location)
    except OSError as error:
      if error.errno != errno.ENOENT:
        raise

  @gen.coroutine
  def _reload(self):
    """ Updates the routing entries if they've changed. """
    time_since_reload = monotonic.monotonic() - self._last_reload
    wait_time = max(self.RELOAD_COOLDOWN - time_since_reload, 0)
    yield gen.sleep(wait_time)
    self._last_reload = monotonic.monotonic()

    try:
      new_content = self.config
    except InvalidConfig as error:
      logger.error(str(error))
      return

    # Ensure process is not running if there is nothing to route.
    if new_content is None:
      self._stop()

    try:
      with open(self._config_location, 'r') as config_file:
        existing_content = config_file.read()
    except IOError as error:
      if error.errno != errno.ENOENT:
        raise

      existing_content = ''

    if new_content == existing_content:
      return

    with open(self._config_location, 'w') as config_file:
      config_file.write(new_content)

    pid = self._get_pid()
    if pid is None:
      subprocess.check_call(['haproxy', '-f', self._config_location, '-D',
                             '-p', self._pid_location])
    else:
      subprocess.check_call(['haproxy', '-f', self._config_location, '-D',
                             '-p', self._pid_location, '-sf', str(pid)])

    logger.info('Updated HAProxy config')
