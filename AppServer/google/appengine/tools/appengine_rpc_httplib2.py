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




"""Library with a variant of appengine_rpc using httplib2.

The httplib2 module offers some of the features in appengine_rpc, with
one important one being a simple integration point for OAuth2 integration.
"""




import cStringIO
import logging
import os
import re
import urllib
import urllib2


import httplib2

from oauth2client import client
from oauth2client import file as oauth2client_file
from oauth2client import tools

logger = logging.getLogger('google.appengine.tools.appengine_rpc')


class Error(Exception):
  pass


class AuthPermanentFail(Error):
  """Authentication will not succeed in the current context."""


class MemoryCache(object):
  """httplib2 Cache implementation which only caches locally."""

  def __init__(self):
    self.cache = {}

  def get(self, key):
    return self.cache.get(key)

  def set(self, key, value):
    self.cache[key] = value

  def delete(self, key):
    self.cache.pop(key, None)


def RaiseHttpError(url, response_info, response_body, extra_msg=''):
  """Raise a urllib2.HTTPError based on an httplib2 response tuple."""
  if response_body is not None:
    stream = cStringIO.StringIO()
    stream.write(response_body)
    stream.seek(0)
  else:
    stream = None
  if not extra_msg:
    msg = response_info.reason
  else:
    msg = response_info.reason + ' ' + extra_msg
  raise urllib2.HTTPError(url, response_info.status, msg, response_info, stream)


class HttpRpcServerHttpLib2(object):
  """A variant of HttpRpcServer which uses httplib2.

  This follows the same interface as appengine_rpc.AbstractRpcServer,
  but is a totally separate implementation.
  """

  def __init__(self, host, auth_function, user_agent, source,
               host_override=None, extra_headers=None, save_cookies=False,
               auth_tries=None, account_type=None, debug_data=True, secure=True,
               ignore_certs=False, rpc_tries=3):
    """Creates a new HttpRpcServerHttpLib2.

    Args:
      host: The host to send requests to.
      auth_function: Saved but ignored; may be used by subclasses.
      user_agent: The user-agent string to send to the server. Specify None to
        omit the user-agent header.
      source: Saved but ignored; may be used by subclasses.
      host_override: The host header to send to the server (defaults to host).
      extra_headers: A dict of extra headers to append to every request. Values
        supplied here will override other default headers that are supplied.
      save_cookies: Saved but ignored; may be used by subclasses.
      auth_tries: The number of times to attempt auth_function before failing.
      account_type: Saved but ignored; may be used by subclasses.
      debug_data: Whether debugging output should include data contents.
      secure: If the requests sent using Send should be sent over HTTPS.
      ignore_certs: If the certificate mismatches should be ignored.
      rpc_tries: The number of rpc retries upon http server error (i.e.
        Response code >= 500 and < 600) before failing.
    """
    self.host = host
    self.auth_function = auth_function
    self.user_agent = user_agent
    self.source = source
    self.host_override = host_override
    self.extra_headers = extra_headers or {}
    self.save_cookies = save_cookies
    self.auth_tries = auth_tries
    self.account_type = account_type
    self.debug_data = debug_data
    self.secure = secure
    self.ignore_certs = ignore_certs
    self.rpc_tries = rpc_tries
    self.scheme = secure and 'https' or 'http'

    self.certpath = None
    self.cert_file_available = False
    if not self.ignore_certs:



      self.certpath = os.path.normpath(os.path.join(
          os.path.dirname(__file__), '..', '..', '..', 'lib', 'cacerts',
          'cacerts.txt'))
      self.cert_file_available = os.path.exists(self.certpath)

    self.memory_cache = MemoryCache()

  def _Authenticate(self, http, saw_error):
    """Pre or Re-auth stuff...

    Args:
      http: An 'Http' object from httplib2.
      saw_error: If the user has already tried to contact the server.
        If they have, it's OK to prompt them. If not, we should not be asking
        them for auth info--it's possible it'll suceed w/o auth.
    """


    raise NotImplementedError()

  def Send(self, request_path, payload='',
           content_type='application/octet-stream',
           timeout=None,
           **kwargs):
    """Sends an RPC and returns the response.

    Args:
      request_path: The path to send the request to, eg /api/appversion/create.
      payload: The body of the request, or None to send an empty request.
      content_type: The Content-Type header to use.
      timeout: timeout in seconds; default None i.e. no timeout.
        (Note: for large requests on OS X, the timeout doesn't work right.)
      Any keyword arguments are converted into query string parameters.

    Returns:
      The response body, as a string.

    Raises:
      AuthPermanentFail: If authorization failed in a permanent way.
      urllib2.HTTPError: On most HTTP errors.
    """









    self.http = httplib2.Http(
        cache=self.memory_cache, ca_certs=self.certpath,
        disable_ssl_certificate_validation=(not self.cert_file_available))
    self.http.follow_redirects = False
    self.http.timeout = timeout
    url = '%s://%s%s' % (self.scheme, self.host, request_path)
    if kwargs:
      url += '?' + urllib.urlencode(sorted(kwargs.items()))
    headers = {}
    if self.extra_headers:
      headers.update(self.extra_headers)



    headers['X-appcfg-api-version'] = '1'

    if payload is not None:
      method = 'POST'

      headers['content-length'] = str(len(payload))
      headers['Content-Type'] = content_type
    else:
      method = 'GET'
    if self.host_override:
      headers['Host'] = self.host_override

    tries = 0
    auth_tries = [0]

    def NeedAuth():
      """Marker that we need auth; it'll actually be tried next time around."""
      auth_tries[0] += 1
      if auth_tries[0] > self.auth_tries:
        RaiseHttpError(url, response_info, response, 'Too many auth attempts.')

    while tries < self.rpc_tries:
      tries += 1
      self._Authenticate(self.http, auth_tries[0] > 0)
      logger.debug('Sending request to %s headers=%s body=%s',
                   url, headers,
                   self.debug_data and payload or payload and 'ELIDED' or '')
      try:
        response_info, response = self.http.request(
            url, method=method, body=payload, headers=headers)
      except client.AccessTokenRefreshError, e:

        logger.info('Got access token error', exc_info=1)
        response_info = httplib2.Response({'status': 401})
        response_info.reason = str(e)
        response = ''

      status = response_info.status
      if status == 200:
        return response
      logger.debug('Got http error %s, this is try #%s',
                   response_info.status, tries)
      if status == 401:
        NeedAuth()
        continue
      elif status >= 500 and status < 600:

        continue
      elif status == 302:


        loc = response_info.get('location')
        logger.debug('Got 302 redirect. Location: %s', loc)
        if (loc.startswith('https://www.google.com/accounts/ServiceLogin') or
            re.match(r'https://www.google.com/a/[a-z0-9.-]+/ServiceLogin',
                     loc)):
          NeedAuth()
          continue
        elif loc.startswith('http://%s/_ah/login' % (self.host,)):

          RaiseHttpError(url, response_info, response,
                         'dev_appserver login not supported')
        else:
          RaiseHttpError(url, response_info, response,
                         'Unexpected redirect to %s' % loc)
      else:
        logger.debug('Unexpected results: %s', response_info)
        RaiseHttpError(url, response_info, response,
                       'Unexpected HTTP status %s' % status)
    logging.info('Too many retries for url %s', url)
    RaiseHttpError(url, response_info, response)


class NoStorage(client.Storage):
  """A no-op implementation of storage."""

  def locked_get(self):
    return None

  def locked_put(self, credentials):
    pass


class HttpRpcServerOauth2(HttpRpcServerHttpLib2):
  """A variant of HttpRpcServer which uses oauth2.

  This variant is specifically meant for interactive command line usage,
  as it will attempt to open a browser and ask the user to enter
  information from the resulting web page.
  """

  def __init__(self, host, refresh_token, user_agent, source,
               host_override=None, extra_headers=None, save_cookies=False,
               auth_tries=None, account_type=None, debug_data=True, secure=True,
               ignore_certs=False, rpc_tries=3):
    """Creates a new HttpRpcServerOauth2.

    Args:
      host: The host to send requests to.
      refresh_token: A string refresh token to use, or None to guide the user
        through the auth flow. (Replaces auth_function on parent class.)
      user_agent: The user-agent string to send to the server. Specify None to
        omit the user-agent header.
      source: Tuple, (client_id, client_secret, scope), for oauth credentials.
      host_override: The host header to send to the server (defaults to host).
      extra_headers: A dict of extra headers to append to every request. Values
        supplied here will override other default headers that are supplied.
      save_cookies: If the refresh token should be saved.
      auth_tries: The number of times to attempt auth_function before failing.
      account_type: Ignored.
      debug_data: Whether debugging output should include data contents.
      secure: If the requests sent using Send should be sent over HTTPS.
      ignore_certs: If the certificate mismatches should be ignored.
      rpc_tries: The number of rpc retries upon http server error (i.e.
        Response code >= 500 and < 600) before failing.
    """
    super(HttpRpcServerOauth2, self).__init__(
        host, None, user_agent, None, host_override=host_override,
        extra_headers=extra_headers, auth_tries=auth_tries,
        debug_data=debug_data, secure=secure, ignore_certs=ignore_certs,
        rpc_tries=rpc_tries)

    if not isinstance(source, tuple) or len(source) not in (3, 4):
      raise TypeError('Source must be tuple (client_id, client_secret, scope).')

    self.client_id = source[0]
    self.client_secret = source[1]
    self.scope = source[2]
    oauth2_credential_file = (len(source) > 3 and source[3]
                              or '~/.appcfg_oauth2_tokens')

    if save_cookies:
      self.storage = oauth2client_file.Storage(
          os.path.expanduser(oauth2_credential_file))
    else:
      self.storage = NoStorage()

    self.refresh_token = refresh_token
    if refresh_token:
      self.credentials = client.OAuth2Credentials(
          None,
          self.client_id,
          self.client_secret,
          refresh_token,
          None,
          ('https://%s/o/oauth2/token' %
           os.getenv('APPENGINE_AUTH_SERVER', 'accounts.google.com')),
          self.user_agent)
    else:
      self.credentials = self.storage.get()

  def _Authenticate(self, http, needs_auth):
    """Pre or Re-auth stuff...

    This will attempt to avoid making any OAuth related HTTP connections or
    user interactions unless it's needed.

    Args:
      http: An 'Http' object from httplib2.
      needs_auth: If the user has already tried to contact the server.
        If they have, it's OK to prompt them. If not, we should not be asking
        them for auth info--it's possible it'll suceed w/o auth, but if we have
        some credentials we'll use them anyway.

    Raises:
      AuthPermanentFail: The user has requested non-interactive auth but
        the token is invalid.
    """
    if needs_auth and (not self.credentials or self.credentials.invalid):
      if self.refresh_token:

        logger.debug('_Authenticate and skipping auth because user explicitly '
                     'supplied a refresh token.')
        raise AuthPermanentFail('Refresh token is invalid.')
      logger.debug('_Authenticate and requesting auth')
      flow = client.OAuth2WebServerFlow(
          client_id=self.client_id,
          client_secret=self.client_secret,
          scope=self.scope,
          user_agent=self.user_agent)
      self.credentials = tools.run(flow, self.storage)
    if self.credentials and not self.credentials.invalid:


      if not self.credentials.access_token_expired or needs_auth:
        logger.debug('_Authenticate configuring auth; needs_auth=%s',
                     needs_auth)
        self.credentials.authorize(http)
        return
    logger.debug('_Authenticate skipped auth; needs_auth=%s', needs_auth)
