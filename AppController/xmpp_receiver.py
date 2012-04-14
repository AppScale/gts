#!/usr/bin/python

# Programmer: Chris Bunch
# a script that receives xmpp messages for an app engine app
# and forwards them to the app, which must have a route
# exposed at /_ah/xmpp/message/chat/ to receive them

# usage is ./xmpp_receiver.py appname login_ip app-password
# TODO: refactor this to not leave the password in the clear 

import sys, os, xmpp, time, re, select, urllib
import logging

my_app_name = sys.argv[1]
login_ip = sys.argv[2]
my_jid = my_app_name + "@" + login_ip
my_password = sys.argv[3]

log_file = "/var/log/ejabberd/receiver-" + my_jid + ".log"
sys.stderr = open(log_file, 'a')
logging.basicConfig(level=logging.INFO,
  format='%(asctime)s %(levelname)s %(message)s',
  filename=log_file,
  filemode='a')

logging.info("receiver script for %s started, waiting for incoming messages" % (my_jid))

def xmpp_message(con, event):
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

  appserver_ip = re.findall('(\d+\.\d+\.\d+\.\d+:\d+)', lb_result)[-1]
  xmpp_url = "http://" + appserver_ip + "/_ah/xmpp/message/chat/"
  urllib.urlopen(xmpp_url, encoded_params)

def xmpp_presence(con, event):
  print str(event)
  logging.info("presence message!")
  logging.info(event)
  prs_type = event.getType()
  logging.info("presence type is %s" % (prs_type))
  who = event.getFrom()
  if prs_type == "subscribe":
    con.send(xmpp.Presence(to=who, typ='subscribed'))
    con.send(xmpp.Presence(to=who, typ='subscribe'))
  
jid = xmpp.protocol.JID(my_jid)
client = xmpp.Client(jid.getDomain(), debug=[])

if not client.connect():
  print "Could not connect"
  logging.info("Could not connect")
  exit(1)

if not client.auth(jid.getNode(), my_password, resource=jid.getResource()):
  print "Could not authenticate"
  logging.info("Could not authenticate")
  exit(1)

client.RegisterHandler('message', xmpp_message)
client.RegisterHandler('presence', xmpp_presence)

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

