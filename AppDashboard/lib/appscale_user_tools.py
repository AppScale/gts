""" Tools to help AppDashboard interact with users. """
import sys
import re
import SOAPpy
from google.appengine.api import users

from user_app_client import UserAppClient
from appcontroller_client import AppControllerClient
from local_state import LocalState


from secret_key import GLOBAL_SECRET_KEY

class AppScaleUserTools:
  """ Tools to help AppDashboard interact with users."""

  @classmethod
  def get_uaserver(cls):
    acc = AppControllerClient('127.0.0.1', GLOBAL_SECRET_KEY)
    uas_host = acc.get_uaserver_host(False)
    uaserver = SOAPpy.SOAPProxy('https://%s:%s' % (uas_host, 4343))
    return uaserver

  @classmethod
  def is_user_logged_in(cls):
    """ Check if the user is logged in.
    Returns:  True or False.
    """
    #TODO Fix to use SOAP and UserAppServer
    user = users.get_current_user()
    if user:
      return True
    return False

  @classmethod
  def get_user_email(cls):
    """ Get the logged in user's email.
    Returns: A str with the user's email, or '' if not found.
    """
    #TODO Fix to use SOAP and UserAppServer
    user = users.get_current_user()
    if user:
      return user.nickname()
    return ''

  @classmethod
  def is_user_cloud_admin(cls):
    """ Check if the logged in user is a cloud admin.
    Returns: True or False.
    """
    #TODO Fix to use SOAP and UserAppServer
    user = users.get_current_user()
    if user:
      return True
    return False

  @classmethod
  def i_can_upload(cls):
    """ Check if the logged in user can upload apps.
    Returns: True or False.
    """
    #TODO Fix to use SOAP and UserAppServer
    user = users.get_current_user()
    if user:
      return True
    return False

  @classmethod
  def create_new_user(cls,email,password):
    """ Create new user in the system. 
    Args: email: email address of the new user.
      password: password for the new user.
    Returns: True if the user was create, otherwise false.
    """
    try:
      acc = AppControllerClient('127.0.0.1', GLOBAL_SECRET_KEY)
      uaserver_host = acc.get_uaserver_host(False)
      uaserver = UserAppClient(uaserver_host, GLOBAL_SECRET_KEY )
      # first, create the standard account
      encrypted_pass = LocalState.encrypt_password(email, password)
      uaserver.create_user(email, encrypted_pass)
      # next, create the XMPP account. if the user's e-mail is a@a.a, then that
      # means their XMPP account name is a@login_ip
      username_regex = re.compile('\A(.*)@')
      username = username_regex.match(email).groups()[0]
      xmpp_user = "{0}@{1}".format(username,
        AppScaleStatusHelper.get_login_host() )
      xmpp_pass = LocalState.encrypt_password(xmpp_user, password)
      uaserver.create_user(xmpp_user, xmpp_pass)
    except Exception as e:
      #TODO:  Log this error
      return False
    return True

  @classmethod
  def logout_user(cls):
    user = users.get_current_user()
    if not user:
      return True
    email = user.nickname()
    uaserver = cls.get_uaserver()
    exp_date = "20121231120000" #exactly what it was before
    uaserver.commit_new_token('invalid', email, exp_date, GLOBAL_SECRET_KEY)

  @classmethod
  def login_user(cls,email,password):
    sys.stderr.write('login_user() BLAH BLERG')
    uaserver = cls.get_uaserver()
    try:
      user_data =  uaserver.get_user_data(email, GLOBAL_SECRET_KEY)
    except Exception as e:
      sys.stderr.write("uaserver.get_user_data() raised exception: "+str(e))
      return False

    if user_data is None:
      sys.stderr.write("uaserver.get_user_data() return none")
      
    sys.stderr.write("user_data = "+str(user_data))
    server_pwd = re.search('password:([0-9a-f]+)',user_data).group(1)
    encrypted_pass = LocalState.encrypt_password(email, password)
    
    if server_pwd != encrypted_pass:
      return False
    
    exp_date = "20121231120000" #exactly what it was before
    uaserver.commit_new_token(email, email, exp_date, GLOBAL_SECRET_KEY)
    return True

  @classmethod
  def list_all_users_permisions(cls):
    """ Returns a list of all the users and the permission they have
      in the system. """
    #TODO Fix to use SOAP and UserAppServer
    user = users.get_current_user()
    if user:
      return [{'email':user.nickname(),'admin':True,'upload_app':True}]
    return []

  @classmethod
  def get_all_permission_items(cls):
    """ Returns a list of all permission items in the system. """
    #TODO Fix to use SOAP and UserAppServer
    return ['upload_app']

  @classmethod
  def add_user_permissions(cls, email, perm):
    """ Add a permission to a user."
    Args: 
      email: email addres of the user.
      perm: name of the permission to give to the user.
    Returns: True if the permission was given to the user,
      else False.
    """
    #TODO Fix to use SOAP and UserAppServer
    return True

  @classmethod
  def remove_user_permissions(cls, email, perm):
    """ Remove a permission from a user."
    Args: 
      email: email addres of the user.
      perm: name of the permission to remove from the user.
    Returns: True if the permission was remove from the user,
      else False.
    """
    #TODO Fix to use SOAP and UserAppServer
    return True

