# pylint: disable-msg=W0703
# pylint: disable-msg=E1103

import logging
import sys
from google.appengine.ext import ndb
from google.appengine.api import users
from app_dashboard_helper import AppDashboardHelper
from app_dashboard_helper import AppHelperException


class DashboardDataRoot(ndb.Model):
  """ Root entity for datastore. """
  initialized_time = ndb.DateTimeProperty(auto_now=True)
  head_node_ip = ndb.StringProperty()
  table = ndb.StringProperty()
  replication = ndb.StringProperty()


class APIstatus(ndb.Model):
  """ A Datastore Model that contains information about the current state of an
  Google App Engine API that AppScale provides support for.

  Fields:
    name: A str that corresponds to the name of the Google App Engine API.
    value: A str that indicates what the current status of the API is (e.g.,
      running, failed, unknown).
    last_update: A timestamp that indicates when this API status was updated
      last (useful to know in case we haven't checked an API's status in a
      while).
  """
  name = ndb.StringProperty()
  value = ndb.StringProperty()
  last_update = ndb.DateTimeProperty(auto_now=True)


class ServerStatus(ndb.Model):
  """ A Datastore Model that contains information about a single virtual machine
  running in this AppScale deployment.

  Fields:
    ip: The hostname (IP or FQDN) corresponding to this machine.
    cpu: The percent of CPU currently in use on this machine.
    memory: The percent of RAM currently in use on this machine.
    disk: The percent of hard disk space in use on this machine.
    cloud: A str indicating which cloud this server runs in. Most deployments
      run in a single cloud ("cloud1").
    roles: A comma-separated str that lists all of the services that this
      machine runs.
  """
  ip = ndb.StringProperty()
  cpu = ndb.StringProperty()
  memory = ndb.StringProperty()
  disk = ndb.StringProperty()
  cloud = ndb.StringProperty()
  roles = ndb.StringProperty()


class AppStatus(ndb.Model):
  """ A Datastore Model that contains information about where an application
  hosted in AppScale can be located, to display to users.

  Fields:
    name: The application ID associated with this Google App Engine app.
    url: A URL that points to an nginx server, which serves a full proxy to
      this Google App Engine app.
    last_update: A timestamp that indicates when this Model was last updated
    (useful to know if the URL that hosts this app changes in response to
    failures).
  """
  name = ndb.StringProperty()
  url = ndb.StringProperty()
  last_update = ndb.DateTimeProperty(auto_now=True)


class UserInfo(ndb.Model):
  """ A Datastore Model that contains information about users who have signed up
  for accounts in this AppScale deployment.

  Fields:
    email: A str that contains the e-mail address the user signed up with.
    is_user_cloud_admin: A bool that indicates if the user is authorized to
      perform any action on this AppScale cloud (e.g., remove any app, view all
      logs).
    i_can_upload: A bool that indicates if the user is authorized to upload
      Google App Engine applications to this AppScale cloud via the web
      interface.
    user_app_list: A list of strs, where each str represents an application ID
      that the user has administrative rights on.
  """
  email = ndb.StringProperty()
  is_user_cloud_admin = ndb.BooleanProperty()
  i_can_upload = ndb.BooleanProperty()
  user_app_list = ndb.StringProperty(repeated=True)


class AppDashboardData():
  """ Helper class to interact with the datastore. """

  # Keyname for AppDashboard root entity
  ROOT_KEYNAME = 'AppDashboard'

  # Number of seconds to wait before launching refresh task.
  REFRESH_FREQUENCY = 30

  # Port number of the Monitoring service.
  MONITOR_PORT = 8050

  # Data refresh URL.
  DATASTORE_REFRESH_URL = '/status/refresh'

  # Delimiter for status roles
  STATUS_ROLES_DELIMITER = ','

  # The charcter that separates apps.
  APP_DELIMITER = ":"

  def __init__(self, helper = None):
    """ Constructor. 

    Args:
      helper: AppDashboardHelper object.
    """
    self.helper = helper
    if self.helper is None:
      self.helper = AppDashboardHelper()

    self.root = self.get_by_id(DashboardDataRoot, self.ROOT_KEYNAME)
    if not self.root:
      self.root = DashboardDataRoot(id = self.ROOT_KEYNAME)
      self.root.put()
      self.initialize_datastore()

  def get_by_id(self, obj, key):
    """ Get one object from the datastore.

    Args:
      obj: A ndb.Model class to retrieve.
      key: A string, the key name to retrieve.
    Returns:
      An object of type obj, or None.
    """
    return obj.get_by_id(key)

  def get_all(self, obj, keys_only=False):
    """ Get all objects from the datastore.

    Args:
      obj: A ndb.Model class to retrieve.
      keys_only: A boolean, to retrieve only the keys.
    Returns:
      A ndb.Query object.
    """
    return obj.query().fetch(keys_only=keys_only)

  def initialize_datastore(self):
    """ Initialze datastore. Run once per appscale deployment. """
    self.update_all()

  def update_all(self):
    """ Update all data stored in the datastore. """
    self.update_head_node_ip()
    self.update_database_info()
    self.update_apistatus()
    self.update_status_info()
    self.update_application_info()
    self.update_users()

  def get_monitoring_url(self):
    """ Returns the url of the monitoring service. 

    Returns:
      A str containing the url of the monitoring service.
    """
    try:
      url = self.get_head_node_ip()
      if url:
        return "http://{0}:{1}".format(url, self.MONITOR_PORT)
    except Exception as err:
      logging.exception(err)
    return ''

  def get_head_node_ip(self):
    """ Return the ip of the head node from the data store. 

    Returns:
      A str containing the ip of the head node.
    """
    return self.root.head_node_ip

  def update_head_node_ip(self):
    """ Query the AppController and store the ip of the head node.  """
    try:
      self.root.head_node_ip = self.helper.get_host_with_role('shadow')
      self.root.put()
    except Exception as err:
      logging.exception(err)


  def get_apistatus(self):
    """ Retrieve the API status from the datastore.

    Returns:
      A dict where the keys are the names of the services, and the values are
        the status of that service.
    """
    statuses = self.get_all(APIstatus)
    ret = {}
    for status in statuses:
      ret[status.name] = status.value
    return ret

  def update_apistatus(self):
    """ Retrieve the API status from the system and store in the datastore. """
    try:
      acc = self.helper.get_server()
      stat_dict = acc.get_api_status()
      for key in stat_dict.keys():
        store = self.get_by_id(APIstatus, key)
        if not store:
          store = APIstatus(id = key)
          store.name = key
        store.value = stat_dict[key]
        store.put()
    except Exception as err:
      logging.exception(err)

  def get_status_info(self):
    """ Return the status information for all the server in the cluster from
        the datastore.

    Returns:
      A list of dicts containing the status information on each server.
    """    
    statuses = self.get_all(ServerStatus)
    ret = []
    for status in statuses:
      server = {}
      server['ip'] = status.ip
      server['cpu'] = status.cpu
      server['memory'] = status.memory
      server['disk'] = status.disk
      server['cloud'] = status.cloud
      server['roles'] = status.roles.split(self.STATUS_ROLES_DELIMITER)
      ret.append(server)
    return ret

  def update_status_info(self):
    """ Query the AppController and get the status information for all the 
        server in the cluster and store in the datastore. """    
    try:
      acc = self.helper.get_server()
      nodes = acc.get_stats()
      for node in nodes:
        status = self.get_by_id(ServerStatus, node['ip'])
        if not status:
          status = ServerStatus(id = node['ip'])
          status.ip = node['ip']
        status.cpu    = str(node['cpu'])
        status.memory = str(node['memory'])
        status.disk   = str(node['disk'])
        status.cloud  = node['cloud']
        status.roles  = self.STATUS_ROLES_DELIMITER.join(node['roles'])
        status.put()
    except Exception as err:
      logging.exception(err)


  def get_database_info(self):
    """ Returns the table and replication information for the database of 
        this AppScale deployment.

    Return:
      A dict containing the database information.
    """
    ret = {}
    ret['table'] = self.root.table
    ret['replication'] =  self.root.replication
    return ret

  def update_database_info(self):
    """ Queries the AppController and stores the database information of this
        cloud and store in the datastore. """
    try:
      acc = self.helper.get_server()
      db_info = acc.get_database_information()
      self.root.table = db_info['table']
      self.root.replication = db_info['replication']
      self.root.put()
    except Exception as err:
      logging.exception(err)

  def get_application_info(self):
    """ Returns the list of applications running on this cloud.
    
    Returns:
      A dict where the key is the app name, and the value is
      the url of the app (if running) or None (if loading).
    """
    statuses = self.get_all(AppStatus)
    ret = {}
    for status in statuses:
      ret[status.name] = status.url
    return ret

  def delete_app_from_datastore(self, app, email=None):
    """ Remove the app from the datastore and the user's app list.

    Args:
      app: A string, the name of the app to be deleted.
      email: A string, the email address of the user's app list to be modified.
    Returns:
      The UserInfo object for the user with email=email.
    """
    if email is None:
      user = users.get_current_user()
      if not user:
        return []
      email = user.email()
    logging.info('AppDashboardData.delete_app_from_datastore(app={0}, '\
      'email={1})'.format(app, email))
      
    try:
      app_status = self.get_by_id(AppStatus, app)
      if app_status:
        app_status.delete()
      user_info = self.get_by_id(UserInfo, email)
      if user_info:
        if app in user_info.user_app_list:
          user_info.user_app_list.remove(app)
          user_info.put()
      return user_info
    except Exception as err:
      logging.exception(err)

 
  def update_application_info(self):
    """ Queries the AppController and stores the list of applications running on
        this cloud. """

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
              ret[app] = "http://" + self.helper.get_login_host() + ":"\
                  + str(self.helper.get_app_port(app))
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
    """ Query the UserAppServer and update the state of all the users. """
    return_list = []
    try:
      all_users_list = self.helper.list_all_users()
      for email in all_users_list:
        user_info = self.get_by_id(UserInfo, email)
        if not user_info:
          user_info = UserInfo(id=email)
          user_info.email = email
        user_info.is_user_cloud_admin = self.helper.is_user_cloud_admin(
          user_info.email)
        user_info.i_can_upload = self.helper.i_can_upload(user_info.email)
        user_info.user_app_list = self.helper.get_user_app_list(user_info.email)
        user_info.put()
        return_list.append(user_info)
      return return_list
    except Exception as err:
      logging.exception(err)

  def get_user_app_list(self):
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
        return user_info.user_app_list
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

  def i_can_upload(self):
    """ Queries the UserAppServer to see if the currently logged in user has the
    authority to upload Google App Engine applications on this AppScale
    deployment.

    Args:
      email: Email address of the user.
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
        return user_info.i_can_upload
      else:
        return False
    except Exception as err:
      logging.exception(err)
      return False
