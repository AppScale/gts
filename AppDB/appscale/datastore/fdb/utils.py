"""
This module contains common utility functions used across the FDB
implementation.
"""
import json
import logging
import random
import time

import fdb
import mmh3
import six
from tornado import gen
from tornado.concurrent import Future as TornadoFuture

from appscale.datastore.dbconstants import InternalError, SCATTER_CHANCE
from appscale.datastore.fdb.codecs import Path

fdb.api_version(610)
logger = logging.getLogger(__name__)

MAX_FDB_TX_DURATION = 5

_MAX_SEQUENTIAL_BIT = 52
_MAX_SEQUENTIAL_ID = (1 << _MAX_SEQUENTIAL_BIT) - 1
_MAX_SCATTERED_COUNTER = (1 << (_MAX_SEQUENTIAL_BIT - 1)) - 1
_MAX_SCATTERED_ID = _MAX_SEQUENTIAL_ID + 1 + _MAX_SCATTERED_COUNTER
_SCATTER_SHIFT = 64 - _MAX_SEQUENTIAL_BIT + 1

# The Cloud Datastore API uses microseconds as version IDs. When the entity
# doesn't exist, it reports the version as "1".
ABSENT_VERSION = 1

# The max number of bytes for each FDB value.
CHUNK_SIZE = 10000

SCATTER_PROP = u'__scatter__'

MAX_32 = 256 ** 4

SCATTER_PROPORTION = int(MAX_32 * SCATTER_CHANCE)

# The number of bytes used to store a commit versionstamp.
VERSIONSTAMP_SIZE = 10

MAX_ENTITY_SIZE = 1048572

# The FDB directory used for the datastore.
DS_ROOT = (u'appscale', u'datastore')


class FDBErrorCodes(object):
  NOT_COMMITTED = 1020


def ReverseBitsInt64(v):
  v = ((v >> 1) & 0x5555555555555555) | ((v & 0x5555555555555555) << 1)
  v = ((v >> 2) & 0x3333333333333333) | ((v & 0x3333333333333333) << 2)
  v = ((v >> 4) & 0x0F0F0F0F0F0F0F0F) | ((v & 0x0F0F0F0F0F0F0F0F) << 4)
  v = ((v >> 8) & 0x00FF00FF00FF00FF) | ((v & 0x00FF00FF00FF00FF) << 8)
  v = ((v >> 16) & 0x0000FFFF0000FFFF) | ((v & 0x0000FFFF0000FFFF) << 16)
  v = int((v >> 32) | (v << 32) & 0xFFFFFFFFFFFFFFFF)
  return v


class ScatteredAllocator(object):
  """ Generates large ID values that are somewhat evenly distributed. """
  def __init__(self):
    self._counter = random.randint(1, _MAX_SCATTERED_COUNTER)

  def invalidate(self):
    self._counter = random.randint(1, _MAX_SCATTERED_COUNTER)

  def get_id(self):
    id_ = (_MAX_SEQUENTIAL_ID + 1 +
           long(ReverseBitsInt64(self._counter << _SCATTER_SHIFT)))

    self._counter += 1
    if self._counter > _MAX_SCATTERED_COUNTER:
      self._counter = 1

    return id_


class TornadoFDB(object):
  """
  Presents FoundationDB operations in an interface that is friendly to Tornado
  coroutines.
  """
  def __init__(self, io_loop):
    self._io_loop = io_loop

  @gen.coroutine
  def commit(self, tr, convert_exceptions=True):
    tornado_future = TornadoFuture()
    callback = lambda fdb_future: self._handle_fdb_result(
      fdb_future, tornado_future)
    commit_future = tr.commit()
    commit_future.on_ready(callback)
    try:
      yield tornado_future
    except fdb.FDBError as fdb_error:
      if convert_exceptions:
        raise InternalError(fdb_error.description)
      else:
        raise

  def get(self, tr, key, snapshot=False):
    tx_reader = tr
    if snapshot:
      tx_reader = tr.snapshot

    tornado_future = TornadoFuture()
    callback = lambda fdb_future: self._handle_fdb_result(
      fdb_future, tornado_future)
    get_future = tx_reader.get(key)
    get_future.on_ready(callback)
    return tornado_future

  def get_range(self, tr, key_slice, limit=0,
                streaming_mode=fdb.StreamingMode.iterator, iteration=1,
                reverse=False, snapshot=False):
    tx_reader = tr
    if snapshot:
      tx_reader = tr.snapshot

    begin = key_slice.start
    if not isinstance(begin, fdb.KeySelector):
      begin = fdb.KeySelector.first_greater_or_equal(begin)

    end = key_slice.stop
    if not isinstance(end, fdb.KeySelector):
      end = fdb.KeySelector.first_greater_or_equal(end)

    tornado_future = TornadoFuture()
    callback = lambda fdb_future: self._handle_fdb_result(
      fdb_future, tornado_future)

    get_future = tx_reader._get_range(begin, end, limit, streaming_mode,
                                      iteration, reverse)

    get_future.on_ready(callback)
    return tornado_future

  def get_read_version(self, tr):
    tornado_future = TornadoFuture()
    callback = lambda fdb_future: self._handle_fdb_result(
      fdb_future, tornado_future)
    get_future = tr.get_read_version()
    get_future.on_ready(callback)
    return tornado_future

  def _handle_fdb_result(self, fdb_future, tornado_future):
    try:
      result = fdb_future.wait()
    except Exception as fdb_error:
      self._io_loop.add_callback(tornado_future.set_exception, fdb_error)
      return

    self._io_loop.add_callback(tornado_future.set_result, result)


class ResultIterator(object):
  """ Allows clients to page through a range of Key-Values. """
  def __init__(self, tr, tornado_fdb, key_slice, limit=0, reverse=False,
               streaming_mode=fdb.StreamingMode.iterator, snapshot=False):
    self.slice = key_slice
    self.done_with_range = False
    self._tr = tr
    self._tornado_fdb = tornado_fdb

    self._limit = limit
    self._reverse = reverse
    self._mode = streaming_mode
    self._snapshot = snapshot

    self._bsel = key_slice.start
    if not isinstance(self._bsel, fdb.KeySelector):
      self._bsel = fdb.KeySelector.first_greater_or_equal(self._bsel)

    self._esel = key_slice.stop
    if not isinstance(self._esel, fdb.KeySelector):
      self._esel = fdb.KeySelector.first_greater_or_equal(self._esel)

    self._fetched = 0
    self._iteration = 1
    self._index = 0
    self._done = False

  def __repr__(self):
    return (u'ResultIterator(key_slice={!r}, limit={!r}, reverse={!r}, '
            u'streaming_mode={!r}, snapshot={!r})').format(
      self.slice, self._limit, self._reverse, self._mode, self._snapshot)

  def increase_limit(self, difference=1):
    if not self.done_with_range:
      self._limit += difference
      self._done = False

  @gen.coroutine
  def next_page(self, mode=None):
    mode = mode or self._mode
    if self._done:
      raise gen.Return(([], False))

    tmp_limit = 0
    if self._limit > 0:
      tmp_limit = self._limit - self._fetched

    results, count, more = yield self._tornado_fdb.get_range(
      self._tr, slice(self._bsel, self._esel), tmp_limit, mode,
      self._iteration, self._reverse, self._snapshot)
    self._fetched += count
    self._iteration += 1

    if results:
      if self._reverse:
        self._esel = fdb.KeySelector.first_greater_or_equal(results[-1].key)
      else:
        self._bsel = fdb.KeySelector.first_greater_than(results[-1].key)

    reached_limit = self._limit > 0 and self._fetched == self._limit
    self._done = not more or reached_limit
    self.done_with_range = not more and not reached_limit

    raise gen.Return((results, not self._done))

  @gen.coroutine
  def list(self):
    all_results = []
    while True:
      results, more_results = yield self.next_page(fdb.StreamingMode.want_all)
      all_results.extend(results)
      if not more_results:
        break

    raise gen.Return(all_results)


def next_entity_version(old_version):
  # Since client timestamps are unreliable, ensure the new version is greater
  # than the old one.
  return max(int(time.time() * 1000 * 1000), old_version + 1)


def get_scatter_val(path):
  hashable_path = u''.join([six.text_type(element) for element in path])
  val = mmh3.hash(hashable_path.encode('utf-8'), signed=False)
  if val >= SCATTER_PROPORTION:
    return None

  return val


def hash_tuple(path):
  """
  Generates a consistent byte value for an entity path or fragment. The return
  value is only suitable to evenly scatter the path's encoding order. It is not
  suitable for a unique identifier.

  Args:
    path: A tuple containing values that can be interpreted as unicode strings.
  Returns:
    An integer ranging from 0 to 255.
  """
  hashable_value = u''.join([six.text_type(element) for element in path])
  val = mmh3.hash(hashable_value.encode('utf-8'), signed=False)
  return six.int2byte(val % 256)


def format_prop_val(prop_value):
  if prop_value.has_int64value():
    return prop_value.int64value()
  elif prop_value.has_booleanvalue():
    return prop_value.booleanvalue()
  elif prop_value.has_stringvalue():
    return repr(prop_value.stringvalue())
  elif prop_value.has_doublevalue():
    return prop_value.doublevalue()
  elif prop_value.has_pointvalue():
    point_val = prop_value.pointvalue()
    return point_val.x(), point_val.y()
  elif prop_value.has_uservalue():
    user_val = prop_value.uservalue()
    details = {'email': user_val.email(),
               'auth_domain': user_val.auth_domain()}
    if user_val.has_nickname():
      details['nickname'] = user_val.nickname()

    if user_val.has_federated_identity():
      details['federatedIdentity'] = user_val.federated_identity()

    if user_val.has_federated_provider():
      details['federatedProvider'] = user_val.federated_provider()

    return json.dumps(details)
  elif prop_value.has_referencevalue():
    return Path.flatten(prop_value.referencevalue())
  else:
    return None
