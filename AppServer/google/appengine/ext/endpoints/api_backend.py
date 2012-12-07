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


"""Interface to the BackendService that serves API configurations."""


from protorpc import message_types
from protorpc import messages
from protorpc import remote

package = 'google.appengine.endpoints'


__all__ = [
    'ApiConfigList',
    'BackendService',
    'package',
]


class ApiConfigList(messages.Message):
  """List of API configuration file contents."""
  items = messages.StringField(1, repeated=True)


class BackendService(remote.Service):
  """API config enumeration service used by Google API Server.

  This is a simple API providing a list of APIs served by this App Engine
  instance.  It is called by the Google API Server during app deployment
  to get an updated interface for each of the supported APIs.
  """



  @remote.method(message_types.VoidMessage, ApiConfigList)
  def getApiConfigs(self, unused_request):
    """Return a list of active APIs and their configuration files.

    Args:
      unused_request: Empty request message, unused

    Returns:
      List of ApiConfigMessages
    """
    raise NotImplementedError()
