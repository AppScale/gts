# pylint: disable-msg=W0703
# pylint: disable-msg=E1103

import datetime
import logging
from google.appengine.ext import ndb
from google.appengine.api import users
from app_dashboard_helper import AppDashboardHelper


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
  avg_request_rate = ndb.FloatProperty()
  timestamp = ndb.DateTimeProperty()


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
  dash_layout_settings = ndb.JsonProperty(default=None)


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

  def build_dict(self, user_info):
    """ Generates the Lookup Dictionary for a user.

    Args:
      user_info: The current user.

    Returns:
      A dictionary containing the layout information.
    """
    if user_info:
      lookup_dict = {
        "cloud_stats": {"title": "Cloud Statistics",
                        "link": "/status/cloud",
                        "is_admin_panel": True,
                        "template": "status/cloud.html"},
        "database_stats": {"title": "Database Information",
                           "is_admin_panel": True,
                           "template": "apps/database.html"},
        "memcache_stats": {"title": "Global Memcache Statistics",
                           "is_admin_panel": True,
                           "template": "apps/memcache.html"},
        "upload_app": {"title": "Upload Application",
                       "link": "/apps/new",
                       "template": "apps/new.html"},
        "delete_app": {"title": "Delete Application",
                       "link": "/apps/delete",
                       "template": "apps/delete.html"},
        "relocate_app": {"title": "Relocate Application",
                         "link": "/apps/relocate",
                         "template": "apps/relocate.html"},
        "service_accounts": {"title": "Service Accounts",
                             "link": "/service_accounts"},
        "manage_users": {"title": "Manage Users",
                         "link": "/authorize",
                         "is_admin_panel": True,
                         "template": "authorize/cloud.html"},
        "logging": {"title": "Log Viewer",
                    "link": "/logs",
                    "template": "logs/main.html"},
        "taskqueue": {"title": "TaskQueue",
                      "link": self.get_flower_url()},
        "pull_queue_viewer": {"title": "Pull Queue Viewer",
                              "link": "/pull_queue_viewer"},
        "cron": {"title": "Cron",
                 "link": "/cron",
                 "template": "cron/console.html"},
        "app_console": {"title": "Application Statistics",
                        "template": "apps/console.html",
                        "link": "/apps/"},
        "datastore_viewer": {"title": "Datastore Viewer",
                             "link": "/datastore_viewer"}
      }
      if user_info.can_upload_apps:
        lookup_dict["app_management"] = {"App Management":
                                         [{"upload_app": lookup_dict[
                                             "upload_app"]},
                                          {"delete_app": lookup_dict[
                                              "delete_app"]},
                                          {"relocate_app": lookup_dict[
                                              "relocate_app"]},
                                          {"service_accounts": lookup_dict[
                                              "service_accounts"]}]}
      if user_info.is_user_cloud_admin:
        lookup_dict["appscale_management"] = {"AppScale Management":
                                              [{"cloud_stats": lookup_dict[
                                                  "cloud_stats"]},
                                               {"manage_users": lookup_dict[
                                                   "manage_users"]}]}
      if user_info.owned_apps or user_info.is_user_cloud_admin:
        sections = ['taskqueue', 'pull_queue_viewer', 'logging',
                    'app_console', 'cron', 'datastore_viewer']
        lookup_dict["debugging_monitoring"] = {
          "Debugging/Monitoring": [{section: lookup_dict[section]}
                                   for section in sections]
        }
      return lookup_dict
    else:
      return {}

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
      obj: The ndb.Model that the requested object belongs to.
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
    self.get_database_info()
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
        dashboard_root = DashboardDataRoot(id=self.ROOT_KEYNAME)
      dashboard_root.head_node_ip = self.helper.get_head_node_ip()
      dashboard_root.put()
      return dashboard_root.head_node_ip
    except Exception as err:
      logging.exception(err)
      return None

  def update_request_info(self, version_key):
    """ Queries the AppController to get request information for the given
    version, storing it in the Datastore for later viewing.

    Args:
      version_key: A string specifying the version key in the form
        project-id_service-id_version-id.
    """
    app_id = version_key.split('_')[0]
    try:
      acc = self.helper.get_appcontroller_client()
      request_info = acc.get_request_info(version_key)
      timestamp = datetime.datetime.fromtimestamp(request_info.get('timestamp'))
      lastHourDateTime = timestamp - datetime.timedelta(hours=1)
      old_requests_query = RequestInfo.query(RequestInfo.timestamp <
                                             lastHourDateTime)
      old_requests = []
      for key in old_requests_query.iter(keys_only=True):
        old_requests.append(key)
      ndb.delete_multi(old_requests)
      request_stats = RequestInfo(
                      app_id=app_id,
                      timestamp=timestamp,
                      avg_request_rate=request_info.get('avg_request_rate'),
                      num_of_requests=request_info.get('num_of_requests'))
      request_stats.put()
    except Exception as err:
      logging.exception(err)

  def get_database_info(self):
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
        'table': dashboard_root.table,
        'replication': dashboard_root.replication
      }
    try:
      acc = self.helper.get_appcontroller_client()
      db_info = acc.get_database_information()
      if dashboard_root is None:
        dashboard_root = DashboardDataRoot(id=self.ROOT_KEYNAME)
      dashboard_root.table = db_info['table']
      dashboard_root.replication = int(db_info['replication'])
      dashboard_root.put()
      return {
        'table': dashboard_root.table,
        'replication': dashboard_root.replication
      }
    except Exception as err:
      logging.exception(err)
      return {
        'table': 'unknown',
        'replication': 0
      }

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
          dash_layout_settings = self.get_dash_layout_settings(user_info)
          stored_layout_settings = user_info.dash_layout_settings
          if stored_layout_settings:
            dash_change = \
              (dash_layout_settings.get("nav") != stored_layout_settings.get(
                "nav")) or \
              (dash_layout_settings.get("panel") != stored_layout_settings.get(
                "panel"))
          else:
            dash_change = True

          if user_info.is_user_cloud_admin != is_user_cloud_admin or \
                  user_info.can_upload_apps != can_upload_apps or \
                  dash_change or \
                  user_info.owned_apps != owned_apps:
            user_info.is_user_cloud_admin = is_user_cloud_admin
            user_info.can_upload_apps = can_upload_apps
            user_info.owned_apps = owned_apps
            user_info.dash_layout_settings = dash_layout_settings
            users_to_update.append(user_info)

          # Either way, add the user's info to the list of all user's info.
          user_list.append(user_info)
        else:
          user_info = UserInfo(id=email)
          user_info.is_user_cloud_admin = self.helper.is_user_cloud_admin(email)
          user_info.can_upload_apps = self.helper.can_upload_apps(email)
          user_info.owned_apps = self.helper.get_owned_apps(email)
          user_info.dash_layout_settings = self.get_dash_layout_settings(
            user_info=user_info)
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

  def set_dash_layout_settings(self, values=None, user_info=None):
    """ Saves user settings for customizing the UI of the Dashboard.

    Args:
      values: A dict that defines the layout of the dash page from
        /ajax/layout/save.
      user_info: The current user.
    """
    if not user_info:
      user = users.get_current_user()
      if not user:
        return
      email = user.email()
      try:
        user_info = self.get_by_id(UserInfo, email)
      except Exception as err:
        logging.exception(err)
        pass
    if user_info:
      if type(values) is not dict:
        # Assign values to the default admin template.
        values = {
          "nav": ["app_management", "appscale_management",
                  "debugging_monitoring"],
          "panel": ["app_console", "upload_app", "cloud_stats",
                    "database_stats",
                    "memcache_stats"]
        }
      layout_settings = values
      lookup_dict = self.build_dict(user_info=user_info)
      layout_settings['nav'] = [{key: lookup_dict.get(key)} for key in
                                layout_settings.get('nav') if
                                key in lookup_dict]

      layout_settings['panel'] = [{key: lookup_dict.get(key)} for key in
                                  layout_settings.get('panel') if
                                  key in lookup_dict and (
                                  lookup_dict.get(key).get(
                                    'is_admin_panel') ==
                                  user_info.is_user_cloud_admin
                                  or not lookup_dict.get(key).get(
                                    'is_admin_panel'))]
      user_info.dash_layout_settings = layout_settings
      user_info.put()
      return user_info.dash_layout_settings
    return

  def rebuild_dash_layout_settings_dict(self, email=None):
    """ Rebuilds the user's layout settings in case there is an update
      to the lookup dictionary.

    Args:
      email: A str that indicates the e-mail address of the user logging in.
    """
    if email is None:
      return {}
    try:
      user_info = self.get_by_id(UserInfo, email)
      if user_info:
        try:
          if user_info.dash_layout_settings:
            lookup_dict = self.build_dict(user_info=user_info)
            values = user_info.dash_layout_settings
            default_nav = ["app_management", "appscale_management",
                           "debugging_monitoring"]

            nav_list = []
            for key_dict in values.get('nav'):
              for temp_key in key_dict:
                nav_list.append(temp_key)

            if set(nav_list) != set(default_nav):
              for key in default_nav:
                if nav_list.count(key) == 0:
                  nav_list.append(key)

            default_panel = ["app_console", "upload_app", "cloud_stats",
                             "database_stats", "memcache_stats"]

            panel_list = []
            for key_dict in values.get('panel'):
              for temp_key in key_dict:
                panel_list.append(temp_key)

            if set(panel_list) != set(default_panel):
              for key in default_panel:
                if panel_list.count(key) == 0:
                  panel_list.append(key)

            values['nav'] = [{key: lookup_dict.get(key)}
                             for key in nav_list if key in lookup_dict]

            new_panel_vals = []
            for key in panel_list:
              is_admin_panel = lookup_dict.get(key).get('is_admin_panel')
              if key in lookup_dict and (not is_admin_panel or
                                         is_admin_panel ==
                                         user_info.is_user_cloud_admin):
                new_panel_vals.append({key: lookup_dict.get(key)})

            values['panel'] = new_panel_vals
            user_info.dash_layout_settings = values
            user_info.put()
            return user_info.dash_layout_settings
          else:
            return self.set_dash_layout_settings(user_info=user_info)
        except Exception as err:
          logging.exception(err)
          return self.set_dash_layout_settings(user_info=user_info)
    except Exception as err:
      logging.exception(err)

  def get_dash_layout_settings(self, user_info=None):
    """ Queries the UserAppServer to see what settings the user has saved
    for customizing the UI of the Dashboard.

    Args:
      user_info: The current user.

    Returns:
      A dictionary containing the customization layout.
    """
    if not user_info:
      user = users.get_current_user()
      if not user:
        return {}
      email = user.email()
      try:
        user_info = self.get_by_id(UserInfo, email)
      except Exception as err:
        logging.exception(err)
    if user_info:
      try:
        if user_info.dash_layout_settings:
          return user_info.dash_layout_settings
      except Exception as err:
        logging.exception(err)
      return self.set_dash_layout_settings(user_info=user_info)
    return {}

  def get_panel_key_info(self, key_val):
    user = users.get_current_user()
    if not user:
      return False
    try:
      user_info = self.get_by_id(UserInfo, user.email())
      if user_info:
        return self.build_dict(user_info=user_info).get(key_val)
      else:
        return
    except Exception as err:
      logging.exception(err)
