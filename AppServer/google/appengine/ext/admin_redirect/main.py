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




"""Main module for admin redirect.

To use, add this to app.yaml:
  builtins:
  - admin_redirect: on
"""


import logging

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util


GOOGLE_SUFFIX = '.google.com'
CONSOLE_SUFFIX = '/dashboard?app_id='
APPENGINE_URL = 'https://appengine.google.com'

ADMIN_CONSOLE_NAME = 'admin-console'
APPLICATION_ID_PARAM = 'APPLICATION_ID'
SERVER_NAME_PARAM = 'SERVER_NAME'


class RedirectToAdminConsole(webapp.RequestHandler):
  """Used to redirect the user to the appropriate Admin Console URL."""

  def get(self):
    """Handler to redirect all /_ah/admin.* requests to Admin Console."""
    app_id = self.request.environ.get(APPLICATION_ID_PARAM)
    if not app_id:
      logging.error('Could not get application id; generic redirect.')
      self.redirect(APPENGINE_URL)
      return

    server = self.request.environ.get(SERVER_NAME_PARAM)
    if not server:
      logging.warning('Server parameter not present; appengine.com redirect.')
      self.redirect('%s%s%s' % (APPENGINE_URL, CONSOLE_SUFFIX, app_id))
      return

    if server.endswith(GOOGLE_SUFFIX):


      if server.find(app_id) == 0:
        new_server = server.replace(app_id, ADMIN_CONSOLE_NAME)
        self.redirect('http://%s%s%s' % (new_server,
                                         CONSOLE_SUFFIX,
                                         app_id))

      else:
        self.response.out.write("""
          Could not determine admin console location from server name.""")


    else:
      self.redirect('%s%s%s' % (APPENGINE_URL, CONSOLE_SUFFIX, app_id))


def CreateApplication():
  """Create new WSGIApplication and register all handlers.

  Returns:
    an instance of webapp.WSGIApplication with all mapreduce handlers
    registered.
  """
  return webapp.WSGIApplication([(r'.*', RedirectToAdminConsole)],
                                debug=True)


APP = CreateApplication()


def main():
  util.run_wsgi_app(APP)


if __name__ == '__main__':
  main()
