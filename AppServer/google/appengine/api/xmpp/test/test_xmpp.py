#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)

import logging
import os
import re
import sys
import unittest


from flexmock import flexmock
import xmpp as xmpppy


xmpp_path = "{0}/../../../../..".format(os.path.dirname(__file__))
sys.path.append(xmpp_path)
from google.appengine.api.xmpp import xmpp_service_pb
from google.appengine.api.xmpp import xmpp_service_real


class TestXMPP(unittest.TestCase):


  def setUp(self):
    # and set up some instance variables to clean up our tests
    self.appid = "my-app"
    self.domain = "domain"
    self.uasecret = "boo"
    self.message = "the message"
    self.message_type = 'chat'
    self.my_jid = self.appid + '@' + self.domain

    # throw in a fake appid into the environment
    os.environ['APPNAME'] = self.appid


  def tearDown(self):
    # get rid of the fake appid we slipped into the environment
    os.environ['APPNAME'] = ''


  def test_send_xmpp_message(self):
    # mock out logging
    flexmock(logging)
    logging.should_receive('info').and_return()

    # set up a fake xmpp message
    fake_xmpp_message = flexmock(name='xmpp_message')

    # and slip in our mocked message
    flexmock(xmpppy)
    flexmock(xmpppy.protocol)
    xmpppy.protocol.should_receive('Message').with_args(frm=self.my_jid,
      to=re.compile('one|two'), body=self.message, typ=self.message_type) \
      .and_return(fake_xmpp_message)

    # set up a fake xmpp client
    fake_xmpp_client = flexmock(name='xmpp')
    fake_xmpp_client.should_receive('connect').with_args(secure=False) \
      .and_return()
    fake_xmpp_client.should_receive('auth').with_args(self.appid, self.uasecret,
      resource='').and_return()
    fake_xmpp_client.should_receive('send').with_args(
      fake_xmpp_message).and_return()

    # and slip in our mocked xmpp client in lieu of the real one
    xmpppy.should_receive('Client').with_args(self.domain, debug=[]) \
      .and_return(fake_xmpp_client)

    xmpp = xmpp_service_real.XmppService(log=logging.info, service_name='xmpp',
      domain=self.domain, uaserver='public-ip', uasecret=self.uasecret)

    # Set up a mocked XMPPRequest, that contains the message we want to send and
    # who we want to send it to.
    fake_request = flexmock(name='xmpp_message_request')
    fake_request.should_receive('jid_list').and_return(['one', 'two'])
    fake_request.should_receive('body').and_return(self.message)
    fake_request.should_receive('type').and_return(self.message_type)

    # _Dynamic_SendMessage will put a NO_ERROR message in the response if the
    # xmpp message was sent successfully, so just make sure the method returned
    # and that the mocked response has that status.
    fake_response = flexmock(name='xmpp_message_response')
    fake_response.should_receive('add_status') \
      .with_args(xmpp_service_pb.XmppMessageResponse.NO_ERROR).and_return()

    self.assertEquals(None, xmpp._Dynamic_SendMessage(fake_request,
      fake_response))


  def test_send_channel_message(self):
    # mock out logging
    flexmock(logging)
    logging.should_receive('info').and_return()

    # set up a fake xmpp message
    fake_xmpp_message = flexmock(name='xmpp_message')

    # and slip in our mocked message
    flexmock(xmpppy)
    flexmock(xmpppy.protocol)
    xmpppy.protocol.should_receive('Message').with_args(frm=self.my_jid,
      to=re.compile('channel.*key@domain'), body=self.message,
      typ=self.message_type).and_return(fake_xmpp_message)

    # set up a fake xmpp client
    fake_xmpp_client = flexmock(name='xmpp')
    fake_xmpp_client.should_receive('connect').with_args(secure=False) \
      .and_return()
    fake_xmpp_client.should_receive('auth').with_args(self.appid, self.uasecret,
      resource='').and_return()
    fake_xmpp_client.should_receive('send').with_args(
      fake_xmpp_message).and_return()

    # and slip in our mocked xmpp client in lieu of the real one
    xmpppy.should_receive('Client').with_args(self.domain, debug=[]) \
      .and_return(fake_xmpp_client)

    xmpp = xmpp_service_real.XmppService(log=logging.info, service_name='xmpp',
      domain=self.domain, uaserver='public-ip', uasecret=self.uasecret)

    # Set up a mocked XMPPRequest, that contains the message we want to send and
    # who we want to send it to.
    fake_request = flexmock(name='xmpp_message_request')
    fake_request.should_receive('message').and_return(self.message)
    fake_request.should_receive('application_key').and_return('key')

    # Unlike _Dynamic_SendMessage, the channel version doesn't set the NO_ERROR
    # status, and it doesn't actually return anything, so just make sure that
    # no exceptions were thrown.
    self.assertEquals(None, xmpp._Dynamic_SendChannelMessage(fake_request,
      None))


if __name__ == "__main__":
  unittest.main()
