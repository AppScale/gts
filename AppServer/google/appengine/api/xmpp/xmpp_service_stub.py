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




"""Stub version of the XMPP API, writes messages to logs."""









import logging
import os

from google.appengine.api import apiproxy_stub
from google.appengine.api import xmpp
from google.appengine.api.xmpp import xmpp_service_pb


class XmppServiceStub(apiproxy_stub.APIProxyStub):
  """Python only xmpp service stub.

  This stub does not use an XMPP network. It prints messages to the console
  instead of sending any stanzas.
  """

  def __init__(self, log=logging.info, service_name='xmpp'):
    """Initializer.

    Args:
      log: A logger, used for dependency injection.
      service_name: Service name expected for all calls.
    """
    super(XmppServiceStub, self).__init__(service_name)
    self.log = log

  def _Dynamic_GetPresence(self, request, response):
    """Implementation of XmppService::GetPresence.

    Returns online if the first character of the JID comes before 'm' in the
    alphabet, otherwise returns offline.

    Args:
      request: A PresenceRequest.
      response: A PresenceResponse.
    """
    jid = request.jid()
    self._GetFrom(request.from_jid())
    if jid[0] < 'm':
      response.set_is_available(True)
    else:
      response.set_is_available(False)

  def _Dynamic_SendMessage(self, request, response):
    """Implementation of XmppService::SendMessage.

    Args:
      request: An XmppMessageRequest.
      response: An XmppMessageResponse .
    """
    from_jid = self._GetFrom(request.from_jid())
    self.log('Sending an XMPP Message:')
    self.log('    From:')
    self.log('       ' + from_jid)
    self.log('    Body:')
    self.log('       ' + request.body())
    self.log('    Type:')
    self.log('       ' + request.type())
    self.log('    Raw Xml:')
    self.log('       ' + str(request.raw_xml()))
    self.log('    To JIDs:')
    for jid in request.jid_list():
      self.log('       ' + jid)

    for jid in request.jid_list():
      response.add_status(xmpp_service_pb.XmppMessageResponse.NO_ERROR)

  def _Dynamic_SendInvite(self, request, response):
    """Implementation of XmppService::SendInvite.

    Args:
      request: An XmppInviteRequest.
      response: An XmppInviteResponse .
    """
    from_jid = self._GetFrom(request.from_jid())
    self.log('Sending an XMPP Invite:')
    self.log('    From:')
    self.log('       ' + from_jid)
    self.log('    To: ' + request.jid())

  def _Dynamic_SendPresence(self, request, response):
    """Implementation of XmppService::SendPresence.

    Args:
      request: An XmppSendPresenceRequest.
      response: An XmppSendPresenceResponse .
    """
    from_jid = self._GetFrom(request.from_jid())
    self.log('Sending an XMPP Presence:')
    self.log('    From:')
    self.log('       ' + from_jid)
    self.log('    To: ' + request.jid())
    if request.type():
      self.log('    Type: ' + request.type())
    if request.show():
      self.log('    Show: ' + request.show())
    if request.status():
      self.log('    Status: ' + request.status())

  def _GetFrom(self, requested):
    """Validates that the from JID is valid.

    Args:
      requested: The requested from JID.

    Returns:
      string, The from JID.

    Raises:
      xmpp.InvalidJidError if the requested JID is invalid.
    """

    appid = os.environ.get('APPLICATION_ID', '')
    if requested == None or requested == '':
      return appid + '@appspot.com/bot'


    node, domain, resource = ('', '', '')
    at = requested.find('@')
    if at == -1:
      self.log('Invalid From JID: No \'@\' character found. JID: %s', requested)
      raise xmpp.InvalidJidError()

    node = requested[:at]
    rest = requested[at+1:]

    if rest.find('@') > -1:
      self.log('Invalid From JID: Second \'@\' character found. JID: %s',
               requested)
      raise xmpp.InvalidJidError()

    slash = rest.find('/')
    if slash == -1:
      domain = rest
      resource = 'bot'
    else:
      domain = rest[:slash]
      resource = rest[slash+1:]

    if resource.find('/') > -1:
      self.log('Invalid From JID: Second \'/\' character found. JID: %s',
               requested)
      raise xmpp.InvalidJidError()

    if domain == 'appspot.com' and node == appid:
      return node + '@' + domain + '/' + resource
    elif domain == appid + '.appspotchat.com':
      return node + '@' + domain + '/' + resource

    self.log('Invalid From JID: Must be appid@appspot.com[/resource] or '
             'node@appid.appspotchat.com[/resource]. JID: %s', requested)
    raise xmpp.InvalidJidError()
