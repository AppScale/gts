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
"""Tests for devappserver2.admin.console."""


import unittest

import google

import mox
import webapp2

from google.appengine.tools.devappserver2 import dispatcher
from google.appengine.tools.devappserver2 import server
from google.appengine.tools.devappserver2.admin import console


class ConsoleRequestHandlerTest(unittest.TestCase):
  """Tests for devappserver2.admin.console.ConsoleRequestHandler."""

  def setUp(self):
    self.mox = mox.Mox()
    self.mox.StubOutWithMock(console.ConsoleRequestHandler, 'dispatcher')
    console.ConsoleRequestHandler._servername_to_shell_server = {}
    self.dispatcher = self.mox.CreateMock(dispatcher.Dispatcher)
    self.server = self.mox.CreateMock(server.Server)
    self.interactive_command_server = self.mox.CreateMock(
        server.InteractiveCommandServer)

  def tearDown(self):
    self.mox.UnsetStubs()

  def test_post_new_server(self):
    request = webapp2.Request.blank('', POST={'code': 'print 5+5',
                                              'server_name': 'default'})
    response = webapp2.Response()

    handler = console.ConsoleRequestHandler(request, response)
    handler.dispatcher = self.dispatcher
    handler.dispatcher.get_server_by_name('default').AndReturn(self.server)
    self.server.create_interactive_command_server().AndReturn(
        self.interactive_command_server)
    self.interactive_command_server.send_interactive_command(
        'print 5+5').AndReturn('10\n')

    self.mox.ReplayAll()
    handler.post()
    self.mox.VerifyAll()
    self.assertEqual(200, response.status_int)
    self.assertEqual('10\n', response.body)

  def test_post_cached_server(self):
    console.ConsoleRequestHandler._servername_to_shell_server = {
        'default': self.interactive_command_server}

    request = webapp2.Request.blank('', POST={'code': 'print 5+5',
                                              'server_name': 'default'})
    response = webapp2.Response()

    handler = console.ConsoleRequestHandler(request, response)
    handler.dispatcher = self.dispatcher
    self.interactive_command_server.send_interactive_command(
        'print 5+5').AndReturn('10\n')

    self.mox.ReplayAll()
    handler.post()
    self.mox.VerifyAll()
    self.assertEqual(200, response.status_int)
    self.assertEqual('10\n', response.body)

  def test_post_exception(self):
    console.ConsoleRequestHandler._servername_to_shell_server = {
        'default': self.interactive_command_server}

    request = webapp2.Request.blank('', POST={'code': 'print 5+5',
                                              'server_name': 'default'})
    response = webapp2.Response()

    handler = console.ConsoleRequestHandler(request, response)
    handler.dispatcher = self.dispatcher
    self.interactive_command_server.send_interactive_command(
        'print 5+5').AndRaise(server.InteractiveCommandError('restart'))

    self.mox.ReplayAll()
    handler.post()
    self.mox.VerifyAll()
    self.assertEqual(200, response.status_int)
    self.assertEqual('restart', response.body)

  def test_restart(self):
    console.ConsoleRequestHandler._servername_to_shell_server = {
        'default': self.interactive_command_server}

    self.interactive_command_server.restart()

    self.mox.ReplayAll()
    console.ConsoleRequestHandler.restart(webapp2.Request.blank('/'), 'default')
    self.mox.VerifyAll()

  def test_restart_uncached_server(self):
    self.mox.ReplayAll()
    console.ConsoleRequestHandler.restart(webapp2.Request.blank('/'), 'default')
    self.mox.VerifyAll()

  def test_quit(self):
    console.ConsoleRequestHandler._servername_to_shell_server = {
        'default': self.interactive_command_server}

    self.interactive_command_server.quit()

    self.mox.ReplayAll()
    console.ConsoleRequestHandler.quit()
    self.mox.VerifyAll()

if __name__ == '__main__':
  unittest.main()
