""" Tools to help AppDashboard interact with users. """

from google.appengine.api import users

class AppScaleUserTools:
  """ Tools to help AppDashboard interact with users."""

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
    #TODO Fix to use SOAP and UserAppServer
    return True

  @classmethod
  def logout_user(cls):
    pass

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

