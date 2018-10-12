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
"""Regression tests for Endpoints server in devappserver2."""


import json
import os.path

from google.testing.pybase import googletest

from google.appengine.tools.devappserver2 import regtest_utils
from google.appengine.tools.devappserver2.endpoints import endpoints_server


class EndpointsServerRegtest(regtest_utils.BaseTestCase):
  """Tests that the development server can correctly serve static content."""

  def setUp(self):
    super(EndpointsServerRegtest, self).setUp()
    server_path = os.path.join(self.devappserver2_path,
                               'endpoints/testdata/app.yaml')
    self.start_server([server_path])

  def test_rest_get(self):
    """Test that a GET request to a REST API works."""
    status, content, headers = self.fetch_url('default', 'GET',
                                              '/_ah/api/test_service/v1/test')
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertEqual({'text': 'Test response'}, response_json)

  def test_rest_post(self):
    """Test that a POST request to a REST API works."""
    body = json.dumps({'name': 'MyName', 'number': 23})
    send_headers = {'content-type': 'application/json'}
    status, content, headers = self.fetch_url('default', 'POST',
                                              '/_ah/api/test_service/v1/t2path',
                                              body, send_headers)
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertEqual({'text': 'MyName 23'}, response_json)

  def test_cors(self):
    """Test that CORS headers are handled properly."""
    send_headers = {'Origin': 'test.com',
                    'Access-control-request-method': 'GET',
                    'Access-Control-Request-Headers': 'Date,Expires'}
    status, _, headers = self.fetch_url('default', 'GET',
                                        '/_ah/api/test_service/v1/test',
                                        headers=send_headers)
    self.assertEqual(200, status)
    self.assertEqual(headers[endpoints_server._CORS_HEADER_ALLOW_ORIGIN],
                     'test.com')
    self.assertIn('GET',
                  headers[endpoints_server._CORS_HEADER_ALLOW_METHODS].split(
                      ','))
    self.assertEqual(headers[endpoints_server._CORS_HEADER_ALLOW_HEADERS],
                     'Date,Expires')

  def test_rpc(self):
    """Test that an RPC request works."""
    body = json.dumps([{'jsonrpc': '2.0',
                        'id': 'gapiRpc',
                        'method': 'testservice.t2name',
                        'params': {'name': 'MyName', 'number': 23},
                        'apiVersion': 'v1'}])
    send_headers = {'content-type': 'application-rpc'}
    status, content, headers = self.fetch_url('default', 'POST',
                                              '/_ah/api/rpc',
                                              body, send_headers)
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertEqual([{'result': {'text': 'MyName 23'},
                       'id': 'gapiRpc'}], response_json)

  def test_echo_datetime_message(self):
    """Test sending and receiving a datetime."""
    body = json.dumps({'milliseconds': '5000', 'time_zone_offset': '60'})
    send_headers = {'content-type': 'application/json'}
    status, content, headers = self.fetch_url(
        'default', 'POST', '/_ah/api/test_service/v1/echo_datetime_message',
        body, send_headers)
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertEqual({'milliseconds': '5000', 'time_zone_offset': '60'},
                     response_json)

  def test_echo_datetime_field(self):
    """Test sending and receiving a message that includes a datetime."""
    body_json = {'datetime_value': '2013-03-13T15:29:37.883000+08:00'}
    body = json.dumps(body_json)
    send_headers = {'content-type': 'application/json'}
    status, content, headers = self.fetch_url(
        'default', 'POST', '/_ah/api/test_service/v1/echo_datetime_field',
        body, send_headers)
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertEqual(body_json, response_json)

  def test_increment_integers(self):
    """Test sending and receiving integer values."""
    body_json = {'var_int32': 100, 'var_int64': '1000',
                 'var_repeated_int64': ['10', '11', '900'],
                 'var_sint64': -555, 'var_uint64': 4320}
    body = json.dumps(body_json)
    send_headers = {'content-type': 'application/json'}
    status, content, headers = self.fetch_url(
        'default', 'POST', '/_ah/api/test_service/v1/increment_integers',
        body, send_headers)
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    expected_response = {'var_int32': 101, 'var_int64': '1001',
                         'var_repeated_int64': ['11', '12', '901'],
                         'var_sint64': '-554', 'var_uint64': '4321'}
    self.assertEqual(expected_response, response_json)

  def test_discovery_config(self):
    """Test that the discovery configuration looks right."""
    status, content, headers = self.fetch_url(
        'default', 'GET', '/_ah/api/discovery/v1/apis/test_service/v1/rest')
    self.assertEqual(200, status)
    self.assertEqual('application/json; charset=UTF-8', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertRegexpMatches(
        response_json['baseUrl'],
        r'^http://localhost(:\d+)?/_ah/api/test_service/v1/$')
    self.assertRegexpMatches(response_json['rootUrl'],
                             r'^http://localhost(:\d+)?/_ah/api/$')

  def test_multiclass_rest_get(self):
    """Test that a GET request to a second class in the REST API works."""
    status, content, headers = self.fetch_url(
        'default', 'GET', '/_ah/api/test_service/v1/extrapath/test')
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertEqual({'text': 'Extra test response'}, response_json)

  def test_multiclass_rpc(self):
    """Test that an RPC request to a second class in the API works."""
    body = json.dumps([{'jsonrpc': '2.0',
                        'id': 'gapiRpc',
                        'method': 'testservice.extraname.test',
                        'params': {},
                        'apiVersion': 'v1'}])
    send_headers = {'content-type': 'application-rpc'}
    status, content, headers = self.fetch_url('default', 'POST',
                                              '/_ah/api/rpc',
                                              body, send_headers)
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertEqual([{'result': {'text': 'Extra test response'},
                       'id': 'gapiRpc'}], response_json)

  def test_second_api_no_collision(self):
    """Test that a GET request to a second similar API works."""
    status, content, headers = self.fetch_url('default', 'GET',
                                              '/_ah/api/second_service/v1/test')
    self.assertEqual(200, status)
    self.assertEqual('application/json', headers['Content-Type'])

    response_json = json.loads(content)
    self.assertEqual({'text': 'Second response'}, response_json)


if __name__ == '__main__':
  googletest.main()
