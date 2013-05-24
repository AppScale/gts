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
"""A handler that provides an interactive console."""


import threading

from google.appengine.tools.devappserver2 import server
from google.appengine.tools.devappserver2.admin import admin_request_handler


class ConsoleRequestHandler(admin_request_handler.AdminRequestHandler):
  """Provides an interactive console for servers that support it."""

  _servername_to_shell_server = {}
  _servername_to_shell_server_lock = threading.Lock()

  def get(self):
    self.response.write(
        self.render('console.html',
                    {'servers': [servr for servr in self.dispatcher.servers
                                 if servr.supports_interactive_commands]}))

  def post(self):
    server_name = self.request.get('server_name')
    with self._servername_to_shell_server_lock:
      if server_name in self._servername_to_shell_server:
        servr = self._servername_to_shell_server[server_name]
      else:
        servr = self.dispatcher.get_server_by_name(
            server_name).create_interactive_command_server()
        self._servername_to_shell_server[server_name] = servr

    self.response.content_type = 'text/plain'
    try:
      response = servr.send_interactive_command(self.request.get('code'))
    except server.InteractiveCommandError, e:
      response = str(e)

    self.response.write(response)

  @classmethod
  def quit(cls):
    with cls._servername_to_shell_server_lock:
      for shell_server in cls._servername_to_shell_server.itervalues():
        shell_server.quit()

  @classmethod
  def restart(cls, request, server_name):
    with cls._servername_to_shell_server_lock:
      if server_name in cls._servername_to_shell_server:
        servr = cls._servername_to_shell_server[server_name]
        servr.restart()
