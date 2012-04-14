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




"""OAuth 2.0 command for Django Google SQL Service backend."""







from google.storage.speckle.python.api import rdbms_googleapi

import apiclient
from django.core.management import base
from oauth2client import client


class Command(base.NoArgsCommand):
  """Management command to fetch OAuth2 credentials for Google SQL Service."""

  requires_model_validation = False
  can_import_settings = False
  help = ('Fetches OAuth2 credentials for accessing the Google SQL Service via'
          'the Google API driver')

  def handle_noargs(self, **unused_options):
    """Perform an OAuth 2.0 oob flow.

    After the flow completes, instructions are provided to manually store the
    OAuth2 refresh_token in the project settings file.
    """
    flow = rdbms_googleapi.GetFlow()
    self.stdout.write('\nGo to the following link in your browser:\n%s\n\n' %
                      flow.step1_get_authorize_url('oob'))
    accepted = 'n'
    while accepted.lower() == 'n':
      accepted = raw_input('Have you authorized me? (y/n) ')
    code = raw_input('What is the verification code? ').strip()
    try:
      credential = flow.step2_exchange(code)
    except client.FlowExchangeError:
      raise base.CommandError('The authentication has failed.')
    self.stdout.write(
        '\nAdd your OAuth refresh token (%s) as an "OAUTH2_SECRET" parameter to'
        ' your database OPTIONS.  For example:\n' % credential.refresh_token)
    self.stdout.write("""
    DATABASES = {
        'default': {
            'ENGINE': 'google.storage.speckle.python.django.backend',
            'INSTANCE': 'examplecom:instance',
            'NAME': 'dbname',
            'OPTIONS': {
                'OAUTH2_SECRET': '%s',
            }
        }
    }\n""" % credential.refresh_token)

