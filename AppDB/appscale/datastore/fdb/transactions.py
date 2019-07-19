"""
This module stores and retrieves datastore transaction metadata. The
TransactionManager is the main interface that clients can use to interact with
the transaction layer. See its documentation for implementation details.
"""
from __future__ import division

import logging
import math
import random
import sys
from collections import defaultdict

import six
import six.moves as sm
from tornado import gen

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.dbconstants import BadRequest, InternalError
from appscale.datastore.fdb.codecs import (
  decode_str, encode_versionstamp_index, Int64, Path, Text, TransactionID)
from appscale.datastore.fdb.utils import (
  DS_ROOT, fdb, MAX_ENTITY_SIZE, ResultIterator, VERSIONSTAMP_SIZE)

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb

logger = logging.getLogger(__name__)


class TransactionMetadata(object):
  """
  A TransactionMetadata directory handles the encoding and decoding details for
  transaction metadata for a specific project.

  The directory path looks like (<project-dir>, 'transactions').
  Within this directory, keys are encoded as
  <scatter-byte> + <txid> + <rpc-type (optional)> + <rpc-details (optional)>.

  The <scatter-byte> is a single byte derived from the txid. Its purpose is to
  spread writes more evenly across the cluster and minimize hotspots. This is
  especially important for this index because each write is given a new, larger
  <txid> value than the last.

  The <txid> is an 8-byte integer that serves as a handle for the client to
  identify a transaction. It also serves as a read versionstamp for FDB
  transactions used within the datastore transaction.

  The initial creation of the datastore transaction does not specify any RPC
  details. The purpose of that KV is to verify that the datastore transaction
  exists (and the garbage collector hasn't cleaned it up) before committing it.

  The <rpc-type> is a single byte that indicates what kind of RPC is being
  logged as having occurred inside the transaction.

  The <rpc-details> encodes the necessary details in order for the datastore
  to reconstruct the RPCs that occurreed during the transaction when it comes
  time to commit the mutations.

  # TODO: Go into more detail about how different RPC types are encoded.
  """
  DIR_NAME = u'transactions'

  LOOKUPS = b'\x00'
  QUERIES = b'\x01'
  PUTS = b'\x02'
  DELETES = b'\x03'

  # The max number of bytes for each FDB value.
  _CHUNK_SIZE = 10000

  _ENTITY_LEN_SIZE = 3

  def __init__(self, directory):
    self.directory = directory

  @property
  def project_id(self):
    return self.directory.get_path()[len(DS_ROOT)]

  @classmethod
  def directory_path(cls, project_id):
    return project_id, cls.DIR_NAME

  def encode_start_key(self, scatter_val, commit_versionstamp=None):
    key = b''.join([self.directory.rawPrefix, six.int2byte(scatter_val),
                    commit_versionstamp or b'\x00' * VERSIONSTAMP_SIZE])
    if not commit_versionstamp:
      key += encode_versionstamp_index(len(key) - VERSIONSTAMP_SIZE)

    return key

  def encode_lookups(self, txid, keys):
    section_prefix = self._txid_prefix(txid) + self.LOOKUPS
    return self._encode_chunks(section_prefix, self._encode_keys(keys))

  def encode_query_key(self, txid, namespace, ancestor_path):
    section_prefix = self._txid_prefix(txid) + self.QUERIES
    encoded_ancestor = Text.encode(namespace) + Path.pack(ancestor_path[:2])
    return section_prefix + encoded_ancestor

  def encode_puts(self, txid, entities):
    section_prefix = self._txid_prefix(txid) + self.PUTS
    encoded_entities = [entity.Encode() for entity in entities]
    value = b''.join([b''.join([self._encode_entity_len(entity), entity])
                      for entity in encoded_entities])
    return self._encode_chunks(section_prefix, value)

  def encode_deletes(self, txid, keys):
    section_prefix = self._txid_prefix(txid) + self.DELETES
    return self._encode_chunks(section_prefix, self._encode_keys(keys))

  def decode_metadata(self, txid, kvs):
    lookup_rpcs = defaultdict(list)
    queried_groups = set()
    mutation_rpcs = []

    rpc_type_index = len(self._txid_prefix(txid))
    current_versionstamp = None
    for kv in kvs:
      rpc_type = kv.key[rpc_type_index]
      pos = rpc_type_index + 1
      if rpc_type == self.QUERIES:
        namespace, pos = Text.decode(kv.key, pos)
        group_path = Path.unpack(kv.key, pos)[0]
        queried_groups.add((namespace, group_path))
        continue

      rpc_versionstamp = kv.key[pos:pos + VERSIONSTAMP_SIZE]
      if rpc_type == self.LOOKUPS:
        lookup_rpcs[rpc_versionstamp].append(kv.value)
      elif rpc_type in (self.PUTS, self.DELETES):
        if current_versionstamp == rpc_versionstamp:
          mutation_rpcs[-1].append(kv.value)
        else:
          current_versionstamp = rpc_versionstamp
          mutation_rpcs.append([rpc_type, kv.value])
      else:
        raise InternalError(u'Unrecognized RPC type')

    lookups = set()
    mutations = []
    for chunks in six.itervalues(lookup_rpcs):
      lookups.update(self._unpack_keys(b''.join(chunks)))

    for rpc_info in mutation_rpcs:
      rpc_type = rpc_info[0]
      blob = b''.join(rpc_info[1:])
      if rpc_type == self.PUTS:
        mutations.extend(self._unpack_entities(blob))
      else:
        mutations.extend(self._unpack_keys(blob))

    return lookups, queried_groups, mutations

  def get_txid_slice(self, txid):
    prefix = self._txid_prefix(txid)
    return slice(fdb.KeySelector.first_greater_or_equal(prefix),
                 fdb.KeySelector.first_greater_or_equal(prefix + b'\xFF'))

  def get_expired_slice(self, scatter_byte, safe_versionstamp):
    prefix = self.directory.rawPrefix + six.int2byte(scatter_byte)
    return slice(
      fdb.KeySelector.first_greater_or_equal(prefix),
      fdb.KeySelector.first_greater_or_equal(prefix + safe_versionstamp))

  def _txid_prefix(self, txid):
    scatter_val, commit_versionstamp = TransactionID.decode(txid)
    return (self.directory.rawPrefix + six.int2byte(scatter_val) +
            commit_versionstamp)

  def _encode_keys(self, keys):
    return b''.join(
      [Text.encode(decode_str(key.name_space())) + Path.pack(key.path())
       for key in keys])

  def _unpack_keys(self, blob):
    keys = []
    pos = 0
    while pos < len(blob):
      namespace, pos = Text.decode(blob, pos)
      path, pos = Path.unpack(blob, pos)

      key = entity_pb.Reference()
      key.set_app(self.project_id)
      key.set_name_space(namespace)
      key.mutable_path().MergeFrom(Path.decode(path))
      keys.append(key)

    return keys

  def _unpack_entities(self, blob):
    pos = 0
    entities = []
    while pos < len(blob):
      entity_len = Int64.decode_bare(blob[pos:pos + self._ENTITY_LEN_SIZE])
      pos += self._ENTITY_LEN_SIZE
      entities.append(entity_pb.EntityProto(blob[pos:pos + entity_len]))
      pos += entity_len

    return entities

  def _encode_key_len(self, key):
    return bytes(bytearray([key.path().element_size()]))

  def _encode_entity_len(self, encoded_entity):
    if len(encoded_entity) > MAX_ENTITY_SIZE:
      raise BadRequest(u'Entity exceeds maximum size')

    return Int64.encode_bare(len(encoded_entity), self._ENTITY_LEN_SIZE)

  def _encode_chunks(self, section_prefix, value):
    full_prefix = section_prefix + b'\x00' * VERSIONSTAMP_SIZE
    versionstamp_index = encode_versionstamp_index(len(section_prefix))
    chunk_count = int(math.ceil(len(value) / self._CHUNK_SIZE))
    return tuple(
      (full_prefix + six.int2byte(index) + versionstamp_index,
       value[index * self._CHUNK_SIZE:(index + 1) * self._CHUNK_SIZE])
      for index in sm.range(chunk_count))


class TransactionManager(object):
  """
  The TransactionManager is the main interface that clients can use to interact
  with the transaction layer. It makes use of TransactionMetadata directories
  to handle the encoding and decoding details when satisfying requests.
  """
  def __init__(self, db, tornado_fdb, directory_cache):
    self._db = db
    self._tornado_fdb = tornado_fdb
    self._directory_cache = directory_cache

  @gen.coroutine
  def create(self, project_id):
    tr = self._db.create_transaction()
    tx_dir = yield self._tx_metadata(tr, project_id)
    scatter_val = random.randint(0, 15)
    tr.set_versionstamped_key(tx_dir.encode_start_key(scatter_val), b'')
    versionstamp_future = tr.get_versionstamp()
    yield self._tornado_fdb.commit(tr)
    txid = TransactionID.encode(scatter_val, versionstamp_future.wait().value)
    raise gen.Return(txid)

  @gen.coroutine
  def log_lookups(self, tr, project_id, get_request):
    txid = get_request.transaction().handle()
    tx_dir = yield self._tx_metadata(tr, project_id)
    for key, value in tx_dir.encode_lookups(txid, get_request.key_list()):
      tr.set_versionstamped_key(key, value)

  @gen.coroutine
  def log_query(self, tr, project_id, query):
    txid = query.transaction().handle()
    namespace = decode_str(query.name_space())
    if not query.has_ancestor():
      raise BadRequest(u'Queries in a transaction must specify an ancestor')

    tx_dir = yield self._tx_metadata(tr, project_id)
    tr[tx_dir.encode_query_key(txid, namespace, query.ancestor().path())] = b''

  @gen.coroutine
  def log_puts(self, tr, project_id, put_request):
    txid = put_request.transaction().handle()
    tx_dir = yield self._tx_metadata(tr, project_id)
    for key, value in tx_dir.encode_puts(txid, put_request.entity_list()):
      tr.set_versionstamped_key(key, value)

  @gen.coroutine
  def log_deletes(self, tr, project_id, delete_request):
    txid = delete_request.transaction().handle()
    tx_dir = yield self._tx_metadata(tr, project_id)
    for key, value in tx_dir.encode_deletes(txid, delete_request.key_list()):
      tr.set_versionstamped_key(key, value)

  @gen.coroutine
  def delete(self, tr, project_id, txid):
    tx_dir = yield self._tx_metadata(tr, project_id)
    txid_slice = tx_dir.get_txid_slice(txid)
    del tr[txid_slice.start.key:txid_slice.stop.key]

  @gen.coroutine
  def get_metadata(self, tr, project_id, txid):
    tx_dir = yield self._tx_metadata(tr, project_id)
    results = yield ResultIterator(tr, self._tornado_fdb,
                                   tx_dir.get_txid_slice(txid)).list()

    scatter_val, tx_start_versionstamp = TransactionID.decode(txid)
    if (not results or
        results[0].key != tx_dir.encode_start_key(scatter_val,
                                                  tx_start_versionstamp)):
      raise BadRequest(u'Transaction not found')

    raise gen.Return(tx_dir.decode_metadata(txid, results[1:]))

  @gen.coroutine
  def clear_range(self, tr, project_id, scatter_byte, safe_versionstamp):
    tx_dir = yield self._tx_metadata(tr, project_id)
    expired_slice = tx_dir.get_expired_slice(scatter_byte, safe_versionstamp)
    del tr[expired_slice.start.key:expired_slice.stop.key]

  @gen.coroutine
  def _tx_metadata(self, tr, project_id):
    path = TransactionMetadata.directory_path(project_id)
    directory = yield self._directory_cache.get(tr, path)
    raise gen.Return(TransactionMetadata(directory))
