import os
import sys
import re
if 'TOOLS_PATH' in os.environ:
  sys.path.append(os.environ['TOOLS_PATH']+'/lib')
else:
  sys.path.append('/usr/local/appscale-tools/lib')
from appcontroller_client import AppControllerClient

from secret_key import GLOBAL_SECRET_KEY

class AppScaleStatusHelper:
  """ Helper class to get info from AppScale. """
  def __init__(self):
    """ Constructor. """
    self.server = None
    self.uaserver = None

  def get_server(self):
    """ Get AppControler handle. """
    if self.server is None:
      self.server = AppControllerClient('127.0.0.1', GLOBAL_SECRET_KEY)
    return self.server

  def get_uaserver(self):
    """ Get UserAppServer handle. """
    if self.uaserver is None:
      acc = self.get_server()
      uas_host = acc.get_uaserver_host(False)
      self.uaserver = SOAPpy.SOAPProxy('https://%s:%s' % (uas_host, 4343))
    return self.uaserver

  def get_status_information(self):
    acc = self.get_server()
    node = acc.get_stats()
    return node

  def get_host_with_role(self, role):
    acc = self.get_server()
    nodes = acc.get_role_info()
    for node in nodes:
      if role in node['jobs']:
        return node['public_ip']

  def get_head_node_ip(self):
    return self.get_host_with_role('shadow')

  def get_login_host(self):
    return sefl.get_host_with_role('login')

  def get_monitoring_url(self):
    return "http://"+self.get_head_node_ip()+":8050"

  def get_application_information(self):
    status = self.get_status_information()
    ret = {}
    for app in status[0]['apps'].keys():
        if app == 'none':
          break
        if status[0]['apps'][app]:
          ret[app] = "http://"+login_node+":"+str(self.get_app_port(app))
        else:
          ret[app] = None
    return ret
 
  def get_database_information(self):
    acc = self.get_server()
    return acc.get_database_information()

  def get_service_info(self):
    acc = self.get_server()
    return acc.get_api_status()

  def get_app_port(self, appname): 
    uas = self.get_uaserver()
    app_data = uas.get_app_data(app_id, self.secret)
    port = int(re.search(".*\sports: (\d+)[\s|:]", app_data).group(1))
    return port

