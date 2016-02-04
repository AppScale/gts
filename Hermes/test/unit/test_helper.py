#!/usr/bin/env python

import os
import Queue
import sys
import threading
import tornado.httpclient
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import helper
import hermes_constants
from custom_hermes_exceptions import MissingRequestArgs

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import appscale_info

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../AppServer'))
from google.appengine.api.appcontroller_client import AppControllerClient

class FakeAppControllerClient():
  def __init__(self, registered):
    self.registered = registered
  def deployment_id_exists(self):
    return self.registered
  def get_deployment_id(self):
    return 'fake_id'

class FakeAsyncClient():
  def fetch(self):
    pass

class FakeClient():
  def fetch(self):
    pass

class FakeLock():
  def __init__(self, wrapped_class):
    pass
  def acquire(self):
    pass
  def release(self):
    pass

class FakeRequest():
  def __init__(self):
    self.url = fake_url
    self.body = fake_data

class FakeResponse():
  def __init__(self, request, code):
    self.request = request
    self.code = code

fake_url = 'http://some.url'
fake_data = 'some data'
fake_node_info = [
  {
    'host': fake_url,
    'role': 'db_master',
    'index': None
  },
  {
    'host': fake_url,
    'role': 'zk',
    'index': 0
  }
]

class TestHelper(unittest.TestCase):
  """ A set of test cases for Hermes helper functions. """

  def test_create_request(self):
    # Test with no args.
    self.assertRaises(MissingRequestArgs, helper.create_request)
    # Test GET.
    self.assertIsNotNone(helper.create_request, ['some url', 'some method'])
    # Test POST.
    self.assertIsNotNone(helper.create_request, ['some url', 'some method',
      'some data'])

  def test_urlfetch(self):
    fake_request = FakeRequest()
    fake_response = FakeResponse(fake_request, 200)
    fake_client = flexmock(tornado.httpclient.HTTPClient())

    fake_client.should_receive('fetch').and_return(fake_response)
    self.assertIsNotNone(helper.urlfetch, fake_request)

  def test_urlfetch_async(self):
    fake_request = FakeRequest()
    fake_response = FakeResponse(fake_request, 200)
    fake_client = flexmock(tornado.httpclient.AsyncHTTPClient())

    fake_client.should_receive('fetch').and_return(fake_response)
    self.assertIsNotNone(helper.urlfetch, fake_request)

  def test_get_br_service_url(self):
    fake_url = 'http://host:{0}{1}'.format(hermes_constants.BR_SERVICE_PORT,
      hermes_constants.BR_SERVICE_PATH)
    self.assertEquals(fake_url, helper.get_br_service_url('host'))

  def test_get_deployment_id(self):
    # Test with a registered AppScale deployment.
    fake_acc = FakeAppControllerClient(True)
    flexmock(appscale_info).should_receive('get_appcontroller_client').\
      and_return(fake_acc)
    flexmock(AppControllerClient).should_receive('deployment_id_exists').\
      and_return(True)
    flexmock(AppControllerClient).should_receive('get_deployment_id').\
      and_return('fake_id')
    self.assertEquals('fake_id', helper.get_deployment_id())

    # Test with an AppScale deployment that's not registered.
    fake_acc = FakeAppControllerClient(False)
    flexmock(appscale_info).should_receive('get_appcontroller_client').\
      and_return(fake_acc)
    flexmock(AppControllerClient).should_receive('deployment_id_exists').\
      and_return(False)
    self.assertIsNone(helper.get_deployment_id())

  def test_get_node_info(self):
    flexmock(appscale_info).should_receive('get_db_master_ip').and_return(
      'foo')
    flexmock(appscale_info).should_receive('get_db_slave_ips').and_return(
      ['bar'])
    flexmock(appscale_info).should_receive('get_zk_node_ips').and_return(
      ['baz'])
    flexmock(helper).should_receive('get_br_service_url').and_return(
      'http://some.url').at_least().times(2)
    self.assertEquals(fake_node_info, helper.get_node_info())

  def test_create_br_json_data(self):
    pass

  def test_delete_task_from_mem(self):
    flexmock(FakeLock(threading.Lock())).should_receive('acquire').\
      and_return()
    flexmock(FakeLock(threading.Lock())).should_receive('release').\
      and_return()
    helper.delete_task_from_mem('foo')

  def test_report_status(self):
    pass

  def test_send_remote_request(self):
    flexmock(Queue.Queue).should_receive('put').and_return().at_least().times(1)
    flexmock(helper).should_receive('urlfetch').and_return('qux').at_least().\
      times(1)

    helper.send_remote_request(FakeRequest(), Queue.Queue())

if __name__ == "__main__":
  unittest.main()
