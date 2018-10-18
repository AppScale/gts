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


"""App Engine Datastore Admin configuration module.

Contains global configuration settings for various deployment environments.

Configuration values are added as class attributes to the respective
environment classes.  The environments form a hierarchy of configurations
that inherit from one another.

At module loading time one module is selected to be the Current module.
This is determined by examining the DATACENTER environment variable.
See GetConfig for details.

Defining values:

  New configuration values should be introduced by simply adding constants
  to the Default class and adding specialized values when needed to override
  those values specifically for each cluster type.  For example, let's say
  we need to configure the Admin Console URL:

    class Default(object):
      ...
      ADMIN_CONSOLE_URL = 'https://appengine.google.com'


    class Local(Default):
      ...
      ADMIN_CONSOLE_URL = 'https://127.0.0.1:8000'


Using values:

  All values of the Current configuration are imported up to the top level of
  this module.  Access to the configuration values should be done via the module
  directly. Note that changing configuration values at runtime is NOT supported.
  It is assumed that values in this configuration module are constants.
"""

import os


class Default(object):
  """Configuration object."""


  BASE_PATH = '/_ah/datastore_admin'
  MAPREDUCE_PATH = '/_ah/mapreduce'
  DEFERRED_PATH = BASE_PATH + '/queue/deferred'
  CLEANUP_MAPREDUCE_STATE = True

  DEFAULT_APP_DOMAIN = 'placeholder.com'
  GOOGLE_API_HOSTNAME = 'www.googleapis.com'
  GOOGLE_API_OAUTH_SCOPE_HOSTNAME = 'https://www.googleapis.com'
  GS_API_HOSTNAME = 'storage.googleapis.com'
  ADMIN_API_APP_ID = 'admin-api'
  ADMIN_API_APP_VERSION = None
  ADMIN_API_NAME = 'appengine'
  ADMIN_API_VERSION = 'vdev'
  ADMIN_API_VALIDATE_SSL = True
  ADMIN_CONSOLE_URL = 'https://appengine.google.com'

  @property
  def GOOGLE_API_HOST(self):
    return 'https://%s' % self.GOOGLE_API_HOSTNAME

  def GoogleApiScope(self, scope_type):
    return '%s/%s' % (self.GOOGLE_API_AUTH, scope_type)

  @property
  def GOOGLE_API_AUTH(self):
    return '%s/auth' % self.GOOGLE_API_OAUTH_SCOPE_HOSTNAME

  @property
  def DISCOVERY_URL(self):
    if self.ADMIN_API_APP_VERSION:
      hostname = '%s-dot-%s.%s' % (self.ADMIN_API_APP_VERSION,
                                   self.ADMIN_API_APP_ID,
                                   self.DEFAULT_APP_DOMAIN)
    else:
      hostname = '%s.%s' % (self.ADMIN_API_APP_ID, self.DEFAULT_APP_DOMAIN)
    path = '_ah/api/discovery/v1/apis/{api}/{apiVersion}/rest'
    return 'https://%s/%s' % (hostname, path)

  def GsBucketURL(self, bucket_name):
    return 'https://%s/%s/' % (self.GS_API_HOSTNAME, bucket_name)


class Local(Default):
  """Dev-appserver configuration."""


class Prod(Default):
  """Production cluster configuration."""
  DEFAULT_APP_DOMAIN = 'appspot.com'




try:

  import config_runtime

  RUNTIME_DATACENTER_TO_CLASS = config_runtime.RUNTIME_DATACENTER_TO_CLASS
except ImportError:
  RUNTIME_DATACENTER_TO_CLASS = {}


def GetConfig():
  """Determine configuration class based on the runtime environment.

  The DATACENTER environment variable is useful for determining which App
  Engine cluster type this services application is deployed on. All
  dev-appservers have no DATACENTER variable set. Production does not have any
  prefix at all.

  Returns:
    Class of the configuration determined by examining the runtime environment.
  """
  datacenter = os.environ.get('DATACENTER')
  if not datacenter:
    return Local
  for prefix, config in RUNTIME_DATACENTER_TO_CLASS.items():
    if datacenter.startswith(prefix):
      return config
  return Prod


def Export(cls):
  """Export public class values to the config module."""
  global current
  current = cls()
  for name in dir(current):
    if not name.startswith('_'):
      globals()[name] = getattr(current, name)


current = None
Export(GetConfig())
