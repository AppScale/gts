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
"""A memcache viewer and editor UI."""


import datetime
import pprint
import types
import urllib

from google.appengine.tools.devappserver2.admin import admin_request_handler

from google.appengine.api import memcache


def _to_bool(string_value):
  """Convert string to boolean value.

  Args:
    string_value: A string.

  Returns:
    Boolean.  True if string_value is "true", False if string_value is
    "false".  This is case-insensitive.

  Raises:
    ValueError: string_value not "true" or "false".
  """
  string_value_low = string_value.lower()
  if string_value_low not in ('false', 'true'):
    raise ValueError(
        'invalid literal for boolean: %s (must be "true" or "false")' %
        string_value)
  return string_value_low == 'true'


class MemcacheViewerRequestHandler(admin_request_handler.AdminRequestHandler):
  # Supported types:  type + conversion function + string description
  # Order is important, must check Boolean before Integer.
  TYPES = ((str, str, 'String'),
           (unicode, unicode, 'Unicode String'),
           (bool, _to_bool, 'Boolean'),
           (int, int, 'Integer'),
           (long, long, 'Long Integer'),
           (float, float, 'Float'))
  DEFAULT_TYPESTR_FOR_NEW = 'String'

  def _get_memcache_value_and_type(self, key):
    """Fetch value from memcache and detect its type.

    Args:
      key: String

    Returns:
      (value, type), value is a Python object or None if the key was not set in
      the cache, type is a string describing the type of the value.
    """
    try:
      value = memcache.get(key)
    except (pickle.UnpicklingError, AttributeError, EOFError, ImportError,
            IndexError), e:
      # Pickled data could be broken or the user might have stored custom class
      # instances in the cache (which can't be unpickled from here).
      msg = 'Failed to retrieve value from cache: %s' % e
      return msg, 'error'

    if value is None:
      # No such value in the cache yet.
      return None, self.DEFAULT_TYPESTR_FOR_NEW

    # Check if one of the editable types.
    for typeobj, _, typestr in self.TYPES:
      if isinstance(value, typeobj):
        break
    else:
      # Unsupported type, just print nicely.
      typestr = 'pickled'
      value = pprint.pformat(value, indent=2)

    return value, typestr

  def _set_memcache_value(self, key, type_, value):
    """Convert a string value and store the result in memcache.

    Args:
      key: String
      type_: String, describing what type the value should have in the cache.
      value: String, will be converted according to type_.

    Returns:
      Result of memcache.set(key, converted_value).  True if value was set.

    Raises:
      ValueError: Value can't be converted according to type_.
    """
    for _, converter, typestr in self.TYPES:
      if typestr == type_:
        value = converter(value)
        break
    else:
      raise ValueError('Type %s not supported.' % type_)
    return memcache.set(key, value)

  def get(self):
    """Show template and prepare stats and/or key+value to display/edit."""
    values = {'request': self.request,
              'message': self.request.get('message')}

    edit = self.request.get('edit')
    key = self.request.get('key')
    if edit:
      # Show the form to edit/create the value.
      key = edit
      values['show_stats'] = False
      values['show_value'] = False
      values['show_valueform'] = True
      values['types'] = [typestr for _, _, typestr in self.TYPES]
    elif key:
      # A key was given, show it's value on the stats page.
      values['show_stats'] = True
      values['show_value'] = True
      values['show_valueform'] = False
    else:
      # Plain stats display + key lookup form.
      values['show_stats'] = True
      values['show_valueform'] = False
      values['show_value'] = False

    if key:
      values['key'] = key
      values['value'], values['type'] = self._get_memcache_value_and_type(key)
      values['key_exists'] = values['value'] is not None

      if values['type'] in ('pickled', 'error'):
        values['writable'] = False
      else:
        values['writable'] = True

    if values['show_stats']:
      memcache_stats = memcache.get_stats()
      if not memcache_stats:
        # No stats means no memcache usage.
        memcache_stats = {'hits': 0, 'misses': 0, 'byte_hits': 0, 'items': 0,
                          'bytes': 0, 'oldest_item_age': 0}
      values['stats'] = memcache_stats
      try:
        hitratio = memcache_stats['hits'] * 100 / (memcache_stats['hits']
                                                   + memcache_stats['misses'])
      except ZeroDivisionError:
        hitratio = 0
      values['hitratio'] = hitratio
      # TODO: oldest_item_age should be formatted in a more useful
      # way.
      delta_t = datetime.timedelta(seconds=memcache_stats['oldest_item_age'])
      values['oldest_item_age'] = datetime.datetime.now() - delta_t

    self.response.write(self.render('memcache_viewer.html', values))

  def _urlencode(self, query):
    """Encode a dictionary into a URL query string.

    In contrast to urllib this encodes unicode characters as UTF8.

    Args:
      query: Dictionary of key/value pairs.

    Returns:
      String.
    """
    return '&'.join('%s=%s' % (urllib.quote_plus(k.encode('utf8')),
                               urllib.quote_plus(v.encode('utf8')))
                    for k, v in query.iteritems())

  def post(self):
    """Handle modifying actions and/or redirect to GET page."""
    next_param = {}

    if self.request.get('action:flush'):
      if memcache.flush_all():
        next_param['message'] = 'Cache flushed, all keys dropped.'
      else:
        next_param['message'] = 'Flushing the cache failed.  Please try again.'

    elif self.request.get('action:display'):
      next_param['key'] = self.request.get('key')

    elif self.request.get('action:edit'):
      next_param['edit'] = self.request.get('key')

    elif self.request.get('action:delete'):
      key = self.request.get('key')
      result = memcache.delete(key)
      if result == memcache.DELETE_NETWORK_FAILURE:
        next_param['message'] = ('ERROR: Network failure, key "%s" not deleted.'
                                 % key)
      elif result == memcache.DELETE_ITEM_MISSING:
        next_param['message'] = 'Key "%s" not in cache.' % key
      elif result == memcache.DELETE_SUCCESSFUL:
        next_param['message'] = 'Key "%s" deleted.' % key
      else:
        next_param['message'] = ('Unknown return value.  Key "%s" might still '
                                 'exist.' % key)

    elif self.request.get('action:save'):
      key = self.request.get('key')
      value = self.request.get('value')
      type_ = self.request.get('type')
      next_param['key'] = key
      try:
        if self._set_memcache_value(key, type_, value):
          next_param['message'] = 'Key "%s" saved.' % key
        else:
          next_param['message'] = 'ERROR: Failed to save key "%s".' % key
      except ValueError, e:
        next_param['message'] = 'ERROR: Unable to encode value: %s' % e

    elif self.request.get('action:cancel'):
      next_param['key'] = self.request.get('key')

    else:
      next_param['message'] = 'Unknown action.'

    next = self.request.path_url
    if next_param:
      next = '%s?%s' % (next, self._urlencode(next_param))
    self.redirect(next)
