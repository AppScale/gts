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
















"""Represents a lexographic range of namespaces."""




__all__ = [
    'NAMESPACE_CHARACTERS',
    'MAX_NAMESPACE_LENGTH',
    'MAX_NAMESPACE',
    'MIN_NAMESPACE',
    'NamespaceRange',
    'get_namespace_keys',
]

import itertools
import string

from google.appengine.api import datastore
from google.appengine.ext import db
from google.appengine.ext.db import metadata

NAMESPACE_CHARACTERS = ''.join(sorted(string.digits +
                                      string.lowercase +
                                      string.uppercase +
                                      '._-'))
MAX_NAMESPACE_LENGTH = 100
MIN_NAMESPACE = ''


def _setup_constants(alphabet=NAMESPACE_CHARACTERS,
                     max_length=MAX_NAMESPACE_LENGTH):
  """Calculate derived constant values. Only useful for testing."""

  global NAMESPACE_CHARACTERS
  global MAX_NAMESPACE_LENGTH
  global MAX_NAMESPACE
  global _LEX_DISTANCE

  NAMESPACE_CHARACTERS = alphabet
  MAX_NAMESPACE_LENGTH = max_length
  MAX_NAMESPACE = NAMESPACE_CHARACTERS[-1] * MAX_NAMESPACE_LENGTH





















  _LEX_DISTANCE = [1]
  for i in range(1, MAX_NAMESPACE_LENGTH):
    _LEX_DISTANCE.append(
        _LEX_DISTANCE[i-1] * len(NAMESPACE_CHARACTERS) + 1)
  del i
_setup_constants()


def _ord_to_namespace(n, _max_length=None):
  """Convert a namespace ordinal to a namespace string.

  Converts an int, representing the sequence number of a namespace ordered
  lexographically, into a namespace string.

  >>> _ord_to_namespace(0)
  ''
  >>> _ord_to_namespace(1)
  '-'
  >>> _ord_to_namespace(2)
  '--'
  >>> _ord_to_namespace(3)
  '---'

  Args:
    n: A number representing the lexographical ordering of a namespace.

  Returns:
    A string representing the nth namespace in lexographical order.
  """
  if _max_length is None:
    _max_length = MAX_NAMESPACE_LENGTH

  length = _LEX_DISTANCE[_max_length - 1]
  if n == 0:
    return ''
  n -= 1
  return (NAMESPACE_CHARACTERS[n / length] +
          _ord_to_namespace(n % length, _max_length - 1))


def _namespace_to_ord(namespace):
  """Converts a namespace string into an int representing its lexographic order.

  >>> _namespace_to_ord('')
  ''
  >>> _namespace_to_ord('_')
  1
  >>> _namespace_to_ord('__')
  2

  Args:
    namespace: A namespace string.

  Returns:
    An int representing the lexographical order of the given namespace string.
  """
  n = 0
  for i, c in enumerate(namespace):
    n += (_LEX_DISTANCE[MAX_NAMESPACE_LENGTH - i- 1] *
          NAMESPACE_CHARACTERS.index(c)
          + 1)
  return n


def _key_for_namespace(namespace, app):
  """Return the __namespace__ key for a namespace.

  Args:
    namespace: The namespace whose key is requested.
    app: The id of the application that the key belongs to.

  Returns:
    A db.Key representing the namespace.
  """
  if namespace:
    return db.Key.from_path(metadata.Namespace.KIND_NAME,
                            namespace,
                            _app=app)
  else:
    return db.Key.from_path(metadata.Namespace.KIND_NAME,
                            metadata.Namespace.EMPTY_NAMESPACE_ID,
                            _app=app)


class NamespaceRange(object):
  """An inclusive lexographical range of namespaces.

  This class is immutable.
  """

  def __init__(self,
               namespace_start=None,
               namespace_end=None,
               _app=None):
    """Initializes a NamespaceRange instance.

    Args:
      namespace_start: A string representing the start of the namespace range.
          namespace_start is included in the range. If namespace_start is None
          then the lexographically first namespace is used.
      namespace_end: A string representing the end of the namespace range.
          namespace_end is included in the range and must be >= namespace_start.
          If namespace_end is None then the lexographically last namespace is
          used.

    Raises:
      ValueError: if namespace_start > namespace_end.
    """
    if namespace_start is None:
      namespace_start = MIN_NAMESPACE

    if namespace_end is None:
      namespace_end = MAX_NAMESPACE

    if namespace_start > namespace_end:
      raise ValueError('namespace_start (%r) > namespace_end (%r)' % (
          namespace_start, namespace_end))
    self.__namespace_start = namespace_start
    self.__namespace_end = namespace_end
    self.__app = _app

  @property
  def app(self):
    return self.__app

  @property
  def namespace_start(self):
    return self.__namespace_start

  @property
  def namespace_end(self):
    return self.__namespace_end

  @property
  def is_single_namespace(self):
    """True if the namespace range only includes a single namespace."""
    return self.namespace_start == self.namespace_end

  def split_range(self):
    """Splits the NamespaceRange into two nearly equal-sized ranges.

    Returns:
      If this NamespaceRange contains a single namespace then a list containing
      this NamespaceRange is returned. Otherwise a two-element list containing
      two NamespaceRanges whose total range is identical to this
      NamespaceRange's is returned.
    """
    if self.is_single_namespace:
      return [self]

    mid_point = (_namespace_to_ord(self.namespace_start) +
                 _namespace_to_ord(self.namespace_end)) // 2

    return [NamespaceRange(self.namespace_start,
                           _ord_to_namespace(mid_point),
                           _app=self.app),
            NamespaceRange(_ord_to_namespace(mid_point+1),
                           self.namespace_end,
                           _app=self.app)]

  def __copy__(self):
    return self.__class__(self.__namespace_start,
                          self.__namespace_end,
                          self.__app)

  def __eq__(self, o):
    return (self.namespace_start == o.namespace_start and
            self.namespace_end == o.namespace_end)

  def __hash__(self):
    return hash((self.namespace_start, self.namespace_end, self.app))

  def __repr__(self):
    if self.app is None:
      return 'NamespaceRange(namespace_start=%r, namespace_end=%r)' % (
          self.namespace_start, self.namespace_end)
    else:
      return 'NamespaceRange(namespace_start=%r, namespace_end=%r, _app=%r)' % (
          self.namespace_start, self.namespace_end, self.app)

  def with_start_after(self, after_namespace):
    """Returns a copy of this NamespaceName with a new namespace_start.

    Args:
      after_namespace: A namespace string.

    Returns:
      A NamespaceRange object whose namespace_start is the lexographically next
      namespace after the given namespace string.

    Raises:
      ValueError: if the NamespaceRange includes only a single namespace.
    """
    namespace_start = _ord_to_namespace(_namespace_to_ord(after_namespace) + 1)
    return NamespaceRange(namespace_start, self.namespace_end, _app=self.app)

  def make_datastore_query(self):
    """Returns a datastore.Query that generates all namespaces in the range.

    Returns:
      A datastore.Query instance that generates db.Keys for each namespace in
      the NamespaceRange.
    """
    filters = {}
    filters['__key__ >= '] = _key_for_namespace(
        self.namespace_start, self.app)
    filters['__key__ <= '] = _key_for_namespace(
        self.namespace_end, self.app)

    return datastore.Query('__namespace__',
                           filters=filters,
                           keys_only=True,
                           _app=self.app)

  def normalized_start(self):
    """Returns a NamespaceRange with leading non-existant namespaces removed.

    Returns:
      A copy of this NamespaceRange whose namespace_start is adjusted to exlcude
      the portion of the range that contains no actual namespaces in the
      datastore. None is returned if the NamespaceRange contains no actual
      namespaces in the datastore.
    """
    namespaces_after_key = self.make_datastore_query().Get(1)

    if not namespaces_after_key:
      return None

    namespace_after_key = namespaces_after_key[0].name() or ''
    return NamespaceRange(namespace_after_key,
                          self.namespace_end,
                          _app=self.app)

  def to_json_object(self):
    """Returns a dict representation that can be serialized to JSON."""
    obj_dict = dict(namespace_start=self.namespace_start,
                    namespace_end=self.namespace_end)
    if self.app is not None:
      obj_dict['app'] = self.app
    return obj_dict

  @classmethod
  def from_json_object(cls, json):
    """Returns a NamespaceRange from an object deserialized from JSON."""
    return cls(json['namespace_start'],
               json['namespace_end'],
               _app=json.get('app'))




  @classmethod
  def split(cls,
            n,
            contiguous,
            can_query=itertools.chain(itertools.repeat(True, 50),
                                      itertools.repeat(False)).next,
            _app=None):
    """Splits the complete NamespaceRange into n equally-sized NamespaceRanges.

    Args:
      n: The maximum number of NamespaceRanges to return. Fewer than n
          namespaces may be returned.
      contiguous: If True then the returned NamespaceRanges will cover the
          entire space of possible namespaces (i.e. from MIN_NAMESPACE to
          MAX_NAMESPACE) without gaps. If False then the returned
          NamespaceRanges may exclude namespaces that don't appear in the
          datastore.
      can_query: A function that returns True if split() can query the datastore
          to generate more fair namespace range splits, and False otherwise.
          If not set then split() is allowed to make 50 datastore queries.

    Returns:
      A list of at most n NamespaceRanges representing a near-equal distribution
      of actual existant datastore namespaces. The returned list will be sorted
      lexographically.

    Raises:
      ValueError: if n is < 1.
    """
    if n < 1:
      raise ValueError('n must be >= 1')

    ns_range = NamespaceRange(_app=_app)
    if can_query():
      ns_range = ns_range.normalized_start()
      if ns_range is None:
        if contiguous:
          return [NamespaceRange(_app=_app)]
        else:
          return []
    ranges = [ns_range]

    singles = []
    while ranges and (len(ranges) + len(singles)) < n:
      namespace_range = ranges.pop(0)
      if namespace_range.is_single_namespace:
        singles.append(namespace_range)
      else:
        left, right = namespace_range.split_range()
        if can_query():
          right = right.normalized_start()
        if right is not None:
          ranges.append(right)
        ranges.append(left)
    ns_ranges = sorted(singles + ranges,
                       key=lambda ns_range: ns_range.namespace_start)

    if contiguous:
      if not ns_ranges:


        return [NamespaceRange(_app=_app)]

      continuous_ns_ranges = []
      for i in range(len(ns_ranges)):
        if i == 0:
          namespace_start = MIN_NAMESPACE
        else:
          namespace_start = ns_ranges[i].namespace_start

        if i == len(ns_ranges) - 1:
          namespace_end = MAX_NAMESPACE
        else:
          namespace_end = _ord_to_namespace(
              _namespace_to_ord(ns_ranges[i+1].namespace_start) - 1)

        continuous_ns_ranges.append(NamespaceRange(namespace_start,
                                                   namespace_end,
                                                   _app=_app))
      return continuous_ns_ranges
    else:
      return ns_ranges

  def __iter__(self):
    """Iterate over all the namespaces within this range."""
    query = self.make_datastore_query()
    for ns_key in query.Run():
      yield ns_key.name() or ''


def get_namespace_keys(app, limit):
  """Get namespace keys."""
  ns_query = datastore.Query('__namespace__', keys_only=True, _app=app)
  return ns_query.Get(limit=limit)
