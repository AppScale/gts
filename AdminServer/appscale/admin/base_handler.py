""" A handler with helper functions that other handlers can extend. """

import base64
import hashlib
import json
import re
import time

from tornado import web
from tornado.escape import json_encode
from tornado.options import options

from appscale.common.constants import HTTPCodes
from appscale.common.ua_client import UAException
from .constants import CustomHTTPError
from .utils import constant_time_compare


class BaseHandler(web.RequestHandler):
  """ A handler with helper functions that other handlers can extend. """

  # Scope for which users are authorized for AdminServer functionality.
  AUTH_SCOPE = 'https://www.googleapis.com/auth/cloud-platform'

  def authenticate(self, project_id, ua_client):
    """ Ensures requests are authenticated.

    Args:
      project_id: The project that we are authenticating for.
      ua_client: A UA Client, used to check if the user can access the given
        project.

    Raises:
      CustomHTTPError if the secret or access token is invalid.
    """
    authorization_header = self.request.headers.get('Authorization')
    secret_header = self.request.headers.get('AppScale-Secret')
    if not authorization_header and not secret_header:
      message = 'A required header is missing: AppScale-Secret or Authorization'
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message=message)
    if (secret_header and
        not constant_time_compare(secret_header, options.secret)):
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid secret')
    elif authorization_header:
      self.authenticate_access_token(self.request.headers, project_id,
                                     ua_client)

  def authenticate_access_token(self, headers, project_id, ua_client):
    """ Method to go through Access Token authentication.
    Args:
      headers: The headers associated with the request.
      project_id: The project that the user wants to access.
      ua_client: A UA Client, used to see if the user can access the project.
    Raises:
      CustomHTTPError specified in called function.
    """
    try:
      token = headers['Authorization'].split()[1]
    except IndexError:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='Malformed '
                                                           'authorization.')

    method_base64, metadata_base64, signature = token.split('.')
    self.check_token_hash(method_base64, metadata_base64, signature)

    metadata = json.loads(base64.urlsafe_b64decode(metadata_base64))
    self.check_token_expiration(metadata)
    self.check_token_scope(metadata)
    if 'project' in metadata:
      if metadata['project'] == project_id:
        return
      else:
        raise CustomHTTPError(HTTPCodes.FORBIDDEN,
                              message='Token is not authorized for project')
    elif 'user' in metadata:
      return self.check_user_access(metadata, project_id, ua_client)
    else:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid token')

  @classmethod
  def check_token_hash(self, method_base64, metadata_base64, signature):
    """
    Args:
      method_base64:
      metadata_base64:
      signature:
    Raises:
       CustomHTTPError if the rehashed signature does not match the given
        signature.
    """
    hasher = hashlib.sha1()
    hasher.update(method_base64)
    hasher.update(metadata_base64)
    hasher.update(options.secret)

    if signature != hasher.hexdigest():
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid token.')

  @classmethod
  def check_token_expiration(self, metadata):
    """
    Args:
      metadata: A dictionary containing the metadata for the token, should
        include 'exp', 'user', and 'scope'.
    Raises:
       CustomHTTPError if the token has expired.
    """
    if time.time() > metadata['exp']:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED,
                            message='Token has expired.')

  def check_token_scope(self, metadata):
    """
    Args:
      metadata: A dictionary containing the metadata for the token, should
        include 'exp', 'user', and 'scope'.
    Raises:
       CustomHTTPError if the token has the wrong scope.
    """
    if metadata['scope'] != self.AUTH_SCOPE:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid scope.')

  def check_user_access(self, metadata, project_id, ua_client):
    """
    Args:
      metadata: A dictionary containing the metadata for the token, should
        include 'exp', 'user', and 'scope'.
      project_id: The project that the user wants to access.
      ua_client: A UA Client, used to see if the user can access the project.
    Raises:
       CustomHTTPError if the user cannot access the project.
    """
    user = metadata['user']

    # If user is cloud admin, return since they can access all projects.
    if ua_client.is_user_cloud_admin(user):
      return

    projects_list = self.get_users_projects(user, ua_client)

    # Unauthorized if user cannot access project.
    if project_id not in projects_list:
      raise CustomHTTPError(HTTPCodes.FORBIDDEN, message=
        '"{}" is not authorized for project "{}".'.format(user, project_id))

  @classmethod
  def get_users_projects(self, user, ua_client):
    """
    Args:
      user: The user, used to query the UAServer to determine projects that
        the user is admin of.
      ua_client: A UA Client for making the request to the UAServer.
    Returns:
      A list of applications the user has admin access to.
    Raises:
       CustomHTTPError if the user cannot be retrieved from the UAServer or
         has no applications.
    """
    # Get user data from UAServer.
    try:
      user_data = ua_client.get_user_data(user)
    except UAException:
      message = 'Unable to determine user data for {}'.format(user)
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR, message=message)
    # Search for application list.
    app_re = re.search(ua_client.USER_APP_LIST_REGEX, user_data)
    if app_re:
      # Return list of applications that the user is admin for.
      return app_re.group(1).split(ua_client.APP_DELIMITER)
    else:
      message = '"{}" has no authorized applications.'.format(user)
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message=message)

  def write_error(self, status_code, **kwargs):
    """ Writes a custom JSON-based error message.

    Args:
      status_code: An integer specifying the HTTP error code.
    """
    details = {'code': status_code}
    if 'exc_info' in kwargs:
      error = kwargs['exc_info'][1]
      try:
        details.update(error.kwargs)
      except AttributeError:
        pass

    self.finish(json_encode({'error': details}))
