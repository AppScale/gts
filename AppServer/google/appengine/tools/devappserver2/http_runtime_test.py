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
"""Tests for google.appengine.tools.devappserver2.http_runtime."""


import base64
import cStringIO
import httplib
import os
import re
import shutil
import socket
import subprocess
import tempfile
import unittest

import google

import mox

from google.appengine.api import appinfo
from google.appengine.tools.devappserver2 import http_runtime
from google.appengine.tools.devappserver2 import http_runtime_constants
from google.appengine.tools.devappserver2 import instance
from google.appengine.tools.devappserver2 import login
from google.appengine.tools.devappserver2 import runtime_config_pb2
from google.appengine.tools.devappserver2 import safe_subprocess
from google.appengine.tools.devappserver2 import shutdown
from google.appengine.tools.devappserver2 import wsgi_test_utils


class MockMessage(object):
  def __init__(self, headers):
    self.headers = headers

  def __iter__(self):
    return iter(set(name for name, _ in self.headers))

  def getheaders(self, name):
    return [value for header_name, value in self.headers if header_name == name]


class FakeHttpResponse(object):
  def __init__(self, status, reason, headers, body):
    self.body = body
    self.has_read = False
    self.status = status
    self.reason = reason
    self.headers = headers
    self.msg = MockMessage(headers)

  def read(self, amt=None):
    if not self.has_read:
      self.has_read = True
      return self.body
    else:
      return ''

  def getheaders(self):
    return self.headers


class ServerConfigurationStub(object):
  def __init__(self, application_root='/tmp', error_handlers=None):
    self.application_root = application_root
    self.error_handlers = error_handlers


class HttpRuntimeProxyTest(wsgi_test_utils.WSGITestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.tmpdir = tempfile.mkdtemp()
    server_configuration = ServerConfigurationStub(
        application_root=self.tmpdir,
        error_handlers=[
            appinfo.ErrorHandlers(error_code='over_quota', file='foo.html'),
            appinfo.ErrorHandlers(error_code='default', file='error.html'),
            ])
    self.runtime_config = runtime_config_pb2.Config()
    self.runtime_config.app_id = 'app'
    self.runtime_config.version_id = 'version'
    self.runtime_config.api_port = 12345
    self.runtime_config.application_root = self.tmpdir
    self.runtime_config.datacenter = 'us1'
    self.runtime_config.instance_id = 'abc3dzac4'
    self.runtime_config.auth_domain = 'gmail.com'
    self.runtime_config_getter = lambda: self.runtime_config
    self.proxy = http_runtime.HttpRuntimeProxy(
        ['/runtime'], self.runtime_config_getter, server_configuration,
        env={'foo': 'bar'})
    self.process = self.mox.CreateMock(subprocess.Popen)
    self.process.stdin = self.mox.CreateMockAnything()
    self.process.stdout = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(safe_subprocess, 'start_process')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'connect')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'request')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'getresponse')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'close')
    self.mox.StubOutWithMock(login, 'get_user_info')
    self.mox.StubOutWithMock(shutdown, 'async_quit')
    self.url_map = appinfo.URLMap(url=r'/(get|post).*',
                                  script=r'\1.py')

  def tearDown(self):
    shutil.rmtree(self.tmpdir)
    self.mox.UnsetStubs()

  def test_handle_get(self):
    response = FakeHttpResponse(200,
                                'OK',
                                [('Foo', 'a'), ('Foo', 'b'), ('Var', 'c')],
                                'response')
    login.get_user_info(None).AndReturn(('', False, ''))
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.request(
        'GET', '/get%20request?key=value', '',
        {'HEADER': 'value',
         http_runtime_constants.REQUEST_ID_HEADER: 'request id',
         'X-AppEngine-Country': 'ZZ',
         'X-Appengine-Internal-User-Email': '',
         'X-Appengine-Internal-User-Id': '',
         'X-Appengine-Internal-User-Is-Admin': '0',
         'X-Appengine-Internal-User-Nickname': '',
         'X-Appengine-Internal-User-Organization': '',
         'X-APPENGINE-INTERNAL-SCRIPT': 'get.py',
         'X-APPENGINE-INTERNAL-SERVER-NAME': 'localhost',
         'X-APPENGINE-INTERNAL-SERVER-PORT': '8080',
         'X-APPENGINE-INTERNAL-SERVER-PROTOCOL': 'HTTP/1.1',
        })
    httplib.HTTPConnection.getresponse().AndReturn(response)
    httplib.HTTPConnection.close()
    environ = {'HTTP_HEADER': 'value', 'PATH_INFO': '/get request',
               'QUERY_STRING': 'key=value',
               'HTTP_X_APPENGINE_INTERNAL_USER_ID': '123',
               'SERVER_NAME': 'localhost',
               'SERVER_PORT': '8080',
               'SERVER_PROTOCOL': 'HTTP/1.1',
              }
    self.mox.ReplayAll()
    expected_headers = [('Foo', 'a'), ('Foo', 'b'), ('Var', 'c')]
    self.assertResponse('200 OK', expected_headers, 'response',
                        self.proxy.handle, environ,
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20request'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_handle_post(self):
    response = FakeHttpResponse(200,
                                'OK',
                                [('Foo', 'a'), ('Foo', 'b'), ('Var', 'c')],
                                'response')
    login.get_user_info('cookie').AndReturn(('user@example.com', True, '12345'))
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.request(
        'POST', '/post', 'post data',
        {'HEADER': 'value',
         'COOKIE': 'cookie',
         'CONTENT-TYPE': 'text/plain',
         'CONTENT-LENGTH': '9',
         http_runtime_constants.REQUEST_ID_HEADER: 'request id',
         'X-AppEngine-Country': 'ZZ',
         'X-Appengine-Internal-User-Email': 'user@example.com',
         'X-Appengine-Internal-User-Id': '12345',
         'X-Appengine-Internal-User-Is-Admin': '1',
         'X-Appengine-Internal-User-Nickname': 'user',
         'X-Appengine-Internal-User-Organization': 'example.com',
         'X-APPENGINE-INTERNAL-SCRIPT': 'post.py',
         'X-APPENGINE-INTERNAL-SERVER-NAME': 'localhost',
         'X-APPENGINE-INTERNAL-SERVER-PORT': '8080',
         'X-APPENGINE-INTERNAL-SERVER-PROTOCOL': 'HTTP/1.1',
        })
    httplib.HTTPConnection.getresponse().AndReturn(response)
    httplib.HTTPConnection.close()
    environ = {'HTTP_HEADER': 'value', 'PATH_INFO': '/post',
               'wsgi.input': cStringIO.StringIO('post data'),
               'CONTENT_LENGTH': '9',
               'CONTENT_TYPE': 'text/plain',
               'REQUEST_METHOD': 'POST',
               'HTTP_COOKIE': 'cookie',
               'SERVER_NAME': 'localhost',
               'SERVER_PORT': '8080',
               'SERVER_PROTOCOL': 'HTTP/1.1',
              }
    self.mox.ReplayAll()
    expected_headers = [('Foo', 'a'), ('Foo', 'b'), ('Var', 'c')]
    self.assertResponse('200 OK', expected_headers, 'response',
                        self.proxy.handle, environ,
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/post'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_handle_with_error(self):
    with open(os.path.join(self.tmpdir, 'error.html'), 'w') as f:
      f.write('error')
    response = FakeHttpResponse(
        500, 'Internal Server Error',
        [(http_runtime_constants.ERROR_CODE_HEADER, '1')], '')
    login.get_user_info(None).AndReturn(('', False, ''))
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.request(
        'GET', '/get%20error', '',
        {'HEADER': 'value',
         http_runtime_constants.REQUEST_ID_HEADER: 'request id',
         'X-AppEngine-Country': 'ZZ',
         'X-Appengine-Internal-User-Email': '',
         'X-Appengine-Internal-User-Id': '',
         'X-Appengine-Internal-User-Is-Admin': '0',
         'X-Appengine-Internal-User-Nickname': '',
         'X-Appengine-Internal-User-Organization': '',
         'X-APPENGINE-INTERNAL-SCRIPT': 'get.py',
         'X-APPENGINE-INTERNAL-SERVER-NAME': 'localhost',
         'X-APPENGINE-INTERNAL-SERVER-PORT': '8080',
         'X-APPENGINE-INTERNAL-SERVER-PROTOCOL': 'HTTP/1.1',
        })
    httplib.HTTPConnection.getresponse().AndReturn(response)
    httplib.HTTPConnection.close()
    environ = {'HTTP_HEADER': 'value', 'PATH_INFO': '/get error',
               'QUERY_STRING': '',
               'HTTP_X_APPENGINE_INTERNAL_USER_ID': '123',
               'SERVER_NAME': 'localhost',
               'SERVER_PORT': '8080',
               'SERVER_PROTOCOL': 'HTTP/1.1',
              }
    self.mox.ReplayAll()
    expected_headers = {
        'Content-Type': 'text/html',
        'Content-Length': '5',
    }
    self.assertResponse('500 Internal Server Error', expected_headers, 'error',
                        self.proxy.handle, environ,
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20error'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_handle_with_error_no_error_handler(self):
    self.proxy = http_runtime.HttpRuntimeProxy(
        ['/runtime'], self.runtime_config_getter, appinfo.AppInfoExternal())
    response = FakeHttpResponse(
        500, 'Internal Server Error',
        [(http_runtime_constants.ERROR_CODE_HEADER, '1')], '')
    login.get_user_info(None).AndReturn(('', False, ''))
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.request(
        'GET', '/get%20error', '',
        {'HEADER': 'value',
         http_runtime_constants.REQUEST_ID_HEADER: 'request id',
         'X-AppEngine-Country': 'ZZ',
         'X-Appengine-Internal-User-Email': '',
         'X-Appengine-Internal-User-Id': '',
         'X-Appengine-Internal-User-Is-Admin': '0',
         'X-Appengine-Internal-User-Nickname': '',
         'X-Appengine-Internal-User-Organization': '',
         'X-APPENGINE-INTERNAL-SCRIPT': 'get.py',
         'X-APPENGINE-INTERNAL-SERVER-NAME': 'localhost',
         'X-APPENGINE-INTERNAL-SERVER-PORT': '8080',
         'X-APPENGINE-INTERNAL-SERVER-PROTOCOL': 'HTTP/1.1',
        })
    httplib.HTTPConnection.getresponse().AndReturn(response)
    httplib.HTTPConnection.close()
    environ = {'HTTP_HEADER': 'value', 'PATH_INFO': '/get error',
               'QUERY_STRING': '',
               'HTTP_X_APPENGINE_INTERNAL_USER_ID': '123',
               'SERVER_NAME': 'localhost',
               'SERVER_PORT': '8080',
               'SERVER_PROTOCOL': 'HTTP/1.1',
              }
    self.mox.ReplayAll()
    self.assertResponse('500 Internal Server Error', {}, '',
                        self.proxy.handle, environ,
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20error'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_handle_with_error_missing_error_handler(self):
    response = FakeHttpResponse(
        500, 'Internal Server Error',
        [(http_runtime_constants.ERROR_CODE_HEADER, '1')], '')
    login.get_user_info(None).AndReturn(('', False, ''))
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.request(
        'GET', '/get%20error', '',
        {'HEADER': 'value',
         http_runtime_constants.REQUEST_ID_HEADER: 'request id',
         'X-AppEngine-Country': 'ZZ',
         'X-Appengine-Internal-User-Email': '',
         'X-Appengine-Internal-User-Id': '',
         'X-Appengine-Internal-User-Is-Admin': '0',
         'X-Appengine-Internal-User-Nickname': '',
         'X-Appengine-Internal-User-Organization': '',
         'X-APPENGINE-INTERNAL-SCRIPT': 'get.py',
         'X-APPENGINE-INTERNAL-SERVER-NAME': 'localhost',
         'X-APPENGINE-INTERNAL-SERVER-PORT': '8080',
         'X-APPENGINE-INTERNAL-SERVER-PROTOCOL': 'HTTP/1.1',
        })
    httplib.HTTPConnection.getresponse().AndReturn(response)
    httplib.HTTPConnection.close()
    environ = {'HTTP_HEADER': 'value', 'PATH_INFO': '/get error',
               'QUERY_STRING': '',
               'HTTP_X_APPENGINE_INTERNAL_USER_ID': '123',
               'SERVER_NAME': 'localhost',
               'SERVER_PORT': '8080',
               'SERVER_PROTOCOL': 'HTTP/1.1',
              }
    self.mox.ReplayAll()
    expected_headers = {
        'Content-Type': 'text/html',
        'Content-Length': '28',
    }
    self.assertResponse('500 Internal Server Error', expected_headers,
                        'Failed to load error handler', self.proxy.handle,
                        environ, url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20error'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_connection_error(self):
    self.proxy = http_runtime.HttpRuntimeProxy(
        ['/runtime'], self.runtime_config_getter, appinfo.AppInfoExternal())
    self.proxy._process = self.mox.CreateMockAnything()
    login.get_user_info(None).AndReturn(('', False, ''))
    httplib.HTTPConnection.connect().AndRaise(socket.error())
    self.proxy._process.poll().AndReturn(None)
    httplib.HTTPConnection.close()

    self.mox.ReplayAll()
    self.assertRaises(socket.error,
                      self.proxy.handle(
                          {'PATH_INFO': '/'},
                          start_response=None,  # Not used.
                          url_map=self.url_map,
                          match=re.match(self.url_map.url, '/get%20error'),
                          request_id='request id',
                          request_type=instance.NORMAL_REQUEST).next)
    self.mox.VerifyAll()

  def test_connection_error_process_quit(self):
    self.proxy = http_runtime.HttpRuntimeProxy(
        ['/runtime'], self.runtime_config_getter, appinfo.AppInfoExternal())
    self.proxy._process = self.mox.CreateMockAnything()
    self.proxy._port = 123
    login.get_user_info(None).AndReturn(('', False, ''))
    httplib.HTTPConnection.connect().AndRaise(socket.error())
    self.proxy._process.poll().AndReturn(1)
    shutdown.async_quit()
    httplib.HTTPConnection.close()

    self.mox.ReplayAll()
    expected_headers = {
        'Content-Type': 'text/plain',
        'Content-Length': '110',
    }
    expected_content = ('the runtime process for the instance running on port '
                        '123 has unexpectedly quit; exiting the development '
                        'server')
    self.assertResponse('500 Internal Server Error',
                        expected_headers,
                        expected_content,
                        self.proxy.handle,
                        {'PATH_INFO': '/'},
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20error'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()
    self.mox.VerifyAll()

  def test_handle_background_thread(self):
    response = FakeHttpResponse(200, 'OK', [('Foo', 'Bar')], 'response')
    login.get_user_info(None).AndReturn(('', False, ''))
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.request(
        'GET', '/get%20request?key=value', '',
        {'HEADER': 'value',
         http_runtime_constants.REQUEST_ID_HEADER: 'request id',
         'X-AppEngine-Country': 'ZZ',
         'X-Appengine-Internal-User-Email': '',
         'X-Appengine-Internal-User-Id': '',
         'X-Appengine-Internal-User-Is-Admin': '0',
         'X-Appengine-Internal-User-Nickname': '',
         'X-Appengine-Internal-User-Organization': '',
         'X-APPENGINE-INTERNAL-SCRIPT': 'get.py',
         'X-APPENGINE-INTERNAL-REQUEST-TYPE': 'background',
         'X-APPENGINE-INTERNAL-SERVER-NAME': 'localhost',
         'X-APPENGINE-INTERNAL-SERVER-PORT': '8080',
         'X-APPENGINE-INTERNAL-SERVER-PROTOCOL': 'HTTP/1.1',
        })
    httplib.HTTPConnection.getresponse().AndReturn(response)
    httplib.HTTPConnection.close()
    environ = {'HTTP_HEADER': 'value', 'PATH_INFO': '/get request',
               'QUERY_STRING': 'key=value',
               'HTTP_X_APPENGINE_INTERNAL_USER_ID': '123',
               'SERVER_NAME': 'localhost',
               'SERVER_PORT': '8080',
               'SERVER_PROTOCOL': 'HTTP/1.1',
              }
    self.mox.ReplayAll()
    expected_headers = {
        'Foo': 'Bar',
    }
    self.assertResponse('200 OK', expected_headers, 'response',
                        self.proxy.handle, environ,
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20request'),
                        request_id='request id',
                        request_type=instance.BACKGROUND_REQUEST)
    self.mox.VerifyAll()

  def test_start_and_quit(self):
    ## Test start()
    # start()
    safe_subprocess.start_process(
        ['/runtime'],
        base64.b64encode(self.runtime_config.SerializeToString()),
        stdout=subprocess.PIPE,
        env={'foo': 'bar'},
        cwd=self.tmpdir).AndReturn(self.process)
    self.process.stdout.readline().AndReturn('34567')

    # _can_connect() via _check_serving().
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.close()

    self.mox.ReplayAll()
    self.proxy.start()
    self.mox.VerifyAll()
    self.mox.ResetAll()

    ## Test quit()
    self.process.kill()
    self.mox.ReplayAll()
    self.proxy.quit()
    self.mox.VerifyAll()

  def test_start_bad_port(self):
    safe_subprocess.start_process(
        ['/runtime'],
        base64.b64encode(self.runtime_config.SerializeToString()),
        stdout=subprocess.PIPE,
        env={'foo': 'bar'},
        cwd=self.tmpdir).AndReturn(self.process)
    self.process.stdout.readline().AndReturn('hello 34567')
    shutdown.async_quit()

    self.mox.ReplayAll()
    self.proxy.start()
    self.mox.VerifyAll()

  def test_start_and_not_serving(self):
    safe_subprocess.start_process(
        ['/runtime'],
        base64.b64encode(self.runtime_config.SerializeToString()),
        stdout=subprocess.PIPE,
        env={'foo': 'bar'},
        cwd=self.tmpdir).AndReturn(self.process)
    self.process.stdout.readline().AndReturn('34567')

    httplib.HTTPConnection.connect().AndRaise(socket.error)
    httplib.HTTPConnection.close()
    shutdown.async_quit()

    self.mox.ReplayAll()
    self.proxy.start()
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
