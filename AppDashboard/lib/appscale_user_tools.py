""" Tools to help AppDashboard interact with users. """
import datetime
import sys
import re
import hashlib
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
    user = users.get_current_user()
    if user:
      return True
    return False

  @classmethod
  def get_user_email(cls):
    """ Get the logged in user's email.
    Returns: A str with the user's email, or '' if not found.
    """
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
  def create_new_user(cls,email,password,response):
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

      cls.create_token(email, email)
      cls.set_appserver_cookie(email, response)
    except Exception as e:
      sys.stderr.write("create_new_user("+email+") caught exception: "+str(e))
      return False
    return True

  @classmethod
  def remove_appserver_cookie(cls, email, response):
    response.delete_cookie('dev_appserver_login')

  @classmethod
  def set_appserver_cookie(cls, email, response):
    uaserver = cls.get_uaserver()
    user_data =  uaserver.get_user_data(email, GLOBAL_SECRET_KEY)
    sys.stderr.write("user_data = "+str(user_data))
    apps_list = re.search("\napplications:(.*)\n",user_data).group(1).split(":")
    apps =  ",".join(apps_list)
    sys.stderr.write("apps = "+str(apps));
    response.set_cookie('dev_appserver_login',
      value = cls.get_cookie_value(email, apps),
      expires = datetime.datetime.now() + datetime.timedelta(days=1) )

  @classmethod
  def get_cookie_value(cls, email, apps):
    nick = re.search('^(.*)@',email).group(1)
    admin = '' #this is always the current behavior
    hsh = cls.get_appengine_hash(email, nick, admin)
    return email+':'+nick+':'+admin+':'+hsh

  @classmethod
  def get_appengine_hash(cls, email, nick, admin):
    return hashlib.sha1(email + nick + admin + GLOBAL_SECRET_KEY).hexdigest()

  @classmethod 
  def create_token(cls, token, email):
    exp_date = "20121231120000" #exactly what it was before
    uaserver = cls.get_uaserver()
    uaserver.commit_new_token('invalid', email, exp_date, GLOBAL_SECRET_KEY)

  @classmethod
  def logout_user(cls, response):
    user = users.get_current_user()
    if not user:
      return True
    email = user.nickname()
    cls.create_token('invalid',email)
    cls.remove_appserver_cookie(email, response)

  @classmethod
  def login_user(cls, email, password, response):
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
    
    cls.create_token(email, email)
    cls.set_appserver_cookie(email, response)
    return True

  @classmethod
  def list_all_users_permisions(cls):
    """ Returns a list of all the users and the permission they have
      in the system. """
    uas = cls.get_uaserver()
    all_users = uas.get_all_users( GLOBAL_SECRET_KEY )
    all_users_list = all_users.split(':')
    user_list = []
    ip = 
    for usr in all_users_list:
      if(

    sys.stderr.write('uas.get_all_users = '+all_users)
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

