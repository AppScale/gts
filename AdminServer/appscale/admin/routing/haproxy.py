""" Manages HAProxy operations. """
import errno
import logging
import os
import pkgutil
import subprocess
import time

from tornado import gen

from appscale.common.appscale_info import get_private_ip

logger = logging.getLogger('appscale-admin')

# The directory that contains HAProxy config files.
CONFIG_DIR = os.path.join('/', 'etc', 'haproxy')


class InvalidConfig(Exception):
  """ Indicates that a given HAProxy configuration cannot be enforced. """
  pass


class HAProxyAppVersion(object):
  """ Represents a version's HAProxy configuration. """

  # The template for a server config line.
  SERVER_TEMPLATE = ('server gae_{version}-{server} {server} '
                     'maxconn {max_connections} check')

  # The template for a version block.
  VERSION_TEMPLATE = pkgutil.get_data('appscale.admin.routing',
                                      'templates/version.cfg')

  def __init__(self, version_key, port, max_connections):
    """ Creates a new HAProxyAppVersion instance.

    Args:
      version_key: A string specifying a version
    """
    self.version_key = version_key
    self.port = port
    self.max_connections = max_connections
    self.servers = []

    self._private_ip = get_private_ip()

  def __repr__(self):
    """ Returns a print-friendly representation of the version config. """
    return 'HAProxyAppVersion<{}:{}, maxconn:{}, servers:{}>'.format(
      self.version_key, self.port, self.max_connections, self.servers)

  @property
  def block(self):
    """ Represents the version as a configuration block.

    Returns:
      A string containing the configuration block or None.
    """
    if not self.servers:
      return None

    server_lines = [
      self.SERVER_TEMPLATE.format(version=self.version_key, server=server,
                                  max_connections=self.max_connections)
      for server in self.servers]
    server_lines.sort()
    bind_location = ':'.join([self._private_ip, str(self.port)])
    return self.VERSION_TEMPLATE.format(
      version=self.version_key, bind_location=bind_location,
      servers='\n  '.join(server_lines))


class HAProxy(object):
  """ Manages HAProxy operations. """

  # The location of the combined HAProxy config file for AppServer instances.
  APP_CONFIG = os.path.join(CONFIG_DIR, 'app-haproxy.cfg')

  # The location of the pidfile for instance-related HAProxy processes.
  APP_PID = os.path.join('/', 'var', 'run', 'appscale', 'app-haproxy.pid')

  # The location of the unix socket used for reporting stats.
  APP_STATS_SOCKET = os.path.join(CONFIG_DIR, 'stats')

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

  def __init__(self):
    """ Creates a new HAProxy operator. """
    self.connect_timeout_ms = self.DEFAULT_CONNECT_TIMEOUT * 1000
    self.client_timeout_ms = self.DEFAULT_CLIENT_TIMEOUT * 1000
    self.server_timeout_ms = self.DEFAULT_SERVER_TIMEOUT * 1000
    self.versions = {}
    self.reload_future = None
    self.last_reload = time.time()

  @property
  def config(self):
    """ Represents the current state as an HAProxy configuration file.

    Returns:
      A string containing a complete HAProxy configuration.
    """
    unique_ports = set()
    for version in self.versions.values():
      if version.port in unique_ports:
        raise InvalidConfig('Port {} is used by more than one '
                            'version'.format(version.port))

      unique_ports.add(version.port)

    version_blocks = [self.versions[key].block
                      for key in sorted(self.versions.keys())
                      if self.versions[key].block]
    return self.BASE_TEMPLATE.format(
      stats_socket=self.APP_STATS_SOCKET,
      connect_timeout=self.connect_timeout_ms,
      client_timeout=self.client_timeout_ms,
      server_timeout=self.server_timeout_ms,
      versions='\n'.join(version_blocks))

  @gen.coroutine
  def reload(self):
    """ Groups closely-timed reload operations. """
    if self.reload_future is None or self.reload_future.done():
      self.reload_future = self._reload()

    yield self.reload_future

  @gen.coroutine
  def _reload(self):
    """ Updates the routing entries if they've changed. """
    time_since_reload = time.time() - self.last_reload
    wait_time = max(self.RELOAD_COOLDOWN - time_since_reload, 0)
    yield gen.sleep(wait_time)
    self.last_reload = time.time()

    try:
      new_content = self.config
    except InvalidConfig as error:
      logger.error(str(error))
      return

    try:
      with open(self.APP_CONFIG, 'r') as app_config_file:
        existing_content = app_config_file.read()
    except IOError as error:
      if error.errno != errno.ENOENT:
        raise

      existing_content = ''

    if new_content == existing_content:
      return

    with open(self.APP_CONFIG, 'w') as app_config_file:
      app_config_file.write(new_content)

    try:
      with open(self.APP_PID) as pid_file:
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

    if pid is None:
      subprocess.check_call(['haproxy', '-f', self.APP_CONFIG, '-D',
                             '-p', self.APP_PID])
    else:
      subprocess.check_call(['haproxy', '-f', self.APP_CONFIG, '-D',
                             '-p', self.APP_PID, '-sf', str(pid)])

    logger.info('Updated HAProxy config')
