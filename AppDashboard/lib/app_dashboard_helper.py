# pylint: disable-msg=W0703
# pylint: disable-msg=R0201

import datetime
import hashlib
import logging
import os
import re
import sys
import tempfile
import urllib


import SOAPpy


from appcontroller_client import AppControllerClient
from local_state import LocalState
from secret_key import GLOBAL_SECRET_KEY


from google.appengine.api import users


class AppHelperException(Exception):
  """ An exception thrown if the requested helper function failed. """
  pass


class AppDashboardHelper():
  """ Helper class to get info from AppScale. """


  # Name of the cookie used for login.
  DEV_APPSERVER_LOGIN_COOKIE = 'dev_appserver_login'


  # IP address of the AppController.
  APP_CONTROLLER_IP = '127.0.0.1'


  # Port number of the UserAppServer.
  UA_SERVER_PORT = 4343


  # Regular expression to parse the port from number.
  GET_APP_PORTS_REGEX = ".*\sports: (\d+)[\s|:]"


  # Regular expression to parse the number of ports.
  NUM_PORT_APP_REGEX = ".*num_ports:(\d+)"


  # The charcter that separates apps.
  APP_DELIMITER = ":"


  # The charcter that seperates users.
  USER_DELIMITER = ":"


  # Regular expression to capture the apps a user is admin of.
  USER_APP_LIST_REGEX = "\napplications:(.+)\n"


  # Regular expression to determine if a user is an admin.
  CLOUD_ADMIN_REGEX = "is_cloud_admin:true"


  # Regular expression to get username from full email.
  USERNAME_FROM_EMAIL_REGEX = '\A(.*)@'


  # Expiration date of the user token.
  TOKEN_EXPIRATION = "20121231120000"


  # Regular expression to get the hashed password from the user data.
  USER_DATA_PASSWORD_REGEX = 'password:([0-9a-fA-F]+)'


  # Regular expression to skip non-users in response from UseAppServer.
  ALL_USERS_NON_USER_REGEX = '^[_]+$'


  # Delimiter to seperate user capabilites.
  USER_CAPABILITIES_DELIMITER = ':'


  def __init__(self):
    """ Sets up SOAP client fields, to avoid creating a new SOAP connection for
    every SOAP call.

    Fields:
      appcontroller: A AppControllerClient, which is a SOAP client connected to
        the AppController running on this machine, responsible for service
        deployment and configuration.
      uaserver: A SOAP client connected to the UserAppServer running in this
        AppScale deployment, responsible for managing user and application
        creation.
    """
    self.appcontroller = None
    self.uaserver = None
    # The cache is a data structure to store data used multiple times in a 
    # single request. This avoids multiple SOAP requests for the same data, and
    # signifiantly increases performance.
    self.cache = {}


  def get_appcontroller_client(self):
    """ Connects to the AppController and returns the connection handle.

    Returns:
      An AppControllerClient object.
    """
    if self.appcontroller is None:
      self.appcontroller = AppControllerClient(self.APP_CONTROLLER_IP, 
        GLOBAL_SECRET_KEY)
    return self.appcontroller


  def get_uaserver(self):
    """ Connects to the UserAppServer and returns the connection handle.

    Returns:
      A SOAPpy object that is connected to the UserAppServer.
    """
    if self.uaserver is None:
      acc = self.get_appcontroller_client()
      uas_host = acc.get_uaserver_host(False)
      self.uaserver = SOAPpy.SOAPProxy('https://%s:%s' % (uas_host, 
        self.UA_SERVER_PORT))
    return self.uaserver


  def get_user_capabilities(self, email):
    """ Query the AppController and return the capabilites of the user.

    Args:
      email: A str containing the email of the user being queried.
    Returns:
      A list of strs containing the capabilities of the user being queried.
    """
    if 'user_caps' in self.cache:
      if email in self.cache['user_caps']:
        return self.cache['user_caps'][email]
    else:
      self.cache['user_caps'] = {}

    try:
      uas = self.get_uaserver()
      caps_list = uas.get_capabilities(email, GLOBAL_SECRET_KEY)\
        .split(self.USER_CAPABILITIES_DELIMITER)
      self.cache['user_caps'][email] = caps_list
      return caps_list
    except Exception as err:
      logging.exception(err)
      return []


  def get_status_info(self):
    """ Query the AppController and get the status information for all the 
        server in the cluster.

    Returns:
      A list of dicts containing the status information on each server.
    """
    try:
      acc = self.get_appcontroller_client()
      node = acc.get_stats()
      return node
    except Exception as err:
      logging.exception(err)
      return []


  def get_host_with_role(self, role):
    """Searches through the local metadata to see which virtual machine runs the
    specified role.

    Args:
      role: A str indicating the role to search for.
    Returns:
      A str containing the host that runs the specified service.
    """
    acc = self.get_appcontroller_client()
    if 'get_role_info' in self.cache:
      node = self.cache['get_role_info']
    else:
      try:
        nodes = acc.get_role_info()
      except Exception as err:
        logging.exception(err)
        return ''
    for node in nodes:
      if role in node['jobs']:
        return node['public_ip']


  def get_head_node_ip(self):
    """ Return the ip of the head node. 

    Returns:
      A str containing the ip of the head node.
    """
    return self.get_host_with_role('shadow')


  def get_login_host(self):
    """ Queries the AppController and returns the ip of the login host. 

    Returns:
      A str containing the host that runs the login service.
    """
    return self.get_host_with_role('login')


  def get_app_port(self, appname): 
    """ Queries the UserAppServer and returns the port that the app is running
        on.
    
    Args:
      appname: 
        Name of the app being queried.
    Returns:
      An int: the port number.
    Raises:
      AppHelperException if the app has no port.
    """
    try:
      uas = self.get_uaserver()
      app_data = uas.get_app_data(appname, GLOBAL_SECRET_KEY )
      result = re.search(self.GET_APP_PORTS_REGEX, app_data)
      if result:
        # GET_APP_PORTS_REGEX define a capture group, which we use here.
        port = int(result.group(1))
        return port
    except Exception as err:
      logging.exception(err)
    raise AppHelperException("app has no port")


  def upload_app(self, upload_file):
    """ Uploads an App into AppScale.

    Args:
      upload_file: a file object containing the uploaded file data.
    Returns:
      A message reporting the success of the upload.
    Raises:
      AppHelperException reporting the failure of the upload.
    """
    user = users.get_current_user()
    if not user:
      raise AppHelperException("There was an error uploading your application."\
             "  You must be logged in.")
    try:
      tgz_file = tempfile.NamedTemporaryFile()
      tgz_file.write( upload_file.read() )
      tgz_file.close()
      name = tgz_file.name
      acc = self.get_appcontroller_client()
      ret = acc.upload_tgz(name, user.email() )
      if ret == "true":
        return "Application uploaded successfully.  Please wait for the "\
               "application to start running."
      else:
        raise AppHelperException(ret)
    except SOAPpy.Types.faultType as err:  #on success Exception is thrown
      return "Application uploaded successfully.  Please wait for the "\
             "application to start running."
    except SOAPpy.Errors.HTTPError as err:  #on success HTTPError is thrown
      return "Application uploaded successfully.  Please wait for the "\
             "application to start running."
    except Exception as err:
      logging.exception(err)
      raise AppHelperException("There was an error uploading your application.")


  def delete_app(self, appname):
    """Instructs AppScale to no longer host the named application.

    Args:
      appname: Name of the app to be removed.
    Returns:
      A str containing a message to be displayed to the user.
    """
    try:
      if not self.does_app_exist(appname):
        return "The given application is not currently running."
      acc = self.get_appcontroller_client()
      ret = acc.stop_app(appname)
      if ret != "true":
        logging.info("delete_app() AppControler returned: " + ret)
        return "There was an error attempting to remove the application."
    except Exception as err:
      logging.exception(err)
      return "There was an error attempting to remove the application."
    return "Application removed successfully. Please wait for your app to shut"\
           " down."


  def does_app_exist(self, appname):
    """Queries the UserAppServer to see if the named application exists.

    Args:
      appname: The name of the app that we should check for existence.
    Returns:
      True if the app does exist, False otherwise.
    """
    try:
      uas = self.get_uaserver()
      app_data = uas.get_app_data(appname, GLOBAL_SECRET_KEY)
      search_data = re.search(self.GET_APP_PORTS_REGEX, app_data)
      if search_data:
        num_ports = int(search_data.group(1))
        if num_ports > 0:
          return True
    except Exception as err:
      logging.exception(err)
    return False


  def is_user_logged_in(self):
    """ Check if the user is logged in.

    Returns:
      True if the user is logged in, else False.
    """
    user = users.get_current_user()
    if user:
      return True
    else:
      return False


  def get_user_email(self):
    """ Get the logged in user's email.

    Returns:
      A str with the user's email, or '' if the user is not logged in. 
    """
    user = users.get_current_user()
    if user:
      return user.email()
    return ''


  def get_user_app_list(self, email=None):
    """ Get a list of apps that the user is an admin of.

    Args:
      email: Email address of the user.
    Returns:
      A list of strs, each is the name of an app. 
    """
    if email is None:
      user = users.get_current_user()
      if not user:
        return []
      email = user.email()
    user_data = self.query_user_data(email)
    user_data_match = re.search(self.USER_APP_LIST_REGEX, user_data)
    if user_data_match:
      return user_data_match.group(1).split(self.APP_DELIMITER)
    return []


  def query_user_data(self, email):
    """ Queries the UserAppServer and returns the data on a user.

    Args:
      email: Email address of the user being queried.
    Returns:
      A str contain the the user data, or empty string on error.
    """
    if 'query_user_data' in self.cache:
      if email in self.cache['query_user_data']:
        return self.cache['query_user_data'][email]
    else:
      self.cache['query_user_data'] = {}

    try:
      uaserver = self.get_uaserver()
      user_data =  uaserver.get_user_data(email, GLOBAL_SECRET_KEY)
      self.cache['query_user_data'][email] = user_data
      return user_data
    except Exception as err:
      logging.exception(err)
      return ''


  def is_user_cloud_admin(self, email=None):
    """ Check if the logged in user is a cloud admin.

    Args:
      email: Email address of the user.
    Returns:
      True if the user is a cloud admin, and False otherwise.
    """
    if email is None:
      user = users.get_current_user()
      if not user:
        return False
      email =  user.email()
    user_data = self.query_user_data(email)
    if re.search(self.CLOUD_ADMIN_REGEX, user_data):
      return True
    else:
      return False


  def i_can_upload(self, email=None):
    """ Check if the user can upload apps.

    Args:
      email: Email address of the user.
    Returns:
      True if the user can upload apps, and False otherwise.
    """
    if email is None:
      user = users.get_current_user()
      if not user:
        return False
      email = user.email()
    if 'upload_app' in self.get_user_capabilities(email):
      return True
    return False


  def create_new_user(self, email, password, response, 
        account_type='xmpp_user'):
    """ Create new user in the system. 

    Args:
      email: Email address of the new user.
      password: Password for the new user.
      response: The webapp2 response object of the parent of ths AppDashboard
                object.
    Returns:
      True if the user was created.
    Raises:
      AppHelperException on error.
    """
    try:
      uaserver = self.get_uaserver()
      # First, create the standard account.
      encrypted_pass = LocalState.encrypt_password(email, password)
      result = uaserver.commit_new_user(email, encrypted_pass, account_type,
        GLOBAL_SECRET_KEY)
      if result != 'true':
        raise AppHelperException(result)
  
      # Next, create the XMPP account. if the user's e-mail is a@a.a, then that
      # means their XMPP account name is a@login_ip.
      username_regex = re.compile(self.USERNAME_FROM_EMAIL_REGEX)
      username = username_regex.match(email).groups()[0]
      xmpp_user = "{0}@{1}".format(username,
        self.get_login_host())
      xmpp_pass = LocalState.encrypt_password(xmpp_user, password)
      result = uaserver.commit_new_user(xmpp_user, xmpp_pass, account_type,
        GLOBAL_SECRET_KEY)
      if result != 'true':
        raise AppHelperException(result)
  
      self.create_token(email, email)
      self.set_appserver_cookie(email, response)
    except AppHelperException as err:
      raise AppHelperException(str(err))
    except Exception as err:
      logging.exception(err)
      raise AppHelperException(str(err))
    return True


  def set_appserver_cookie(self, email, response):
    """ Sets the login cookie.

    Args:
      email: Email of the user to login.
      response: The webapp2 response object of the parent of ths AppDashboard
                object.
    """
    apps = ''
    user_data = self.query_user_data(email)
    app_re = re.search(self.USER_APP_LIST_REGEX, user_data)
    if app_re:
      apps_list = app_re.group(1).split(self.APP_DELIMITER)
      apps =  ",".join(apps_list)
    response.set_cookie(self.DEV_APPSERVER_LOGIN_COOKIE,
      value=self.get_cookie_value(email, apps),
      expires=datetime.datetime.now() + datetime.timedelta(days=1))


  def get_cookie_value(self, email, apps):
    """ Generates a hash corresponding to the given user's credentials.
        It is a hashed string containing the email, nickname, and list 
        of apps the user is an admin of.
    
    Args:
      email: Email of the user to login.
      apps: List of applications the user is admin of.
    Retuns:
      A str that is the value of the login cookie.
    """
    nick = re.search('^(.*)@', email).group(1)
    hsh = self.get_appengine_hash(email, nick, apps)
    return urllib.quote("{0}:{1}:{2}:{3}".format(email, nick, apps, hsh))


  def get_appengine_hash(self, email, nick, apps):
    """ Encrypt the values and return the hash.

    Args:
      email: Email of the user to login.
      nick: Email of the user to login.
      apps: A str with a comma-seperated list of apps the user is an admin of.
    Returns:
      A str that is the hex hash of the input values.
    """
    return hashlib.sha1(email + nick + apps + GLOBAL_SECRET_KEY).hexdigest()


  def create_token(self, token, email):
    """ Create a login token and commit it to the UserAppServer.
    
    Args:
      token: Name of the token to create (usually the email address).
      email: Email of the user to create the login token for.
    """
    try:
      uaserver = self.get_uaserver()
      uaserver.commit_new_token(token, email, self.TOKEN_EXPIRATION, 
        GLOBAL_SECRET_KEY)
    except Exception as err:
      logging.exception(err)


  def logout_user(self, response):
    """ Remove the user's login cookie and invalidate the login token in
        the AppScale deployment.  This results in the user being logged out.

    Args:
      response: The webapp2 response object of the parent of ths AppDashboard
                object.
    """
    user = users.get_current_user()
    if user:
      self.create_token('invalid', user.email())
      response.delete_cookie(self.DEV_APPSERVER_LOGIN_COOKIE)


  def login_user(self, email, password, response):
    """ Attempt to login the user.

    Args:
      email: Email of the user to login.
      password: Password of the user to login.
      response: The webapp2 response object of the parent of ths AppDashboard
                object.
    Return:
      True if the user logged in successfully, and False otherwise.
    """
    user_data =  self.query_user_data(email) 
    server_re = re.search(self.USER_DATA_PASSWORD_REGEX, user_data)
    if not server_re:
      logging.info("Failed Login: {0} regex failed".format(email))
      return False
    server_pwd = server_re.group(1)
    encrypted_pass = LocalState.encrypt_password(email, password)
    if server_pwd != encrypted_pass:
      logging.info("Failed Login: {0} password mismatch".format(email))
      return False
    self.create_token(email, email)
    self.set_appserver_cookie(email, response)
    return True


  def list_all_users(self):
    """ Queries the UserAppServer and return a list of all users in the system.

    Returns:
      A list of strings, each string is a user the email of a user.
    """
    ret_list = []
    try:
      uas = self.get_uaserver()
      all_users = uas.get_all_users(GLOBAL_SECRET_KEY)
      all_users_list = all_users.split(self.USER_DELIMITER)
      my_ip = self.get_head_node_ip()
      for usr in all_users_list:
        if re.search('@' + my_ip + '$', usr): # Skip the XMPP user accounts.
          continue 
        if re.search(self.ALL_USERS_NON_USER_REGEX, usr): # Skip non users.
          continue
        ret_list.append(usr)
    except Exception as err:
      logging.exception(err)
    return ret_list


  def list_all_users_permissions(self):
    """ Queries the UserAppServer and returns a list of all the users and the 
        permissions they have in the system.

    Returns:
      A list of dicts with the email and permissions of each user in the system.
    """
    ret_list = []
    try:
      all_users_list = self.list_all_users()
      perm_items = self.get_all_permission_items()
      for usr in all_users_list:
        usr_cap = {'email' : usr}
        caps_list = self.get_user_capabilities(usr)
        for perm in perm_items:
          if perm in caps_list:
            usr_cap[perm] = True
          else:
            usr_cap[perm] = False
        ret_list.append(usr_cap)
    except Exception as err:
      logging.exception(err)
    return ret_list


  def get_all_permission_items(self):
    """ Returns a list of the types of permissions that can be assigned to 
        users in this system.
   
    Returns:
      A list of strs with the permission items to display. 
    """
    return ['upload_app']


  def add_user_permissions(self, email, perm):
    """ Add a permission to a user.

    Args: 
      email: Email address of the user.
      perm: Name of the permission to give to the user.
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
        return True

      ret = uas.set_capabilities(email, 
        self.USER_CAPABILITIES_DELIMITER.join(new_caps), GLOBAL_SECRET_KEY)
      if ret == 'true':
        self.cache['user_caps'][email] = new_caps
        return True
      else:
        logging.info("ERROR: UserAppServer.set_capabilities returned: " + ret)
        return False
    except Exception as err:
      logging.exception(err)
      return False
    return True


  def remove_user_permissions(self, email, perm):
    """ Remove a permission from a user.

    Args: 
      email: Email address of the user.
      perm: Name of the permission to remove from the user.
    Returns: 
      True if the permission was removed from the user, else False.
    """
    try:
      caps_list = self.get_user_capabilities(email)
      uas = self.get_uaserver()
      if perm in caps_list:
        caps_list.remove(perm)
      else:
        return True 

      ret = uas.set_capabilities(email, 
        self.USER_CAPABILITIES_DELIMITER.join(caps_list), GLOBAL_SECRET_KEY)
      if ret == 'true':
        self.cache['user_caps'][email] = caps_list
        return True
      else:
        logging.info("uas.set_capabilities returned: " + ret)
        return False
    except Exception as err:
      logging.exception(err)
      return False
    return True
