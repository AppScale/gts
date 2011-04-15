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




"""Stub version of the Channel API, queues messages and writes them to a log."""








import logging
import random

from google.appengine.api import apiproxy_stub
from google.appengine.api.channel import channel_service_pb
from google.appengine.runtime import apiproxy_errors


class ChannelServiceStub(apiproxy_stub.APIProxyStub):
  """Python only channel service stub.

  This stub does not use a browser channel to push messages to a client.
  Instead it queues messages internally.
  """

  def __init__(self, log=logging.debug, service_name='channel'):
    """Initializer.

    Args:
      log: A logger, used for dependency injection.
      service_name: Service name expected for all calls.
    """
    apiproxy_stub.APIProxyStub.__init__(self, service_name)
    self._log = log
    self._channel_messages = {}


  def _Dynamic_CreateChannel(self, request, response):
    """Implementation of channel.get_channel.

    Args:
      request: A ChannelServiceRequest.
      response: A ChannelServiceResponse
    """
    application_key = request.application_key()
    if not application_key:
      raise apiproxy_errors.ApplicationError(
          channel_service_pb.ChannelServiceError.INVALID_CHANNEL_KEY)

    client_id = 'channel-%s-%s' % (random.randint(0, 2 ** 32),
                                   application_key)
    self._log('Creating channel id %s with application key %s',
              client_id, request.application_key())

    if application_key not in self._channel_messages:
      self._channel_messages[application_key] = []

    response.set_client_id(client_id)


  def _Dynamic_SendChannelMessage(self, request, response):
    """Implementation of channel.send_message.

    Queues a message to be retrieved by the client when it polls.

    Args:
      request: A SendMessageRequest.
      response: A VoidProto.
    """

    application_key = request.application_key()
    self._log('Sending a message (%s) to channel with key (%s)',
              request.message(), application_key)

    if not request.message():
      raise apiproxy_errors.ApplicationError(
          channel_service_pb.ChannelServiceError.BAD_MESSAGE)

    if application_key not in self._channel_messages:
      raise apiproxy_errors.ApplicationError(
          channel_service_pb.ChannelServiceError.INVALID_CHANNEL_KEY)

    self._channel_messages[application_key].append(request.message())

  def app_key_from_client_id(self, client_id):
    """Returns the app key from a given client id.

    Args:
       client_id: String representing a client id, returned by CreateChannel.

    Returns:
       String representing the application key used to create this client_id,
       or None if this client_id is incorrectly formed and doesn't map to an
       application key.
    """
    pieces = client_id.split('-', 2)
    if len(pieces) == 3:
      return pieces[2]
    else:
      return None

  def get_channel_messages(self, client_id):
    """Returns the pending messages for a given channel.

    Args:
      client_id: String representing the channel. Note that this is the id
        returned by CreateChannel, not the application key.

    Returns:
      List of messages, or None if the channel doesn't exist. The messages are
      strings.
    """
    self._log('Received request for messages for channel: ' + client_id)
    app_key = self.app_key_from_client_id(client_id)
    if app_key in self._channel_messages:
      return self._channel_messages[app_key]

    return None

  def has_channel_messages(self, client_id):
    """Checks to see if the given channel has any pending messages.

    Args:
      client_id: String representing the channel. Note that this is the id
        returned by CreateChannel, not the application key.

    Returns:
      True if the channel exists and has pending messages.
    """
    app_key = self.app_key_from_client_id(client_id)
    has_messages = (app_key in self._channel_messages and
                    bool(self._channel_messages[app_key]))
    self._log('Checking for messages on channel (%s) (%s)',
              client_id, has_messages)
    return has_messages

  def pop_first_message(self, client_id):
    """Returns and clears the first message from the message queue.

    Args:
      client_id: String representing the channel. Note that this is the id
        returned by CreateChannel, not the application key.

    Returns:
      The first message in the queue, or None if no messages.
    """
    if self.has_channel_messages(client_id):
      app_key = self.app_key_from_client_id(client_id)
      self._log('Popping first message of queue for channel (%s)', client_id)
      return self._channel_messages[app_key].pop(0)

    return None

  def clear_channel_messages(self, client_id):
    """Clears all messages from the channel.

    Args:
      client_id: String representing the channel. Note that this is the id
        returned by CreateChannel, not the application key.
    """
    app_key = self.app_key_from_client_id(client_id)
    self._log('Clearing messages on channel (' + client_id + ')')
    if app_key in self._channel_messages:
      self._channel_messages[app_key] = []
