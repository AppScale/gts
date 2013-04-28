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
  """
  head_node_ip = ndb.StringProperty()
  table = ndb.StringProperty()
  replication = ndb.IntegerProperty()


class ApiStatus(ndb.Model):
  """ A Datastore Model that contains information about the current state of an
  Google App Engine API that AppScale provides support for.

  Fields:
    name: A str that corresponds to the name of the Google App Engine API.
    value: A str that indicates what the current status of the API is (e.g.,
      running, failed, unknown).
  """
  name = ndb.StringProperty()
  value = ndb.StringProperty()


class ServerStatus(ndb.Model):
  """ A Datastore Model that contains information about a single virtual machine
  running in this AppScale deployment.

  Fields:
    ip: The hostname (IP or FQDN) corresponding to this machine.
    cpu: The percent of CPU currently in use on this machine.
    memory: The percent of RAM currently in use on this machine.
    disk: The percent of hard disk space in use on this machine.
    roles: A list of strs, where each str corresponds to a service that this
      machine runs.
  """
  ip = ndb.StringProperty()
  cpu = ndb.StringProperty()
  memory = ndb.StringProperty()
  disk = ndb.StringProperty()
  roles = ndb.StringProperty(repeated=True)


class AppStatus(ndb.Model):
  """ A Datastore Model that contains information about where an application
  hosted in AppScale can be located, to display to users.

  Fields:
    name: The application ID associated with this Google App Engine app.
    url: A URL that points to an nginx server, which serves a full proxy to
      this Google App Engine app.
  """
  name = ndb.StringProperty()
  url = ndb.StringProperty()


class UserInfo(ndb.Model):
  """ A Datastore Model that contains information about users who have signed up
  for accounts in this AppScale deployment.

  Fields:
    email: A str that contains the e-mail address the user signed up with.
    is_user_cloud_admin: A bool that indicates if the user is authorized to
      perform any action on this AppScale cloud (e.g., remove any app, view all
      logs).
    can_upload_apps: A bool that indicates if the user is authorized to upload
      Google App Engine applications to this AppScale cloud via the web
      interface.
    owned_apps: A list of strs, where each str represents an application ID
      that the user has administrative rights on.
  """
  email = ndb.StringProperty()
  is_user_cloud_admin = ndb.BooleanProperty()
  can_upload_apps = ndb.BooleanProperty()
  owned_apps = ndb.StringProperty(repeated=True)


class AppDashboardData():
  """ AppDashboardData leverages ndb (which itself utilizes Memcache and the
  Datastore) to implement a cache in front of SOAP-exposed services provided
  by the AppController. """


  # The name of the key that we store globally accessible Dashboard information
  # in. 
  ROOT_KEYNAME = 'AppDashboard'


  # The port that the AppMonitoring service runs on, by default.
  MONITOR_PORT = 8050


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
    self.root = self.get_by_id(DashboardDataRoot, self.ROOT_KEYNAME)
    if not self.root:
      self.root = DashboardDataRoot(id = self.ROOT_KEYNAME)
      self.root.put()
      self.update_all()


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
    self.update_api_status()
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


  def get_head_node_ip(self):
    """ Retrieves the IP address or FQDN where the machine running the
    shadow service can be found, via the Datastore.

    Returns:
      A str containing the IP address or FQDN of the shadow node.
    """
    return self.root.head_node_ip


  def update_head_node_ip(self):
    """ Updates the Datastore with the IP address or FQDN where the node running
    the shadow service can be found. """
    try:
      self.root.head_node_ip = self.helper.get_host_with_role('shadow')
      self.root.put()
    except Exception as err:
      logging.exception(err)


  def get_api_status(self):
    """ Retrieves the current status of Google App Engine APIs in this AppScale
    deployment from the Datastore.

    Returns:
      A dict, where each key is the name of an API (a str), and each value
      indicates if the API is running, has failed, or is in an unknown state
      (also a str).
    """
    return dict((api.name, api.value) for api in self.get_all(ApiStatus))


  def update_api_status(self):
    """ Updates the Datastore with the newest information about the health of
    the Google App Engine APIs available in this AppScale deployment, by
    contacting the AppController. """
    try:
      acc = self.helper.get_appcontroller_client()
      stat_dict = acc.get_api_status()
      for key in stat_dict.keys():
        store = self.get_by_id(ApiStatus, key)
        if not store:
          store = ApiStatus(id = key)
          store.name = key
        store.value = stat_dict[key]
        store.put()
    except Exception as err:
      logging.exception(err)


  def get_status_info(self):
    """ Retrieves the current status of each machine in this AppScale deployment
    from the Datastore.

    Returns:
      A list of dicts, where each dict contains information about one machine
        in this AppScale deployment.
    """
    servers = self.get_all(ServerStatus)
    return [{'ip' : server.ip, 'cpu' : server.cpu, 'memory' : server.memory,
      'disk' : server.disk, 'roles' : server.roles,
      'key' : server.key.id().translate(None, '.') } for server in servers]


  def update_status_info(self):
    """ Queries the AppController to get status information for all servers in
    this deployment, storing it in the Datastore for later viewing.
    """
    try:
      acc = self.helper.get_appcontroller_client()
      nodes = acc.get_stats()
      for node in nodes:
        status = self.get_by_id(ServerStatus, node['ip'])
        if not status:
          status = ServerStatus(id = node['ip'])
          status.ip = node['ip']
        status.cpu = str(node['cpu'])
        status.memory = str(node['memory'])
        status.disk = str(node['disk'])
        status.roles = node['roles']
        status.put()
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
    return {'table' : self.root.table, 'replication' : self.root.replication}


  def update_database_info(self):
    """ Queries the AppController for information about what datastore is used
    to implement support for the Google App Engine Datastore API, placing this
    info in the Datastore for later viewing.
    """
    try:
      acc = self.helper.get_appcontroller_client()
      db_info = acc.get_database_information()
      self.root.table = db_info['table']
      self.root.replication = int(db_info['replication'])
      self.root.put()
    except Exception as err:
      logging.exception(err)


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
        return []
      email = user.email()

    try:
      app_status = self.get_by_id(AppStatus, app)
      if app_status:
        app_status.delete()
      user_info = self.get_by_id(UserInfo, email)
      if user_info:
        if app in user_info.owned_apps:
          user_info.owned_apps.remove(app)
          user_info.put()
      return user_info
    except Exception as err:
      logging.exception(err)

 
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
      updated_status = []
      status = self.helper.get_status_info()
      ret = {}
      if len(status) > 0 and 'apps' in status[0]:
        for app in status[0]['apps'].keys():
          if app == 'none':
            break
          if status[0]['apps'][app]:
            try:
              ret[app] = "http://{0}:{1}".format(self.helper.get_login_host(),
                self.helper.get_app_port(app))
            except AppHelperException:
              ret[app] = None
          else:
            ret[app] = None
          app_status = self.get_by_id(AppStatus, app)
          if not app_status:
            app_status = AppStatus(id = app)
            app_status.name = app
          app_status.url = ret[app]
          updated_status.append(app_status)

        statuses = self.get_all(AppStatus, keys_only=True)
        ndb.delete_multi(statuses)
        return_list = []
        for status in updated_status:
          status.put()
          return_list.append(status)
      return ret
    except Exception as err:
      logging.exception(err)


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
      for email in all_users_list:
        user_info = self.get_by_id(UserInfo, email)
        if not user_info:
          user_info = UserInfo(id=email)
          user_info.email = email
        user_info.is_user_cloud_admin = self.helper.is_user_cloud_admin(
          user_info.email)
        user_info.can_upload_apps = self.helper.can_upload_apps(user_info.email)
        user_info.owned_apps = self.helper.get_owned_apps(user_info.email)
        user_info.put()
        user_list.append(user_info)
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
