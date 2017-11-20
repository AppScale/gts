""" Generates and keeps track of transaction IDs. """
from __future__ import division

import logging
import time

from kazoo.exceptions import KazooException
from kazoo.exceptions import NodeExistsError
from kazoo.exceptions import NotEmptyError
from tornado.ioloop import IOLoop

from appscale.admin.utils import retry_children_watch_coroutine
from ..dbconstants import BadRequest
from ..dbconstants import InternalError

logger = logging.getLogger('appscale-datastore')

# Containers for txid sequences start with this string.
CONTAINER_PREFIX = 'txids'

# Transaction ID sequence nodes start with this string.
COUNTER_NODE_PREFIX = 'tx'

# ZooKeeper stores the sequence counter as a signed 32-bit integer.
MAX_SEQUENCE_COUNTER = 2 ** 31 - 1

# The name of the node used for manually setting a txid offset.
OFFSET_NODE = 'txid_offset'

# Nodes that indicate a cross-group transaction start with this string.
XG_PREFIX = 'xg'


class ProjectTransactionManager(object):
  """ Generates and keeps track of transaction IDs for a project. """
  def __init__(self, project_id, zk_client):
    """ Creates a new ProjectTransactionManager.

    Args:
      project_id: A string specifying a project ID.
    """
    self.project_id = project_id
    self.zk_client = zk_client

    self._project_node = '/appscale/apps/{}'.format(self.project_id)

    # Allows users to manually modify transaction IDs after a binary migration.
    self._txid_manual_offset = 0
    self._offset_node = '/'.join([self._project_node, OFFSET_NODE])
    self.zk_client.DataWatch(self._offset_node, self._update_offset)

    # Allows the manager to use a new container after one is exhausted.
    self._txid_automatic_offset = 0
    self._counter_path = '/'.join([self._project_node, CONTAINER_PREFIX])
    self.zk_client.ensure_path(self._project_node)
    self.zk_client.ensure_path(self._counter_path)
    self.zk_client.ChildrenWatch(self._project_node, self._update_project)

    # Containers that do not need to be checked for open transactions.
    self._inactive_containers = set()

  def create_transaction_id(self, xg):
    """ Generates a new transaction ID.

    Args:
      xg: A boolean indicating a cross-group transaction.
    Returns:
      An integer specifying the created transaction ID.
    Raises:
      InternalError if unable to create a new transaction ID.
    """
    current_time = time.time()
    counter_path_prefix = '/'.join([self._counter_path, COUNTER_NODE_PREFIX])
    try:
      new_path = self.zk_client.create(
        counter_path_prefix, value=str(current_time), sequence=True)
    except KazooException:
      message = 'Unable to create new transaction ID'
      logger.exception(message)
      raise InternalError(message)

    counter = int(new_path.split('/')[-1].lstrip(COUNTER_NODE_PREFIX))

    if counter < 0:
      logger.debug('Removing invalid counter')
      self._delete_counter(new_path)
      self._update_auto_offset()
      return self.create_transaction_id(xg)

    txid = self._txid_manual_offset + self._txid_automatic_offset + counter

    if txid == 0:
      self._delete_counter(new_path)
      return self.create_transaction_id(xg)

    if xg:
      xg_path = '/'.join([new_path, XG_PREFIX])
      try:
        self.zk_client.create(xg_path, value=str(current_time))
      except KazooException:
        message = 'Unable to create new cross-group transaction ID'
        logger.exception(message)
        raise InternalError(message)

    self._last_txid_created = txid
    return txid

  def delete_transaction_id(self, txid):
    """ Removes a transaction ID from the list of active transactions.

    Args:
      txid: An integer specifying a transaction ID.
    """
    corrected_counter = txid - self._txid_manual_offset

    # The number of counters a container can store (including 0).
    container_size = MAX_SEQUENCE_COUNTER + 1

    container_count = int(corrected_counter / container_size) + 1
    container_suffix = '' if container_count == 1 else str(container_count)
    container_name = CONTAINER_PREFIX + container_suffix
    container_path = '/'.join([self._project_node, container_name])

    counter_value = corrected_counter % container_size
    node_name = COUNTER_NODE_PREFIX + str(counter_value).zfill(10)
    full_path = '/'.join([container_path, node_name])
    self._delete_counter(full_path)

  def get_open_transactions(self):
    """ Fetches a list of active transactions.

    Returns:
      A list of integers specifying transaction IDs.
    Raises:
      InternalError if unable to fetch list of transaction IDs.
    """
    txids = []
    active_containers = self._active_containers()
    for index, container in enumerate(active_containers):
      container_name = container.split('/')[-1]
      container_count = int(container_name[len(CONTAINER_PREFIX):] or 1)
      container_size = MAX_SEQUENCE_COUNTER + 1
      auto_offset = (container_count - 1) * container_size
      offset = self._txid_manual_offset + auto_offset

      try:
        paths = self.zk_client.get_children(container)
      except KazooException:
        message = 'Unable to fetch list of counters'
        logger.exception(message)
        raise InternalError(message)

      counter_nodes = [path.split('/')[-1] for path in paths]
      txids.extend([offset + int(node.lstrip(COUNTER_NODE_PREFIX))
                    for node in counter_nodes])

      # If there are no counters left in an old container, mark it inactive.
      if not counter_nodes and index < len(active_containers) - 1:
        self._inactive_containers.add(container_name)

    return txids

  def _delete_counter(self, path):
    """ Removes a counter node.

    Args:
      path: A string specifying a ZooKeeper path.
    """
    try:
      try:
        self.zk_client.delete(path)
      except NotEmptyError:
        # Cross-group transaction nodes have a child node.
        self.zk_client.delete(path, recursive=True)
    except KazooException:
      # Let the transaction groomer clean it up.
      logger.exception('Unable to delete counter')

  def _active_containers(self):
    """ Determines the containers that need to be checked for transactions.

    Returns:
      A tuple of strings specifying ZooKeeper paths.
    """
    container_name = self._counter_path.split('/')[-1]
    container_count = int(container_name[len(CONTAINER_PREFIX):] or 1)

    all_containers = [CONTAINER_PREFIX + str(index + 1)
                      for index in range(container_count)]
    all_containers[0] = CONTAINER_PREFIX

    return tuple('/'.join([self._project_node, container])
                 for container in all_containers
                 if container not in self._inactive_containers)

  def _update_auto_offset(self):
    """ Ensures there is a usable sequence container. """
    container_name = self._counter_path.split('/')[-1]
    container_count = int(container_name[len(CONTAINER_PREFIX):] or 1)
    next_node = CONTAINER_PREFIX + str(container_count + 1)
    next_path = '/'.join([self._project_node, next_node])

    try:
      self.zk_client.create(next_path)
    except NodeExistsError:
      # Another process may have already created the new counter.
      pass
    except KazooException:
      message = 'Unable to create transaction ID counter'
      logger.exception(message)
      raise InternalError(message)

    try:
      node_list = self.zk_client.get_children(self._project_node)
    except KazooException:
      message = 'Unable to find transaction ID counter'
      logger.exception(message)
      raise InternalError(message)

    self._update_project_sync(node_list)

  def _update_offset(self, new_offset, _):
    """ Watches for updates to the manual offset node. """
    # This assignment is atomic, so it does not need to happen in the IOLoop.
    self._txid_manual_offset = int(new_offset or 0)

  def _update_project_sync(self, node_list):
    """ Updates the record of usable sequence containers. """
    counters = [int(node[len(CONTAINER_PREFIX):] or 1)
                for node in node_list if node.startswith('txid')]
    counters.sort()

    container_suffix = '' if len(counters) == 1 else str(counters[-1])
    latest_node = CONTAINER_PREFIX + container_suffix

    self._counter_path = '/'.join([self._project_node, latest_node])

    # The number of counters a container can store (including 0).
    container_size = MAX_SEQUENCE_COUNTER + 1
    self._txid_automatic_offset = (len(counters) - 1) * container_size

  def _update_project(self, node_list):
    """ Watches for updates to the list of containers. """
    IOLoop.instance().add_callback(self._update_project_sync, node_list)


class TransactionManager(object):
  """ Generates and keeps track of transaction IDs. """
  def __init__(self, zk_client):
    """ Creates a new TransactionManager.

    Args:
      zk_client: A KazooClient.
    """
    self.zk_client = zk_client
    self.zk_client.ensure_path('/appscale/projects')
    self.projects = {}

    # Since this manager can be used synchronously, ensure that the projects
    # are populated for this IOLoop iteration.
    project_ids = self.zk_client.get_children('/appscale/projects')
    self._update_projects_sync(project_ids)

    self.zk_client.ChildrenWatch('/appscale/projects', self._update_projects)

  def create_transaction_id(self, project_id, xg=False):
    """ Generates a new transaction ID.

    Args:
      project_id: A string specifying a project ID.
      xg: A boolean indicating a cross-group transaction.
    Raises:
      BadRequest if the project does not exist.
      InternalError if unable to create a new transaction ID.
    """
    try:
      project_tx_manager = self.projects[project_id]
    except KeyError:
      raise BadRequest('The project {} was not found'.format(project_id))

    return project_tx_manager.create_transaction_id(xg)

  def delete_transaction_id(self, project_id, txid):
    """ Removes a transaction ID from the list of active transactions.

    Args:
      project_id: A string specifying a project ID.
      txid: An integer specifying a transaction ID.
    Raises:
      BadRequest if the project does not exist.
    """
    try:
      project_tx_manager = self.projects[project_id]
    except KeyError:
      raise BadRequest('The project {} was not found'.format(project_id))

    return project_tx_manager.delete_transaction_id(txid)

  def get_open_transactions(self, project_id):
    """ Fetch a list of open transactions for a given project.

    Args:
      project_id: A string specifying a project ID.
    Returns:
      A list of integers specifying transaction IDs.
    Raises:
      BadRequest if the project does not exist.
      InternalError if unable to fetch list of open transactions.
    """
    try:
      project_tx_manager = self.projects[project_id]
    except KeyError:
      raise BadRequest('The project {} was not found'.format(project_id))

    return project_tx_manager.get_open_transactions()

  def _update_projects_sync(self, new_project_ids):
    """ Updates the available projects for starting transactions.

    Args:
      new_project_ids: A list of strings specifying current project IDs.
    """
    for project_id in new_project_ids:
      if project_id not in self.projects:
        self.projects[project_id] = ProjectTransactionManager(project_id,
                                                              self.zk_client)

    for project_id in self.projects.keys():
      if project_id not in new_project_ids:
        del self.projects[project_id]

  def _update_projects(self, project_ids):
    """ Watches for changes to list of existing projects.

    Args:
      project_ids: A list of strings specifying current project IDs.
    """
    persistent_setup_projects = retry_children_watch_coroutine(
      '/appscale/projects', self._update_projects_sync)
    IOLoop.instance().add_callback(persistent_setup_projects, project_ids)
