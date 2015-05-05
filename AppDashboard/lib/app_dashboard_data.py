# pylint: disable-msg=W0703
# pylint: disable-msg=E1103

import logging
import sys
from google.appengine.ext import ndb
from google.appengine.api import users
from app_dashboard_helper import AppDashboardHelper
from app_dashboard_helper import AppHelperException


class DashboardDataRoot(ndb.Model):
  """ A Datastore Model that contains information about the AppScale cloud
  itself, and is shown to users regardless of whether or not they are logged in.

  Fields:
    head_node_ip: A str that corresponds the hostname (IP or FQDN) of the
      machine that runs the nginx service, providing a full proxy to Google App
      Engine apps hosted in this cloud.
    table: A str containing the name of the database that we are using to
      implement support for the Datastore API (e.g., hypertable, cassandra).
    replication: An int that corresponds to the number of replicas present for
      each piece of data in the underlying datastore.
    timestamp: A timestamp of when this entity was created.
  """
  head_node_ip = ndb.StringProperty()
  table = ndb.StringProperty()
  replication = ndb.IntegerProperty()
  timestamp = ndb.DateTimeProperty(auto_now=True, auto_now_add=True)


class ServerStatus(ndb.Model):
  """ A Datastore Model that contains information about a single virtual machine
  running in this AppScale deployment.

  Fields:
    id: The hostname (IP or FQDN) corresponding to this machine. This field
      isn't explicitly defined because all ndb.Models have a str id that
      uniquely identifies them in the Datastore.
    cpu: The percent of CPU currently in use on this machine.
    memory: The percent of RAM currently in use on this machine.
    disk: The percent of hard disk space in use on this machine.
    roles: A list of strs, where each str corresponds to a service that this
      machine runs.
    timestamp: A timestamp of when this entity was created.
  """
  cpu = ndb.StringProperty()
  memory = ndb.StringProperty()
  disk = ndb.StringProperty()
  roles = ndb.StringProperty(repeated=True)
  timestamp = ndb.DateTimeProperty(auto_now=True, auto_now_add=True)


class RequestInfo(ndb.Model):
  """ A Datastore Model that stores a single measurement of the average number
  of requests per second that reach a Google App Engine application.

  Fields:
    app_id: A string, the application identifier.
    num_of_requests: The average number of requests per second that reached
      haproxy for a Google App Engine application.
    timestamp: The date and time when the AppController took the measurement
      of how many requests access haproxy for an App Engine app.
  """
  app_id = ndb.StringProperty(required=True)
  num_of_requests = ndb.FloatProperty()
  timestamp = ndb.DateTimeProperty()


class AppStatus(ndb.Model):
  """ A Datastore Model that contains information about where an application
  hosted in AppScale can be located, to display to users.

  Fields:
    name: The application ID associated with this Google App Engine app.
    url: A URL that points to an nginx server, which serves a full proxy to
      this Google App Engine app.
    timestamp: A timestamp of when this entity was created.
  """
  name = ndb.StringProperty()
  url = ndb.StringProperty()
  timestamp = ndb.DateTimeProperty(auto_now=True, auto_now_add=True)


class UserInfo(ndb.Model):
  """ A Datastore Model that contains information about users who have signed up
  for accounts in this AppScale deployment.

  Fields:
    id: A str that contains the e-mail address the user signed up with. This
      field isn't explicitly defined because all ndb.Models have a str id that
      uniquely identifies them in the Datastore.
    is_user_cloud_admin: A bool that indicates if the user is authorized to
      perform any action on this AppScale cloud (e.g., remove any app, view all
      logs).
    can_upload_apps: A bool that indicates if the user is authorized to upload
      Google App Engine applications to this AppScale cloud via the web
      interface.
    owned_apps: A list of strs, where each str represents an application ID
      that the user has administrative rights on.
    timestamp: A timestamp of when this entity was created.
  """
  is_user_cloud_admin = ndb.BooleanProperty()
  can_upload_apps = ndb.BooleanProperty()
  owned_apps = ndb.StringProperty(repeated=True)
  timestamp = ndb.DateTimeProperty(auto_now=True, auto_now_add=True)


class InstanceInfo(ndb.Model):
  """ A Datastore Model that contains information about AppServer processes that
  are running Google App Engine applications in this AppScale deployment.

  Fields:
    appid: A str that names that application ID this instance is running an app
      for. We avoid setting the appid as the Model's id here because multiple
      AppServers can run for the same appid.
    host: A str that names the IP address or FQDN of the machine that runs this
      instance.
    port: An int that indicates what port this AppServer process is bound to
      on the given hostname. Note that this port is firewalled off to outside
      traffic, so users cannot access the AppServer by visiting host:port in a
      browser.
    language: A str that indicates if this instance is running a Python, Java,
      Go, or PHP App Engine application.
    timestamp: A timestamp of when this entity was created.
  """
  appid = ndb.StringProperty()
  host = ndb.StringProperty()
  port = ndb.IntegerProperty()
  language = ndb.StringProperty()
  timestamp = ndb.DateTimeProperty(auto_now=True, auto_now_add=True)

class AppDashboardData():
  """ AppDashboardData leverages ndb (which itself utilizes Memcache and the
  Datastore) to implement a cache in front of SOAP-exposed services provided
  by the AppController. """


  # The name of the key that we store globally accessible Dashboard information
  # in. 
  ROOT_KEYNAME = 'AppDashboard'


  # The port that the AppMonitoring service runs on, by default.
  MONITOR_PORT = 8050


  # The port that the Celery Flower service runs on, by default.
  FLOWER_PORT = 5555


  # The port that the Monit Dashboard runs on, by default.
  MONIT_PORT = 2812


  # The sentinel app name that indicates that no apps are running on a given
  # machine.
  NO_APPS_RUNNING = "none"


  def __init__(self, helper=None):
    """ Creates a new AppDashboard, which will cache SOAP-exposed information
    provided to us by the AppDashboardHelper.

    Args:
      helper: An AppDashboardHelper, which will perform SOAP calls to the
        AppController whenever the AppDashboardData needs to update its caches.
        If None is provided here, then the AppDashboardData will create a new
        AppDashboardHelper to talk to the AppController.
    """
    self.helper = helper or AppDashboardHelper()


  def get_by_id(self, model, key_name):
    """ Retrieves an object from the datastore, referenced by its keyname.

    ndb does provide a method of the same name that does this, but we ran into
    issues mocking out both ModelName() and ModelName.get_by_id() in the same
    unit test, so using this level of indirection lets us mock out both without
    issues.

    Args:
      model: The ndb.Model that the requested object belongs to.
      key_name: A str that corresponds to the the Model's key name.
    Returns:
      The object with the given keyname, or None if that object does not exist.
    """
    return model.get_by_id(key_name)


  def get_all(self, obj, keys_only=False):
    """ Retrieves all objects from the datastore for a given model, or all of
    the keys for those objects.

    Args:
      model: The ndb.Model that the requested object belongs to.
      keys_only: A bool that indicates that only keys should be returned,
        instead of the actual objects.
    Returns:
      A list of keys (if keys_only is True), or a list of objects in the given
      model (if keys_only is False).
    """
    return obj.query().fetch(keys_only=keys_only)


  def update_all(self):
    """ Queries the AppController to learn about the currently running
    AppScale deployment.

    This method stores all information it learns about this deployment in
    the Datastore, to speed up future accesses to this data.
    """
    self.update_head_node_ip()
    self.update_database_info()
    self.update_status_info()
    self.update_application_info()
    self.update_users()


  def get_monitoring_url(self):
    """ Retrieves the URL where the AppMonitoring web service can be found in
    this AppScale deployment (typically on the login node).

    Returns:
      A str that contains a URL where low-level monitoring information is
      displayed to users.
    """
    return "http://{0}:{1}".format(self.get_head_node_ip(), self.MONITOR_PORT)


  def get_flower_url(self):
    """ Retrieves the URL where the Celery Flower web service can be found in
    this AppScale deployment (typically on the login node).

    Returns:
      A str that contains a URL where low-level monitoring information is
      displayed to users.
    """
    return "http://{0}:{1}".format(self.get_head_node_ip(), self.FLOWER_PORT)


  def get_monit_url(self):
    """ Retrieves the URL where the Monit Dashboard web service can be found in
    this AppScale deployment.

    Note that although a Monit Dashboard runs on each node, we will send users
    to the one on the login node.

    Returns:
      A str that names the URL where the services on the login node can be
      viewed, started, and stopped.
    """
    return "http://{0}:{1}".format(self.get_head_node_ip(), self.MONIT_PORT)


  def get_head_node_ip(self):
    """ Retrieves the IP address or FQDN where the machine running the
    shadow service can be found, via the Datastore.

    Returns:
      A str containing the IP address or FQDN of the shadow node.
    """
    dashboard_root = self.get_by_id(DashboardDataRoot, self.ROOT_KEYNAME)
    if dashboard_root and dashboard_root.head_node_ip is not None:
      return dashboard_root.head_node_ip
    else:
      return self.update_head_node_ip()


  def update_head_node_ip(self):
    """ Updates the Datastore with the IP address or FQDN of the node running
    the shadow service.

    This update is only performed if there is no data in the Datastore about the
    current location of the head node, as this is unlikely to dynamically change
    at this time.

    Returns:
      A str containing the IP address or FQDN of the shadow node, or None if
      there was an error updating the head node's IP address.
    """
    dashboard_root = self.get_by_id(DashboardDataRoot, self.ROOT_KEYNAME)
    if dashboard_root and dashboard_root.head_node_ip is not None:
      return dashboard_root.head_node_ip

    try:
      if dashboard_root is None:
        dashboard_root = DashboardDataRoot(id = self.ROOT_KEYNAME)
      dashboard_root.head_node_ip = self.helper.get_host_with_role('shadow')
      dashboard_root.put()
      return dashboard_root.head_node_ip
    except Exception as err:
      logging.exception(err)
      return None


  def get_status_info(self):
    """ Retrieves the current status of each machine in this AppScale deployment
    from the Datastore.

    Returns:
      A list of dicts, where each dict contains information about one machine
        in this AppScale deployment.
    """
    servers = self.get_all(ServerStatus)
    return [{'ip' : server.key.id(), 'cpu' : server.cpu,
      'memory' : server.memory, 'disk' : server.disk, 'roles' : server.roles,
      'key' : server.key.id().translate(None, '.') } for server in servers]


  def update_status_info(self):
    """ Queries the AppController to get status information for all servers in
    this deployment, storing it in the Datastore for later viewing.
    """
    try:
      nodes = self.helper.get_appcontroller_client().get_stats()
      updated_statuses = []
      for node in nodes:
        status = self.get_by_id(ServerStatus, node['ip'])
        if status:
          # Make sure that at least one field changed before we decide to
          # update this ServerStatus.
          if status.cpu != str(node['cpu']) or \
            status.memory != str(node['memory']) or \
            status.disk != str(node['disk']) or status.roles != node['roles']:

            status.cpu = str(node['cpu'])
            status.memory = str(node['memory'])
            status.disk = str(node['disk'])
            status.roles = node['roles']
            updated_statuses.append(status)
        else:
          status = ServerStatus(id = node['ip'])
          status.cpu = str(node['cpu'])
          status.memory = str(node['memory'])
          status.disk = str(node['disk'])
          status.roles = node['roles']
          updated_statuses.append(status)
      ndb.put_multi(updated_statuses)
    except Exception as err:
      logging.exception(err)


  def get_database_info(self):
    """ Retrieves the name of the database used to implement the Datastore API
    in this AppScale deployment, as well as the number of replicas stored for
    each piece of data.

    Returns:
      A dict containing the name of the database used (a str), as well as the
      number of replicas for each piece of data (an int).
    """
    dashboard_root = self.get_by_id(DashboardDataRoot, self.ROOT_KEYNAME)
    if dashboard_root and dashboard_root.table is not None and \
      dashboard_root.replication is not None:

      return {
        'table' : dashboard_root.table,
        'replication' : dashboard_root.replication
      }
    else:
      return self.update_database_info()


  def update_database_info(self):
    """ Queries the AppController for information about what datastore is used
    to implement support for the Google App Engine Datastore API, placing this
    info in the Datastore for later viewing.

    This update is only performed if there is no data in the Datastore about the
    current location of the head node, as this is unlikely to dynamically change
    at this time.

    Returns:
      A dict containing the name of the database used (a str), as well as the
      number of replicas for each piece of data (an int).
    """
    dashboard_root = self.get_by_id(DashboardDataRoot, self.ROOT_KEYNAME)
    if dashboard_root and dashboard_root.table is not None and \
      dashboard_root.replication is not None:

      return {
        'table' : dashboard_root.table,
        'replication' : dashboard_root.replication
      }
    try:
      acc = self.helper.get_appcontroller_client()
      db_info = acc.get_database_information()
      if dashboard_root is None:
        dashboard_root = DashboardDataRoot(id = self.ROOT_KEYNAME)
      dashboard_root.table = db_info['table']
      dashboard_root.replication = int(db_info['replication'])
      dashboard_root.put()
      return {
        'table' : dashboard_root.table,
        'replication' : dashboard_root.replication
      }
    except Exception as err:
      logging.exception(err)
      return {
        'table' : 'unknown',
        'replication' : 0
      }


  def get_application_info(self):
    """ Retrieves a list of Google App Engine applications running in this
      AppScale deployment, along with the URL that users can access them at.
    
    Returns:
      A dict, where each key is a str indicating the name of a Google App Engine
      application, and each value is either a str, indicating the URL where the
      application is running, or None, if the application has been uploaded but
      is not yet running (e.g., it is loading).
    """
    return dict((app.name, app.url) for app in self.get_all(AppStatus))


  def delete_app_from_datastore(self, app, email=None):
    """ Removes information about the named app from the datastore and, if
      necessary, the list of applications that this user owns.

    Args:
      app: A str that corresponds to the appid of the app to delete.
      email: A str that indicates the e-mail address of the administrator of
        this application, or None if the currently logged-in user is the admin.
    Returns:
      A UserInfo object for the user with the specified e-mail address, or if
        None was provided, the currently logged in user.
    """
    if email is None:
      user = users.get_current_user()
      if not user:
        return None
      email = user.email()

    try:
      app_status = self.get_by_id(AppStatus, app)
      if app_status:
        app_status.key.delete()
      user_info = self.get_by_id(UserInfo, email)
      if user_info:
        if app in user_info.owned_apps:
          user_info.owned_apps.remove(app)
          user_info.put()
      return user_info
    except Exception as err:
      logging.exception(err)
      return None

 
  def update_application_info(self):
    """ Queries the AppController for information about which Google App Engine
    applications are currently running, and if they are done loading, the URL
    that they can be accessed at, storing this info in the Datastore for later
    viewing.

    Returns:
      A dict, where each key is a str indicating the name of a Google App Engine
      application running in this deployment, and each value is either a str
      indicating the URL that the app can be found at, or None, if the
      application is still loading.
    """
    try:
      status_on_all_nodes = self.helper.get_status_info()
      app_names_and_urls = {}

      if not status_on_all_nodes:
        return {}

      for status in status_on_all_nodes:
        for app, done_loading in status['apps'].iteritems():
          if app == self.NO_APPS_RUNNING:
            continue
          if done_loading:
            try:
              app_names_and_urls[app] = "http://{0}:{1}".format(
                self.helper.get_login_host(), self.helper.get_app_port(app))
            except AppHelperException:
              app_names_and_urls[app] = None
          else:
            app_names_and_urls[app] = None

      # To make sure that we only update apps that have been recently uploaded
      # or removed, we grab a list of all the apps that were running before we
      # asked the AppController and compare it against the list of apps that the
      # AppController reports are now running.
      all_apps = self.get_all(AppStatus)
      all_app_names_were_running = [app.key.id() for app in all_apps]
      all_app_names_are_running = [app for app in app_names_and_urls.keys()]

      # Delete any apps that are no longer running.
      app_names_to_delete = []
      for app_name in all_app_names_were_running:
        if app_name not in all_app_names_are_running:
          app_names_to_delete.append(app_name)
        elif not app_names_and_urls[app_name]:
          app_names_to_delete.append(app_name)

      if app_names_to_delete:
        apps_to_delete = []
        for app in all_apps:
          if app.name in app_names_to_delete:
            apps_to_delete.append(app.key)
        ndb.delete_multi(apps_to_delete)

      # Add in new apps that are now running.
      app_names_to_add = []
      for app_name in all_app_names_are_running:
        if app_name not in all_app_names_were_running:
          app_names_to_add.append(app_name)
        elif app_names_and_urls[app_name]:
          app_names_to_add.append(app_name)

      # Also add in apps that have been relocated, since we need to update the
      # URL that the user can access the app at.
      for app in all_apps:
        if app.key.id() in all_app_names_are_running and \
          app.url != app_names_and_urls[app.key.id()]:
          app_names_to_add.append(app_name)

      if app_names_to_add:
        apps_to_add = [AppStatus(id=app, name=app, url=app_names_and_urls[app])
          for app in app_names_to_add]
        ndb.put_multi(apps_to_add)

      return app_names_and_urls
    except Exception as err:
      logging.exception(err)
      return {}


  def update_users(self):
    """ Queries the UserAppServer for information every user account registered
    in this AppScale deployment, storing this info in the Datastore for later
    viewing.

    Returns:
      A list of UserInfo objects, where each UserInfo corresponds to a user
      account registered in this AppScale deployment. This list will be empty if
      there was a problem accessing user information from the UserAppServer.
    """
    user_list = []
    try:
      all_users_list = self.helper.list_all_users()
      users_to_update = []
      for email in all_users_list:
        user_info = self.get_by_id(UserInfo, email)
        if user_info:
          # Only update the model in the Datastore if one of the fields has
          # changed.
          is_user_cloud_admin = self.helper.is_user_cloud_admin(email)
          can_upload_apps = self.helper.can_upload_apps(email)
          owned_apps = self.helper.get_owned_apps(email)

          if user_info.is_user_cloud_admin != is_user_cloud_admin or \
            user_info.can_upload_apps != can_upload_apps or \
            user_info.owned_apps != owned_apps:

            user_info.is_user_cloud_admin = is_user_cloud_admin
            user_info.can_upload_apps = can_upload_apps
            user_info.owned_apps = owned_apps
            users_to_update.append(user_info)

          # Either way, add the user's info to the list of all user's info.
          user_list.append(user_info)
        else:
          user_info = UserInfo(id = email)
          user_info.is_user_cloud_admin = self.helper.is_user_cloud_admin(email)
          user_info.can_upload_apps = self.helper.can_upload_apps(email)
          user_info.owned_apps = self.helper.get_owned_apps(email)
          users_to_update.append(user_info)
          user_list.append(user_info)
      ndb.put_multi(users_to_update)
      return user_list
    except Exception as err:
      logging.exception(err)
      return []


  def get_owned_apps(self):
    """ Queries the UserAppServer to see which Google App Engine applications
    the currently logged in user has administrative permissions on.

    Returns:
      A list of strs, where each str corresponds to an appid that this user
      can administer. Returns an empty list if this user isn't logged in.
    """
    user = users.get_current_user()
    if not user:
      return []
    email = user.email()
    try:
      user_info = self.get_by_id(UserInfo, email)
      if user_info:
        return user_info.owned_apps
      else:
        return []
    except Exception as err:
      logging.exception(err)
      return []


  def is_user_cloud_admin(self):
    """ Queries the UserAppServer to see if the currently logged in user has the
    authority to administer this AppScale deployment.

    Returns:
      True if the currently logged in user is a cloud administrator, and False
      otherwise (or if the user isn't logged in).
    """
    user = users.get_current_user()
    if not user:
      return False
    try:
      user_info = self.get_by_id(UserInfo, user.email())
      if user_info:
        return user_info.is_user_cloud_admin
      else:
        return False
    except Exception as err:
      logging.exception(err)
      return False


  def can_upload_apps(self):
    """ Queries the UserAppServer to see if the currently logged in user has the
    authority to upload Google App Engine applications on this AppScale
    deployment.

    Returns:
      True if the currently logged in user can upload Google App Engine
      applications, and False otherwise (or if the user isn't logged in).
    """
    user = users.get_current_user()
    if not user:
      return False
    try:
      user_info = self.get_by_id(UserInfo, user.email())
      if user_info:
        return user_info.can_upload_apps
      else:
        return False
    except Exception as err:
      logging.exception(err)
      return False
