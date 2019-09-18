""" A client that makes requests to the UAServer. """

import random

from SOAPpy import SOAPProxy

from .appscale_info import get_load_balancer_ips, get_secret
from .constants import UA_SERVER_PORT


# A message returned by the UAServer to indicate that the project exists.
EXISTING_PROJECT_MESSAGE = 'Error: appname already exist'


class UAException(Exception):
  """ Indicates that there was a problem executing a UAServer operation. """
  pass


class UAClient(object):
  """ A client that makes requests to the UAServer. """

  # Users have a list of applications that they own stored in their user data.
  # This character is the delimiter that separates them in their data.
  APP_DELIMITER = ":"

  # A regular expression that can be used to retrieve the SHA1-hashed password
  # stored in a user's data with the UserAppServer.
  USER_DATA_PASSWORD_REGEX = 'password:([0-9a-fA-F]+)'

  # A regular expression that can be used to find out which Google App Engine
  # applications a user owns, when applied to their user data.
  USER_APP_LIST_REGEX = "\napplications:(.+)\n"

  def __init__(self, host=None, secret=None):
    """ Creates a UAClient instance.

    Args:
      host: A string specifying the location of the UAServer.
      secret: A string specifying the deployment secret.
    """
    if host is None:
      host = random.choice(get_load_balancer_ips())

    if secret is None:
      secret = get_secret()

    self.secret = secret
    self.server = SOAPProxy('http://{}:{}'.format(host, UA_SERVER_PORT))

  def add_admin_for_app(self, email, app_id):
    """ Grants a user admin privileges for an application.
    
    Args:
      email: A string specifying the user's email address.
      app_id: A string specifying an application ID.
    Raises:
      UAException if the operation was not successful.
    """
    response = self.server.add_admin_for_app(email, app_id, self.secret)
    if response.lower() != 'true':
      raise UAException(response)

  def commit_new_user(self, email, hashed_pwd, type):
    """ Creates a new user.

    Args:
      email: A string specifying the user's email address.
      hashed_pwd: A string containing a hashed password.
      type: A string specifying the type of user to create.
    Raises:
      UAException if the commit was not successful.
    """
    response = self.server.commit_new_user(email, hashed_pwd, type,
                                           self.secret)
    if response.lower() != 'true':
      raise UAException(response)

  def delete_user(self, email):
    """ Deletes a user.

    Args:
      email: A string specifying the user's email address.
    Raises:
      UAException if the deletion was not successful.
    """
    response = self.server.delete_user(email, self.secret)
    if response.lower() != 'true':
      raise UAException(response)

  def disable_user(self, email):
    """ Disables a user.

    Args:
      email: A string specifying the user's email address.
    Raises:
      UAException if the operation was not successful.
    """
    response = self.server.disable_user(email, self.secret)
    if response.lower() != 'true':
      raise UAException(response)

  def does_user_exist(self, email):
    """ Checks if a user exists.
    
    Args:
      email: A string specifying an email address.
    Returns:
      A boolean indicating whether or not the user exists.
    Raises:
      UAException when unable to determine if user exist.
    """
    response = self.server.does_user_exist(email, self.secret)

    if response.lower() not in ['true', 'false']:
      raise UAException(response)

    return response.lower() == 'true'

  def get_all_users(self):
    """ Retrieves a list of all users.

    Returns:
      A list of string containing user email addresses.
    Raises:
      UAException if unable to retrieve list of users.
    """
    response = self.server.get_all_users(self.secret)

    if response.startswith('Error'):
      raise UAException(response)

    # Strip opening prefix that the UAServer adds.
    if response.startswith('____'):
      response = response[4:]

    return response.split(':')

  def get_user_data(self, email):
    """ Retrieves user metadata.

    Args:
      email: A string specifying an email address.
    Returns:
      A string containing user metadata.
    """
    return self.server.get_user_data(email, self.secret)

  def is_user_cloud_admin(self, email):
    """ Checks if a user has cloud admin privliges.

    Args:
      email: A string specifying an email address.
    Returns:
      A boolean indicating whether or not the user has admin privileges.
    Raises:
      UAException when unable to determine the status.
    """
    response = self.server.is_user_cloud_admin(email, self.secret)
    if response.lower() not in ['true', 'false']:
      raise UAException(response)

    return response.lower() == 'true'

  def set_cloud_admin_status(self, email, is_admin):
    """ Grants or revokes cloud admin privileges.
    
    Args:
      email: A string specifying an email address.
      is_admin: A boolean specifying if the user should be admin or not.
    Raises:
      UAException if the operation was not successful.
    """
    response = self.server.set_cloud_admin_status(email, str(is_admin).lower(),
                                                  self.secret)
    if response.lower() != 'true':
      raise UAException(response)
