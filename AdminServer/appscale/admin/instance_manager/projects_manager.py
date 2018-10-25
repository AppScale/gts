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

logger = logging.getLogger(__name__)


class Event(object):
  """ Represents a change in configuration. """

  PROJECT_CREATED = 'project_created'
  PROJECT_DELETED = 'project_deleted'
  SERVICE_CREATED = 'service_created'
  SERVICE_DELETED = 'service_deleted'
  VERSION_CREATED = 'version_created'
  VERSION_DELETED = 'version_deleted'
  VERSION_UPDATED = 'version_updated'

  __slots__ = ['type', 'resource']

  def __init__(self, event_type, resource):
    self.type = event_type
    self.resource = resource

  def affects_version(self, version_key):
    """ Reports whether or not the event affects a given version.

    Args:
      version_key: A string specifying the relevant version key.
    Returns:
      A boolean specifying whether or not the version is affected.
    """
    project_id, service_id, _ = version_key.split(
      VERSION_PATH_SEPARATOR)

    if self.type in (self.PROJECT_CREATED, self.PROJECT_DELETED):
      return self.resource == project_id

    if self.type in (self.SERVICE_CREATED, self.SERVICE_DELETED):
      service_key = VERSION_PATH_SEPARATOR.join([project_id, service_id])
      return self.resource == service_key

    if self.type in (self.VERSION_CREATED, self.VERSION_DELETED,
                     self.VERSION_UPDATED):
      return self.resource == version_key

    return False


class Version(object):
  """ Keeps track of version details. """
  def __init__(self, zk_client, projects_manager, project_id, service_id,
               version_id):
    """ Creates a new Version.

    Args:
      zk_client: A KazooClient.
      projects_manager: A GlobalProjectsManager object.
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
      version_id: A string specifying a version ID.
    """
    self._zk_client = zk_client
    self._projects_manager = projects_manager
    self.version_details = None
    self.project_id = project_id
    self.service_id = service_id
    self.version_id = version_id

    self._stopped = False

    self.version_node = '/appscale/projects/{}/services/{}/versions/{}'.format(
      project_id, service_id, version_id)

    # Update the version details in case this is used synchronously.
    try:
      version_details = self._zk_client.get(self.version_node)[0]
    except NoNodeError:
      version_details = None

    self.update_version(version_details)

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
    self._projects_manager.publish(Event(Event.VERSION_UPDATED, version_key))

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


class ProjectService(dict):
  """ Keeps track of a project's service details. """
  def __init__(self, zk_client, projects_manager, project_id, service_id):
    """ Creates a new ProjectService.

    Args:
      zk_client: A KazooClient.
      projects_manager: A GlobalProjectsManager object.
      project_id: A string specifying a project ID.
      service_id: A string specifying a service ID.
    """
    super(ProjectService, self).__init__()
    self._zk_client = zk_client
    self._projects_manager = projects_manager
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
      self._projects_manager.publish(Event(Event.VERSION_DELETED, version_id))

    for version_id in new_versions_list:
      if version_id not in self:
        self[version_id] = Version(
          self._zk_client, self._projects_manager, self.project_id,
          self.service_id, version_id)
        self._projects_manager.publish(
          Event(Event.VERSION_CREATED, version_id))

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


class Project(dict):
  """ Keeps track of project details. """
  def __init__(self, zk_client, projects_manager, project_id):
    """ Creates a new Project.

    Args:
      zk_client: A KazooClient.
      projects_manager: A GlobalProjectsManager object.
      project_id: A string specifying a project ID.
    """
    super(Project, self).__init__()
    self._zk_client = zk_client
    self._projects_manager = projects_manager
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
      self._projects_manager.publish(Event(Event.SERVICE_DELETED, service_id))

    for service_id in new_services_list:
      if service_id not in self:
        self[service_id] = ProjectService(
          self._zk_client, self._projects_manager, self.project_id, service_id)
        self._projects_manager.publish(
          Event(Event.SERVICE_CREATED, service_id))

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

    # A list of functions to call when configuration changes are made.
    self.subscriptions = []

    self._zk_client.ensure_path(self.PROJECTS_NODE)

    # Update the projects list in case this is used synchronously.
    projects = self._zk_client.get_children(self.PROJECTS_NODE)
    self.update_projects(projects)

    self._zk_client.ChildrenWatch(self.PROJECTS_NODE,
                                  self._update_projects_watch)

  def publish(self, event):
    """ Notifies subscribers that a configuration change happened. """
    for callback in self.subscriptions:
      IOLoop.instance().spawn_callback(callback, event)

  def version_from_key(self, version_key):
    """ Retrieves a Version from a given key.

    Args:
      version_key: A string specifying a version key.
    Returns:
      A Version object.
    """
    project_id, service_id, version_id = version_key.split(
      VERSION_PATH_SEPARATOR)
    return self[project_id][service_id][version_id]

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
      self.publish(Event(Event.PROJECT_DELETED, project_id))

    for project_id in new_projects_list:
      if project_id not in self:
        self[project_id] = Project(self._zk_client, self, project_id)
        self.publish(Event(Event.PROJECT_CREATED, project_id))

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
