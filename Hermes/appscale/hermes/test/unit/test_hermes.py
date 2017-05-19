#!/usr/bin/env python

import json
import socket
import sys
import tarfile
import unittest

import tornado.httpclient
from appscale.common import appscale_info
from appscale.common.ua_client import UAClient
from appscale.common.ua_client import UAException
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from flexmock import flexmock
from tornado.ioloop import IOLoop

from appscale import hermes
from appscale.hermes import deploy_sensor_app
from appscale.hermes import helper
from appscale.hermes import poll
from appscale.hermes import shutdown
from appscale.hermes import signal_handler

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.appcontroller_client import AppControllerClient


class TestHelper(unittest.TestCase):
  """ A set of test cases for Hermes top level functions. """

  DEPLOYMENT_ID = "deployment_id"

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

  def test_signal_handler(self):
    flexmock(IOLoop.instance()).should_receive('add_callback').and_return()\
      .times(1)
    signal_handler(15, None)

  def test_shutdown(self):
    flexmock(IOLoop.instance()).should_receive('stop').and_return().times(1)
    shutdown()

  def test_sensor_app_not_deployed_when_deployment_not_registered(self):
    # Test sensor app is not deployed when deployment is not registered.
    flexmock(helper).should_receive('get_deployment_id').and_return(None)
    flexmock(hermes).should_receive('create_appscale_user').and_return().\
      times(0)
    flexmock(hermes).should_receive('create_xmpp_user').and_return().\
      times(0)
    flexmock(AppControllerClient).should_receive('upload_app').and_return().\
      times(0)
    deploy_sensor_app()

    # Test sensor app is not deployed when it is already running.
    flexmock(helper).should_receive('get_deployment_id').and_return(
      self.DEPLOYMENT_ID)
    fake_options = flexmock(secret="fake_secret")
    hermes.options = fake_options
    flexmock(appscale_info).should_receive('get_db_master_ip').and_return()
    # Assume appscalesensor app already running.
    flexmock(UAClient).should_receive('is_app_enabled').and_return(True)
    flexmock(AppControllerClient).should_receive('upload_app').and_return(). \
      times(0)
    deploy_sensor_app()

    # Test sensor app is not deployed when the app is not currently running but
    # there was an error in creating a new user.
    flexmock(UAClient).should_receive('is_app_enabled').and_return(False)
    # Assume error while creating a new user.
    flexmock(UAClient).should_receive('does_user_exist').and_return(False)
    flexmock(UAClient).should_receive('commit_new_user').and_raise(UAException)
    flexmock(hermes).should_receive('create_appscale_user').and_return(). \
      times(1)
    flexmock(AppControllerClient).should_receive('upload_app').and_return(). \
      times(0)
    deploy_sensor_app()

    # Test sensor app is deployed after successfully creating a new user or
    # with an existing user.
    flexmock(UAClient).should_receive('commit_new_user')
    flexmock(tarfile).should_receive('open').and_return(tarfile.TarFile)
    flexmock(tarfile.TarFile).should_receive('add').and_return()
    flexmock(tarfile.TarFile).should_receive('close').and_return()
    flexmock(appscale_info).should_receive('get_appcontroller_client').and_return(
      AppControllerClient)
    flexmock(hermes).should_receive('create_appscale_user').and_return(True)
    flexmock(hermes).should_receive('create_xmpp_user').and_return(True)
    flexmock(AppControllerClient).should_receive('upload_app').and_return(). \
      times(1)
    deploy_sensor_app()

if __name__ == "__main__":
  unittest.main()
