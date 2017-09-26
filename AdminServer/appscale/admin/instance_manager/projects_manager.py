""" Keeps track of details for each active version. """

import json
import logging
import os

from tornado.ioloop import IOLoop

from appscale.common.constants import CONFIG_DIR
from appscale.common.constants import VERSION_PATH_SEPARATOR

logger = logging.getLogger('appscale-admin')


class VersionManager(object):
  """ Keeps track of version details. """
  def __init__(self, zk_client, project_id, service_id, version_id, callback):
    """ Creates a new VersionManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
      callback: A function to call whenever the version is updated.
    """
    self.zk_client = zk_client
    self.version_details = None
    self.project_id = project_id
    self.service_id = service_id
    self.version_id = version_id
    self.callback = callback
    self._stopped = False

    self.version_node = '/appscale/projects/{}/services/{}/versions/{}'.format(
      project_id, service_id, version_id)
    self.watch = zk_client.DataWatch(self.version_node,
                                     self._update_version_watch)

  def update_version(self, new_version):
    """ Caches new version details.

    Args:
      new_version: A JSON string specifying version details.
    """
    if new_version is not None:
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
    if self.callback is not None:
      self.callback()

  def ensure_watch(self):
    """ Restarts the watch if it has been cancelled. """
    if self._stopped:
      self._stopped = False
      self.watch = self.zk_client.DataWatch(self.version_node,
                                            self._update_version_watch)

  def _update_version_watch(self, new_version, _):
    """ Handles updates to a version node.

    Args:
      new_version: A JSON string specifying version details.
    """
    if new_version is None:
      self._stopped = True
      return False

    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_version, new_version)


class ServiceManager(dict):
  """ Keeps track of versions for a service. """
  def __init__(self, zk_client, project_id, service_id, callback):
    """ Creates a new ServiceManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      callback: A function to call whenever a version is updated.
    """
    super(ServiceManager, self).__init__()
    self.zk_client = zk_client
    self.project_id = project_id
    self.service_id = service_id
    self.callback = callback
    self._stopped = False

    self.versions_node = '/appscale/projects/{}/services/{}/versions'.format(
      project_id, service_id)
    zk_client.ensure_path(self.versions_node)
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
        self[version_id] = VersionManager(
          self.zk_client, self.project_id, self.service_id, version_id,
          self.callback)

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

    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_versions, new_versions_list)


class ProjectManager(dict):
  """ Keeps track of services for a project. """
  def __init__(self, zk_client, project_id, callback):
    """ Creates a new ProjectManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
      callback: A function to call whenever a version is updated.
    """
    super(ProjectManager, self).__init__()
    self.zk_client = zk_client
    self.project_id = project_id
    self.callback = callback
    self._stopped = False

    self.services_node = '/appscale/projects/{}/services'.format(project_id)
    zk_client.ensure_path(self.services_node)
    self.watch = zk_client.ChildrenWatch(self.services_node,
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
        self[service_id] = ServiceManager(self.zk_client, self.project_id,
                                          service_id, self.callback)

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

    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_services, new_services_list)


class GlobalProjectsManager(dict):
  """ Keeps track of projects. """
  def __init__(self, zk_client, callback=None):
    """ Creates a new GlobalProjectsManager.

    Args:
      zk_client: A KazooClient.
      callback: A function to call whenever a version is updated.
    """
    super(GlobalProjectsManager, self).__init__()
    self.zk_client = zk_client
    self.callback = callback

    zk_client.ensure_path('/appscale/projects')
    zk_client.ChildrenWatch('/appscale/projects', self._update_projects_watch)

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
        self[project_id] = ProjectManager(self.zk_client, project_id,
                                          self.callback)

  def _update_projects_watch(self, new_projects_list):
    """ Handles the creation and deletion of projects.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_projects_list: A fresh list of strings specifying existing projects.
    """
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_projects, new_projects_list)
