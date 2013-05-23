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
"""Test service for regression testing of Cloud Endpoints support."""

import logging

from protorpc import message_types
from protorpc import messages
from protorpc import remote

from google.appengine.ext import endpoints


class TestRequest(messages.Message):
  """Simple ProtoRPC request, for testing."""
  name = messages.StringField(1)
  number = messages.IntegerField(2)


class TestResponse(messages.Message):
  """Simple ProtoRPC response with a text field."""
  text = messages.StringField(1)


class TestDateTime(messages.Message):
  """Simple ProtoRPC request/response with a datetime."""
  datetime_value = message_types.DateTimeField(1)


@endpoints.api(name='test_service', version='v1')
class TestService(remote.Service):
  """ProtoRPC test class for Cloud Endpoints."""

  @endpoints.method(message_types.VoidMessage, TestResponse,
                    http_method='GET', name='test', path='test',
                    scopes=[])
  def test(self, unused_request):
    return TestResponse(text='Test response')

  @endpoints.method(TestRequest, TestResponse,
                    http_method='POST', name='t2name', path='t2path',
                    scopes=[])
  def getenviron(self, request):
    return TestResponse(text='%s %d' % (request.name, request.number))

  @endpoints.method(message_types.DateTimeMessage,
                    message_types.DateTimeMessage,
                    http_method='POST', name='echodtmsg',
                    path='echo_datetime_message',
                    scopes=[])
  def echo_datetime_message(self, request):
    return request

  @endpoints.method(TestDateTime, TestDateTime,
                    http_method='POST', name='echodtfield',
                    path='echo_datetime_field',
                    scopes=[])
  def echo_datetime_field(self, request):
    # Make sure we can access the fields of the datetime object.
    logging.info('Year %d, Month %d', request.datetime_value.year,
                 request.datetime_value.month)
    return request


application = endpoints.api_server([TestService])
