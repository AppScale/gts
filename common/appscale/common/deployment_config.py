import json
import logging
import time

from kazoo.client import KazooException
from kazoo.client import KazooState
from kazoo.client import NoNodeError
from kazoo.exceptions import ZookeeperError
from threading import Lock

from .constants import TINY_WAIT


class ConfigInaccessible(Exception):
  """ Indicates that the configuration storage is not accessible. """
  pass


class InvalidConfig(Exception):
  """ Indicates that a configuration option is invalid. """
  pass


class ConfigStates(object):
  """ Possible states for DeploymentConfig. """
  LOADING = 'loading'
  LOADED = 'loaded'


class DeploymentConfigSection(object):
  """ Keeps track of a section of configuration data. """
  def __init__(self, zk_client, section):
    """ Creates a new DeploymentConfigSection.

    Args:
      zk_client: A KazooClient.
      section: A string specifying a configuration section name.
    """
    self.logger = logging.getLogger(self.__class__.__name__)
    self.zk_client = zk_client
    self.section_name = section
    self.data = {}
    self._stopped = False

    self.section_node = '/appscale/config/{}'.format(section)
    self.watch = zk_client.DataWatch(self.section_node, self._update_section)

  def ensure_watch(self):
    """ Restart the watch if it has been cancelled. """
    if self._stopped:
      self._stopped = False
      self.watch = self.zk_client.DataWatch(self.section_node,
                                            self._update_section)

  def _update_section(self, section_data, _):
    """ Updates the configuration data when the section node gets updated.

    Args:
      section_data: A JSON string specifying configuration data.
    """
    # If the section no longer exists, stop watching it.
    if section_data is None:
      self._stopped = True
      return False

    try:
      self.data = json.loads(section_data)
    except ValueError:
      self.logger.error('Invalid deployment config for {}: {}'.format(
        self.section_name, section_data))


class DeploymentConfig(object):
  """ Accesses deployment configuration options. """
  # The ZooKeeper node where configuration is stored.
  CONFIG_ROOT = '/appscale/config'

  def __init__(self, zk_client):
    """ Creates new DeploymentConfig object.

    Args:
      zk_client: A KazooClient.
    """
    self.logger = logging.getLogger(self.__class__.__name__)
    self.update_lock = Lock()
    self.state = ConfigStates.LOADING
    self.config = {}
    self.conn = zk_client
    self.conn.add_listener(self._conn_listener)
    self.conn.ensure_path(self.CONFIG_ROOT)
    self.conn.ChildrenWatch(self.CONFIG_ROOT, func=self._update_config)

  def _conn_listener(self, state):
    """ Handles changes in ZooKeeper connection state.

    Args:
      state: A string indicating the new state.
    """
    if state == KazooState.LOST:
      self.logger.warning('ZK connection lost')
    if state == KazooState.SUSPENDED:
      self.logger.warning('ZK connection suspended')
    else:
      self.logger.info('ZK connection established')

  def _load_child(self, child):
    """ Fetches the data for a configuration node.

    Args:
      child: A string containing the ZooKeeper node to fetch.
    Returns:
      A dictionary containing configuration data.
    Raises:
      InaccessibleConfig if ZooKeeper is not accessible.
    """
    node = '/'.join([self.CONFIG_ROOT, child])
    try:
      data, _ = self.conn.retry(self.conn.get, node)
    except (KazooException, ZookeeperError):
      raise ConfigInaccessible('ZooKeeper connection not available')
    except NoNodeError:
      return {}

    try:
      return json.loads(data)
    except ValueError:
      self.logger.warning('Invalid deployment config: {}'.format(child))
      return {}

  def _update_config(self, children):
    """ Updates configuration when it changes.

    Args:
      children: A list of ZooKeeper nodes.
    """
    with self.update_lock:
      self.state = ConfigStates.LOADING

      # Remove configuration sections that no longer exist.
      to_remove = [section for section in self.config
                   if section not in children]
      for section_name in to_remove:
        del self.config[section_name]

      # Add new configuration sections.
      for child in children:
        if child not in self.config:
          self.config[child] = DeploymentConfigSection(self.conn, child)

        # Handle changes that happen between watches.
        self.config[child].ensure_watch()

      self.logger.info('Deployment configuration updated')
      self.state = ConfigStates.LOADED

  def get_config(self, section):
    """ Fetches the configuration for a given section.

    Args:
      section: A string specifying the section to fetch.
    Returns:
      A dictionary containing configuration data.
    Raises:
      InaccessibleConfig if ZooKeeper is inaccessible.
    """
    # If the connection is established, it should finish loading very soon.
    while (self.state == ConfigStates.LOADING and
           self.conn.state not in (KazooState.LOST, KazooState.SUSPENDED)):
      time.sleep(TINY_WAIT)

    if self.state != ConfigStates.LOADED:
      raise ConfigInaccessible('ZooKeeper connection not available')

    with self.update_lock:
      if section not in self.config:
        return {}
      return self.config[section].data

  def close(self):
    """ Close the ZooKeeper connection. """
    self.conn.stop()
