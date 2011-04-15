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
"""Helper CGI for logins/logout in the development application server.

This CGI has these parameters:

  continue: URL to redirect to after a login or logout has completed.
  email: Email address to set for the client.
  admin: If 'True', the client should be logged in as an admin.
  action: What action to take ('Login' or 'Logout').

To view the current user information and a form for logging in and out,
supply no parameters.
"""


import cgi
import Cookie
import md5
import os
import sys
import urllib
import sha
import logging
from django.utils import simplejson
from google.appengine.api import urlfetch


CONTINUE_PARAM = 'continue'
EMAIL_PARAM = 'email'
ADMIN_PARAM = 'admin'
ACTION_PARAM = 'action'

LOGOUT_ACTION = 'Logout'
LOGIN_ACTION = 'Login'

LOGOUT_PARAM = 'action=%s' % LOGOUT_ACTION

COOKIE_NAME = 'dev_appserver_login'


def GetUserInfo(http_cookie, cookie_name=COOKIE_NAME):
  """Get the requestor's user info from the HTTP cookie in the CGI environment.

  Args:
    http_cookie: Value of the HTTP_COOKIE environment variable.
    cookie_name: Name of the cookie that stores the user info.

  Returns:
    Tuple (email, admin) where:
      email: The user's email address, if any.
      admin: True if the user is an admin; False otherwise.
  """
  COOKIE_SECRET = ""
  try:
    COOKIE_SECRET = os.environ['COOKIE_SECRET']
  except Exception, e:
    logging.info("WARNING: Cookie secret not set" + str(e))

  cookie = Cookie.SimpleCookie(http_cookie)

  valid_cookie = True
  cookie_value = ''

  if cookie_name in cookie:
    cookie_value = cookie[cookie_name].value
  cookie_value = cookie_value.replace("%3A",":")
  cookie_value = cookie_value.replace("%40",'@')
  cookie_value = cookie_value.replace("%2C",",")
  email, nickname, admin, hsh = (cookie_value.split(':') + ['', '', '', ''])[:4]
  if email == '':
    nickname = ''
    admin = ''
  else:
    vhsh = sha.new(email+nickname+admin+COOKIE_SECRET).hexdigest()
    if hsh != vhsh:
      logging.info(email+" had invalid cookie")
      valid_cookie = False
  isAdmin = False
  admin_apps = admin.split(',')
  current_app = os.environ['APPLICATION_ID']
  if current_app in admin_apps:
    isAdmin = True
  return email, nickname, isAdmin, valid_cookie

def ClearUserInfoCookie(cookie_name=COOKIE_NAME):
  """Clears the user info cookie from the requestor, logging them out.

  Args:
    cookie_name: Name of the cookie that stores the user info.

  Returns:
    'Set-Cookie' header for clearing the user info of the requestor.
  """
  set_cookie = Cookie.SimpleCookie()
  set_cookie[cookie_name] = ''
  set_cookie[cookie_name]['path'] = '/'
  set_cookie[cookie_name]['max-age'] = '0'
  return '%s\r\n' % set_cookie

def LoginRedirect(login_url,
                  hostname,
                  port,
                  relative_url,
                  outfile):
  """Writes a login redirection URL to a user.

  Args:
    login_url: Relative URL which should be used for handling user logins.
    hostname: Name of the host on which the webserver is running.
    port: Port on which the webserver is running.
    relative_url: String containing the URL accessed.
    outfile: File-like object to which the response should be written.
  """
  NGINX_HOST = os.environ['NGINX_HOST']
  NGINX_PORT = os.environ['NGINX_PORT']
  hostname = NGINX_HOST
  port = NGINX_PORT
  dest_url = "http://%s:%s%s" % (hostname, port, relative_url)
  redirect_url = 'http://%s:%s%s?%s=%s' % (hostname,
                                           port,
                                           login_url,
                                           CONTINUE_PARAM,
                                           urllib.quote(dest_url))
  outfile.write('Status: 302 Requires login\r\n')
  output_headers = []
  output_headers.append(ClearUserInfoCookie())
  for header in output_headers:
    outfile.write(header)

  outfile.write('Location: %s\r\n\r\n' % redirect_url)

def LoginServiceRedirect(dest_url, endpoint, ah_url, outfile):
  dest_url = "foo" # cgb fix for grinder testing
  redirect_url = '%s?%s=%s' % (endpoint,
                        CONTINUE_PARAM,
                        urllib.quote('%s?%s=%s' %(ah_url,CONTINUE_PARAM,dest_url)))
  #logging.info("redirect url: " + redirect_url)             
  outfile.write('Status: 302 Redirecting to login service URL\r\n')
  outfile.write('Location: %s\r\n' % redirect_url)
  outfile.write('\r\n')

def Logout(continue_url, outfile):
  output_headers = []
  output_headers.append(ClearUserInfoCookie())

  outfile.write('Status: 302 Redirecting to continue URL\r\n')
  for header in output_headers:
    outfile.write(header)
  #logging.info("logout redirect url: " + continue_url)             
  outfile.write('Location: %s\r\n' % continue_url)
  outfile.write('\r\n')


def main():
  """Runs the login and logout CGI redirector script."""
  form = cgi.FieldStorage()
  ah_path = os.environ['PATH_INFO']
  LOGIN_SERVER = os.environ['LOGIN_SERVER']

  nginx_url = os.environ['NGINX_HOST']
  nginx_port = os.environ['NGINX_PORT']
  ah_login_url = 'http://' + nginx_url + ":" + nginx_port + ah_path

  host = 'https://'+os.environ['SERVER_NAME']
  if os.environ['SERVER_PORT'] != '80':
    host = host + ":" + os.environ['SERVER_PORT']

  action = form.getfirst(ACTION_PARAM)

  if action == None:
    action = 'Login'
  continue_url = form.getfirst(CONTINUE_PARAM, '')
  login_service_endpoint = "https://"+LOGIN_SERVER+"/login"
  if action.lower() == LOGOUT_ACTION.lower():
    Logout(continue_url, sys.stdout)
  else:
    LoginServiceRedirect(continue_url, login_service_endpoint, ah_login_url, sys.stdout)
  return 0

if __name__ == '__main__':
  main()



