""" Keeps track of configured datastore indexes. """
import json
import logging
import time
from kazoo.client import NoNodeError
from kazoo.protocol.states import KazooState

from tornado import gen
from tornado.ioloop import IOLoop
from tornado.locks import Event as AsyncEvent

from appscale.common.async_retrying import retry_children_watch_coroutine
from appscale.common.datastore_index import DatastoreIndex
from appscale.datastore.zkappscale.tornado_kazoo import AsyncKazooLock

logger = logging.getLogger('appscale-admin')


class IndexInaccessible(Exception):
  """ Indicates that an index is not currently accessible. """
  pass


class ProjectIndexManager(object):
  """ Keeps track of composite index definitions for a project. """

  def __init__(self, project_id, zk_client, index_manager, datastore_access):
    """ Creates a new ProjectIndexManager.

    Args:
      project_id: A string specifying a project ID.
      zk_client: A KazooClient.
      update_callback: A function that should be called with the project ID
        and index list every time the indexes get updated.
      index_manager: An IndexManager used for checking lock status.
      datastore_access: A DatastoreDistributed object.
    """
    self.project_id = project_id
    self.indexes_node = '/appscale/projects/{}/indexes'.format(self.project_id)
    self.active = True
    self.update_event = AsyncEvent()

    self._creation_times = {}
    self._index_manager = index_manager
    self._zk_client = zk_client
    self._ds_access = datastore_access

    self._zk_client.DataWatch(self.indexes_node, self._update_indexes_watch)

    # Since this manager can be used synchronously, ensure that the indexes
    # are populated for this IOLoop iteration.
    try:
      encoded_indexes = self._zk_client.get(self.indexes_node)[0]
    except NoNodeError:
      encoded_indexes = '[]'

    self.indexes = [DatastoreIndex.from_dict(self.project_id, index)
                    for index in json.loads(encoded_indexes)]

  @property
  def indexes_pb(self):
    if self._zk_client.state != KazooState.CONNECTED:
      raise IndexInaccessible('ZooKeeper connection is not active')

    return [index.to_pb() for index in self.indexes]

  @gen.coroutine
  def apply_definitions(self):
    """ Populate composite indexes that are not marked as ready yet. """
    try:
      yield self.update_event.wait()
      self.update_event.clear()
      if not self._index_manager.admin_lock.is_acquired or not self.active:
        return

      logger.info(
        'Applying composite index definitions for {}'.format(self.project_id))

      for index in self.indexes:
        if index.ready:
          continue

        # Wait until all clients have either timed out or received the new index
        # definition. This prevents entities from being added without entries
        # while the index is being rebuilt.
        creation_time = self._creation_times.get(index.id, time.time())
        consensus = creation_time + (self._zk_client._session_timeout / 1000.0)
        yield gen.sleep(max(consensus - time.time(), 0))

        yield self._ds_access.update_composite_index(
          self.project_id, index.to_pb())
        logger.info('Index {} is now ready'.format(index.id))
        self._mark_index_ready(index.id)

      logging.info(
        'All composite indexes for {} are ready'.format(self.project_id))
    finally:
      IOLoop.current().spawn_callback(self.apply_definitions)

  def delete_index_definition(self, index_id):
    """ Remove a definition from a project's list of configured indexes.

    Args:
      index_id: An integer specifying an index ID.
    """
    try:
      encoded_indexes, znode_stat = self._zk_client.get(self.indexes_node)
    except NoNodeError:
      # If there are no index definitions, there is nothing to do.
      return

    node_version = znode_stat.version
    indexes = [DatastoreIndex.from_dict(self.project_id, index)
               for index in json.loads(encoded_indexes)]

    encoded_indexes = json.dumps([index.to_dict() for index in indexes
                                  if index.id != index_id])
    self._zk_client.set(self.indexes_node, encoded_indexes,
                        version=node_version)

  def _mark_index_ready(self, index_id):
    """ Updates the index metadata to reflect the new state of the index.

    Args:
      index_id: An integer specifying an index ID.
    """
    try:
      encoded_indexes, znode_stat = self._zk_client.get(self.indexes_node)
      node_version = znode_stat.version
    except NoNodeError:
      # If for some reason the index no longer exists, there's nothing to do.
      return

    existing_indexes = [DatastoreIndex.from_dict(self.project_id, index)
                        for index in json.loads(encoded_indexes)]
    for existing_index in existing_indexes:
      if existing_index.id == index_id:
        existing_index.ready = True

    indexes_dict = [index.to_dict() for index in existing_indexes]
    self._zk_client.set(self.indexes_node, json.dumps(indexes_dict),
                        version=node_version)

  @gen.coroutine
  def _update_indexes(self, encoded_indexes):
    """ Handles changes to the list of a project's indexes.

    Args:
      encoded_indexes: A string containing index node data.
    """
    encoded_indexes = encoded_indexes or '[]'
    self.indexes = [DatastoreIndex.from_dict(self.project_id, index)
                    for index in json.loads(encoded_indexes)]

    # Mark when indexes are defined so they can be backfilled later.
    self._creation_times.update(
      {index.id: time.time() for index in self.indexes
       if not index.ready and index.id not in self._creation_times})

    self.update_event.set()

  def _update_indexes_watch(self, encoded_indexes, znode_stat):
    """ Handles updates to the project's indexes node.

    Args:
      encoded_indexes: A string containing index node data.
      znode_stat: A kazoo.protocol.states.ZnodeStat object.
    """
    if not self.active:
      return False

    IOLoop.current().add_callback(self._update_indexes, encoded_indexes)


class IndexManager(object):
  """ Keeps track of configured datastore indexes. """
  # The node which keeps track of admin lock contenders.
  ADMIN_LOCK_NODE = '/appscale/datastore/index_manager_lock'

  def __init__(self, zk_client, datastore_access, perform_admin=False):
    """ Creates a new IndexManager.

    Args:
      zk_client: A kazoo.client.KazooClient object.
      datastore_access: A DatastoreDistributed object.
      perform_admin: A boolean specifying whether or not to perform admin
        operations.
    """
    self.projects = {}
    self._wake_event = AsyncEvent()
    self._zk_client = zk_client
    self.admin_lock = AsyncKazooLock(self._zk_client, self.ADMIN_LOCK_NODE)

    # TODO: Refactor so that this dependency is not needed.
    self._ds_access = datastore_access

    self._zk_client.ensure_path('/appscale/projects')
    self._zk_client.ChildrenWatch('/appscale/projects', self._update_projects)

    # Since this manager can be used synchronously, ensure that the projects
    # are populated for this IOLoop iteration.
    project_ids = self._zk_client.get_children('/appscale/projects')
    self._update_projects_sync(project_ids)

    if perform_admin:
      IOLoop.current().spawn_callback(self._contend_for_admin_lock)

  def _update_projects_sync(self, new_project_ids):
    """ Updates the list of the deployment's projects.

    Args:
      new_project_ids: A list of strings specifying current project IDs.
    """
    for project_id in new_project_ids:
      if project_id not in self.projects:
        self.projects[project_id] = ProjectIndexManager(
          project_id, self._zk_client, self, self._ds_access)
        if self.admin_lock.is_acquired:
          IOLoop.current().spawn_callback(
            self.projects[project_id].apply_definitions)

    for project_id in self.projects.keys():
      if project_id not in new_project_ids:
        self.projects[project_id].active = False
        del self.projects[project_id]

  def _update_projects(self, project_ids):
    """ Watches for changes to list of existing projects.

    Args:
      project_ids: A list of strings specifying current project IDs.
    """
    persistent_update_projects = retry_children_watch_coroutine(
      '/appscale/projects', self._update_projects_sync)
    IOLoop.instance().add_callback(persistent_update_projects, project_ids)

  def _handle_connection_change(self, state):
    """ Notifies the admin lock holder when the connection changes.

    Args:
      state: The new connection state.
    """
    IOLoop.current().add_callback(self._wake_event.set)

  @gen.coroutine
  def _contend_for_admin_lock(self):
    """
    Waits to acquire an admin lock that gives permission to apply index
    definitions. The lock is useful for preventing many servers from writing
    the same index entries at the same time. After acquiring the lock, the
    individual ProjectIndexManagers are responsible for mutating state whenever
    a project's index definitions change.
    """
    while True:
      # Set up a callback to get notified if the ZK connection changes.
      self._wake_event.clear()
      self._zk_client.add_listener(self._handle_connection_change)

      yield self.admin_lock.acquire()
      try:
        for project_index_manager in self.projects.values():
          IOLoop.current().spawn_callback(
            project_index_manager.apply_definitions)

        # Release the lock if the kazoo client gets disconnected.
        yield self._wake_event.wait()
      finally:
        self.admin_lock.release()
