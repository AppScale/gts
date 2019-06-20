"""
This module stores and retrieves entity data as well as the metadata needed to
achieve snapshot isolation during transactions. The DataManager is the main
interface that clients can use to interact with the data layer. See its
documentation for implementation details.
"""
from __future__ import division
import logging
import math
import sys

import six
import six.moves as sm
from tornado import gen

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.fdb.cache import NSCache
from appscale.datastore.fdb.codecs import encode_vs_index, Int64, Path, Text
from appscale.datastore.fdb.utils import (
  ABSENT_VERSION, DS_ROOT, fdb, hash_tuple, KVIterator, VS_SIZE)

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb

logger = logging.getLogger(__name__)


class VersionEntry(object):
  """ Encapsulates details for an entity version. """
  __slots__ = ['project_id', 'namespace', 'path', 'commit_vs', 'version',
               '_encoded_entity', '_decoded_entity']

  def __init__(self, project_id, namespace, path, commit_vs=None,
               encoded_entity=None, version=None):
    self.project_id = project_id
    self.namespace = namespace
    self.path = path
    self.commit_vs = commit_vs
    self.version = ABSENT_VERSION if version is None else version
    self._encoded_entity = encoded_entity
    self._decoded_entity = None

  @property
  def complete(self):
    return self._encoded_entity is not None or self._decoded_entity is not None

  @property
  def present(self):
    return self.version != ABSENT_VERSION

  @property
  def key(self):
    key = entity_pb.Reference()
    key.set_app(self.project_id)
    key.set_name_space(self.namespace)
    key.mutable_path().MergeFrom(Path.decode(self.path))
    return key

  @property
  def encoded(self):
    if self._encoded_entity is not None:
      return self._encoded_entity
    elif self._decoded_entity is not None:
      self._encoded_entity = self._decoded_entity.Encode()
      return self._encoded_entity
    else:
      return None

  @property
  def decoded(self):
    if self._decoded_entity is not None:
      return self._decoded_entity
    elif self._encoded_entity is not None:
      self._decoded_entity = entity_pb.EntityProto(self._encoded_entity)
      return self._decoded_entity
    else:
      return None


class DataNamespace(object):
  """
  A DataNamespace handles the encoding and decoding details for entity data
  for a specific project_id/namespace combination.

  The directory path looks like (<project-dir>, 'data', <namespace>).

  Within this directory, keys are encoded as
  <scatter-byte> + <path> + <commit-vs> + <index>.

  The <scatter-byte> is a single byte determined by hashing the entity path.
  Its purpose is to spread writes more evenly across the cluster and minimize
  hotspots.

  The <path> contains the entity path. See codecs.Path for encoding details.

  The <commit-vs> is a 10-byte versionstamp that specifies the commit version
  of the transaction that wrote the entity data.

  The <index> is a single byte specifying which chunk number the KV contains.

  Values are encoded as <entity-version> + <entity-encoding> + <entity>.

  The <entity-version> is an integer specifying the approximate insert
  timestamp in microseconds (according to the client performing the insert).
  Though there is a one-to-one mapping of commit versionstamps to entity
  versions, the datastore uses a different value for the entity version in
  order to satisfy the 8-byte constraint and to follow the GAE convention of
  the value representing a timestamp. It is encoded using 7 bytes.

  The <entity-encoding> is a single byte specifying the encoding scheme of the
  entity to follow.

  The <entity> is an encoded protobuffer value.

  Since encoded values can exceed the size limit imposed by FoundationDB,
  values encoded values are split into chunks. Each chunk is stored as a
  KV and ordered by a unique <index> byte.
  """
  DIR_NAME = u'data'

  # The max number of bytes for each FDB value.
  _CHUNK_SIZE = 10000

  # The number of bytes used to store an entity version.
  _VERSION_SIZE = 7

  # The number of bytes used to encode the chunk index.
  _INDEX_SIZE = 1

  # Indicates the encoded blob is a V3 entity object.
  _V3_MARKER = 0x01

  def __init__(self, directory):
    self.directory = directory

  @property
  def project_id(self):
    return self.directory.get_path()[len(DS_ROOT)]

  @property
  def namespace(self):
    return self.directory.get_path()[len(DS_ROOT) + 2]

  @property
  def path_slice(self):
    """ The portion of keys that contain the encoded path. """
    return slice(len(self.directory.rawPrefix) + 1,
                 -1 * (VS_SIZE + self._INDEX_SIZE))

  @property
  def vs_slice(self):
    """ The portion of keys that contain the commit versionstamp. """
    return slice(self.path_slice.stop, self.path_slice.stop + VS_SIZE)

  @property
  def index_slice(self):
    """ The portion of keys that contain the chunk index. """
    return slice(-1 * self._INDEX_SIZE, None)

  @property
  def version_slice(self):
    """ The portion of values that contain the entity version. """
    return slice(None, self._VERSION_SIZE)

  @property
  def encoding_slice(self):
    """ The portion of values that specify the entity encoding type. """
    return slice(self._VERSION_SIZE, self._VERSION_SIZE + 1)

  @property
  def entity_slice(self):
    """ The portion of values that contain the encoded entity. """
    return slice(self._VERSION_SIZE + 1, None)

  def encode(self, path, entity, version):
    """ Encodes a tuple of KV tuples for a given version entry.

    Args:
      path: A tuple or protobuf path object.
      entity: An encoded entity or protobuf object.
      version: An integer specifying the new entity version.
    Returns:
      A tuple of KV tuples suitable for writing in an FDB transaction.
    """
    if isinstance(entity, entity_pb.EntityProto):
      entity = entity.Encode()

    value = b''.join([Int64.encode_bare(version, self._VERSION_SIZE),
                      six.int2byte(self._V3_MARKER), entity])
    chunk_count = int(math.ceil(len(value) / self._CHUNK_SIZE))
    return tuple(self._encode_kv(value, index, path, commit_vs=None)
                 for index in sm.range(chunk_count))

  def encode_key(self, path, commit_vs, index):
    """ Encodes a key for the given version entry.

    Args:
      path: A tuple or protobuf path object.
      commit_vs: A 10-byte string specifying the version's commit versionstamp
        or None.
      index: An integer specifying the chunk index.
    Returns:
      A string containing an FDB key. If commit_vs was None, the key should be
      used with set_versionstamped_key.
    """
    encoded_key = b''.join([self._encode_path_prefix(path),
                            commit_vs or b'\x00' * VS_SIZE,
                            six.int2byte(index)])
    if not commit_vs:
      vs_index = len(encoded_key) - (VS_SIZE + self._INDEX_SIZE)
      encoded_key += encode_vs_index(vs_index)

    return encoded_key

  def decode(self, kvs):
    """ Decodes KVs to a version entry.

    Args:
      kvs: An iterable containing KeyValue objects.
    Returns:
      A VersionEntry object.
    """
    path = Path.unpack(kvs[0].key, self.path_slice.start)[0]
    commit_vs = kvs[0].key[self.vs_slice]
    first_index = ord(kvs[0].key[self.index_slice])

    encoded_entity = None
    version = None
    if first_index == 0:
      encoded_val = b''.join([kv.value for kv in kvs])
      version = Int64.decode_bare(encoded_val[self.version_slice])
      encoded_entity = encoded_val[self.entity_slice]

    return VersionEntry(self.project_id, self.namespace, path, commit_vs,
                        encoded_entity, version)

  def get_slice(self, path, commit_vs=None, read_vs=None):
    """ Gets the range of keys relevant to the given constraints.

    Args:
      path: A tuple or protobuf path object.
      commit_vs: The commit versionstamp for a specific entity version.
      read_vs: The transaction's read versionstamp. All newer entity versions
        are ignored.
    Returns:
      A slice specifying the start and stop keys.
    """
    path_prefix = self._encode_path_prefix(path)
    if commit_vs is not None:
      prefix = path_prefix + commit_vs
      # All chunks for a given version.
      return slice(fdb.KeySelector.first_greater_or_equal(prefix + b'\x00'),
                   fdb.KeySelector.first_greater_than(prefix + b'\xFF'))

    if read_vs is not None:
      version_prefix = path_prefix + read_vs
      # All versions for a given path except those written after the read_vs.
      return slice(
        fdb.KeySelector.first_greater_or_equal(path_prefix + b'\x00'),
        fdb.KeySelector.first_greater_than(version_prefix + b'\xFF'))

    # All versions for a given path.
    return slice(fdb.KeySelector.first_greater_or_equal(path_prefix + b'\x00'),
                 fdb.KeySelector.first_greater_than(path_prefix + b'\xFF'))

  def _encode_path_prefix(self, path):
    """ Encodes the portion of the key up to and including the path.

    Args:
      path: A tuple or protobuf path object.
    Returns:
      A string containing the path prefix.
    """
    if not isinstance(path, tuple):
      path = Path.flatten(path)

    return b''.join([self.directory.rawPrefix, hash_tuple(path),
                     Path.pack(path)])

  def _encode_kv(self, value, index, path, commit_vs):
    """ Encodes an individual KV entry for a single chunk.

    Args:
      value: A byte string containing the full encoded version entry value.
      index: An integer specifying the chunk index.
      path: A tuple or protobuf path object.
      commit_vs: A 10-byte string specifying the version's commit versionstamp
        or None.
    Returns:
      A tuple in the form of (key, value) suitable for using with FDB. If
      commit_vs was None, the tuple should be used with set_versionstamped_key.
    """
    data_range = slice(index * self._CHUNK_SIZE,
                       (index + 1) * self._CHUNK_SIZE)
    encoded_val = value[data_range]
    return self.encode_key(path, commit_vs, index), encoded_val


class GroupUpdatesNS(object):
  """
  A GroupUpdatesNS handles the encoding and decoding details for commit
  versionstamps for each entity group. These are used to materialize conflicts
  for transactions that involve ancestory queries on the same entity groups.

  The directory path looks like (<project-dir>, 'group-updates', <namespace>).

  Within this directory, keys are encoded as <scatter-byte> + <group-path>.

  The <scatter-byte> is a single byte determined by hashing the group path.
  Its purpose is to spread writes more evenly across the cluster and minimize
  hotspots.

  The <group-path> contains the entity group path.

  Values are 10-byte strings that specify the latest commit version for the
  entity group.
  """
  DIR_NAME = u'group-updates'

  def __init__(self, directory):
    self.directory = directory

  def encode(self, path):
    """ Creates a KV tuple for updating a group's commit versionstamp.

    Args:
      path: A tuple or protobuf path object.
    Returns:
      A (key, value) tuple suitable for set_versionstamped_value.
    """
    if not isinstance(path, tuple):
      path = Path.flatten(path)

    group_path = path[:2]
    return self.encode_key(group_path), b'\x00' * VS_SIZE + encode_vs_index(0)

  def encode_key(self, group_path):
    """ Encodes a key for a given entity group.

    Args:
      group_path: A tuple containing path elements.
    Returns:
      A byte string containing the relevant FDB key.
    """
    return b''.join([
      self.directory.rawPrefix, hash_tuple(group_path),
      Text.encode(group_path[0]) + Path.encode_id_or_name(group_path[1])])


class DataManager(object):
  """
  The DataManager is the main interface that clients can use to interact with
  the data layer. It makes use of the DataNamespace and GroupUpdateNS
  namespaces to handle the encoding and decoding details when satisfying
  requests. When a client requests data, the DataManager encapsulates entity
  data in a VersionEntry object.

  See the DataNamespace and GroupUpdateNS classes for implementation details
  about how data is stored and retrieved.
  """
  def __init__(self, tornado_fdb, project_cache):
    self._tornado_fdb = tornado_fdb
    self._data_cache = NSCache(self._tornado_fdb, project_cache, DataNamespace)
    self._group_updates_cache = NSCache(
      self._tornado_fdb, project_cache, GroupUpdatesNS)

  @gen.coroutine
  def get_latest(self, tr, key, read_vs=None, include_data=True):
    """ Gets the newest entity version for the given read VS.

    Args:
      tr: An FDB transaction.
      key: A protubuf reference object.
      read_vs: A 10-byte string specifying the FDB read versionstamp. Newer
        versionstamps are ignored.
      include_data: A boolean specifying whether or not to fetch all of the
        entity's KVs.
    """
    data_ns = yield self._data_cache.get_from_key(tr, key)
    desired_slice = data_ns.get_slice(key.path(), read_vs=read_vs)
    last_entry = yield self._last_version(
      tr, data_ns, desired_slice, include_data)
    if last_entry is None:
      last_entry = VersionEntry(data_ns.project_id, data_ns.namespace,
                                Path.flatten(key.path()))

    raise gen.Return(last_entry)

  @gen.coroutine
  def get_entry(self, tr, index_entry, snapshot=False):
    """ Gets the entity data from an index entry.

    Args:
      tr: An FDB transaction.
      index_entry: An IndexEntry object.
      snapshot: If True, the read will not cause a transaction conflict.
    Returns:
      A VersionEntry or None.
    """
    version_entry = yield self.get_version_from_path(
      tr, index_entry.project_id, index_entry.namespace, index_entry.path,
      index_entry.commit_vs, snapshot)
    raise gen.Return(version_entry)

  @gen.coroutine
  def get_version_from_path(self, tr, project_id, namespace, path, commit_vs,
                            snapshot=False):
    """ Gets the entity data for a specific version.

    Args:
      tr: An FDB transaction.
      project_id: A string specifying the project ID.
      namespace: A string specifying the namespace.
      path: A tuple or protobuf path object.
      commit_vs: A 10-byte string specyfing the FDB commit versionstamp.
      snapshot: If True, the read will not cause a transaction conflict.
    Returns:
      A VersionEntry or None.
    """
    data_ns = yield self._data_cache.get(tr, project_id, namespace)
    desired_slice = data_ns.get_slice(path, commit_vs)
    kvs = yield KVIterator(tr, self._tornado_fdb, desired_slice,
                           snapshot=snapshot).list()
    raise gen.Return(data_ns.decode(kvs))

  @gen.coroutine
  def last_group_vs(self, tr, project_id, namespace, group_path):
    """ Gets the most recent commit versionstamp for the entity group.

    Args:
      tr: An FDB transaction.
      project_id: A string specifying the project ID.
      namespace: A string specifying the namespace.
      group_path: A tuple containing the group's path elements.
    Returns:
      A 10-byte string specifying the versionstamp or None.
    """
    group_ns = yield self._group_updates_cache.get(tr, project_id, namespace)
    last_updated_vs = yield self._tornado_fdb.get(
      tr, group_ns.encode_key(group_path))
    if not last_updated_vs.present():
      return

    raise gen.Return(last_updated_vs.value)

  @gen.coroutine
  def put(self, tr, key, version, encoded_entity):
    """ Writes a new version entry and updates the entity group VS.

    Args:
      tr: An FDB transaction.
      key: A protobuf reference object.
      version: An integer specifying the new entity version.
      encoded_entity: A string specifying the encoded entity data.
    """
    data_ns = yield self._data_cache.get_from_key(tr, key)
    for fdb_key, val in data_ns.encode(key.path(), encoded_entity, version):
      tr[fdb_key] = val

    group_ns = yield self._group_updates_cache.get(
      tr, data_ns.project_id, data_ns.namespace)
    tr.set_versionstamped_value(*group_ns.encode(key.path()))

  @gen.coroutine
  def hard_delete(self, tr, key, commit_vs):
    """ Deletes a version entry. Only the GC should use this.

    Args:
      tr: An FDB transaction.
      key: A protobuf reference object.
      commit_vs: A 10-byte string specifying the commit versionstamp.
    """
    data_ns = yield self._data_cache.get_from_key(tr, key)
    del tr[data_ns.get_slice(key.path(), commit_vs)]

  @gen.coroutine
  def _last_version(self, tr, data_ns, desired_slice, include_data=True):
    """ Gets the most recent entity data for a given slice.

    Args:
      tr: An FDB transaction.
      data_ns: A DataNamespace.
      desired_slice: A slice specifying the start and stop keys.
      include_data: A boolean indicating that all chunks should be fetched.
    Returns:
      A VersionEntry or None.
    """
    kvs, count, more_results = yield self._tornado_fdb.get_range(
      tr, desired_slice, limit=1, reverse=True)

    if not kvs:
      return

    last_kv = kvs[0]
    entry = data_ns.decode([last_kv])
    if not include_data or entry.complete:
      raise gen.Return(entry)

    # Retrieve the remaining chunks.
    version_slice = data_ns.get_slice(entry.path, entry.commit_vs)
    end_key = data_ns.encode_key(entry.path, entry.commit_vs, entry.index)
    remaining_slice = slice(version_slice.start,
                            fdb.KeySelector.first_greater_or_equal(end_key))
    kvs = yield KVIterator(tr, self._tornado_fdb, remaining_slice).list()
    raise gen.Return(data_ns.decode(kvs + [last_kv]))
