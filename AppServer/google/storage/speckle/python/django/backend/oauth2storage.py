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




"""OAuth 2.0 credential storage for rdbms."""


import apiclient
from django.core.cache import cache
from oauth2client import client


class CacheStorage(client.Storage):
  """An OAuth2.0 storage class that stores credentials in Django's cache.

  Credentials are also stored in memory as an instance attribute to allow for
  storage to function without hitting the cache in situations where it's not
  needed, such as with command line Django management commands.

  Attributes:
    credentials: The client.OAuth2Credentials instance.
  """
  CACHE_KEY = '__google_sql_oauth2__'

  def __init__(self):
    self.credentials = None

  def locked_get(self):
    if self.credentials is None:
      json = cache.get(self.CACHE_KEY)
      if json is not None:
        self.credentials = client.Credentials.new_from_json(json)
    if self.credentials and hasattr(self.credentials, 'set_store'):
      self.credentials.set_store(self)
    return self.credentials

  def locked_put(self, credentials):
    self.credentials = credentials
    cache.set(self.CACHE_KEY, credentials.to_json())


storage = CacheStorage()
