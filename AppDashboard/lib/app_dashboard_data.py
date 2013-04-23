# pylint: disable-msg=W0703
# pylint: disable-msg=E1103

import logging
import sys
import traceback
from google.appengine.ext import db
from google.appengine.api import users
from app_dashboard_helper import AppDashboardHelper
from app_dashboard_helper import AppHelperException


class DashboardDataRoot(db.Model):
  """ Root entity for datastore. """
  initialized_time = db.DateTimeProperty(auto_now=True)
  head_node_ip = db.StringProperty()
  table = db.StringProperty()
  replication = db.StringProperty()

class APIstatus(db.Model):
  """ Status of each API in AppScale. """
  name = db.StringProperty()
  value = db.StringProperty()
  last_update = db.DateTimeProperty(auto_now=True)

class ServerStatus(db.Model):
  """ Stats of each server in the AppScale deployment. """
  ip = db.StringProperty()
  cpu = db.StringProperty()
  memory = db.StringProperty()
  disk = db.StringProperty()
  cloud = db.StringProperty()
  roles = db.StringProperty()

class AppStatus(db.Model):
  """ Status of each app running in AppScale. """
  name = db.StringProperty()
  url = db.StringProperty()
  last_update = db.DateTimeProperty(auto_now=True)

class UserInfo(db.Model):
  """ Information about users in AppScale. """
  email = db.StringProperty()
  is_user_cloud_admin = db.BooleanProperty()
  i_can_upload  = db.BooleanProperty()
  user_app_list = db.StringProperty()


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

  # The charcter that seperates apps.
  APP_DELIMITER = ":"

  def __init__(self, helper = None):
    """ Constructor. 

    Args:
      helper: AppDashboardHelper object.
    """
    self.helper = helper
    if self.helper is None:
      self.helper = AppDashboardHelper()

    self.root = self.get_one(DashboardDataRoot, self.ROOT_KEYNAME)
    if not self.root:
      self.root = DashboardDataRoot(key_name=self.ROOT_KEYNAME)
      self.root.put()
      self.initialize_datastore()

  def get_one(self, obj, key):
    """ Get one object from the datastore.

    Args:
      obj: A db.Model class to reterive.
      key: A string, the key name to reterive.
    Returns:
      An object of type obj, or None.
    """
    return obj.get_by_key_name(key)

  def get_all(self, obj, keys_only=False):
    """ Get all objects from the datastore.

    Args:
      obj: A db.Model class to reterive.
      keys_only: A boolean, to reterive only the keys.
    Returns:
      A db.Query object.
    """
    return obj.all(keys_only=keys_only)

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
      logging.info("AppDashboardData.get_monitoring_url() caught "\
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())
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
      logging.info("AppDashboardData.update_head_node_ip() caught "\
        "Exception "+ str(type(err)) + ":" + str(err) + traceback.format_exc())


  def get_apistatus(self):
    """ Reterive the API status from the datastore.

    Returns:
      A dict where the keys are the names of the services, and the values or the
       status of that service.
    """
    status_query = self.get_all(APIstatus)
    status_query.ancestor(self.root)
    ret = {}
    for status in status_query.run():
      ret[ status.name ] = status.value
    return ret

  def update_apistatus(self):
    """ Reterive the API status from the system and store in the datastore. """
    try:
      acc = self.helper.get_server()
      stat_dict = acc.get_api_status()
      for key in stat_dict.keys():
        store = self.get_one(APIstatus, key)
        if not store:
          store = APIstatus(parent = self.root, key_name = key)
          store.name = key
        store.value = stat_dict[key]
        store.put()
    except Exception as err:
      logging.info("AppDashboardData.update_apistatus() caught Exception"\
        + str(type(err)) + ":" + str(err)+ traceback.format_exc())

  def get_status_info(self):
    """ Return the status information for all the server in the cluster from
        the datastore.

    Returns:
      A list of dicts containing the status information on each server.
    """    
    status_query = self.get_all(ServerStatus)
    status_query.ancestor(self.root)
    ret = []
    for status in status_query.run():
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
        status = self.get_one(ServerStatus, node['ip'])
        if not status:
          status = ServerStatus(parent = self.root, key_name = node['ip'])
          status.ip = node['ip']
        status.cpu    = str(node['cpu'])
        status.memory = str(node['memory'])
        status.disk   = str(node['disk'])
        status.cloud  = node['cloud']
        status.roles  = self.STATUS_ROLES_DELIMITER.join(node['roles'])
        status.put()
    except Exception as err:
      logging.info("AppDashboardData.update_status_info() caught Exception"\
        + str(type(err)) + ":" + str(err) + traceback.format_exc())


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
    """ Querys the AppController and stores the database information of this
        cloud and store in the datastore. """
    try:
      acc = self.helper.get_server()
      db_info = acc.get_database_information()
      self.root.table = db_info['table']
      self.root.replication = db_info['replication']
      self.root.put()
    except Exception as err:
      logging.info("AppDashboardData.get_database_info() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())

  def get_application_info(self):
    """ Returns the list of applications running on this cloud.
    
    Returns:
      A dict where the key is the app name, and the value is
      the url of the app (if running) or None (if loading).
    """
    status_query = self.get_all(AppStatus)
    status_query.ancestor(self.root)
    ret = {}
    for status in status_query.run():
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
      app_status = self.get_one(AppStatus, app)
      if app_status:
        app_status.delete()
      user_info = self.get_one(UserInfo, email)
      if user_info:
          app_list = user_info.user_app_list.split(self.APP_DELIMITER)
          if app in app_list:
            app_list.remove(app)
            user_info.user_app_list = self.APP_DELIMITER.join(app_list)
            user_info.put()
      return user_info
    except Exception as err:
      logging.info("AppDashboardData.delete_app_from_datastore() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())

 
  def update_application_info(self):
    """ Querys the AppController and stores the list of applications running on
        this cloud.  """

    def update_application_info_tx(root, input_list):
      """ Transactional function for update_application_info(). """
      query = self.get_all(AppStatus, keys_only=True)
      query.ancestor(root)
      db.delete(query)
      for status in input_list:
        status.put()
        return_list.append(status)

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
          app_status = self.get_one(AppStatus, app)
          if not app_status:
            app_status =  AppStatus(parent = self.root, key_name = app)
            app_status.name = app
          app_status.url = ret[app]
          updated_status.append( app_status )

        db.run_in_transaction(update_application_info_tx, self.root, \
          updated_status)
      return ret

    except Exception as err:
      logging.info("AppDashboardData.update_application_info() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())

  def update_users(self):
    """ Query the UserAppServer and update the state of all the users. """
    return_list = []
    try:
      all_users_list = self.helper.list_all_users()
      for email in all_users_list:
        user_info = self.get_one(UserInfo, email)
        if not user_info:
          user_info = UserInfo(key_name=email)
          user_info.email = email
        user_info.is_user_cloud_admin = self.helper.is_user_cloud_admin(
          user_info.email)
        user_info.i_can_upload = self.helper.i_can_upload(user_info.email)
        user_info.user_app_list = self.APP_DELIMITER.join(
          self.helper.get_user_app_list(user_info.email))
        user_info.put()
        return_list.append(user_info)
      return return_list
    except Exception as err:
      logging.info("AppDashboardData.update_users() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())

  def get_user_app_list(self):
    """ Get a list of apps that the current logged in user is an 
        admin of.

    Returns:
      A list of strs, each is the name of an app. 
    """
    user = users.get_current_user()
    if not user:
      return []
    email = user.email()
    try:
      user_info = self.get_one(UserInfo, email)
      if not user_info:
        return []
      app_list = user_info.user_app_list
      if len(app_list) == 0:
        return []
      return app_list.split(self.APP_DELIMITER)
    except Exception as err:
      logging.info("AppDashboardData.get_user_app_list() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())
      return []

  def is_user_cloud_admin(self):
    """ Check if the logged in user is a cloud admin.

    Returns:
      True if the user is a cloud admin, and False otherwise.
    """
    user = users.get_current_user()
    if not user:
      return False
    try:
      user_info = self.get_one(UserInfo, user.email())
      if not user_info:
        return False
      return user_info.is_user_cloud_admin
    except Exception as err:
      logging.info("AppDashboardData.is_user_cloud_admin() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())
      return False

  def i_can_upload(self):
    """ Check if the logged in user can upload apps.

    Args:
      email: Email address of the user.
    Returns:
      True if the user can upload apps, and False otherwise.
    """
    user = users.get_current_user()
    if not user:
      return False
    try:
      user_info = self.get_one(UserInfo, user.email())
      if not user_info:
        return False
      return user_info.i_can_upload
    except Exception as err:
      logging.info("AppDashboardData.i_can_upload() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())
      return False
