""" Iterates through a range of index entries. """

import sys
from collections import namedtuple

from tornado import gen

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.dbconstants import (
  ASC_PROPERTY_TABLE, BadRequest, KEY_DELIMITER, PROPERTY_SCHEMA,
  TERMINATING_STRING)
from appscale.datastore.utils import decode_path, encode_index_pb

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore.datastore_pb import Path, Query_Filter


IndexEntry = namedtuple('IndexEntry',
                        ['encoded_path', 'entity_reference', 'key', 'path'])


class Cursor(object):
  """ Represents a position within a range. """
  __slots__ = ['key', 'inclusive']

  def __init__(self, key, inclusive):
    """ Creates a new Cursor.

    Args:
      key: A string specifying an encoded entity key.
      inclusive: A boolean indicating that the next value can include the key.
    """
    self.key = key
    self.inclusive = inclusive


class RangeExhausted(Exception):
  """ Indicates that there are no more entries in the range. """
  pass


class RangeIterator(object):
  """ Iterates through a range of index entries.

  This was designed for merge join queries. The range can only be narrowed.
  """
  CHUNK_SIZE = 1000

  def __init__(self, db, project_id, namespace, kind, prop_name, value):
    """ Creates a new RangeIterator.

    Args:
      db: A database interface object.
      project_id: A string specifying a project ID.
      namespace: A string specifying a namespace.
      kind: A string specifying an entity kind.
      prop_name: A string specifying a property name.
      value: An entity_pb.PropertyValue.
    """
    self.project_id = project_id
    self.namespace = namespace
    self.kind = kind
    self.prop_name = prop_name

    self._db = db
    self._value = value

    self._range = (self.prefix, ''.join([self.prefix, TERMINATING_STRING]))
    self._cursor = Cursor(self.prefix, inclusive=True)

    self._cache = []
    self._index_exhausted = False

  @property
  def prefix(self):
    """ The encoded reference without the path element. """
    return KEY_DELIMITER.join(
      [self.project_id, self.namespace, self.kind, self.prop_name,
       str(encode_index_pb(self._value))])

  @gen.coroutine
  def async_next(self):
    """ Retrieves the next index entry in the range.

    Returns:
      An IndexEntry.
    Raises:
      RangeExhausted when there are no more entries in the range.
    """
    try:
      # First check if the request can be fulfilled with the cache.
      entry = self._next_from_cache()
      self._cursor = Cursor(entry.key, inclusive=False)
      raise gen.Return(entry)
    except ValueError:
      # If the cache and index have been exhausted, there are no more entries.
      if self._index_exhausted:
        raise RangeExhausted()

    self._cache = yield self._db.range_query(
      ASC_PROPERTY_TABLE, PROPERTY_SCHEMA, self._cursor.key, self._range[-1],
      self.CHUNK_SIZE, start_inclusive=self._cursor.inclusive)

    if len(self._cache) < self.CHUNK_SIZE:
      self._index_exhausted = True

    if not self._cache:
      raise RangeExhausted()

    entry = self.entry_from_result(self._cache[0])
    self._cursor = Cursor(entry.key, inclusive=False)
    raise gen.Return(entry)

  @classmethod
  def from_filter(cls, db, project_id, namespace, kind, pb_filter):
    """ Creates a new RangeIterator from a filter.

    Args:
      db: A database interface object.
      project_id: A string specifying a project ID.
      namespace: A string specifying a namespace.
      kind: A string specifying an entity kind.
      pb_filter: A datastore_pb.Query_Filter object.
    Raises:
      BadRequest if the filter cannot be used to create the range.
    """
    # Make sure this filter can be used for a merge join.
    if pb_filter.op() != Query_Filter.EQUAL:
      raise BadRequest('Invalid filter for merge join '
                       '(op must be equal): {}'.format(pb_filter))

    if pb_filter.property_size() != 1:
      raise BadRequest('Invalid filter for merge join '
                       '(multiple properties): {}'.format(pb_filter))

    property_ = pb_filter.property(0)
    if property_.name() == '__key__':
      raise BadRequest('Invalid property for merge join '
                       '(must not be __key__): {}'.format(property_))

    return cls(db, project_id, namespace, kind, property_.name(),
               property_.value())

  @staticmethod
  def entry_from_result(result):
    """ Creates an IndexEntry from a Cassandra result.

    Args:
      result: A dictionary mapping a Cassandra key to a reference value.
    Returns:
      An IndexEntry.
    """
    entry_key = result.keys()[0]
    encoded_path = entry_key.rsplit(KEY_DELIMITER)[-1]
    path = decode_path(encoded_path)
    entity_ref = result.values()[0]['reference']
    return IndexEntry(encoded_path, entity_ref, entry_key, path)

  def get_cursor(self):
    """ Fetches the range's current cursor position.

    Returns:
      An entity_pb.Path object.
    """
    # If the current cursor does not have a path, return an empty one.
    if self._cursor.key == self.prefix:
      return Path()

    encoded_path = self._cursor.key.rsplit(KEY_DELIMITER)[-1]
    return decode_path(encoded_path)

  def set_cursor(self, path, inclusive):
    """ Changes the range's cursor position.

    Args:
      path: An entity_pb.Path object.
      inclusive: A boolean specifying that the next result can include the
        given path.
    Raises:
      BadRequest if unable to set the cursor to the given path.
    """
    range_start, range_end = self._range
    cursor = Cursor(
      KEY_DELIMITER.join([self.prefix, str(encode_index_pb(path))]), inclusive)

    if cursor.key < self._cursor.key:
      raise BadRequest(
        'Cursor cannot be moved backwards '
        '({} < {})'.format(repr(cursor.key), repr(self._cursor.key)))

    if cursor.key < range_start or cursor.key > range_end:
      raise BadRequest('Cursor outside range: {}'.format(self._range))

    self._cursor = cursor

  def restrict_to_path(self, path):
    """ Narrows the range to a specific entity path.

    Args:
      path: An entity_pb.Path object.
    """
    start_key = KEY_DELIMITER.join([self.prefix, str(encode_index_pb(path))])
    end_key = ''.join([start_key, TERMINATING_STRING])
    if start_key < self._range[0] or end_key > self._range[-1]:
      raise BadRequest('Restriction must be within range')

    if self._cursor.key > end_key:
      raise BadRequest('Cursor already exceeds new range')

    self._range = (start_key, end_key)
    self._cursor.key = max(start_key, self._cursor.key)

  def _next_from_cache(self):
    """ Retrieves the next index entry from the cache.

    Returns:
      An IndexEntry.
    Raises:
      ValueError if the cache does not contain a suitable entry.
    """
    lo = 0
    hi = len(self._cache)
    # Bisect the cache to find the smallest key that is >= the cursor.
    while lo < hi:
      mid = (lo + hi) // 2
      if self._cache[mid].keys()[0] < self._cursor.key:
        lo = mid + 1
      else:
        hi = mid

    try:
      entry = self.entry_from_result(self._cache[lo])
    except IndexError:
      raise ValueError

    # If cursor is not inclusive, exclude matching entries.
    if entry.key == self._cursor.key and not self._cursor.inclusive:
      try:
        entry = self.entry_from_result(self._cache[lo + 1])
      except IndexError:
        raise ValueError

    return entry
