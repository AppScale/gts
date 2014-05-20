#!/usr/bin/python
# pylint: disable-msg=E1101

# a script that receives xmpp messages for an app engine app
# and forwards them to the app, which must have a route
# exposed at /_ah/xmpp/message/chat/ to receive them

# usage is ./xmpp_receiver.py appname login_ip app-password


# General-purpose Python libraries
import httplib
import logging
import os
import re
import select
import sys
import urllib


# Third-party libraries
# On AppScale VMs, we use Python 2.7 to run the XMPPReceiver, but because we
# install the xmpp library for the default Python (Python 2.6), we have to add
# it to our path.
try:
  import xmpp
except ImportError:
  PYTHON_PACKAGES = '/usr/local/lib/python2.7/dist-packages/'
  sys.path.append(PYTHON_PACKAGES + 'xmpppy-0.5.0rc1-py2.7.egg')
  import xmpp


class XMPPReceiver():
  """XMPPReceiver provides callers with a way to receive XMPP messages on
  behalf of Google App Engine applications. The receiver will POST any
  received message to an App Server that runs the app, and will respond
  to presence notifications that users may send to it.
  """


  # The headers necessary for posting XMPP messages to App Engine apps.
  HEADERS = {
    'Content-Type' : 'application/x-www-form-urlencoded'
  }


  def __init__(self, appid, login_ip, app_password):
    """Creates a new XMPPReceiver, which will listen for XMPP messages for
    an App Engine app.

    Args:
      appid: A str representing the application ID that this XMPPReceiver
        should poll on behalf of.
      login_ip: A str representing the IP address or FQDN that runs the
        full proxy nginx service, sitting in front of the app we'll be
        posting messages to.
      app_password: A str representing the password associated with the
        XMPP user account for the Google App Engine app that the receiver
        will log in on behalf of.
    """
    self.appid = appid
    self.login_ip = login_ip
    self.app_password = app_password

    with open("/etc/appscale/port-{0}.txt".format(self.appid)) as file_handle:
      self.app_port = int(file_handle.read().strip())

    self.my_jid = self.appid + "@" + self.login_ip
    log_file = "/var/log/appscale/xmppreceiver-{0}.log".format(self.my_jid)
    sys.stderr = open(log_file, 'a')
    logging.basicConfig(level=logging.INFO,
      format='%(asctime)s %(levelname)s %(message)s',
      filename=log_file,
      filemode='a')
    logging.info("Started receiver script for {0}".format(self.my_jid))


  def xmpp_message(self, _, event):
    """Responds to the receipt of an XMPP message, by finding an App Server that
    hosts the given application and POSTing the message's payload to it.

    Args:
      _: The connection that the message was received on (not used).
      event: The actual message that was received.
    """
    logging.info("received a message from {0}, with body {1}" \
      .format(event.getFrom().getStripped(), event.getBody()))
    logging.info("message type is {0}".format(event.getType))
    from_jid = event.getFrom().getStripped()
    params = {}
    params['from'] = from_jid
    params['to'] = self.my_jid
    params['body'] = event.getBody()
    encoded_params = urllib.urlencode(params)

    try:
      logging.debug("Attempting to open connection to {0}:{1}".format(
        self.login_ip, self.app_port))
      connection = httplib.HTTPConnection(self.login_ip, self.app_port)
      connection.request('POST', '/_ah/xmpp/message/chat/', encoded_params,
        self.HEADERS)
      response = connection.getresponse()
      logging.info("POST XMPP message returned status of {0}".format(
        response.status))
      connection.close()
    except Exception as e:
      logging.exception(e)


  def xmpp_presence(self, conn, event):
    """Responds to the receipt of a presence message, by telling the sender
    that we are subscribing to their presence and that they should do the same.

    Args:
      conn: The connection that the message was received on.
      event: The actual message that was received.
    """
    logging.info("received a presence from {0}, with payload {1}" \
      .format(event.getFrom().getStripped(), event.getPayload()))
    prs_type = event.getType()
    logging.info("presence type is {0}".format(prs_type))
    who = event.getFrom()
    if prs_type == "subscribe":
      conn.send(xmpp.Presence(to=who, typ='subscribed'))
      conn.send(xmpp.Presence(to=who, typ='subscribe'))


  def listen_for_messages(self, messages_to_listen_for=-1):
    """Polls the XMPP server for messages, responding to any that are seen.

    Args:
      messages_to_listen_for: An int that represents how many messages we
        should listen for. If set to the default value (-1), then we listen
        for an infinite number of messages.
    Returns:
      An int that indicates how many messages were processed.
    """
    jid = xmpp.protocol.JID(self.my_jid)
    client = xmpp.Client(jid.getDomain(), debug=[])

    if not client.connect():
      logging.info("Could not connect")
      raise SystemExit("Could not connect to XMPP server at {0}" \
        .format(self.login_ip))

    if not client.auth(jid.getNode(), self.app_password,
      resource=jid.getResource()):
      logging.info("Could not authenticate with username {0}, password {1}" \
        .format(jid.getNode(), self.app_password))
      raise SystemExit("Could not authenticate to XMPP server at {0}" \
        .format(self.login_ip))

    client.RegisterHandler('message', self.xmpp_message)
    client.RegisterHandler('presence', self.xmpp_presence)

    client.sendInitPresence(requestRoster=0)

    socketlist = {client.Connection._sock:'xmpp'}

    logging.info("About to begin processing requests")

    messages_processed = 0
    while messages_processed != messages_to_listen_for:
      (input_data, _, __) = select.select(socketlist.keys(), [], [], 1)
      for _ in input_data:
        try:
          client.Process(1)
          messages_processed += 1
        except xmpp.protocol.Conflict:
          logging.info("Lost connection after processing {0} messages" \
            .format(messages_processed))
          return messages_processed

    return messages_processed


if __name__ == "__main__":
  RECEIVER = XMPPReceiver(sys.argv[1], sys.argv[2], sys.argv[3])
  while True:
    RECEIVER.listen_for_messages()
