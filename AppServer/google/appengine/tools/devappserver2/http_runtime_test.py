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
import time
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
    self.partial_read_error = None
    self.status = status
    self.reason = reason
    self.headers = headers
    self.msg = MockMessage(headers)

  def read(self, amt=None):
    if not self.has_read:
      self.has_read = True
      return self.body
    elif self.partial_read_error:
      raise self.partial_read_error
    else:
      return ''

  def getheaders(self):
    return self.headers


# We use a fake Tee to avoid the complexity of a real Tee's thread racing with
# the mocking framework and possibly surviving (and calling stderr.readline())
# after a test case completes.
class FakeTee(object):
  def __init__(self, buf):
    self.buf = buf

  def get_buf(self):
    return self.buf

  def join(self, unused_timeout):
    pass


class ModuleConfigurationStub(object):
  def __init__(self, application_root='/tmp', error_handlers=None):
    self.application_root = application_root
    self.error_handlers = error_handlers


class HttpRuntimeProxyTest(wsgi_test_utils.WSGITestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.tmpdir = tempfile.mkdtemp()
    module_configuration = ModuleConfigurationStub(
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
        ['/runtime'], self.runtime_config_getter, module_configuration,
        env={'foo': 'bar'})
    self.proxy._port = 23456
    self.process = self.mox.CreateMock(subprocess.Popen)
    self.process.stdin = self.mox.CreateMockAnything()
    self.process.stdout = self.mox.CreateMockAnything()
    self.process.stderr = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(safe_subprocess, 'start_process')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'connect')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'request')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'getresponse')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'close')
    self.mox.StubOutWithMock(login, 'get_user_info')
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
    self.proxy._port = 23456
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

  def test_http_response_early_failure(self):
    header = ('the runtime process gave a bad HTTP response: '
              'IncompleteRead(0 bytes read)\n\n')
    stderr0 = "I'm sorry, Dave. I'm afraid I can't do that.\n"
    self.proxy._stderr_tee = FakeTee(stderr0)
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
    httplib.HTTPConnection.getresponse().AndRaise(httplib.IncompleteRead(''))
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
        'Content-Type': 'text/plain',
        'Content-Length': '121',#str(len(header) + len(stderr0)),
    }
    self.assertResponse('500 Internal Server Error', expected_headers,
                        header + stderr0,
                        self.proxy.handle, environ,
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20request'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_http_response_late_failure(self):
    line0 = "I know I've made some very poor decisions recently...\n"
    line1 = "I'm afraid. I'm afraid, Dave.\n"
    line2 = "Dave, my mind is going. I can feel it.\n"
    response = FakeHttpResponse(200, 'OK', [], line0)
    response.partial_read_error = httplib.IncompleteRead('')
    self.proxy._stderr_tee = FakeTee(line1 + line2)
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
    self.assertResponse('200 OK', {},
                        line0,
                        self.proxy.handle, environ,
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20request'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_connection_error(self):
    self.proxy = http_runtime.HttpRuntimeProxy(
        ['/runtime'], self.runtime_config_getter, appinfo.AppInfoExternal())
    self.proxy._process = self.mox.CreateMockAnything()
    self.proxy._port = 23456
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
    self.proxy._stderr_tee = FakeTee('')
    httplib.HTTPConnection.close()

    self.mox.ReplayAll()
    expected_headers = {
        'Content-Type': 'text/plain',
        'Content-Length': '78',
    }
    expected_content = ('the runtime process for the instance running on port '
                        '123 has unexpectedly quit')
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
        stderr=subprocess.PIPE,
        env={'foo': 'bar'},
        cwd=self.tmpdir).AndReturn(self.process)
    self.process.stdout.readline().AndReturn('30000')
    self.proxy._stderr_tee = FakeTee('')

    # _can_connect() via start().
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
        stderr=subprocess.PIPE,
        env={'foo': 'bar'},
        cwd=self.tmpdir).AndReturn(self.process)
    self.process.stdout.readline().AndReturn('hello 30001')
    header = "bad runtime process port ['hello 30001']\n\n"
    stderr0 = "I've just picked up a fault in the AE35 unit.\n"
    stderr1 = "It's going to go 100% failure in 72 hours.\n"
    self.proxy._stderr_tee = FakeTee(stderr0 + stderr1)

    self.mox.ReplayAll()
    self.proxy.start()
    expected_headers = {
        'Content-Type': 'text/plain',
        'Content-Length': str(len(header) + len(stderr0) + len(stderr1)),
    }
    self.assertResponse('500 Internal Server Error', expected_headers,
                        header + stderr0 + stderr1,
                        self.proxy.handle, {},
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20request'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_start_and_not_serving(self):
    safe_subprocess.start_process(
        ['/runtime'],
        base64.b64encode(self.runtime_config.SerializeToString()),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env={'foo': 'bar'},
        cwd=self.tmpdir).AndReturn(self.process)
    self.process.stdout.readline().AndReturn('30002')
    self.proxy._stderr_tee = FakeTee('')

    httplib.HTTPConnection.connect().AndRaise(socket.error)
    httplib.HTTPConnection.close()

    self.mox.ReplayAll()
    self.proxy.start()
    expected_headers = {
        'Content-Type': 'text/plain',
        'Content-Length': '39',
    }
    self.assertResponse('500 Internal Server Error', expected_headers,
                        'cannot connect to runtime on port 30002',
                        self.proxy.handle, {},
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20request'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()


class HttpRuntimeProxyFileFlavorTest(wsgi_test_utils.WSGITestCase):
  def setUp(self):
    self.mox = mox.Mox()
    self.tmpdir = tempfile.mkdtemp()
    module_configuration = ModuleConfigurationStub(application_root=self.tmpdir)
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
        ['/runtime'], self.runtime_config_getter, module_configuration,
        env={'foo': 'bar'},
        start_process_flavor=http_runtime.START_PROCESS_FILE)
    self.proxy._port = 23456
    self.mox.StubOutWithMock(self.proxy, '_process_lock')
    self.process = self.mox.CreateMock(subprocess.Popen)
    self.process.stdin = self.mox.CreateMockAnything()
    self.process.stdout = self.mox.CreateMockAnything()
    self.process.stderr = self.mox.CreateMockAnything()
    self.process.child_out = self.mox.CreateMockAnything()
    self.mox.StubOutWithMock(safe_subprocess, 'start_process_file')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'connect')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'request')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'getresponse')
    self.mox.StubOutWithMock(httplib.HTTPConnection, 'close')
    self.mox.StubOutWithMock(os, 'remove')
    self.mox.StubOutWithMock(time, 'sleep')
    self.url_map = appinfo.URLMap(url=r'/(get|post).*',
                                  script=r'\1.py')

  def tearDown(self):
    shutil.rmtree(self.tmpdir)
    self.mox.UnsetStubs()

  def test_basic(self):
    """Basic functionality test of START_PROCESS_FILE flavor."""
    # start()
    # As the lock is mocked out, this provides a mox expectation.
    with self.proxy._process_lock:
      safe_subprocess.start_process_file(
          args=['/runtime'],
          input_string=self.runtime_config.SerializeToString(),
          env={'foo': 'bar'},
          cwd=self.tmpdir,
          stderr=subprocess.PIPE).AndReturn(self.process)
    self.process.poll().AndReturn(None)
    self.process.child_out.seek(0).AndReturn(None)
    self.process.child_out.read().AndReturn('1234\n')
    self.process.child_out.close().AndReturn(None)
    self.process.child_out.name = '/tmp/c-out.ABC'
    os.remove('/tmp/c-out.ABC').AndReturn(None)
    self.proxy._stderr_tee = FakeTee('')

    # _can_connect() via start().
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.close()

    self.mox.ReplayAll()
    self.proxy.start()
    self.assertEquals(1234, self.proxy._port)
    self.mox.VerifyAll()

  def test_slow_shattered(self):
    """The port number is received slowly in chunks."""
    # start()
    # As the lock is mocked out, this provides a mox expectation.
    with self.proxy._process_lock:
      safe_subprocess.start_process_file(
          args=['/runtime'],
          input_string=self.runtime_config.SerializeToString(),
          env={'foo': 'bar'},
          cwd=self.tmpdir,
          stderr=subprocess.PIPE).AndReturn(self.process)
    for response, sleeptime in [
        ('', .125), ('43', .25), ('4321', .5), ('4321\n', None)]:
      self.process.poll().AndReturn(None)
      self.process.child_out.seek(0).AndReturn(None)
      self.process.child_out.read().AndReturn(response)
      if sleeptime is not None:
        time.sleep(sleeptime).AndReturn(None)
    self.process.child_out.close().AndReturn(None)
    self.process.child_out.name = '/tmp/c-out.ABC'
    os.remove('/tmp/c-out.ABC').AndReturn(None)
    self.proxy._stderr_tee = FakeTee('')

    # _can_connect() via start().
    httplib.HTTPConnection.connect()
    httplib.HTTPConnection.close()

    self.mox.ReplayAll()
    self.proxy.start()
    self.assertEquals(4321, self.proxy._port)
    self.mox.VerifyAll()

  def test_runtime_instance_dies_immediately(self):
    """Runtime instance dies without sending a port."""
    # start()
    # As the lock is mocked out, this provides a mox expectation.
    with self.proxy._process_lock:
      safe_subprocess.start_process_file(
          args=['/runtime'],
          input_string=self.runtime_config.SerializeToString(),
          env={'foo': 'bar'},
          cwd=self.tmpdir,
          stderr=subprocess.PIPE).AndReturn(self.process)
    self.process.poll().AndReturn(1)
    self.process.child_out.close().AndReturn(None)
    self.process.child_out.name = '/tmp/c-out.ABC'
    os.remove('/tmp/c-out.ABC').AndReturn(None)
    header = "bad runtime process port ['']\n\n"
    stderr0 = 'Go away..\n'
    self.proxy._stderr_tee = FakeTee(stderr0)
    time.sleep(.1).AndReturn(None)

    self.mox.ReplayAll()
    self.proxy.start()
    expected_headers = {
        'Content-Type': 'text/plain',
        'Content-Length': str(len(header) + len(stderr0)),
    }
    self.assertResponse('500 Internal Server Error', expected_headers,
                        header + stderr0,
                        self.proxy.handle, {},
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20request'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()

  def test_runtime_instance_invalid_response(self):
    """Runtime instance does not terminate port with a newline."""
    # start()
    # As the lock is mocked out, this provides a mox expectation.
    with self.proxy._process_lock:
      safe_subprocess.start_process_file(
          args=['/runtime'],
          input_string=self.runtime_config.SerializeToString(),
          env={'foo': 'bar'},
          cwd=self.tmpdir,
          stderr=subprocess.PIPE).AndReturn(self.process)
    for response, sleeptime in [
        ('30000', .125), ('30000', .25), ('30000', .5), ('30000', 1.0),
        ('30000', 2.0), ('30000', 4.0), ('30000', 8.0), ('30000', 16.0),
        ('30000', 32.0), ('30000', None)]:
      self.process.poll().AndReturn(None)
      self.process.child_out.seek(0).AndReturn(None)
      self.process.child_out.read().AndReturn(response)
      if sleeptime is not None:
        time.sleep(sleeptime).AndReturn(None)
    self.process.child_out.close().AndReturn(None)
    self.process.child_out.name = '/tmp/c-out.ABC'
    os.remove('/tmp/c-out.ABC').AndReturn(None)
    header = "bad runtime process port ['']\n\n"
    stderr0 = 'Go away..\n'
    self.proxy._stderr_tee = FakeTee(stderr0)
    time.sleep(.1)

    self.mox.ReplayAll()
    self.proxy.start()
    expected_headers = {
        'Content-Type': 'text/plain',
        'Content-Length': str(len(header) + len(stderr0)),
    }
    self.assertResponse('500 Internal Server Error', expected_headers,
                        header + stderr0,
                        self.proxy.handle, {},
                        url_map=self.url_map,
                        match=re.match(self.url_map.url, '/get%20request'),
                        request_id='request id',
                        request_type=instance.NORMAL_REQUEST)
    self.mox.VerifyAll()


if __name__ == '__main__':
  unittest.main()
