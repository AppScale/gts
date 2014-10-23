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





"""
Handler for OAuth operation to get access token for Google Cloud Storage.
Required in AppScale because app_identity API does not work outside GAE.
"""


import logging
import pickle
import os
import sys
import webapp2

from google.appengine.ext import db
from google.appengine.api import users

from google.appengine.ext.datastore_admin import utils

sys.path.append(os.path.join(os.path.dirname(__file__),
  "../../../../lib/google-api-python-client"))
sys.path.append(os.path.join(os.path.dirname(__file__),
  "../../../../lib/httplib2"))
from oauth2client import client

XSRF_ACTION = 'auth'

class GCSOAuth(db.Model):
  """ A datastore object to store the oauth token. """
  user = db.UserProperty()
  gsc_token = db.StringProperty(indexed=False)
  creation_ts = db.DateTimeProperty(auto_now_add=True)
  pickled_creds = db.BlobProperty()
  pickled_flow = db.BlobProperty()

  STORED_KIND_NAME = '__GCS_OAUTH__'

  @classmethod
  def kind(cls):
    """Kind name override."""
    return cls.STORED_KIND_NAME

def get_credentials():
  """ Gets the current credentials of the logged in user if there are any. """
  current_user = users.get_current_user().email() 
  oauth_model = GCSOAuth.get_by_key_name(current_user)
  pickled_creds = oauth_model.pickled_creds
  if not pickled_creds:
    return None
  else:
    return pickle.loads(pickled_creds)

class StartAuthHandler(webapp2.RequestHandler):
  """Handler to deal with initial auth. User supplies required information."""

  SUFFIX = "auth.start"

  def get(self):
    """Get request for starting authentication.

    Args:
      handler: the webapp2.RequestHandler invoking the method
    """
    template_params = {
        'base_path': utils.config.BASE_PATH,
        'form_target': DoAuthHandler.SUFFIX,
        'app_id': os.getenv('APPLICATION_ID'),
        'xsrf_token': utils.CreateXsrfToken(XSRF_ACTION),
    }
    utils.RenderToResponse(self, 'start_auth.html', template_params)


class DoAuthHandler(webapp2.RequestHandler):
  """Handler to deal with requests from the admin console to copy data."""

  SUFFIX = 'auth.do'

  # This is the initial path we go to in order to start OAuth2 procedure.
  OAUTH_REQUEST_PATH = "https://accounts.google.com/o/oauth2/auth"

  SCOPE = "https://www.googleapis.com/auth/devstorage.read_write"

  def get(self):
    """ Callback handler for get requests to datastore_admin/auth.do. 

    This will get the token and save it to memcaceh. Otherwise it will handle
    any errors during auth.
    """
    error = self.request.get('error', '')
    code = self.request.get('code')
    state = self.request.get('state')
    if not error:
      error = self.request.get('error', '')
    if not state:
      raise Exception("No state returned!") 
    if not code:
      raise Exception("No code returned!")
    logging.info("STATE: {0}".format(state))
    oauth_model = GCSOAuth.get_by_key_name(state)
    pickled_flow = oauth_model.pickled_flow
    if not pickled_flow:
      raise Exception("Unable to resume auth flow.")
    flow = pickle.loads(pickled_flow)
    current_user = users.get_current_user().email() 

    # This step fails right now. Needs debugging.
    credentials = flow.step2_exchange(code)
    oauth_model = GCSOAuth.get_by_key_name(current_user)
    oauth_model.pickled_creds = pickle.dumps(credentials)
    oauth_model.put()

    template_params = {
        'error': error,
        'datastore_admin_home': utils.config.BASE_PATH,
        'code': code,
    }
    utils.RenderToResponse(self, 'do_auth.html', template_params)

  def post(self):
    """Handler for post requests to datastore_admin/auth.do.

    This will redirect to Google's OAuth service with the required information.
    """
    token = self.request.get('xsrf_token')
    if not utils.ValidateXsrfToken(token, XSRF_ACTION):
      raise Exception("XSRF Token was not valid")

    client_id = self.request.get('client_id')
    logging.info("CLIENT ID: {0}".format(client_id))
    client_secret = self.request.get('client_secret')
    # TODO verify the app path is a valid URL to redirect to
    app_path = self.request.get('app_path')
    if not client_id or not client_secret or not app_path:
      raise Exception("Missing client ID, client secret, or app path.")

    client_id = client_id.rstrip()
    client_secret = client_secret.rstrip()
    app_path = app_path.rstrip()
    redirect_uri = '{0}{1}/{2}'.format(app_path, utils.config.BASE_PATH, 
      self.SUFFIX)
    logging.info("REDIRECT URI: {0}".format(redirect_uri)) 
    current_user = users.get_current_user().email() 
    flow = client.OAuth2WebServerFlow(client_id=client_id, 
      client_secret=client_secret, scope=self.SCOPE, redirect_uri=redirect_uri, 
      state=current_user)
    oauth_model = GCSOAuth(key_name=current_user, pickled_flow=pickle.dumps(flow))
    oauth_model.put()

    auth_uri = flow.step1_get_authorize_url()
    logging.info("Auth URI: {0}".format(auth_uri))
    self.redirect(auth_uri)
