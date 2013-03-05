#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)


# General-purpose Python library imports
import logging
import os
import sys
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

    self.assertRaises(SystemExit, XMPPReceiver.listen_for_messages, self.appid,
      self.login_ip, self.password, messages_to_listen_for=1)


  def test_connect_to_xmpp_but_cannot_auth(self):
    # mock out the xmpp connection and have it connect, but not authenticate
    fake_client = flexmock(name='fake_client')
    fake_client.should_receive('connect').and_return(True)
    fake_client.should_receive('auth').with_args(self.appid, self.password,
      resource='').and_return(None)

    flexmock(xmpp)
    xmpp.should_receive('Client').with_args(self.login_ip, debug=[]) \
      .and_return(fake_client)

    self.assertRaises(SystemExit, XMPPReceiver.listen_for_messages, self.appid,
      self.login_ip, self.password, messages_to_listen_for=1)
