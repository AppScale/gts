#!/usr/bin/python
# Programmer: Chris Bunch (chris@appscale.com)

# a script that receives xmpp messages for an app engine app
# and forwards them to the app, which must have a route
# exposed at /_ah/xmpp/message/chat/ to receive them

# usage is ./xmpp_receiver.py appname login_ip app-password
# TODO: refactor this to not leave the password in the clear 


# General-purpose Python libraries
import logging
import os
import re
import select
import sys
import time
import urllib


# Third-party libraries
import xmpp


class XMPPReceiver():


  @classmethod
  def xmpp_message(cls, con, event):
    logging.info("received a message!")
    logging.info(event)
    type = event.getType()
    logging.info("message type is %s" % (type))
    from_jid = event.getFrom().getStripped()
    params = {}
    params['from'] = from_jid
    params['to'] = my_jid
    params['body'] = event.getBody()
    encoded_params = urllib.urlencode(params)

    lb_url = "http://" + login_ip + "/apps/" + my_app_name + "/"

    cmd = "curl -L -i -k -X GET " + lb_url
    lb_result = os.popen(cmd).read()

    appserver_ip = re.findall('Location: http://(.*)', lb_result)[-1]
    xmpp_url = "http://" + appserver_ip + "/_ah/xmpp/message/chat/"
    urllib.urlopen(xmpp_url, encoded_params)


  @classmethod
  def xmpp_presence(cls, con, event):
    print str(event)
    logging.info("presence message!")
    logging.info(event)
    prs_type = event.getType()
    logging.info("presence type is %s" % (prs_type))
    who = event.getFrom()
    if prs_type == "subscribe":
      con.send(xmpp.Presence(to=who, typ='subscribed'))
      con.send(xmpp.Presence(to=who, typ='subscribe'))


  @classmethod
  def listen_for_messages(cls, appid, login_ip, app_password,
    messages_to_listen_for=-1):

    my_jid = appid + "@" + login_ip
    log_file = "/var/log/appscale/xmppreceiver-{0}.log".format(my_jid)
    #sys.stderr = open(log_file, 'a')
    logging.basicConfig(level=logging.INFO,
      format='%(asctime)s %(levelname)s %(message)s',
      filename=log_file,
      filemode='a')

    logging.info("Receiver script for XMPP user {0} started".format(my_jid))

    jid = xmpp.protocol.JID(my_jid)
    client = xmpp.Client(jid.getDomain(), debug=[])

    if not client.connect():
      logging.info("Could not connect")
      raise SystemExit("Could not connect to XMPP server at {0}" \
        .format(login_ip))

    if not client.auth(jid.getNode(), my_password, resource=jid.getResource()):
      logging.info("Could not authenticate")
      sys.exit(1)

    client.RegisterHandler('message', cls.xmpp_message)
    client.RegisterHandler('presence', cls.xmpp_presence)

    client.sendInitPresence(requestRoster=0)

    socketlist = {client.Connection._sock:'xmpp'}

    logging.info("About to begin processing requests")

    while True:
      (i , o, e) = select.select(socketlist.keys(),[],[],1)
      for each in i:
        if socketlist[each] == 'xmpp':
          client.Process(1)
        else:
          raise Exception("Unknown socket type: %s" % repr(socketlist[each]))


if __name__ == "__main__":
  XMPPReceiver.listen_for_messages(sys.argv[1], sys.argv[2], sys.argv[3])
