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




"""Django database backend for rdbms.

This acts as a simple wrapper around the MySQLdb database backend to utilize an
alternate settings.py configuration.  When used in an application running on
Google App Engine, this backend will use the GAE Apiproxy as a communications
driver.  When used with dev_appserver, or from outside the context of an App
Engine app, this backend will instead use a driver that communicates over the
Google API for SQL Service.

Communicating over Google API requires valid OAuth 2.0 credentials.  Before
the backend can be used with this transport on dev_appserver, users should
first run the Django 'syncdb' management command (or any other of the commands
that interact with the database), and follow the instructions to obtain an
OAuth2 token and persist it to disk for subsequent use.

If you should need to manually force the selection of a particular driver
module, you can do so by specifying it in the OPTIONS section of the database
configuration in settings.py.  For example:

DATABASES = {
    'default': {
        'ENGINE': 'google.storage.speckle.python.django.backend',
        'INSTANCE': 'example.com:project:instance',
        'NAME': 'mydb',
        'USER': 'myusername',
        'PASSWORD': 'mypassword',
        'OPTIONS': {
            'driver': 'google.storage.speckle.python.api.rdbms_googleapi',
        }
    }
}
"""




import logging
import os
import sys

from django.core import exceptions
from django.db.backends import signals
from django.utils import safestring

from google.storage.speckle.python.api import rdbms
from google.storage.speckle.python.django.backend import client

PROD_SERVER_SOFTWARE = 'Google App Engine'






modules_to_swap = (
    'MySQLdb',
    'MySQLdb.constants',
    'MySQLdb.constants.CLIENT',
    'MySQLdb.constants.FIELD_TYPE',
    'MySQLdb.constants.FLAG',
    'MySQLdb.converters',
    )


old_modules = [(name, sys.modules.pop(name)) for name in modules_to_swap
               if name in sys.modules]

sys.modules['MySQLdb'] = rdbms

try:

  from google.third_party import python
  python.MySQLdb = rdbms
  for module_name in modules_to_swap:
    module_name = 'google.third_party.python.' + module_name
    old_modules.append((module_name, sys.modules.pop(module_name, None)))
  sys.modules['google.third_party.python.MySQLdb'] = rdbms
except ImportError:
  pass

from django.db.backends.mysql import base


for module_name, module in old_modules:
  sys.modules[module_name] = module






_SETTINGS_CONNECT_ARGS = (
    ('HOST', 'dsn', False),
    ('INSTANCE', 'instance', True),
    ('NAME', 'database', True),

    ('USER', 'user', False),
    ('PASSWORD', 'password', False),


    ('OAUTH2_SECRET', 'oauth2_refresh_token', False),
    ('driver', 'driver_name', False),
    ('oauth_storage', 'oauth_storage', False),
)


def _GetDriver(driver_name=None):
  """Imports the driver module specified by the given module name.

  If no name is given, this will attempt to automatically determine an
  appropriate driver to use based on the current environment.  When running on
  a production App Engine instance, the ApiProxy driver will be used, otherwise,
  the Google API driver will be used.  This conveniently allows the backend to
  be used with the same configuration on production, and with command line tools
  like manage.py syncdb.

  Args:
    driver_name: The name of the driver module to import.

  Returns:
    The imported driver module, or None if a suitable driver can not be found.
  """
  if not driver_name:
    server_software = os.getenv('SERVER_SOFTWARE', '')
    base_pkg_path = 'google.storage.speckle.python.api.'
    if server_software.startswith(PROD_SERVER_SOFTWARE):
      driver_name = base_pkg_path + 'rdbms_apiproxy'
    else:
      driver_name = base_pkg_path + 'rdbms_googleapi'
  __import__(driver_name)
  return sys.modules[driver_name]


def Connect(driver_name=None, oauth2_refresh_token=None, **kwargs):
  """Gets an appropriate connection driver, and connects with it.

  Args:
    driver_name: The name of the driver module to use.
    oauth2_refresh_token: The OAuth2 refresh token used to aquire an access
      token for authenticating requests made by the Google API driver; defaults
      to the value provided by the GOOGLE_SQL_OAUTH2_REFRESH_TOKEN environment
      variable, if present.
    kwargs: Additional keyword arguments to pass to the driver's connect
      function.

  Returns:
    An rdbms.Connection subclass instance.

  Raises:
    exceptions.ImproperlyConfigured: Valid OAuth 2.0 credentials could not be
      found in storage and no oauth2_refresh_token was given.
  """
  driver = _GetDriver(driver_name)
  server_software = os.getenv('SERVER_SOFTWARE', '')
  if server_software and driver.__name__.endswith('rdbms_googleapi'):
    if server_software.startswith(PROD_SERVER_SOFTWARE):
      logging.warning(
          'Using the Google API driver is not recommended when running on '
          'production App Engine.  You should instead use the GAE API Proxy '
          'driver (google.storage.speckle.python.api.rdbms_apiproxy).')


    import oauth2client.client
    from google.storage.speckle.python.api import rdbms_googleapi
    from google.storage.speckle.python.django.backend import oauth2storage


    storage = kwargs.setdefault('oauth_storage', oauth2storage.storage)
    credentials = storage.get()
    if credentials is None or credentials.invalid:
      if not oauth2_refresh_token:
        oauth2_refresh_token = os.getenv('GOOGLE_SQL_OAUTH2_REFRESH_TOKEN')
      if not oauth2_refresh_token:
        raise exceptions.ImproperlyConfigured(
            'No valid OAuth 2.0 credentials.  Before using the Google SQL '
            'Service backend on dev_appserver, you must first run "manage.py '
            'syncdb" and proceed through the given instructions to fetch an '
            'OAuth 2.0 token.')
      credentials = oauth2client.client.OAuth2Credentials(
          None, rdbms_googleapi.CLIENT_ID, rdbms_googleapi.CLIENT_SECRET,
          oauth2_refresh_token, None,
          'https://accounts.google.com/o/oauth2/token',
          rdbms_googleapi.USER_AGENT)
      credentials.set_store(storage)
      storage.put(credentials)
  return driver.connect(**kwargs)


class DatabaseWrapper(base.DatabaseWrapper):
  """Django DatabaseWrapper for use with rdbms.

  Overrides many pieces of the MySQL DatabaseWrapper for compatibility with
  the rdbms API.
  """
  vendor = 'rdbms'

  def __init__(self, *args, **kwargs):
    super(DatabaseWrapper, self).__init__(*args, **kwargs)
    self.client = client.DatabaseClient(self)

  def _cursor(self):
    if not self._valid_connection():
      kwargs = {'conv': base.django_conversions, 'dsn': None}
      settings_dict = self.settings_dict
      settings_dict.update(settings_dict.get('OPTIONS', {}))
      for settings_key, kwarg, required in _SETTINGS_CONNECT_ARGS:
        value = settings_dict.get(settings_key)
        if value:
          kwargs[kwarg] = value
        elif required:
          raise exceptions.ImproperlyConfigured(
              "You must specify a '%s' for database '%s'" %
              (settings_key, self.alias))
      self.connection = Connect(**kwargs)
      encoders = {safestring.SafeUnicode: self.connection.encoders[unicode],
                  safestring.SafeString: self.connection.encoders[str]}
      self.connection.encoders.update(encoders)
      signals.connection_created.send(sender=self.__class__, connection=self)
    cursor = base.CursorWrapper(self.connection.cursor())
    return cursor
