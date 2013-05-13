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

""" Implementation of the XMPP API, using the xmpppy library powered by 
    ejabberd.
"""

import hashlib
import logging
import os
import SOAPpy
import urllib
import xmpp as xmpppy

from google.appengine.api import xmpp
from google.appengine.api.xmpp import xmpp_service_pb
from google.appengine.api import apiproxy_stub
from google.appengine.api.channel import channel_service_pb
from google.appengine.runtime import apiproxy_errors


class XmppService(apiproxy_stub.APIProxyStub):
  """Python only xmpp service stub. Ejabberd as the backend. Channel API
     support is also in this file.
  """

  def __init__(self, 
              log=logging.info, 
              service_name='xmpp', 
              domain="localhost", 
              uaserver="localhost",
              uasecret=""):
    """Initializer.

    Args:
      log: A logger, used for dependency injection.
      service_name: Service name expected for all calls.
    """
    super(XmppService, self).__init__(service_name)
    self.log = log
    self.xmpp_domain = domain
    self.uaserver = "https://" + uaserver
    self.login = "https://localhost:17443"

    if not uasecret:
      secret_file = open("/etc/appscale/secret.key", 'r')
      uasecret = secret_file.read().rstrip('\n')
      secret_file.close()

    self.uasecret = uasecret

  def _Dynamic_GetPresence(self, request, response):
    """Implementation of XmppService::GetPresence.

    Reads the file containing the list of online users to see
    if the given user is online or not.

    Args:
      request: A PresenceRequest.
      response: A PresenceResponse.
    """
    jid = request.jid()
    server = SOAPpy.SOAPProxy(self.login)
    online_users = server.get_online_users_list(self.uasecret)
    user_is_online = False
    try:
      online_users.index(jid)
      user_is_online = True
    except ValueError:
      pass
    response.set_is_available(user_is_online)

  def _Dynamic_SendMessage(self, request, response):
    """Implementation of XmppService::SendMessage.

    Args:
      request: An XmppMessageRequest.
      response: An XmppMessageResponse .
    """
    for jid in request.jid_list():
      self.log('       ' + jid)

    appname = os.environ['APPNAME']

    xmpp_username = appname + "@" + self.xmpp_domain

    my_jid = xmpppy.protocol.JID(xmpp_username)
    client = xmpppy.Client(my_jid.getDomain(), debug=[])
    client.connect(secure=False)
    client.auth(my_jid.getNode(), self.uasecret, resource=my_jid.getResource())

    for jid in request.jid_list():
      message = xmpppy.protocol.Message(frm=xmpp_username, to=jid, 
                                        body=request.body(), typ=request.type())
      client.send(message)
      response.add_status(xmpp_service_pb.XmppMessageResponse.NO_ERROR)

  def _Dynamic_SendInvite(self, request, response):
    """Implementation of XmppService::SendInvite.

    Args:
      request: An XmppInviteRequest.
      response: An XmppInviteResponse .
    """
    pass

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
      return appid + '@' + self.xmpp_domain + '/bot'

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

    if domain == self.xmpp_domain and node == appid:
      return node + '@' + domain + '/' + resource

    self.log('Invalid From JID: Must be appid@[IP address or ' +\
             'FQDN][/resource]. JID: %s', requested)
    raise xmpp.InvalidJidError()

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
    application_key = urllib.quote(application_key)
    if '@' in application_key:
      raise apiproxy_errors.ApplicationError(
          channel_service_pb.ChannelServiceError.INVALID_CHANNEL_KEY)
  
    appname = os.environ['APPNAME']
    unique_app_id = hashlib.sha1(appname + application_key).hexdigest()
    client_id = 'channel~%s~%s@%s' % (unique_app_id,
                                      application_key,
                                      self.xmpp_domain)

    server = SOAPpy.SOAPProxy(self.uaserver) 
    password = application_key
    encry_pw = hashlib.sha1(client_id+password)
    ret = server.commit_new_user(client_id, 
                                 encry_pw.hexdigest(),
                                 "channel", 
                                 self.uasecret)
    if ret == "Error: user already exists":
      # We are allowing reuse of ids
      # TODO reset the timestamp of the xmpp user
      pass
    elif ret != "true":
      self.log("Committing a new channel user error: %s" % ret) 
      raise apiproxy_errors.ApplicationError(
          channel_service_pb.ChannelServiceError.INTERNAL_ERROR)
    
    response.set_token(client_id)

  def _Dynamic_SendChannelMessage(self, request, response):
    """Implementation of channel.send_message.

    Queues a message to be retrieved by the client when it polls.

    Args:
      request: A SendMessageRequest.
      response: A VoidProto.
    """
    application_key = urllib.quote(request.application_key())

    if not request.message():
      raise apiproxy_errors.ApplicationError(
          channel_service_pb.ChannelServiceError.BAD_MESSAGE)
    
    appname = os.environ['APPNAME']
    unique_app_id = hashlib.sha1(appname + application_key).hexdigest()
    jid = 'channel~%s~%s@%s' % (unique_app_id, 
                               application_key,
                               self.xmpp_domain)
 
    xmpp_username = appname + "@" + self.xmpp_domain
    my_jid = xmpppy.protocol.JID(xmpp_username)
    client = xmpppy.Client(my_jid.getDomain(), debug=[])
    client.connect(secure=False)
    client.auth(my_jid.getNode(), self.uasecret, resource=my_jid.getResource())

    message = xmpppy.protocol.Message(frm=xmpp_username, to=jid, 
                                      body=request.message(), typ="chat")
    client.send(message)


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
      atindex = pieces[2].rfind('@')      
      token = pieces[2]
      appkey = token[0:atindex]
      return appkey
    else:
      return None

