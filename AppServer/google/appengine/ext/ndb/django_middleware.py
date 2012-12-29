#!/usr/bin/env python
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
"""Django middleware for NDB."""

__author__ = 'James A. Morrison'

from . import eventloop, tasklets


class NdbDjangoMiddleware(object):
  """Django middleware for NDB.

  To use NDB with django, add

    'ndb.NdbDjangoMiddleware',

  to the MIDDLEWARE_CLASSES entry in your Django settings.py file.
  Or, if you are using the ndb version from the SDK, use

    'google.appengine.ext.ndb.NdbDjangoMiddleware',

  It's best to insert it in front of any other middleware classes,
  since some other middleware may make datastore calls and those won't be
  handled properly if that middleware is invoked before this middleware.

  See http://docs.djangoproject.com/en/dev/topics/http/middleware/.
  """

  def process_request(self, unused_request):
    """Called by Django before deciding which view to execute."""
    # Compare to the first half of toplevel() in context.py.
    tasklets._state.clear_all_pending()
    # Create and install a new context.
    ctx = tasklets.make_default_context()
    tasklets.set_context(ctx)

  @staticmethod
  def _finish():
    # Compare to the finally clause in toplevel() in context.py.
    ctx = tasklets.get_context()
    tasklets.set_context(None)
    ctx.flush().check_success()
    eventloop.run()  # Ensure writes are flushed, etc.

  def process_response(self, request, response):
    """Called by Django just before returning a response."""
    self._finish()
    return response

  def process_exception(self, unused_request, unused_exception):
    """Called by Django when a view raises an exception."""
    self._finish()
    return None
