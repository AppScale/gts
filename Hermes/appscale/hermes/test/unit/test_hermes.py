#!/usr/bin/env python

import json
import socket
import tarfile
import unittest

import tornado.httpclient
from appscale.appcontroller_client import AppControllerClient
from appscale.common import appscale_info
from appscale.common.ua_client import UAClient
from appscale.common.ua_client import UAException
from flexmock import flexmock
from tornado.ioloop import IOLoop

from appscale.hermes import helper, server
from appscale.hermes.server import poll
from appscale.hermes.server import SensorDeployer
from appscale.hermes.server import shutdown
from appscale.hermes.server import signal_handler


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
    server.zk_client = flexmock(stop=lambda: None)
    flexmock(IOLoop.instance()).should_receive('add_callback').and_return()\
      .times(1)
    signal_handler(15, None)

  def test_shutdown(self):
    flexmock(IOLoop.instance()).should_receive('stop').and_return().times(1)
    shutdown()

  def test_sensor_app_not_deployed_when_deployment_not_registered(self):
    # Test sensor app is not deployed when deployment is not registered.
    flexmock(helper).should_receive('get_deployment_id').and_return(None)
    flexmock(server).should_receive('create_appscale_user').and_return().\
      times(0)
    flexmock(server).should_receive('create_xmpp_user').and_return().\
      times(0)
    flexmock(AppControllerClient).should_receive('upload_app').and_return().\
      times(0)

    zk_client = flexmock(exists=lambda node: None)
    sensor_deployer = SensorDeployer(zk_client)
    sensor_deployer.deploy()

    # Test sensor app is not deployed when it is already running.
    flexmock(helper).should_receive('get_deployment_id').and_return(
      self.DEPLOYMENT_ID)
    fake_options = flexmock(secret="fake_secret")
    server.options = fake_options
    flexmock(appscale_info).should_receive('get_db_master_ip').and_return()
    # Assume appscalesensor app already running.
    flexmock(AppControllerClient).should_receive('upload_app').and_return(). \
      times(0)

    zk_client = flexmock(exists=lambda node: True)
    sensor_deployer = SensorDeployer(zk_client)
    sensor_deployer.deploy()

    # Test sensor app is not deployed when the app is not currently running but
    # there was an error in creating a new user.
    # Assume error while creating a new user.
    flexmock(UAClient).should_receive('does_user_exist').and_return(False)
    flexmock(UAClient).should_receive('commit_new_user').and_raise(UAException)
    flexmock(server).should_receive('create_appscale_user').and_return(). \
      times(1)
    flexmock(AppControllerClient).should_receive('upload_app').and_return(). \
      times(0)

    zk_client = flexmock(exists=lambda node: None)
    sensor_deployer = SensorDeployer(zk_client)
    sensor_deployer.deploy()

    # Test sensor app is deployed after successfully creating a new user or
    # with an existing user.
    flexmock(UAClient).should_receive('commit_new_user')
    flexmock(tarfile).should_receive('open').and_return(tarfile.TarFile)
    flexmock(tarfile.TarFile).should_receive('add').and_return()
    flexmock(tarfile.TarFile).should_receive('close').and_return()
    flexmock(appscale_info).should_receive('get_appcontroller_client').and_return(
      AppControllerClient)
    flexmock(server).should_receive('create_appscale_user').and_return(True)
    flexmock(server).should_receive('create_xmpp_user').and_return(True)
    flexmock(AppControllerClient).should_receive('upload_app').and_return(). \
      times(1)

    zk_client = flexmock(exists=lambda node: None)
    sensor_deployer = SensorDeployer(zk_client)
    sensor_deployer.deploy()

if __name__ == "__main__":
  unittest.main()
