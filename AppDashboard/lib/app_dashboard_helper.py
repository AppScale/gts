import datetime
import hashlib
import os
import re
import sys
import tempfile
import SOAPpy
if 'TOOLS_PATH' in os.environ:
  sys.path.append(os.environ['TOOLS_PATH']+'/lib')
else:
  sys.path.append('/usr/local/appscale-tools/lib')
from appcontroller_client import AppControllerClient
from local_state import LocalState

from google.appengine.api import users

from secret_key import GLOBAL_SECRET_KEY

class AppDashboardHelper:
  """ Helper class to get info from AppScale. """
  def __init__(self, response):
    """ Constructor. """
    self.server = None
    self.uaserver = None
    self.response = response
    self.cache = {}

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

  def get_user_capabilities(self, email):
    if 'user_caps' in self.cache:
      if email in self.cache['user_caps']:
        return self.cache['user_caps'][email]
    else:
      self.cache['user_caps'] = {}
    uas = self.get_uaserver()
    caps_list = uas.get_capabilities(email, GLOBAL_SECRET_KEY).split(':')
    sys.stderr.write("uaserver.get_capabilities("+email+")="+",".join(caps_list)+"\n")
    self.cache['user_caps'][email] = caps_list
    return caps_list

  def get_status_information(self):
    acc = self.get_server()
    node = acc.get_stats()
    return node

  def get_host_with_role(self, role):
    acc = self.get_server()
    if 'get_role_info' in self.cache:
      node = self.cache['get_role_info']
    else:
      nodes = acc.get_role_info()
    for node in nodes:
      if role in node['jobs']:
        return node['public_ip']

  def get_head_node_ip(self):
    return self.get_host_with_role('shadow')

  def get_login_host(self):
    return self.get_host_with_role('login')

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

  def upload_app(self, upload_file):
    """ Uploads and App into AppScale.
    Args:  tgz_file: a 'StringIO' object containing the uploaded file data.
    Returns: a message reporting the success or failure of the upload.
    """
    #TODO
    tgz_file = tempfile.NamedTemporaryFile()
    tgz_file.write( upload_file.read() )
    name = tgz_file.name
    tgz_file.close()
    return "AppScaleAppTools.upload_app("+name+")"

  def delete_app(self, app_name):
    #TODO
    return "AppScaleAppTools.delete_app("+app_name+")"

  def is_user_logged_in(self):
    """ Check if the user is logged in.
    Returns:  True or False.
    """
    user = users.get_current_user()
    if user:
      return True
    return False

  def get_user_email(self):
    """ Get the logged in user's email.
    Returns: A str with the user's email, or '' if not found.
    """
    user = users.get_current_user()
    if user:
      return user.nickname()
    return ''

  def query_user_data(self, email):
    if 'query_user_data' in self.cache:
      if email in self.cache['query_user_data']:
        return self.cache['query_user_data'][email]
      else:
        uaserver = self.get_uaserver()
        sys.stderr.write("uaserver.get_user_data()\n")
        user_data =  uaserver.get_user_data(email, GLOBAL_SECRET_KEY)
    else:
      self.cache['query_user_data'] = {}
      uaserver = self.get_uaserver()
      sys.stderr.write("uaserver.get_user_data()\n")
      user_data =  uaserver.get_user_data(email, GLOBAL_SECRET_KEY)
    self.cache['query_user_data'][email] = user_data
    return user_data

  def is_user_cloud_admin(self):
    """ Check if the logged in user is a cloud admin.
    Returns: True or False.
    """
    user = users.get_current_user()
    if not user:
      return False
    email =  user.nickname()
    user_data = self.query_user_data(email)
    sys.stderr.write("user_data = "+str(user_data))
    if re.search("is_cloud_admin:true",user_data):
      return True
    else:
      return False

  def i_can_upload(self):
    """ Check if the logged in user can upload apps.
    Returns: True or False.
    """
    user = users.get_current_user()
    if user:
      if 'upload_app' in self.get_user_capabilities(user.nickname()):
        return True
    return False

  def create_new_user(self, email, password, account_type='xmpp_user'):
    """ Create new user in the system. 
    Args: email: email address of the new user.
      password: password for the new user.
    Returns: True if the user was create, otherwise false.
    """
    try:
      uaserver = self.get_uaserver()
      # first, create the standard account
      encrypted_pass = LocalState.encrypt_password(email, password)
      sys.stderr.write("uaserver.commit_new_user()\n")
      result = uaserver.commit_new_user(email, password, account_type,
        GLOBAL_SECRET_KEY)
      if result != 'true':
        raise Exception(result)
      # next, create the XMPP account. if the user's e-mail is a@a.a, then that
      # means their XMPP account name is a@login_ip
      username_regex = re.compile('\A(.*)@')
      username = username_regex.match(email).groups()[0]
      xmpp_user = "{0}@{1}".format(username,
        self.get_login_host() )
      xmpp_pass = LocalState.encrypt_password(xmpp_user, password)
      result = uaserver.commit_new_user(xmpp_user, xmpp_pass, account_type,
        GLOBAL_SECRET_KEY)
      if result != 'true':
        raise Exception(result)

      sys.stderr.write("create_new_user("+email+") created")

      self.create_token(email, email)
      self.set_appserver_cookie(email)
    except Exception as e:
      sys.stderr.write("create_new_user("+email+") caught exception: "+str(e))
      sys.stderr.write("create_new_user() return FALSE\n\n")
      return False
    sys.stderr.write("create_new_user() return TRUE\n\n")
    return True

  def remove_appserver_cookie(self, email):
    self.response.delete_cookie('dev_appserver_login')

  def set_appserver_cookie(self, email):
    user_data =  self.query_user_data(email)
    sys.stderr.write("user_data = "+str(user_data))
    apps_list = re.search("\napplications:(.*)\n",user_data).group(1).split(":")
    apps =  ",".join(apps_list)
    sys.stderr.write("apps = "+str(apps))
    self.response.set_cookie('dev_appserver_login',
      value = self.get_cookie_value(email, apps),
      expires = datetime.datetime.now() + datetime.timedelta(days=1) )

  def get_cookie_value(self, email, apps):
    nick = re.search('^(.*)@',email).group(1)
    admin = '' #this is always the current behavior
    hsh = self.get_appengine_hash(email, nick, admin)
    return email+':'+nick+':'+admin+':'+hsh

  def get_appengine_hash(self, email, nick, admin):
    return hashlib.sha1(email + nick + admin + GLOBAL_SECRET_KEY).hexdigest()

  def create_token(self, token, email):
    exp_date = "20121231120000" #exactly what it was before
    uaserver = self.get_uaserver()
    sys.stderr.write("uaserver.commit_new_token()\n")
    uaserver.commit_new_token('invalid', email, exp_date, GLOBAL_SECRET_KEY)

  def logout_user(self):
    user = users.get_current_user()
    if not user:
      return True
    email = user.nickname()
    self.create_token('invalid',email)
    self.remove_appserver_cookie(email)

  def login_user(self, email, password):
    user_data =  self.query_user_data(email) 
    sys.stderr.write("user_data = "+str(user_data))
    server_pwd = re.search('password:([0-9a-f]+)',user_data).group(1)
    encrypted_pass = LocalState.encrypt_password(email, password)
    if server_pwd != encrypted_pass:
      return False
    self.create_token(email, email)
    self.set_appserver_cookie(email)
    return True

  def list_all_users_permisions(self):
    """ Returns a list of all the users and the permission they have
      in the system. """
    uas = self.get_uaserver()
    sys.stderr.write("uaserver.get_all_users()\n")
    all_users = uas.get_all_users( GLOBAL_SECRET_KEY )
    sys.stderr.write('uas.get_all_users = '+all_users)
    all_users_list = all_users.split(':')
    user_list = []
    ip = self.get_head_node_ip()
    perm_items = self.get_all_permission_items()
    ret_list = []
    for usr in all_users_list:
      if re.search('@'+ip+'$',usr): #{ip}\Z/ # skip the XMPP user accounts
        continue 
      if re.search('^[_]+$',usr): #skip non users
        continue
      usr_cap = {'email' : usr }
      caps_list = self.get_user_capabilities(usr)
      for perm in perm_items:
        if perm in caps_list:
          usr_cap[perm]=True
        else:
          usr_cap[perm]=False
      ret_list.append(usr_cap)
    sys.stderr.write("list_all_users_permisions():"+str(ret_list))
    return ret_list
#    user = users.get_current_user()
#    if user:
#      return [{'email':user.nickname(),'upload_app':True}]
#    return []

  def get_all_permission_items(self):
    """ Returns a list of all permission items in the system. """
    return ['upload_app']

  def add_user_permissions(self, email, perm):
    """ Add a permission to a user."
    Args: 
      email: email addres of the user.
      perm: name of the permission to give to the user.
    Returns: True if the permission was given to the user,
      else False.
    """
    try:
      caps_list = self.get_user_capabilities(email)
      uas = self.get_uaserver()
      new_caps = caps_list
      if perm not in new_caps:
        new_caps.append(perm)
      else:
        return True  #already there, shortcut out
      ret = uas.set_capabilities(email, ':'.join(new_caps),  GLOBAL_SECRET_KEY)
      if ret == 'true':
        return True
        self.cache['user_caps'][email] = new_caps
      else:
        sys.stderr.write("uas.set_capabilities returned: "+ret)
        return False
    except Exception as e:
      sys.stderr.write("add_user_permissions() caught Exception: "+str(e))
      return False
    return True

  def remove_user_permissions(self, email, perm):
    """ Remove a permission from a user."
    Args: 
      email: email addres of the user.
      perm: name of the permission to remove from the user.
    Returns: True if the permission was remove from the user,
      else False.
    """
    try:
      caps_list = self.get_user_capabilities(email)
      uas = self.get_uaserver()
      new_caps = []
      if perm in caps_list:
        for pitem in caps_list:
          if pitem != perm:
            new_caps.append(pitem)
      else:
        return True  #not there, shortcut out
      ret = uas.set_capabilities(email, ':'.join(new_caps),  GLOBAL_SECRET_KEY)
      if ret == 'true':
        self.cache['user_caps'][email] = new_caps
        return True
      else:
        sys.stderr.write("uas.set_capabilities returned: "+ret)
        return False
    except Exception as e:
      sys.stderr.write("remove_user_permissions() caught Exception: "+str(e))
      return False
    return True

