#!/usr/bin/env python

from flexmock import flexmock
import json
import os
import socket
import sys
import tornado.httpclient
from tornado.ioloop import IOLoop
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import helper
from hermes import poll
from hermes import send_all_stats
from hermes import shutdown
from hermes import signal_handler

class TestHelper(unittest.TestCase):
  """ A set of test cases for Hermes top level functions. """

  def test_poll(self):
    # Assume deployment is not registered.
    flexmock(helper).should_receive('get_deployment_id').and_return(None)
    poll()

    flexmock(helper).should_receive('get_deployment_id').\
      and_return('deployment_id')
    br_nodes = [
      {helper.NodeInfoTags.HOST: 'node1'},
      {helper.NodeInfoTags.HOST: 'node2'},
    ]
    flexmock(helper).should_receive('get_node_info').and_return(br_nodes)

    # Assume backup and recovery service is down.
    http_client = flexmock()
    http_client.should_receive('fetch').and_raise(socket.error)
    flexmock(tornado.httpclient).should_receive('HTTPClient').\
      and_return(http_client)
    poll()

    # Assume backup and recovery service is up.
    response = flexmock(body=json.dumps({'status': 'up'}))
    http_client.should_receive('fetch').and_return(response)
    flexmock(tornado.httpclient).should_receive('HTTPClient').\
      and_return(http_client)
    flexmock(json).should_receive('dumps').and_return('{}')
    flexmock(helper).should_receive('create_request').and_return()

    # Assume request to the AppScale Portal is successful.
    flexmock(helper).should_receive('urlfetch').\
      and_return({"success": True, "body": {}})
    flexmock(helper).should_receive('urlfetch_async').and_return()
    poll()

    # Assume request to the AppScale Portal is successful.
    flexmock(helper).should_receive('urlfetch').\
      and_return({"success": False, "reason": "error"})
    poll()

  def test_send_all_stats(self):
    # Assume deployment is not registered.
    flexmock(helper).should_receive('get_deployment_id').and_return(None)
    send_all_stats()

    flexmock(helper).should_receive('get_deployment_id').\
      and_return('deployment_id')

    fake_stats = {}
    flexmock(helper).should_receive('get_all_stats').and_return(fake_stats)
    flexmock(helper).should_receive('create_request').and_return()
    flexmock(helper).should_receive('urlfetch').\
      and_return({"success": True, "body": {}})
    send_all_stats()

  def test_signal_handler(self):
    flexmock(IOLoop.instance()).should_receive('add_callback').and_return()\
      .times(1)
    signal_handler(15, None)

  def test_shutdown(self):
    flexmock(IOLoop.instance()).should_receive('stop').and_return().times(1)
    shutdown()

if __name__ == "__main__":
  unittest.main()
