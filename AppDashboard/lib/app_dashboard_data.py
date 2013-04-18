import datetime
import sys
import traceback
from google.appengine.ext import db
from app_dashboard_helper import AppDashboardHelper
from app_dashboard_helper import AppHelperException

from google.appengine.ext.db import Timeout
from google.appengine.ext.db import TransactionFailedError
from google.appengine.ext.db import InternalError


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


class AppDashboardData:
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

  def __init__(self, helper = None):
    """ Constructor. 

    Args:
      helper: AppDashboardHelper object.
    """
    self.helper = helper
    if self.helper is None:
      self.helper = AppDashboardHelper(None)

    self.root = DashboardDataRoot.get_by_key_name(self.ROOT_KEYNAME)
    if not self.root:
      self.root = DashboardDataRoot(key_name=self.ROOT_KEYNAME)
      self.root.put()
      self.initialize_datastore()

  def initialize_datastore(self):
    """ Initialze datastore. Run once per appscale deployment. """
    self.update_all()

  def update_all(self):
    """ Update all stored data. """
    self.update_head_node_ip()
    self.update_database_info()
    self.update_apistatus()
    self.update_status_info()
    self.update_application_info()

  def get_monitoring_url(self):
    """ Returns the url of the monitoring service. 

    Returns:
      A str containing the url of the monitoring service.
    """
    try:
      url = self.get_head_node_ip()
      if url:
        return "http://{0}:{1}".format(url,  self.MONITOR_PORT)
    except Exception as err:
      sys.stderr.write("AppDashboardData.get_monitoring_url() caught "\
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
      sys.stderr.write("AppDashboardData.update_head_node_ip() caught "\
        "Exception "+ str(type(err)) + ":" + str(err) + traceback.format_exc())


  def get_apistatus(self):
    """ Reterive the API status from the datastore.

    Returns:
      A dict where the keys are the names of the services, and the values or the
       status of that service.
    """
    status_query = APIstatus.all()
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
        store = APIstatus.get_by_key_name(key)
        if not store:
          store = APIstatus(parent = self.root, key_name = key)
          store.name = key
        store.value = stat_dict[key]
        store.put()
    except Exception as err:
      sys.stderr.write("AppDashboardData.update_apistatus() caught Exception"\
        + str(type(err)) + ":" + str(err )+ traceback.format_exc())

  def get_status_info(self):
    """ Return the status information for all the server in the cluster from
        the datastore.

    Returns:
      A list of dicts containing the status information on each server.
    """    
    status_query = ServerStatus().all()
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
        status = ServerStatus.get_by_key_name(node['ip'])
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
      sys.stderr.write("AppDashboardData.update_status_info() caught Exception"\
        + str(type(err)) + ":" + str(err) + traceback.format_exc())


  def get_database_info(self):
    """ Returns the database information of this cloud.

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
      sys.stderr.write("AppDashboardData.get_database_info() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())
      return {}

  def get_application_info(self):
    """ Returns the list of applications running on this cloud.
    
    Returns:
      A dict where the key is the app name, and the value is
      the url of the app (if running) or None (if loading).
    """
    status_query = AppStatus().all()
    status_query.ancestor(self.root)
    ret = {}
    for status in status_query.run():
      ret[ status.name ] = status.url
    return ret
 
  def update_application_info(self):
    """ Querys the AppController and stores the list of applications running on
        this cloud.  """

    def update_application_info_tx(root, input_list):
      """ Transactional function for update_application_info(). """
      query = AppStatus.all(keys_only=True)
      query.ancestor(root)
      db.delete(query)
      for status in input_list:
        status.put()

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
          status = AppStatus.get_by_key_name(app)
          if not status:
            status =  AppStatus(parent = self.root, key_name = app)
            status.name = app
          status.url = ret[app]
          updated_status.append( status )

        db.run_in_transaction(update_application_info_tx, self.root, \
          updated_status)

    except Exception as err:
      sys.stderr.write("AppDashboardData.update_application_info() caught "
        "Exception " + str(type(err)) + ":" + str(err) + traceback.format_exc())
