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
from appscale.datastore.fdb.codecs import (
  decode_str, encode_versionstamp_index, Int64, Path, Text)
from appscale.datastore.fdb.utils import (
  ABSENT_VERSION, DS_ROOT, fdb, hash_tuple, ResultIterator, VERSIONSTAMP_SIZE)

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb

logger = logging.getLogger(__name__)

first_gt_or_equal = fdb.KeySelector.first_greater_or_equal


class VersionEntry(object):
  """ Encapsulates details for an entity version. """
  INCOMPLETE = 1
  __slots__ = ['project_id', 'namespace', 'path', 'commit_versionstamp',
               'version', '_encoded_entity', '_decoded_entity']

  def __init__(self, project_id, namespace, path, commit_versionstamp=None,
               version=None, encoded_entity=None):
    self.project_id = project_id
    self.namespace = namespace
    self.path = path
    self.commit_versionstamp = commit_versionstamp
    self.version = ABSENT_VERSION if version is None else version
    self._encoded_entity = encoded_entity
    self._decoded_entity = None

  def __repr__(self):
    # Since the encoded entity can be large, it probably does not make sense to
    # include it in the string representation.
    blob_repr = self._encoded_entity
    if blob_repr is not None:
      blob_repr = u'<bytes object with length={}>'.format(len(blob_repr))

    return u'VersionEntry({!r}, {!r}, {!r}, {!r}, {!r}, {})'.format(
      self.project_id, self.namespace, self.path, self.commit_versionstamp,
      self.version, blob_repr)

  @property
  def present(self):
    return self.commit_versionstamp is not None

  @property
  def complete(self):
    return self._encoded_entity != self.INCOMPLETE

  @property
  def has_entity(self):
    return bool(self._encoded_entity)

  @property
  def key(self):
    key = entity_pb.Reference()
    key.set_app(self.project_id)
    if self.namespace is not None:
      key.set_name_space(self.namespace)

    key.mutable_path().MergeFrom(Path.decode(self.path))
    return key

  @property
  def encoded(self):
    if not self.complete:
      raise ValueError(u'Version entry is not complete')

    return self._encoded_entity

  @property
  def decoded(self):
    if not self.has_entity:
      return None

    if self._decoded_entity is None:
      self._decoded_entity = entity_pb.EntityProto(self.encoded)

    return self._decoded_entity

  @classmethod
  def from_key(cls, key):
    project_id = decode_str(key.app())
    namespace = None
    if key.has_name_space():
      namespace = decode_str(key.name_space())

    path = Path.flatten(key.path())
    return cls(project_id, namespace, path)


class DataNamespace(object):
  """
  A DataNamespace handles the encoding and decoding details for entity data
  for a specific project_id/namespace combination.

  The directory path looks like (<project-dir>, 'data', <namespace>).

  Within this directory, keys are encoded as
  <scatter-byte> + <path> + <commit-versionstamp> + <index>.

  The <scatter-byte> is a single byte determined by hashing the entity path.
  Its purpose is to spread writes more evenly across the cluster and minimize
  hotspots.

  The <path> contains the entity path. See codecs.Path for encoding details.

  The <commit-versionstamp> is a 10-byte versionstamp that specifies the commit version
  of the transaction that wrote the entity data.

  The <index> is a single byte specifying the position of the value's chunk.

  Values are encoded as <entity-encoding> + <entity> + <entity-version>.

  The <entity-encoding> is a single byte specifying the encoding scheme of the
  entity to follow.

  The <entity> is an encoded protobuffer value.

  The <entity-version> is an integer specifying the approximate insert
  timestamp in microseconds (according to the client performing the insert).
  Though there is a one-to-one mapping of commit versionstamps to entity
  versions, the datastore uses a different value for the entity version in
  order to satisfy the 8-byte constraint and to follow the GAE convention of
  the value representing a timestamp. It is encoded using 7 bytes.

  Since encoded values can exceed the size limit imposed by FoundationDB,
  values encoded values are split into chunks. Each chunk is stored as a
  Key-Value and ordered by a unique <index> byte.
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
                 -1 * (VERSIONSTAMP_SIZE + self._INDEX_SIZE))

  @property
  def versionstamp_slice(self):
    """ The portion of keys that contain the commit versionstamp. """
    return slice(self.path_slice.stop,
                 self.path_slice.stop + VERSIONSTAMP_SIZE)

  @property
  def index_slice(self):
    """ The portion of keys that contain the chunk index. """
    return slice(-1 * self._INDEX_SIZE, None)

  @property
  def encoding_slice(self):
    """ The portion of values that specify the entity encoding type. """
    return slice(0, 1)

  @property
  def entity_slice(self):
    """ The portion of values that contain the encoded entity. """
    return slice(1, -self._VERSION_SIZE)

  @property
  def version_slice(self):
    """ The portion of values that contain the entity version. """
    return slice(-self._VERSION_SIZE, None)

  @classmethod
  def directory_path(cls, project_id, namespace):
    return project_id, cls.DIR_NAME, namespace

  def encode(self, path, entity, version):
    """ Encodes a tuple of Key-Value tuples for a given version entry.

    Args:
      path: A tuple or protobuf path object.
      entity: An encoded entity or protobuf object.
      version: An integer specifying the new entity version.
    Returns:
      A tuple of Key-Value tuples suitable for writing in an FDB transaction.
    """
    if isinstance(entity, entity_pb.EntityProto):
      entity = entity.Encode()

    encoded_version = Int64.encode_bare(version, self._VERSION_SIZE)
    if not entity:
      return ((self.encode_key(path, commit_versionstamp=None, index=0),
               encoded_version),)

    value = b''.join([six.int2byte(self._V3_MARKER), entity])
    chunk_count = int(math.ceil(len(value) / self._CHUNK_SIZE))
    chunks = [
      value[slice(index * self._CHUNK_SIZE, (index + 1) * self._CHUNK_SIZE)]
      for index in sm.range(chunk_count)]
    # Place the version at the end of the last chunk. Though this allows the
    # last chunk to exceed the chunk size, it ensures that the entity version
    # can always be retrieved from the last chunk.
    chunks[-1] += encoded_version
    return tuple(
      (self.encode_key(path, commit_versionstamp=None, index=index), chunk)
      for index, chunk in enumerate(chunks))

  def encode_key(self, path, commit_versionstamp, index):
    """ Encodes a key for the given version entry.

    Args:
      path: A tuple or protobuf path object.
      commit_versionstamp: A 10-byte string specifying the version's commit
        versionstamp or None.
      index: An integer specifying the chunk index.
    Returns:
      A string containing an FDB key. If commit_versionstamp was None, the key
      should be used with set_versionstamped_key.
    """
    encoded_key = b''.join([self._encode_path_prefix(path),
                            commit_versionstamp or b'\x00' * VERSIONSTAMP_SIZE,
                            six.int2byte(index)])
    if not commit_versionstamp:
      versionstamp_index = (len(encoded_key) -
                            (VERSIONSTAMP_SIZE + self._INDEX_SIZE))
      encoded_key += encode_versionstamp_index(versionstamp_index)

    return encoded_key

  def decode(self, kvs):
    """ Decodes Key-Values to a version entry.

    Args:
      kvs: An iterable containing KeyValue objects.
    Returns:
      A VersionEntry object.
    """
    path = Path.unpack(kvs[0].key, self.path_slice.start)[0]
    commit_versionstamp = kvs[0].key[self.versionstamp_slice]
    first_index = ord(kvs[0].key[self.index_slice])

    version = Int64.decode_bare(kvs[-1].value[self.version_slice])
    if first_index == 0:
      encoded_entity = b''.join([kv.value for kv in kvs])[self.entity_slice]
    else:
      encoded_entity = VersionEntry.INCOMPLETE

    return VersionEntry(self.project_id, self.namespace, path,
                        commit_versionstamp, version, encoded_entity)

  def get_slice(self, path, commit_versionstamp=None, read_versionstamp=None):
    """ Gets the range of keys relevant to the given constraints.

    Args:
      path: A tuple or protobuf path object.
      commit_versionstamp: The commit versionstamp for a specific entity
        version.
      read_versionstamp: The transaction's read versionstamp. All newer entity
        versions are ignored.
    Returns:
      A slice specifying the start and stop keys.
    """
    path_prefix = self._encode_path_prefix(path)
    if commit_versionstamp is not None:
      # All chunks for a given version.
      prefix = path_prefix + commit_versionstamp
      return slice(first_gt_or_equal(prefix + b'\x00'),
                   first_gt_or_equal(prefix + b'\xFF'))

    if read_versionstamp is not None:
      # All versions for a given path except those written after the
      # read_versionstamp.
      version_prefix = path_prefix + read_versionstamp
      return slice(first_gt_or_equal(path_prefix + b'\x00'),
                   first_gt_or_equal(version_prefix + b'\xFF'))

    # All versions for a given path.
    return slice(first_gt_or_equal(path_prefix + b'\x00'),
                 first_gt_or_equal(path_prefix + b'\xFF'))

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

  @classmethod
  def directory_path(cls, project_id, namespace):
    return project_id, cls.DIR_NAME, namespace

  def encode(self, path):
    """ Creates a Key-Value tuple for updating a group's commit versionstamp.

    Args:
      path: A tuple or protobuf path object.
    Returns:
      A (key, value) tuple suitable for set_versionstamped_value.
    """
    if not isinstance(path, tuple):
      path = Path.flatten(path)

    group_path = path[:2]
    return (self.encode_key(group_path),
            b'\x00' * VERSIONSTAMP_SIZE + encode_versionstamp_index(0))

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
  def __init__(self, tornado_fdb, directory_cache):
    self._tornado_fdb = tornado_fdb
    self._directory_cache = directory_cache

  @gen.coroutine
  def get_latest(self, tr, key, read_versionstamp=None, include_data=True,
                 snapshot=False):
    """ Gets the newest entity version for the given read versionstamp.

    Args:
      tr: An FDB transaction.
      key: A protubuf reference object.
      read_versionstamp: A 10-byte string specifying the FDB read versionstamp.
        Newer versionstamps are ignored.
      include_data: A boolean specifying whether or not to fetch all of the
        entity's Key-Values.
      snapshot: If True, the read will not cause a transaction conflict.
    """
    data_ns = yield self._data_ns_from_key(tr, key)
    desired_slice = data_ns.get_slice(
      key.path(), read_versionstamp=read_versionstamp)
    last_entry = yield self._last_version(
      tr, data_ns, desired_slice, include_data, snapshot=snapshot)
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
    if index_entry.kind in (u'__namespace__', u'__kind__'):
      entity = entity_pb.EntityProto()
      entity.mutable_key().MergeFrom(index_entry.key)
      entity.mutable_entity_group()
      version_entry = VersionEntry(
        index_entry.project_id, index_entry.namespace, index_entry.path,
        encoded_entity=entity.Encode())
      raise gen.Return(version_entry)

    version_entry = yield self.get_version_from_path(
      tr, index_entry.project_id, index_entry.namespace, index_entry.path,
      index_entry.commit_versionstamp, snapshot)
    raise gen.Return(version_entry)

  @gen.coroutine
  def get_version_from_path(self, tr, project_id, namespace, path,
                            commit_versionstamp, snapshot=False):
    """ Gets the entity data for a specific version.

    Args:
      tr: An FDB transaction.
      project_id: A string specifying the project ID.
      namespace: A string specifying the namespace.
      path: A tuple or protobuf path object.
      commit_versionstamp: A 10-byte string specyfing the FDB commit
        versionstamp.
      snapshot: If True, the read will not cause a transaction conflict.
    Returns:
      A VersionEntry or None.
    """
    data_ns = yield self._data_ns(tr, project_id, namespace)
    desired_slice = data_ns.get_slice(path, commit_versionstamp)
    results = yield ResultIterator(tr, self._tornado_fdb, desired_slice,
                                   snapshot=snapshot).list()
    raise gen.Return(data_ns.decode(results))

  @gen.coroutine
  def last_group_versionstamp(self, tr, project_id, namespace, group_path):
    """ Gets the most recent commit versionstamp for the entity group.

    Args:
      tr: An FDB transaction.
      project_id: A string specifying the project ID.
      namespace: A string specifying the namespace.
      group_path: A tuple containing the group's path elements.
    Returns:
      A 10-byte string specifying the versionstamp or None.
    """
    group_ns = yield self._group_updates_ns(tr, project_id, namespace)
    last_updated_versionstamp = yield self._tornado_fdb.get(
      tr, group_ns.encode_key(group_path))
    if not last_updated_versionstamp.present():
      return

    raise gen.Return(last_updated_versionstamp.value)

  @gen.coroutine
  def put(self, tr, key, version, encoded_entity):
    """ Writes a new version entry and updates the entity group versionstamp.

    Args:
      tr: An FDB transaction.
      key: A protobuf reference object.
      version: An integer specifying the new entity version.
      encoded_entity: A string specifying the encoded entity data.
    """
    data_ns = yield self._data_ns_from_key(tr, key)
    for fdb_key, val in data_ns.encode(key.path(), encoded_entity, version):
      tr.set_versionstamped_key(fdb_key, val)

    group_ns = yield self._group_updates_ns(
      tr, data_ns.project_id, data_ns.namespace)
    tr.set_versionstamped_value(*group_ns.encode(key.path()))

  @gen.coroutine
  def hard_delete(self, tr, version_entry):
    """ Deletes a version entry. Only the GC should use this.

    Args:
      tr: An FDB transaction.
      version_entry: A VersionEntry object.
    """
    data_ns = yield self._data_ns(
      tr, version_entry.project_id, version_entry.namespace)
    version_slice = data_ns.get_slice(version_entry.path,
                                      version_entry.commit_versionstamp)
    del tr[version_slice.start.key:version_slice.stop.key]

  @gen.coroutine
  def _data_ns(self, tr, project_id, namespace):
    directory = yield self._directory_cache.get(
      tr, DataNamespace.directory_path(project_id, namespace))
    raise gen.Return(DataNamespace(directory))

  @gen.coroutine
  def _data_ns_from_key(self, tr, key):
    project_id = decode_str(key.app())
    namespace = decode_str(key.name_space())
    data_ns = yield self._data_ns(tr, project_id, namespace)
    raise gen.Return(data_ns)

  @gen.coroutine
  def _group_updates_ns(self, tr, project_id, namespace):
    directory = yield self._directory_cache.get(
      tr, GroupUpdatesNS.directory_path(project_id, namespace))
    raise gen.Return(GroupUpdatesNS(directory))

  @gen.coroutine
  def _last_version(self, tr, data_ns, desired_slice, include_data=True,
                    snapshot=False):
    """ Gets the most recent entity data for a given slice.

    Args:
      tr: An FDB transaction.
      data_ns: A DataNamespace.
      desired_slice: A slice specifying the start and stop keys.
      include_data: A boolean indicating that all chunks should be fetched.
      snapshot: If True, the read will not cause a transaction conflict.
    Returns:
      A VersionEntry or None.
    """
    results, count, more_results = yield self._tornado_fdb.get_range(
      tr, desired_slice, limit=1, reverse=True, snapshot=snapshot)

    if not results:
      return

    last_chunk = results[0]
    entry = data_ns.decode([last_chunk])
    if not include_data or not entry.present or entry.complete:
      raise gen.Return(entry)

    # Retrieve the remaining chunks.
    version_slice = data_ns.get_slice(entry.path, entry.commit_versionstamp)
    remaining = slice(version_slice.start, first_gt_or_equal(last_chunk.key))
    results = yield ResultIterator(tr, self._tornado_fdb, remaining).list()
    raise gen.Return(data_ns.decode(results + [last_chunk]))
