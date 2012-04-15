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




"""Channel API.

This module allows App Engine apps to push messages to a client.

Functions defined in this module:
  create_channel: Creates a channel to send messages to.
  send_message: Send a message to any clients listening on the given channel.
"""






import os

from google.appengine.api import api_base_pb
from google.appengine.api import apiproxy_stub_map
from google.appengine.api.channel import channel_service_pb
from google.appengine.runtime import apiproxy_errors







MAXIMUM_CLIENT_ID_LENGTH = 64






MAXIMUM_MESSAGE_LENGTH = 32767


class Error(Exception):
  """Base error class for this module."""


class InvalidChannelClientIdError(Error):
  """Error that indicates a bad client id."""


class InvalidMessageError(Error):
  """Error that indicates a message is malformed."""


def _ToChannelError(error):
  """Translate an application error to a channel Error, if possible.

  Args:
    error: An ApplicationError to translate.

  Returns:
    The appropriate channel service error, if a match is found, or the original
    ApplicationError.
  """
  error_map = {
      channel_service_pb.ChannelServiceError.INVALID_CHANNEL_KEY:
      InvalidChannelClientIdError,
      channel_service_pb.ChannelServiceError.BAD_MESSAGE:
      InvalidMessageError,
      }

  if error.application_error in error_map:
    return error_map[error.application_error](error.error_detail)
  else:
    return error


def _GetService():
  """Gets the service name to use, based on if we're on the dev server."""
  if os.environ.get('SERVER_SOFTWARE', '').startswith('Devel'):
    return 'channel'
  else:
    return 'xmpp'


def _ValidateClientId(client_id):
  """Valides a client id.

  Args:
    client_id: The client id provided by the application.

  Returns:
    If the client id is of type str, returns the original client id.
    If the client id is of type unicode, returns the id encoded to utf-8.

  Raises:
    InvalidChannelClientIdError: if client id is not an instance of str or
        unicode, or if the (utf-8 encoded) string is longer than 64 characters.
  """
  if isinstance(client_id, unicode):
    client_id = client_id.encode('utf-8')
  elif not isinstance(client_id, str):
    raise InvalidChannelClientIdError

  if len(client_id) > MAXIMUM_CLIENT_ID_LENGTH:
    raise InvalidChannelClientIdError

  return client_id



def create_channel(client_id):
  """Create a channel.

  Args:
    client_id: A string to identify this channel on the server side.

  Returns:
    A token that the client can use to connect to the channel.

  Raises:
    InvalidChannelClientIdError: if clientid is not an instance of str or
        unicode, or if the (utf-8 encoded) string is longer than 64 characters.
    Other errors returned by _ToChannelError
  """


  client_id = _ValidateClientId(client_id)

  request = channel_service_pb.CreateChannelRequest()
  response = channel_service_pb.CreateChannelResponse()

  request.set_application_key(client_id)

  try:
    apiproxy_stub_map.MakeSyncCall(_GetService(),
                                   'CreateChannel',
                                   request,
                                   response)
  except apiproxy_errors.ApplicationError, e:
    raise _ToChannelError(e)

  return response.client_id()



def send_message(client_id, message):
  """Send a message to a channel.

  Args:
    client_id: The client id passed to create_channel.
    message: A string representing the message to send.

  Raises:
    InvalidChannelClientIdError: if client_id is not an instance of str or
        unicode, or if the (utf-8 encoded) string is longer than 64 characters.
    InvalidMessageError: if the message isn't a string or is too long.
    Errors returned by _ToChannelError
  """

  client_id = _ValidateClientId(client_id)

  if isinstance(message, unicode):
    message = message.encode('utf-8')
  elif not isinstance(message, str):
    raise InvalidMessageError

  if len(message) > MAXIMUM_MESSAGE_LENGTH:
    raise InvalidMessageError

  request = channel_service_pb.SendMessageRequest()
  response = api_base_pb.VoidProto()

  request.set_application_key(client_id)
  request.set_message(message)

  try:
    apiproxy_stub_map.MakeSyncCall(_GetService(),
                                   'SendChannelMessage',
                                   request,
                                   response)
  except apiproxy_errors.ApplicationError, e:
    raise _ToChannelError(e)
