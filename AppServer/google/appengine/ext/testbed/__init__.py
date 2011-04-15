#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""A module to use service stubs for testing.

To test applications which use App Engine services such as the
datastore, developers can use the available stub
implementations. Service stubs behave like the original service
without permanent side effects. The datastore stub for example allows
to write entities into memory without storing them to the actual
datastore. This module makes using those stubs for testing easier.

Here is a basic example:
'''
from google.appengine.ext import db
from google.appengine.ext import testbed


class TestModel(db.Model):
  number = db.IntegerProperty(default=42)


class MyTestCase(unittest.TestCase):

  def setUp(self):
    # At first, create an instance of the Testbed class.
    self.testbed = testbed.Testbed()
    # Then activate the testbed which will prepare the usage of service stubs.
    self.testbed.activate()
    # Next, declare which service stubs you want to use.
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()

  def tearDown(self):
    # Never forget to deactivate the testbed once the tests are
    # completed. Otherwise the original stubs will not be restored.
    self.testbed.deactivate()

  def testInsertEntity(self):
    # Because we use the datastore stub, this put() does not have
    # permanent side effects.
    TestModel().put()
    fetched_entities = TestModel.all().fetch(2)
    self.assertEqual(1, len(fetched_entities))
    self.assertEqual(42, fetched_entities[0].number)
'''


Enable stubs and disable services
---------------------------------

This module allows you to use stubs for the following services:
- datastore_v3 (aka datastore)
- images (only for dev_appserver)
- mail (only for dev_appserver)
- memcache
- taskqueue
- urlfetch
- user
- xmpp
- channel

To use a particular service stub, call self.init_SERVICENAME_stub().
This will replace calls to the service with calls to the service
stub. If you want to disable any calls to a particular service, call
self.init_SERVICENAME_stub(enable=False). This can be useful if you
want to test code that must not use a certain service.


Environment variables
---------------------

App Engine service stubs often depend on environment variables. For
example, the datastore stub uses os.environ['APPLICATION_ID'] to store
entities linked to a particular app. testbed will use default values
if nothing else is provided, but you can change those with
self.setup_env().
"""





import os
import unittest

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import datastore_file_stub
try:
  from google.appengine.api import mail_stub
except AttributeError:



  mail_stub = None
from google.appengine.api import urlfetch_stub
from google.appengine.api import user_service_stub
from google.appengine.api.channel import channel_service_stub
from google.appengine.api.images import images_stub
from google.appengine.api.memcache import memcache_stub
from google.appengine.api.taskqueue import taskqueue_stub
from google.appengine.api.xmpp import xmpp_service_stub


__all__ = ['DEFAULT_APP_ID',
           'DATASTORE_SERVICE_NAME',
           'IMAGES_SERVICE_NAME',
           'MAIL_SERVICE_NAME',
           'MEMCACHE_SERVICE_NAME',
           'TASKQUEUE_SERVICE_NAME',
           'URLFETCH_SERVICE_NAME',
           'USER_SERVICE_NAME',
           'XMPP_SERVICE_NAME',
           'CHANNEL_SERVICE_NAME'
           'TestMixin',
           'TestCase']


DEFAULT_APP_ID = 'testbed-test'
DEFAULT_AUTH_DOMAIN = 'gmail.com'
DEFAULT_SERVER_NAME = 'testbed.example.com'
DEFAULT_SERVER_SOFTWARE = 'testbed/1.2.3 (testbed)'
DEFAULT_SERVER_PORT = '80'


DATASTORE_SERVICE_NAME = 'datastore_v3'
IMAGES_SERVICE_NAME = 'images'
MAIL_SERVICE_NAME = 'mail'
MEMCACHE_SERVICE_NAME = 'memcache'
TASKQUEUE_SERVICE_NAME = 'taskqueue'
URLFETCH_SERVICE_NAME = 'urlfetch'
USER_SERVICE_NAME = 'user'
XMPP_SERVICE_NAME = 'xmpp'
CHANNEL_SERVICE_NAME = 'channel'


class InMemoryDatastoreStub(datastore_file_stub.DatastoreFileStub):
  """File-based Datastore stub which does not actually write files."""

  def _DatastoreFileStub__WriteDatastore(self):
    """Override parent's method to no-op, so no writes are done."""



class Testbed(object):
  """Class providing APIs to manipulate stubs for testing.

  This class allows to replace App Engine services with fake stub
  implementations. These stubs act like the actual APIs but do not
  invoke the replaced services.

  In order to use a fake service stub or disable a real service,
  invoke the corresponding 'init_*_stub' methods of this class.
  """

  def activate(self):
    """Activate the testbed.

    Invoking this method will also assign default values to
    environment variables required by App Engine services such as
    os.environ['APPLICATION_ID']. You can set custom values with
    setup_env().
    """
    self._orig_env = dict(os.environ)
    self.setup_env()






    self._original_stub_map = apiproxy_stub_map.apiproxy
    self._test_stub_map = apiproxy_stub_map.APIProxyStubMap()
    internal_map = self._original_stub_map._APIProxyStubMap__stub_map
    self._test_stub_map._APIProxyStubMap__stub_map = dict(internal_map)
    apiproxy_stub_map.apiproxy = self._test_stub_map

  def deactivate(self):
    apiproxy_stub_map.apiproxy = self._original_stub_map
    os.environ = self._orig_env

  def setup_env(self, app_id=DEFAULT_APP_ID,
                auth_domain=DEFAULT_AUTH_DOMAIN,
                server_software=DEFAULT_SERVER_SOFTWARE,
                server_name=DEFAULT_SERVER_NAME,
                server_port=DEFAULT_SERVER_PORT):
    """Setup environment variables."""
    os.environ['APPLICATION_ID'] = app_id
    os.environ['AUTH_DOMAIN'] = auth_domain
    os.environ['SERVER_SOFTWARE'] = server_software
    os.environ['SERVER_NAME'] = server_name
    os.environ['SERVER_PORT'] = server_port

  def _register_stub(self, service_name, stub):
    if service_name in self._test_stub_map._APIProxyStubMap__stub_map:
      del self._test_stub_map._APIProxyStubMap__stub_map[service_name]
    self._test_stub_map.RegisterStub(service_name, stub)

  def _disable_stub(self, service_name):
    if service_name in self._test_stub_map._APIProxyStubMap__stub_map:
      del self._test_stub_map._APIProxyStubMap__stub_map[service_name]

  def get_stub(self, service_name):
    return self._test_stub_map.GetStub(service_name)

  def init_datastore_v3_stub(self, enable=True, datastore_file=None,
                             **stub_kw_args):
    """Enable the datastore stub.

    The 'datastore_file' argument is the path to an existing datastore
    file or None (default) to use an in-memory datastore that is
    initially empty. In either case, the datastore is _not_ saved to
    disk, and any changes are gone after tearDown executes, so unit
    tests cannot interfere with each other.

    Note that you can only access those entities of the datastore file
    which have the same application ID associated with them as the
    test run. You can change the application ID for a test with
    setup_env().

    Currently, the datastore stub only supports the file-based
    datastore stub, not the sqlite-based stub.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
      datastore_file: Filename of a dev_appserver datastore file.
      stub_kw_args: Keyword arguments passed on to the service stub.
    """
    if not enable:
      self._disable_stub(DATASTORE_SERVICE_NAME)
      return
    stub = InMemoryDatastoreStub(os.environ['APPLICATION_ID'],
                                 datastore_file, **stub_kw_args)
    self._register_stub(DATASTORE_SERVICE_NAME, stub)

  def init_images_stub(self, enable=True):
    """Enable the images stub.

    The images service stub is only available in dev_appserver because
    it uses the PIL library.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
    """
    if not enable:
      self._disable_stub(IMAGES_SERVICE_NAME)
      return
    stub = images_stub.ImagesServiceStub()
    self._register_stub(IMAGES_SERVICE_NAME, stub)

  def init_mail_stub(self, enable=True, **stub_kw_args):
    """Enable the mail stub.

    The email service stub is only available in dev_appserver because
    it uses the subprocess module.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
      stub_kw_args: Keyword arguments passed on to the service stub.
    """
    if not enable:
      self._disable_stub(MAIL_SERVICE_NAME)
      return
    stub = mail_stub.MailServiceStub(**stub_kw_args)
    self._register_stub(MAIL_SERVICE_NAME, stub)

  def init_memcache_stub(self, enable=True):
    """Enable the memcache stub.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
    """
    if not enable:
      self._disable_stub(MEMCACHE_SERVICE_NAME)
      return
    stub = memcache_stub.MemcacheServiceStub()
    self._register_stub(MEMCACHE_SERVICE_NAME, stub)

  def init_taskqueue_stub(self, enable=True, **stub_kw_args):
    """Enable the taskqueue stub.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
      stub_kw_args: Keyword arguments passed on to the service stub.
    """
    if not enable:
      self._disable_stub(TASKQUEUE_SERVICE_NAME)
      return
    stub = taskqueue_stub.TaskQueueServiceStub(**stub_kw_args)
    self._register_stub(TASKQUEUE_SERVICE_NAME, stub)

  def init_urlfetch_stub(self, enable=True):
    """Enable the urlfetch stub.

    The urlfetch service stub uses the urllib module to make
    requests. Because on appserver urllib also relies the urlfetch
    infrastructure, using this stub will have no effect.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
    """
    if not enable:
      self._disable_stub(URLFETCH_SERVICE_NAME)
      return
    stub = urlfetch_stub.URLFetchServiceStub()
    self._register_stub(URLFETCH_SERVICE_NAME, stub)

  def init_user_stub(self, enable=True, **stub_kw_args):
    """Enable the users stub.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
      stub_kw_args: Keyword arguments passed on to the service stub.
    """
    if not enable:
      self._disable_stub(USER_SERVICE_NAME)
      return
    stub = user_service_stub.UserServiceStub(**stub_kw_args)
    self._register_stub(USER_SERVICE_NAME, stub)

  def init_xmpp_stub(self, enable=True):
    """Enable the xmpp stub.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
    """
    if not enable:
      self._disable_stub(XMPP_SERVICE_NAME)
      return
    stub = xmpp_service_stub.XmppServiceStub()
    self._register_stub(XMPP_SERVICE_NAME, stub)

  def init_channel_stub(self, enable=True):
    """Enable the channel stub.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
    """
    self.setup_env(server_software='Devel')
    if not enable:
      self._disable_stub(CHANNEL_SERVICE_NAME)
      return
    stub = channel_service_stub.ChannelServiceStub()
    self._register_stub(CHANNEL_SERVICE_NAME, stub)
