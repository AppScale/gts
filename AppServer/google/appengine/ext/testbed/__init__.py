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
import unittest

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
from google.appengine.api.blobstore import blobstore_stub
from google.appengine.api.blobstore import dict_blob_storage
from google.appengine.api.channel import channel_service_stub
try:
  from google.appengine.api.images import images_stub
except ImportError:
  images_stub = None

from google.appengine.api.memcache import memcache_stub
from google.appengine.api.taskqueue import taskqueue_stub
from google.appengine.api.xmpp import xmpp_service_stub
try:
  from google.appengine.datastore import datastore_sqlite_stub
except ImportError:
  datastore_sqlite_stub = None
from google.appengine.datastore import datastore_stub_util


DEFAULT_ENVIRONMENT = {
    'APPLICATION_ID': 'testbed-test',
    'AUTH_DOMAIN': 'gmail.com',
    'REQUEST_ID_HASH': 'testbed-request-id-hash',
    'SERVER_NAME': 'testbed.example.com',
    'SERVER_SOFTWARE': 'Development/1.0 (testbed)',
    'SERVER_PORT': '80',
    'USER_EMAIL': '',
    'USER_ID': '',
}

# Deprecated legacy aliases for default environment variables. New code

DEFAULT_APP_ID = DEFAULT_ENVIRONMENT['APPLICATION_ID']
DEFAULT_AUTH_DOMAIN = DEFAULT_ENVIRONMENT['AUTH_DOMAIN']
DEFAULT_SERVER_NAME = DEFAULT_ENVIRONMENT['SERVER_NAME']
DEFAULT_SERVER_SOFTWARE = DEFAULT_ENVIRONMENT['SERVER_SOFTWARE']
DEFAULT_SERVER_PORT = DEFAULT_ENVIRONMENT['SERVER_PORT']


BLOBSTORE_SERVICE_NAME = 'blobstore'
CHANNEL_SERVICE_NAME = 'channel'
DATASTORE_SERVICE_NAME = 'datastore_v3'
IMAGES_SERVICE_NAME = 'images'
MAIL_SERVICE_NAME = 'mail'
MEMCACHE_SERVICE_NAME = 'memcache'
TASKQUEUE_SERVICE_NAME = 'taskqueue'
URLFETCH_SERVICE_NAME = 'urlfetch'
USER_SERVICE_NAME = 'user'
XMPP_SERVICE_NAME = 'xmpp'


SUPPORTED_SERVICES = [BLOBSTORE_SERVICE_NAME,
                      CHANNEL_SERVICE_NAME,
                      DATASTORE_SERVICE_NAME,
                      IMAGES_SERVICE_NAME,
                      MAIL_SERVICE_NAME,
                      MEMCACHE_SERVICE_NAME,
                      TASKQUEUE_SERVICE_NAME,
                      URLFETCH_SERVICE_NAME,
                      USER_SERVICE_NAME,
                      XMPP_SERVICE_NAME,
                      ]


class Error(Exception):
  """Base testbed error type."""


class NotActivatedError(Error):
  """Raised if the used testbed instance is not activated."""


class StubNotSupportedError(Error):
  """Raised if an unsupported service stub is accessed."""



class Testbed(object):
  """Class providing APIs to manipulate stubs for testing.

  This class allows to replace App Engine services with fake stub
  implementations. These stubs act like the actual APIs but do not
  invoke the replaced services.

  In order to use a fake service stub or disable a real service,
  invoke the corresponding 'init_*_stub' methods of this class.
  """

  def __init__(self):
    self._activated = False
    self._enabled_stubs = []

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
    self._activated = True

  def deactivate(self):
    if not self._activated:
      raise NotActivatedError('The testbed is not activated.')
    apiproxy_stub_map.apiproxy = self._original_stub_map
    self._enabled_stubs = []
    os.environ = self._orig_env
    self._activated = False

  def setup_env(self, overwrite=False, **kwargs):
    """Set up environment variables.

    Sets default and custom environment variables.  By default, all the items in
    DEFAULT_ENVIRONMENT will be created without being specified.  To set a value
    other than the default, or to pass a custom environment variable, pass a
    corresponding keyword argument:

    testbed_instance.setup_env()  # All defaults.
    testbed_instance.setup_env(auth_domain='custom')  # All defaults, overriding
                                                      # AUTH_DOMAIN.
    testbed_instance.setup_env(custom='foo')  # All defaults, plus a custom
                                              # os.environ['CUSTOM'] = 'foo'.

    To overwrite values set by a previous invocation, pass overwrite=True.  This
    will not result in an OVERWRITE entry in os.environ.

    Args:
      overwrite: boolean.  Whether to overwrite items with corresponding entries
                 in os.environ.
      **kwargs: environment variables to set.  The name of the argument will be
                uppercased and used as a key in os.environ.
    """
    merged_kwargs = {}
    for key, value in kwargs.iteritems():

      if key == 'app_id':
        key = 'APPLICATION_ID'
      merged_kwargs[key.upper()] = value
    if not overwrite:
      for key, value in DEFAULT_ENVIRONMENT.iteritems():
        if key not in merged_kwargs:
          merged_kwargs[key] = value
    for key, value in merged_kwargs.iteritems():
      if overwrite or key not in os.environ:
        os.environ[key] = value

  def _register_stub(self, service_name, stub):
    """Register a service stub.

    Args:
      service_name: The name of the service the stub represents.
      stub: The stub.

    Raises:
      NotActivatedError: The testbed is not activated.
    """
    if not self._activated:
      raise NotActivatedError('The testbed is not activated.')
    if service_name in self._test_stub_map._APIProxyStubMap__stub_map:
      del self._test_stub_map._APIProxyStubMap__stub_map[service_name]
    self._test_stub_map.RegisterStub(service_name, stub)
    self._enabled_stubs.append(service_name)

  def _disable_stub(self, service_name):
    """Disable a service stub.

    Args:
      service_name: The name of the service to disable.

    Raises:
      NotActivatedError: The testbed is not activated.
    """
    if not self._activated:
      raise NotActivatedError('The testbed is not activated.')
    if service_name in self._test_stub_map._APIProxyStubMap__stub_map:
      del self._test_stub_map._APIProxyStubMap__stub_map[service_name]
    if service_name in self._enabled_stubs:
      self._enabled_stubs.remove(service_name)

  def get_stub(self, service_name):
    """Get the stub for a service.

    Args:
      service_name: The name of the service.

    Returns:
      The stub for 'service_name'.

    Raises:
      NotActivatedError: The testbed is not activated.
      StubNotSupportedError: The service is not supported by testbed.
      StubNotEnabledError: The service stub has not been enabled.
    """
    if not self._activated:
      raise NotActivatedError('The testbed is not activated.')
    if service_name not in SUPPORTED_SERVICES:
      msg = 'The "%s" service is not supported by testbed' % service_name
      raise StubNotSupportedError(msg)
    if service_name not in self._enabled_stubs:
      return None
    return self._test_stub_map.GetStub(service_name)

  def init_blobstore_stub(self, enable=True):
    """Enable the blobstore stub.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
    """
    if not enable:
      self._disable_stub(BLOBSTORE_SERVICE_NAME)
      return

    storage = dict_blob_storage.DictBlobStorage()
    stub = blobstore_stub.BlobstoreServiceStub(storage)
    self._register_stub(BLOBSTORE_SERVICE_NAME, stub)

  def init_channel_stub(self, enable=True):
    """Enable the channel stub.

    Args:
      enable: True, if the fake service should be enabled, False if real
              service should be disabled.
    """
    if not enable:
      self._disable_stub(CHANNEL_SERVICE_NAME)
      return
    stub = channel_service_stub.ChannelServiceStub()
    self._register_stub(CHANNEL_SERVICE_NAME, stub)

  def init_datastore_v3_stub(self, enable=True, datastore_file=None,
                             use_sqlite=False, **stub_kw_args):
    """Enable the datastore stub.

    The 'datastore_file' argument can be the path to an existing
    datastore file, or None (default) to use an in-memory datastore
    that is initially empty.  If you use the sqlite stub and have
    'datastore_file' defined, changes you apply in a test will be
    written to the file.  If you use the default datastore stub,
    changes are _not_ saved to disk unless you set save_changes=True.

    Note that you can only access those entities of the datastore file
    which have the same application ID associated with them as the
    test run. You can change the application ID for a test with
    setup_env().

    Args:
      enable: True if the fake service should be enabled, False if real
        service should be disabled.
      datastore_file: Filename of a dev_appserver datastore file.
      use_sqlite: True to use the Sqlite stub, False (default) for file stub.
      stub_kw_args: Keyword arguments passed on to the service stub.
    """
    if not enable:
      self._disable_stub(DATASTORE_SERVICE_NAME)
      return
    if use_sqlite:
      if datastore_sqlite_stub is None:
        raise StubNotSupportedError(
            'The sqlite stub is not supported in production.')
      stub = datastore_sqlite_stub.DatastoreSqliteStub(
          os.environ['APPLICATION_ID'],
          datastore_file,
          **stub_kw_args)
    else:
      stub_kw_args.setdefault('save_changes', False)
      stub = datastore_file_stub.DatastoreFileStub(
          os.environ['APPLICATION_ID'],
          datastore_file,
          **stub_kw_args)
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
    if images_stub is None:
      msg = ('Could not initialize images API; you are likely '
             'missing the Python "PIL" module.')
      raise StubNotSupportedError(msg)
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
