from google.appengine.ext import db

from app_dashboard_helper import AppDashboardHelper


class DashboardDataRoot(db.model):
  """ Root entity for datastore. """
  initialized_time = db.DateTimeProperty(auto_now = True)
  head_node_ip = db.StringProperty()
  table = db.StringProperty()
  replication = db.StringProperty()

class APIstatus(db.model):
  """ Status of each API in AppScale. """
  name = db.StringProperty()
  value = db.StringProperty()
  last_update = db.DateTimeProperty(auto_now = True)

class ServerStatus(db.model):
  """ Stats of each server in the AppScale deployment. """
  ip = db.StringProperty()
  cpu = db.StringProperty()
  memory = db.StringProperty()
  disk = db.StringProperty()
  cloud = db.StringProperty()
  roles = db.StringProperty()


class AppDashboardData:
  """ Helper class to interact with the datastore. """

  def __init__(self, helper = None):
    """ Constructor. 

    Args:
      helper: AppDashboardHelper object.
    """
    self.helper = helper
    if self.helper is None:
      self.helper = AppDashboardHelper(None)

    self.root = DashboardDataRoot.get('appscale')
    if not self.root:
      self.root = DashboardDataRoot(key_name = 'appscale')
      self.root.put()
      self.initialize_datastore()

  def initialize_datastore(self):
    """ Initialze datastore. Run once per appscale deployment. """
    self.update_head_node_ip()
    self.update_database_info()
    #TODO: refresh these periodically
    self.update_apistatus()
    self.update_status_info()

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
        "Exception "+ str(type(e)) + ":" + str(e))


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
        store = APIstatus.get(key)
        if not store:
          store = APIstatus(parent = self.root, key_name = key)
          store.name = key
        store.value = stat_dict[key]
        store.put()
    except Exception as err:
      sys.stderr.write("AppDashboardData.update_apistatus() caught Exception"\
        + str(type(e)) + ":" + str(e))

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
      server['roles'] = status.roles.split(',')
      ret.append(server)
    return ret

  def update_status_info(self):
    """ Query the AppController and get the status information for all the 
        server in the cluster and store in the datastore. """    
    try:
      acc = self.helper.get_server()
      nodes = acc.get_stats()
      for node in nodes:
        status = ServerStatus(node['ip'])
        if not status:
          status = ServerStatus(parent = self.root, key_name = node['ip'])
          status.ip = node['ip']
        status.cpu    = node['cpu']
        status.memory = node['memory']
        status.disk   = node['disk']
        status.cloud  = node['cloud']
        status.roles  = ",".join(node['roles'])
        status.put()
    except Exception as err:
      sys.stderr.write("AppDashboardData.update_status_info() caught Exception"\
        + str(type(e)) + ":" + str(e))


   def get_database_info(self):
    """ Returns the database information of this cloud.

    Return:
      A dict containing the database information.
    """
    ret = {}
    ret['table'] = self.root.table
    ret['replication'] self.root.replication
    return ret

   def update_database_info(self):
    """ Querys the AppController and returns the database information of this
        cloud and store in the datastore. """
    try:
      acc = self.get_server()
      db_info = acc.get_database_information()
      self.root.table = db_info['table']
      self.root.table = db_into['replication']
      self.root.put()
    except Exception as e:
      sys.stderr.write("AppDashboardData.get_database_info() caught "
        "Exception " + str(type(e)) + ":" + str(e))
      return {}
 
