""" Keeps track of details for each active version. """

import json
import logging
import os

from kazoo.exceptions import NoNodeError
from tornado.ioloop import IOLoop

from appscale.common.async_retrying import (
  retry_children_watch_coroutine, retry_data_watch_coroutine
)
from appscale.common.constants import CONFIG_DIR
from appscale.common.constants import VERSION_PATH_SEPARATOR

logger = logging.getLogger('appscale-admin')


class Version(object):
  """ Keeps track of version details. """
  def __init__(self, zk_client, project_id, service_id, version_id):
    """ Creates a new Version.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    self._zk_client = zk_client
    self.version_details = None
    self.project_id = project_id
    self.service_id = service_id
    self.version_id = version_id

    self._callbacks = []
    self._stopped = False

    self.version_node = '/appscale/projects/{}/services/{}/versions/{}'.format(
      project_id, service_id, version_id)

    # Update the version details in case this is used synchronously.
    try:
      version = self._zk_client.get(self.version_node)[0]
    except NoNodeError:
      version = None

    self.update_version(version)

    self.watch = zk_client.DataWatch(self.version_node,
                                     self._update_version_watch)

  @property
  def revision_key(self):
    if self.version_details is None:
      return None

    try:
      revision_id = self.version_details['revision']
    except KeyError:
      return None

    return VERSION_PATH_SEPARATOR.join(
      [self.project_id, self.service_id, self.version_id, str(revision_id)])

  @property
  def version_key(self):
    return VERSION_PATH_SEPARATOR.join(
      [self.project_id, self.service_id, self.version_id])

  def __repr__(self):
    details = self.version_key
    if self.version_details is not None:
      details += ', runtime={}'.format(self.version_details.get('runtime'))

    return 'Version<{}>'.format(details)

  def add_callback(self, callback):
    """ Adds function to call when there is an update.

    callback: A callable object.
    """
    if callback in self._callbacks:
      return

    self._callbacks.append(callback)

  def update_version(self, new_version):
    """ Caches new version details.

    Args:
      new_version: A JSON string specifying version details.
    """
    if new_version is None:
      self.version_details = None
      return

    self.version_details = json.loads(new_version)

    # Update port file.
    http_port = self.version_details['appscaleExtensions']['httpPort']
    version_key = VERSION_PATH_SEPARATOR.join(
      [self.project_id, self.service_id, self.version_id])
    port_file_location = os.path.join(
      CONFIG_DIR, 'port-{}.txt'.format(version_key))
    with open(port_file_location, 'w') as port_file:
      port_file.write(str(http_port))

    logger.info('Updated version details: {}'.format(version_key))
    for callback in self._callbacks:
      callback(self.version_details)

  def ensure_watch(self):
    """ Restarts the watch if it has been cancelled. """
    if self._stopped:
      self._stopped = False
      self.watch = self._zk_client.DataWatch(self.version_node,
                                            self._update_version_watch)

  def _update_version_watch(self, new_version, _):
    """ Handles updates to a version node.

    Args:
      new_version: A JSON string specifying version details.
    """
    if new_version is None:
      self._stopped = True
      return False

    persistent_update_version = retry_data_watch_coroutine(
      self.version_node, self.update_version
    )
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(persistent_update_version, new_version)


class ServiceManager(dict):
  """ Keeps track of versions for a service. """
  def __init__(self, zk_client, project_id, service_id):
    """ Creates a new ServiceManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
    """
    super(ServiceManager, self).__init__()
    self._zk_client = zk_client
    self.project_id = project_id
    self.service_id = service_id
    self._stopped = False

    self.versions_node = '/appscale/projects/{}/services/{}/versions'.format(
      project_id, service_id)
    self._zk_client.ensure_path(self.versions_node)

    # Update the versions list in case this is used synchronously.
    versions = self._zk_client.get_children(self.versions_node)
    self.update_versions(versions)

    self.watch = zk_client.ChildrenWatch(self.versions_node,
                                         self._update_versions_watch)

  def update_versions(self, new_versions_list):
    """ Establishes watches for all of a service's versions.

    Args:
      new_versions_list: A fresh list of strings specifying a service's
        version IDs.
    """
    to_stop = [version for version in self if version not in new_versions_list]
    for version_id in to_stop:
      del self[version_id]

    for version_id in new_versions_list:
      if version_id not in self:
        self[version_id] = Version(
          self._zk_client, self.project_id, self.service_id, version_id)

      self[version_id].ensure_watch()

  def stop(self):
    """ Stops all watches associated with this service. """
    for version_id in self.keys():
      del self[version_id]

    self._stopped = True

  def _update_versions_watch(self, new_versions_list):
    """ Handles the creation and deletion of a service's versions.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_versions_list: A fresh list of strings specifying a service's
        version IDs.
    """
    if self._stopped:
      return False

    persistent_update_versions = retry_children_watch_coroutine(
      self.versions_node, self.update_versions
    )
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(persistent_update_versions, new_versions_list)


class ProjectManager(dict):
  """ Keeps track of services for a project. """
  def __init__(self, zk_client, project_id):
    """ Creates a new ProjectManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
    """
    super(ProjectManager, self).__init__()
    self._zk_client = zk_client
    self.project_id = project_id
    self._stopped = False

    self.services_node = '/appscale/projects/{}/services'.format(project_id)
    self._zk_client.ensure_path(self.services_node)

    # Update the services list in case this is used synchronously.
    services = self._zk_client.get_children(self.services_node)
    self.update_services(services)

    self.watch = self._zk_client.ChildrenWatch(self.services_node,
                                               self._update_services_watch)

  def update_services(self, new_services_list):
    """ Establishes watches for all of a project's services.

    Args:
      new_services_list: A fresh list of strings specifying a project's
        service IDs.
    """
    to_stop = [service for service in self if service not in new_services_list]
    for service_id in to_stop:
      self[service_id].stop()
      del self[service_id]

    for service_id in new_services_list:
      if service_id not in self:
        self[service_id] = ServiceManager(self._zk_client, self.project_id,
                                          service_id)

  def stop(self):
    """ Stops all watches associated with this service. """
    for service_id in self.keys():
      self[service_id].stop()
      del self[service_id]

    self._stopped = True

  def _update_services_watch(self, new_services_list):
    """ Handles the creation and deletion of a project's services.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_services_list: A fresh list of strings specifying a project's
        service IDs.
    """
    if self._stopped:
      return False

    persistent_update_services = retry_children_watch_coroutine(
      self.services_node, self.update_services
    )
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(persistent_update_services, new_services_list)


class GlobalProjectsManager(dict):
  """ Keeps track of projects. """

  # The ZooKeeper node where a list of projects is stored.
  PROJECTS_NODE = '/appscale/projects'

  def __init__(self, zk_client):
    """ Creates a new GlobalProjectsManager.

    Args:
      zk_client: A KazooClient.
    """
    super(GlobalProjectsManager, self).__init__()
    self._zk_client = zk_client

    self._zk_client.ensure_path(self.PROJECTS_NODE)

    # Update the projects list in case this is used synchronously.
    projects = self._zk_client.get_children(self.PROJECTS_NODE)
    self.update_projects(projects)

    self._zk_client.ChildrenWatch(self.PROJECTS_NODE,
                                  self._update_projects_watch)

  def update_projects(self, new_projects_list):
    """ Establishes watches for all existing projects.

    Args:
      new_projects_list: A fresh list of strings specifying existing
        project IDs.
    """
    to_stop = [project for project in self if project not in new_projects_list]
    for project_id in to_stop:
      self[project_id].stop()
      del self[project_id]

    for project_id in new_projects_list:
      if project_id not in self:
        self[project_id] = ProjectManager(self._zk_client, project_id)

  def _update_projects_watch(self, new_projects_list):
    """ Handles the creation and deletion of projects.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_projects_list: A fresh list of strings specifying existing projects.
    """
    persistent_update_project = retry_children_watch_coroutine(
      self.PROJECTS_NODE, self.update_projects
    )
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(persistent_update_project, new_projects_list)
