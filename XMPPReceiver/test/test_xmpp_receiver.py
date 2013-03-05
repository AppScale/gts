#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)


# General-purpose Python library imports
import logging
import os
import re
import select
import sys
import types
import unittest
import urllib


# Third party libraries
from flexmock import flexmock
import xmpp


# AppScale import, the library that we're testing here
lib = os.path.dirname(__file__) + os.sep + ".." + os.sep
sys.path.append(lib)
from xmpp_receiver import XMPPReceiver


class TestXMPPReceiver(unittest.TestCase):


  def setUp(self):
    # throw up some instance vars that the tests can use
    self.appid = 'bazapp'
    self.login_ip = 'publicip1'
    self.password = 'bazpassword'
    self.jid = self.appid + '@' + self.login_ip

    # mock out all calls to the logging library
    flexmock(logging)
    logging.should_receive('basicConfig').and_return()
    logging.should_receive('info').with_args(str).and_return()


  def test_connect_to_xmpp_but_it_is_down(self):
    # mock out the xmpp connection and have it not connect
    fake_client = flexmock(name='fake_client')
    fake_client.should_receive('connect').and_return(None)

    flexmock(xmpp)
    xmpp.should_receive('Client').with_args(self.login_ip, debug=[]) \
      .and_return(fake_client)

    receiver = XMPPReceiver(self.appid, self.login_ip, self.password)
    self.assertRaises(SystemExit, receiver.listen_for_messages, messages_to_listen_for=1)


  def test_connect_to_xmpp_but_cannot_auth(self):
    # mock out the xmpp connection and have it connect, but not authenticate
    fake_client = flexmock(name='fake_client')
    fake_client.should_receive('connect').and_return(True)
    fake_client.should_receive('auth').with_args(self.appid, self.password,
      resource='').and_return(None)

    flexmock(xmpp)
    xmpp.should_receive('Client').with_args(self.login_ip, debug=[]) \
      .and_return(fake_client)

    receiver = XMPPReceiver(self.appid, self.login_ip, self.password)
    self.assertRaises(SystemExit, receiver.listen_for_messages,
      messages_to_listen_for=1)

  
  def test_receive_one_message(self):
    # mock out the xmpp connection and have it connect and authenticate
    fake_connection = flexmock(name='fake_connection', _sock="the socket")
    fake_client = flexmock(name='fake_client', Connection=fake_connection)
    fake_client.should_receive('connect').and_return(True)
    fake_client.should_receive('auth').with_args(self.appid, self.password,
      resource='').and_return(True)

    # also add in mocks for when messages are received or when we see
    # presence notifications
    fake_client.should_receive('RegisterHandler').and_return()

    # add in a mock for when we send our presence message to the XMPP server
    fake_client.should_receive('sendInitPresence').and_return()

    # and make sure that we only process one message
    fake_client.should_receive('Process').with_args(1).once()

    flexmock(xmpp)
    xmpp.should_receive('Client').with_args(self.login_ip, debug=[]) \
      .and_return(fake_client)

    # finally, mock out 'select', and have it put in a message
    flexmock(select)
    message = {"the socket" : "xmpp"}
    select.should_receive('select').with_args(['the socket'], [], [], 1) \
      .and_return(message, None, None)

    receiver = XMPPReceiver(self.appid, self.login_ip, self.password)
    actual_messages_sent = receiver.listen_for_messages(
      messages_to_listen_for=1)
    self.assertEquals(1, actual_messages_sent)


  def test_message_results_in_post(self):
    # since we mock out the xmpp client in previous tests, we can't rely on it
    # to call the xmpp_message method. therefore, let's test it separately.
    fake_conn = flexmock(name='fake_conn')

    fake_from = flexmock(name='fake_from')
    fake_from.should_receive('getStripped').and_return('me@public1')

    fake_event = flexmock(name='fake_event')
    fake_event.should_receive('getFrom').and_return(fake_from)
    fake_event.should_receive('getBody').and_return('doesnt matter')
    fake_event.should_receive('getType').and_return('chat')

    # mock out the curl call to the AppLoadBalancer, and slip in our own
    # ip to send the XMPP message to
    fake_curl = flexmock(name='curl_result')
    fake_curl.should_receive('read').and_return('Location: http://public2')

    flexmock(os)
    os.should_receive('popen').with_args(re.compile('curl')).and_return(fake_curl)

    # and finally mock out the urllib call
    flexmock(urllib)
    urllib.should_receive('urlopen').with_args(
      "http://public2/_ah/xmpp/message/chat/", str).and_return()

    receiver = XMPPReceiver(self.appid, self.login_ip, self.password)
    receiver.xmpp_message(fake_conn, fake_event)
