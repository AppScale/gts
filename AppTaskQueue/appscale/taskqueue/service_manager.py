""" Keeps track of the HAProxy port to use for a specific version. """

import json

from tornado.ioloop import IOLoop


class VersionPortManager(dict):
  """ Keeps track of version port details for a single service. """
  def __init__(self, zk_client, project_id, service_id):
    """ Creates a new VersionPortManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
    """
    super(VersionPortManager, self).__init__()
    self.zk_client = zk_client
    self.versions_node = '/appscale/projects/{0}/services/{1}/versions'.format(
      project_id, service_id)
    zk_client.ensure_path(self.versions_node)
    self.watch = zk_client.ChildrenWatch(self.versions_node,
                                         self._update_versions_watch)

  def update_version_ports(self, new_versions_list):
    """ Establishes watches for all existing versions and ports.

    Args:
      new_versions_list: A list of strings specifying existing version IDs.
    """
    to_remove = [version for version in self if version not in
                 new_versions_list]
    for version_id in to_remove:
      del self[version_id]

    for version_id in new_versions_list:
      if version_id not in self:
        version_info = json.loads(self.zk_client.get("{0}/{1}".format(
          self.versions_node, version_id))[0].decode('utf-8'))
        self[version_id] = version_info['appscaleExtensions']['haproxyPort']

  def _update_versions_watch(self, new_versions):
    """ Handles creation and deletion of versions.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_versions: A list of strings specifying all existing versions.
    """
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_version_ports, new_versions)

class ProjectServiceManager(dict):
  """ Keeps track of service configuration details for a single project. """
  def __init__(self, zk_client, project_id):
    """ Creates a new ProjectServiceManager.

    Args:
      zk_client: A KazooClient.
      project_id: A string specifying a project ID.
    """
    super(ProjectServiceManager, self).__init__()
    self._stopped = False
    self.zk_client = zk_client
    self.project_id = project_id
    services_node = '/appscale/projects/{}/services'.format(self.project_id)
    zk_client.ensure_path(services_node)
    self.watch = zk_client.ChildrenWatch(services_node,
                                         self._update_services_watch)

  def update_services(self, new_services_list):
    """ Establishes watches for all existing services.

    Args:
      new_services_list: A list of strings specifying existing service IDs.
    """
    to_remove = [service for service in self if service not in
                 new_services_list]
    for service_id in to_remove:
      del self[service_id]

    for service_id in new_services_list:
      if service_id not in self:
        self[service_id] = VersionPortManager(self.zk_client,
                                              self.project_id, service_id)

  def stop(self):
    """ Stops all watches associated with this service. """
    for service_id in list(self):
      del self[service_id]

    self._stopped = True

  def _update_services_watch(self, new_services):
    """ Handles creation and deletion of services.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_services: A list of strings specifying all existing services.
    """
    if self._stopped:
      return False
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_services, new_services)

class GlobalServiceManager(dict):
  """ Keeps track of service details for all projects. """
  def __init__(self, zk_client):
    """ Creates a new GlobalServiceManager.

    Args:
      zk_client: A KazooClient.
    """
    super(GlobalServiceManager, self).__init__()
    self.zk_client = zk_client
    zk_client.ensure_path('/appscale/projects')
    zk_client.ChildrenWatch('/appscale/projects', self._update_projects_watch)

  def update_projects(self, new_project_list):
    """ Establishes watches for all existing projects.

    Args:
      new_project_list: A list of strings specifying existing project IDs.
    """
    to_stop = [project for project in self if project not in new_project_list]
    for project_id in to_stop:
      self[project_id].stop()
      del self[project_id]

    for project_id in new_project_list:
      if project_id not in self:
        self[project_id] = ProjectServiceManager(self.zk_client, project_id)

  def _update_projects_watch(self, new_projects):
    """ Handles creation and deletion of projects.

    Since this runs in a separate thread, it doesn't change any state directly.
    Instead, it just acts as a bridge back to the main IO loop.

    Args:
      new_projects: A list of strings specifying all existing project IDs.
    """
    main_io_loop = IOLoop.instance()
    main_io_loop.add_callback(self.update_projects, new_projects)
