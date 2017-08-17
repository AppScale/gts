""" A client that makes requests to the UAServer. """

import json
import ssl

from SOAPpy import SOAPProxy
from .constants import UA_SERVER_PORT


# A message returned by the UAServer to indicate that the project exists.
EXISTING_PROJECT_MESSAGE = 'Error: appname already exist'


class UAException(Exception):
  """ Indicates that there was a problem executing a UAServer operation. """
  pass


class UAClient(object):
  """ A client that makes requests to the UAServer. """
  def __init__(self, host, secret):
    """ Creates a UAClient instance.

    Args:
      host: A string specifying the location of the UAServer.
      secret: A string specifying the deployment secret.
    """
    # Disable certificate verification for Python >= 2.7.9.
    if hasattr(ssl, '_create_unverified_context'):
      ssl._create_default_https_context = ssl._create_unverified_context

    self.secret = secret
    self.server = SOAPProxy('https://{}:{}'.format(host, UA_SERVER_PORT))

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

  def enable_app(self, app_id):
    """ Enables a project.

    Args:
      app_id: A string specifying an application ID.
    Raises:
      UAException when unable to enable project.
    """
    response = self.server.enable_app(app_id, self.secret)

    # This operation should be idempotent.
    already_enabled = 'Error: Trying to enable an application that is '\
                      'already enabled'
    if response.lower() == 'true' or response == already_enabled:
      return

    raise UAException(response)

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

  def get_app_data(self, app_id):
    """ Retrieves application metadata.

    Args:
      app_id: A string specifying an application ID.
    Returns:
      A dictionary containing application metadata.
    Raises:
      UAException if unable to retrieve application metadata.
    """
    response = self.server.get_app_data(app_id, self.secret)

    try:
      data = json.loads(response)
    except ValueError:
      raise UAException(response)

    return data

  def get_user_data(self, email):
    """ Retrieves user metadata.

    Args:
      email: A string specifying an email address.
    Returns:
      A string containing user metadata.
    """
    return self.server.get_user_data(email, self.secret)

  def is_app_enabled(self, app_id):
    """ Checks if an application is enabled.

    Args:
      app_id: A string specifying an application ID.
    Returns:
      A boolean indicating whether or not an application is enabled.
    """
    response = self.server.is_app_enabled(app_id, self.secret)
    return response.lower() == 'true'

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
