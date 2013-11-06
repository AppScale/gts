#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)


# General-purpose Python library imports
import httplib
import logging
import os
import re
import select
import sys
import types
import unittest


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
    self.app_port = 1234
    self.password = 'bazpassword'
    self.jid = self.appid + '@' + self.login_ip

    # mock out all calls to the logging library
    flexmock(logging)
    logging.should_receive('basicConfig').and_return()
    logging.should_receive('info').with_args(str).and_return()

    # and mock out all calls to try to make stderr write to the logger
    fake_open = flexmock(sys.modules['__builtin__'])
    fake_open.should_call('open')  # set the fall-through
    fake_open.should_receive('open').with_args(
      '/var/log/appscale/xmppreceiver-bazapp@publicip1.log', 'a')

    # finally, pretend that the file on the local filesystem that contains the
    # port number exists
    fake_port_file = flexmock(name="fake_port_file")
    fake_port_file.should_receive('read').and_return(str(self.app_port))
    fake_open.should_receive('open').with_args('/etc/appscale/port-{0}.txt' \
      .format(self.appid)).and_return(fake_port_file)


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

    # and mock out the httplib call
    fake_response = flexmock(name='fake_response', status=200)

    fake_http_connection = flexmock(name='fake_http_connection')
    fake_http_connection.should_receive('request').with_args('POST',
      '/_ah/xmpp/message/chat/', str, XMPPReceiver.HEADERS)
    fake_http_connection.should_receive('getresponse').and_return(fake_response)
    fake_http_connection.should_receive('close').and_return()

    flexmock(httplib)
    httplib.should_receive('HTTPConnection').with_args('publicip1', 1234) \
      .and_return(fake_http_connection)

    receiver = XMPPReceiver(self.appid, self.login_ip, self.password)
    receiver.xmpp_message(fake_conn, fake_event)


  def test_presence_message(self):
    # since we mock out the xmpp client in previous tests, we can't rely on it
    # to call the xmpp_presence method. therefore, let's test it separately.
    fake_subscribed_presence = flexmock(name='subscribed')
    fake_subscribe_presence = flexmock(name='subscribe')

    fake_from = flexmock(name='fake_from')
    fake_from.should_receive('getStripped').and_return('me@public1')

    flexmock(xmpp)
    xmpp.should_receive('Presence').with_args(to=fake_from,
      typ='subscribed').and_return(fake_subscribed_presence)
    xmpp.should_receive('Presence').with_args(to=fake_from,
      typ='subscribe').and_return(fake_subscribe_presence)

    fake_conn = flexmock(name='fake_conn')
    fake_conn.should_receive('send').with_args(fake_subscribed_presence)
    fake_conn.should_receive('send').with_args(fake_subscribe_presence)

    fake_event = flexmock(name='fake_event')
    fake_event.should_receive('getFrom').and_return(fake_from)
    fake_event.should_receive('getPayload').and_return('doesnt matter')
    fake_event.should_receive('getType').and_return('subscribe')

    receiver = XMPPReceiver(self.appid, self.login_ip, self.password)
    receiver.xmpp_presence(fake_conn, fake_event)
