#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


"""OAuth API.

A service that enables App Engine apps to validate OAuth requests.

Classes defined here:
  Error: base exception type
  NotAllowedError: OAuthService exception
  OAuthRequestError: OAuthService exception
  InvalidOAuthParametersError: OAuthService exception
  InvalidOAuthTokenError: OAuthService exception
  OAuthServiceFailureError: OAuthService exception
"""














import os

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import user_service_pb
from google.appengine.api import users
from google.appengine.runtime import apiproxy_errors


class Error(Exception):
  """Base error class for this module."""


class OAuthRequestError(Error):
  """Base error type for invalid OAuth requests."""


class NotAllowedError(OAuthRequestError):
  """Raised if the requested URL does not permit OAuth authentication."""


class InvalidOAuthParametersError(OAuthRequestError):
  """Raised if the request was a malformed OAuth request.

  For example, the request may have omitted a required parameter, contained
  an invalid signature, or was made by an unknown consumer.
  """


class InvalidOAuthTokenError(OAuthRequestError):
  """Raised if the request contained an invalid token.

  For example, the token may have been revoked by the user.
  """


class OAuthServiceFailureError(Error):
  """Raised if there was a problem communicating with the OAuth service."""


def get_current_user(_scope=None):
  """Returns the User on whose behalf the request was made.

  Returns:
    User

  Raises:
    OAuthRequestError: The request was not a valid OAuth request.
    OAuthServiceFailureError: An unknown error occurred.
  """

  _maybe_call_get_oauth_user(_scope)
  return _get_user_from_environ()


def is_current_user_admin(_scope=None):
  """Returns true if the User on whose behalf the request was made is an admin.

  Returns:
    boolean

  Raises:
    OAuthRequestError: The request was not a valid OAuth request.
    OAuthServiceFailureError: An unknown error occurred.
  """

  _maybe_call_get_oauth_user(_scope)
  return os.environ.get('OAUTH_IS_ADMIN', '0') == '1'



def get_oauth_consumer_key():
  """Returns the value of the 'oauth_consumer_key' parameter from the request.

  Returns:
    string: The value of the 'oauth_consumer_key' parameter from the request,
        an identifier for the consumer that signed the request.

  Raises:
    OAuthRequestError: The request was not a valid OAuth request.
    OAuthServiceFailureError: An unknown error occurred.
  """
  req = user_service_pb.CheckOAuthSignatureRequest()
  resp = user_service_pb.CheckOAuthSignatureResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('user', 'CheckOAuthSignature', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        user_service_pb.UserServiceError.OAUTH_INVALID_REQUEST):
      raise InvalidOAuthParametersError(e.error_detail)
    elif (e.application_error ==
          user_service_pb.UserServiceError.OAUTH_ERROR):
      raise OAuthServiceFailureError(e.error_detail)
    else:
      raise OAuthServiceFailureError(e.error_detail)
  return resp.oauth_consumer_key()


def _maybe_call_get_oauth_user(_scope=None):
  """Makes an GetOAuthUser RPC and stores the results in os.environ.

  This method will only make the RPC if 'OAUTH_ERROR_CODE' has not already
  been set or 'OAUTH_LAST_SCOPE' is different to _scope.
  """

  if ('OAUTH_ERROR_CODE' not in os.environ or
      os.environ.get('OAUTH_LAST_SCOPE', None) != _scope):
    req = user_service_pb.GetOAuthUserRequest()
    if _scope:
      req.set_scope(_scope)

    resp = user_service_pb.GetOAuthUserResponse()
    try:
      apiproxy_stub_map.MakeSyncCall('user', 'GetOAuthUser', req, resp)
      os.environ['OAUTH_EMAIL'] = resp.email()
      os.environ['OAUTH_AUTH_DOMAIN'] = resp.auth_domain()
      os.environ['OAUTH_USER_ID'] = resp.user_id()
      if resp.is_admin():
        os.environ['OAUTH_IS_ADMIN'] = '1'
      else:
        os.environ['OAUTH_IS_ADMIN'] = '0'
      os.environ['OAUTH_ERROR_CODE'] = ''
    except apiproxy_errors.ApplicationError, e:
      os.environ['OAUTH_ERROR_CODE'] = str(e.application_error)
      os.environ['OAUTH_ERROR_DETAIL'] = e.error_detail
    if _scope:
      os.environ['OAUTH_LAST_SCOPE'] = _scope
    else:
      os.environ.pop('OAUTH_LAST_SCOPE', None)
  _maybe_raise_exception()


def _maybe_raise_exception():
  """Raises an error if one has been stored in os.environ.

  This method requires that 'OAUTH_ERROR_CODE' has already been set (an empty
  string indicates that there is no actual error).
  """
  assert 'OAUTH_ERROR_CODE' in os.environ
  error = os.environ['OAUTH_ERROR_CODE']
  if error:
    assert 'OAUTH_ERROR_DETAIL' in os.environ
    error_detail = os.environ['OAUTH_ERROR_DETAIL']
    if error == str(user_service_pb.UserServiceError.NOT_ALLOWED):
      raise NotAllowedError(error_detail)
    elif error == str(user_service_pb.UserServiceError.OAUTH_INVALID_REQUEST):
      raise InvalidOAuthParametersError(error_detail)
    elif error == str(user_service_pb.UserServiceError.OAUTH_INVALID_TOKEN):
      raise InvalidOAuthTokenError(error_detail)
    elif error == str(user_service_pb.UserServiceError.OAUTH_ERROR):
      raise OAuthServiceFailureError(error_detail)
    else:
      raise OAuthServiceFailureError(error_detail)


def _get_user_from_environ():
  """Returns a User based on values stored in os.environ.

  This method requires that 'OAUTH_EMAIL', 'OAUTH_AUTH_DOMAIN', and
  'OAUTH_USER_ID' have already been set.

  Returns:
    User
  """
  assert 'OAUTH_EMAIL' in os.environ
  assert 'OAUTH_AUTH_DOMAIN' in os.environ
  assert 'OAUTH_USER_ID' in os.environ
  return users.User(email=os.environ['OAUTH_EMAIL'],
                    _auth_domain=os.environ['OAUTH_AUTH_DOMAIN'],
                    _user_id=os.environ['OAUTH_USER_ID'])
