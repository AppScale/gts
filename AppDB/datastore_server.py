#!/usr/bin/python
# Programmer: Navraj Chohan <nlake44@gmail.com>
# See LICENSE file
#
"""
This web service interfaces with the datastore. It takes protocol buffer
requests from AppServers and responds according to the type of request its
given (Put, Get, Delete, Query, etc).
"""
import __builtin__
import getopt
import itertools
import logging
import md5
import os
import sys
import threading

import tornado.httpserver
import tornado.ioloop
import tornado.web

import appscale_datastore_batch
import dbconstants
import groomer
import helper_functions

from zkappscale import zktransaction as zk
from zkappscale.zktransaction import ZKTransactionException

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api import api_base_pb
from google.appengine.api import datastore_errors

from google.appengine.datastore import cassandra_stub_util
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.datastore import entity_pb
from google.appengine.datastore import sortable_pb_encoder

from google.appengine.runtime import apiproxy_errors

from google.appengine.ext.remote_api import remote_api_pb

from M2Crypto import SSL

# Buffer type used for key storage in the datastore
buffer = __builtin__.buffer

# Global for accessing the datastore. An instance of DatastoreDistributed.
datastore_access = None

# ZooKeeper global variable for locking
zookeeper = None

entity_pb.Reference.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Query.__hash__ = lambda self: hash(self.Encode())

# The datastores supported for this version of the AppScale datastore
VALID_DATASTORES = ['cassandra', 'hbase', 'hypertable']

# Port this service binds to if using SSL
DEFAULT_SSL_PORT = 8443

# Port this service binds to (unencrypted and hence better performance)
DEFAULT_PORT = 4080

# IDs are acquired in block sizes of this
BLOCK_SIZE = 10000

# The length of an ID string meant to make sure we have lexigraphically ordering
ID_KEY_LENGTH = 10

# Tombstone value for soft deletes
TOMBSTONE = "APPSCALE_SOFT_DELETE"

# Local datastore location through nginx.
LOCAL_DATASTORE = "localhost:8888"

 
class DatastoreDistributed():
  """ AppScale persistent layer for the datastore API. It is the 
      replacement for the AppServers to persist their data into 
      a distributed datastore instead of a flat file.
  """
  # Max number of results for a query
  _MAXIMUM_RESULTS = 1000000

  # The number of entries looked at when doing a composite query
  # It will keep looking at this size window when getting the result
  _MAX_COMPOSITE_WINDOW = 1000

  # Maximum amount of filter and orderings allowed within a query
  _MAX_QUERY_COMPONENTS = 63

 
  # For enabling and disabling range inclusivity
  _ENABLE_INCLUSIVITY = True
  _DISABLE_INCLUSIVITY = False

  # Delimiter between app names and namespace and the rest of an entity key
  _NAMESPACE_SEPARATOR = '/'

  # This is the terminating string for range queries
  _TERM_STRING = chr(255) * 500

  # When assigning the first allocated ID, give this value
  _FIRST_VALID_ALLOCATED_ID = 1

  # The key we use to lock for allocating new IDs
  _ALLOCATE_ROOT_KEY = "__allocate__"

  def __init__(self, datastore_batch, zookeeper=None):
    """
       Constructor.
     
     Args:
       datastore_batch: a reference to the batch datastore interface .
       zookeeper: a reference to the zookeeper interface.
    """
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
      '%(lineno)s %(message)s ', level=logging.INFO)
    logging.debug("Started logging")

    # Each entry contains a tuple (last_accessed_timestamp, namespace)
    # The key is the <app_id>/<namespace>
    self.__namespaces = []

    # Each entry contains a tuple (last_accessed_timestamp, index_name)
    # The key is the <app_id>/<namespace>/<kind>/<index>
    self.__indexes = {}

    #TODO: Use locks for operations that should be atomic, i.e., we are
    # updating global shared state
    # lock for namespace and indexes during periodic garbage collection
    self.__lock = threading.Lock()

    # datastore accessor used by this class to do datastore operations
    self.datastore_batch = datastore_batch 

    # zookeeper instance for accesing ZK functionality
    self.zookeeper = zookeeper

  @staticmethod
  def get_entity_kind(key_path):
    """ Returns the Kind of the Entity. A Kind is like a type or a 
        particular class of entity.

    Args:
        key_path: the key path of entity
    Returns:
        kind of the entity
    """
    if isinstance(key_path, entity_pb.EntityProto):
      key_path = key_path.key()
    return key_path.path().element_list()[-1].type()

  def get_entity_key(self, prefix, pb):
    """ Returns the key for the entity table
    
    Args:
        prefix: app name and namespace string
                example-- 'guestbook/mynamespace'
        pb: protocol buffer that we will encode the index name
    Returns:
        Key for entity table
    """
    return buffer(prefix + self._NAMESPACE_SEPARATOR) + \
                  self.__encode_index_pb(pb) 

  def get_kind_key(self, prefix, key_path):
    """ Returns a key for the kind table
    
    Args:
        prefix: App name and namespace string
        key_path: Key path to build row key with
    Returns:
        Row key for kind table
    """
    path = []
    # reverse of index paths because child kind must come first
    all_reversed = key_path.element_list()[::-1]
    for e in all_reversed:
      if e.has_name():
        key_id = e.name()
      elif e.has_id():
        # make sure ids are ordered lexigraphically by making sure they 
        # are of set size i.e. 2 > 0003 but 0002 < 0003
        key_id = str(e.id()).zfill(ID_KEY_LENGTH)
      path.append('%s:%s' % (e.type(), key_id))
    encoded_path = '!'.join(path)
    encoded_path += '!'
    
    return prefix + self._NAMESPACE_SEPARATOR + encoded_path
    
  @staticmethod
  def __encode_index_pb(pb):
    """ Returns an encoded protocol buffer.
  
    Args:
        pb: The protocol buffer to encode.
    Returns:
        An encoded protocol buffer.
    """
    def _encode_path(pb):
      """ Takes a protocol buffer and returns the encoded path """
      path = []
      for e in pb.element_list():
        if e.has_name():
          key_id = e.name()
        elif e.has_id():
          key_id = str(e.id()).zfill(ID_KEY_LENGTH)
        path.append('%s:%s' % (e.type(), key_id))
      val = '!'.join(path)
      val += '!'
      return val

    if isinstance(pb, entity_pb.PropertyValue) and pb.has_uservalue():
      userval = entity_pb.PropertyValue()
      userval.mutable_uservalue().set_email(pb.uservalue().email())
      userval.mutable_uservalue().set_auth_domain(pb.uservalue().auth_domain())
      userval.mutable_uservalue().set_gaiaid(0)
      pb = userval

    encoder = sortable_pb_encoder.Encoder()
    pb.Output(encoder)

    if isinstance(pb, entity_pb.PropertyValue):
      return buffer(encoder.buffer().tostring())
    elif isinstance(pb, entity_pb.Path):
      return buffer(_encode_path(pb))

  def validate_app_id(self, app_id):
    """ Verify that this is the stub for app_id.

    Args:
      app_id: An application ID.
    Raises:
      AppScaleBadArg: If the application id is not set.
    """
    if not app_id: 
      raise dbconstants.AppScaleBadArg("Application name must be set")

  def validate_key(self, key):
    """ Validate this key by checking to see if it has a name or id.

    Args:
      key: entity_pb.Reference
    Raises:
      datastore_errors.BadRequestError: if the key is invalid
      TypeError: if key is not of entity_pb.Reference
    """

    if not isinstance(key, entity_pb.Reference): 
      raise TypeError("Expected type Reference")

    self.validate_app_id(key.app())

    for elem in key.path().element_list():
      if elem.has_id() and elem.has_name():
        raise datastore_errors.BadRequestError(
            'each key path element should have id or name but not both: %r'
            % key)

  def get_index_key(self, app_id, name_space, kind, index_name):
    """ Returns key string for storing namespaces.

    Args:
      app_id: The app ID.
      name_space: The per-app namespace name.
      kind: The per-app kind name.
      index_name: The per-app index name.
    Returns:
      Key string for storing namespaces.
    """
    return app_id + "/" + name_space + "/" + kind + "/" + index_name

  def configure_namespace(self, prefix, app_id, name_space):
    """ Stores a key for the given namespace.

    Args:
      prefix: The namespace prefix to configure.
      app_id: The app ID.
      name_space: The per-app namespace name.
    Returns:
      True on success.
    """
    vals = {}
    row_key = prefix
    vals[row_key] = {"namespaces":name_space}
    self.datastore_batch.batch_put_entity(dbconstants.APP_NAMESPACE_TABLE, 
                          [row_key], 
                          dbconstants.APP_NAMESPACE_SCHEMA, 
                          vals)
    return True

  def get_table_prefix(self, data):
    """ Returns the namespace prefix for a query.

    Args:
      data: An Entity, Key or Query PB, or an (app_id, ns) tuple.
    Returns:
      A valid table prefix.
    """
    if isinstance(data, entity_pb.EntityProto):
      data = data.key()

    if not isinstance(data, tuple):
      data = (data.app(), data.name_space())

    prefix = ('%s/%s' % data).replace('"', '""')

    if data not in self.__namespaces:
      self.configure_namespace(prefix, *data)
      self.__namespaces.append(data)

    return prefix

  def get_index_key_from_params(self, params):
    """Returns the index key from params.

    Args:
       params: a list of strings to be concatenated to form the key made of:
              prefix, kind, property name, and path
    Returns:
       a string
    Raises:
       ValueError: if params are not of the correct cardinality
    """
    if len(params) != 5 and len(params) != 4: 
      raise ValueError("Bad number of params")

    if params[-1] == None:
      # strip off the last None item
      key = '/'.join(params[:-1]) + '/'
    else:
      key = '/'.join(params) 
    return key

  def get_index_kv_from_tuple(self, tuple_list, reverse=False):
    """ Returns keys/value of indexes for a set of entities.
 
    Args: 
       tuple_list: A list of tuples of prefix and pb entities
       reverse: if these keys are for the descending table
    Returns:
       A list of keys and values of indexes
    """
    all_rows = []
    for prefix, e in tuple_list:
      for p in e.property_list():
        val = str(self.__encode_index_pb(p.value()))
        # Remove the first binary character for lexigraphical ordering
        val = str(val[1:])

        if reverse:
          val = helper_functions.reverse_lex(val)

        params = [prefix, 
                  self.get_entity_kind(e), 
                  p.name(), 
                  val, 
                  str(self.__encode_index_pb(e.key().path()))]

        index_key = self.get_index_key_from_params(params)
        p_vals = [index_key, 
                  buffer(prefix + '/') + \
                  self.__encode_index_pb(e.key().path())] 
        all_rows.append(p_vals)
    return tuple(ii for ii in all_rows)

  def delete_index_entries(self, entities):
    """ Deletes the entities in the DB.

    Args:
       entities: A list of entities for which their 
                 indexes are to be deleted
    """

    if len(entities) == 0: 
      return

    entities_tuple = sorted((self.get_table_prefix(x), x) for x in entities)
    asc_index_keys = self.get_index_kv_from_tuple(entities_tuple, 
                                                     reverse=False)
    desc_index_keys = self.get_index_kv_from_tuple(entities_tuple, 
                                                     reverse=True)
    # Remove the value, just get keys
    asc_index_keys = [x[0] for x in asc_index_keys] 
    desc_index_keys = [x[0] for x in desc_index_keys] 
    # TODO Consider doing these in parallel with threads
    self.datastore_batch.batch_delete(dbconstants.ASC_PROPERTY_TABLE, 
                                      asc_index_keys, 
                                      column_names=dbconstants.PROPERTY_SCHEMA)
    self.datastore_batch.batch_delete(dbconstants.DSC_PROPERTY_TABLE, 
                                      desc_index_keys,
                                      column_names=dbconstants.PROPERTY_SCHEMA)
    
  def insert_entities(self, entities, txn_hash):
    """Inserts or updates entities in the DB.

    Args:      
      entities: A list of entities to store.
      txn_hash: A mapping of root keys to transaction IDs.
    """

    def row_generator(entities):
      """ Generates keys and encoded entities for a list of entities. 

      Args:
        entities: A list of entity objects
      """
      for prefix, e in entities:
        yield (self.get_entity_key(prefix, e.key().path()),
               buffer(e.Encode()))

    def kind_row_generator(entities):
      """ Generates keys for the kind table and a reference key to the entity
          table.

      Args:
        entities: A list of entitiy objects
      """
      for prefix, e in entities:
        # yield a tuple of kind key and a reference to entity table
        yield (self.get_kind_key(prefix, e.key().path()),
               self.get_entity_key(prefix, e.key().path()))

    logging.debug("Inserting entities {0} in DB with transaction hash {1}"
      .format(str(entities), str(txn_hash)))
    row_values = {}
    row_keys = []

    kind_row_keys = []
    kind_row_values = {}

    entities = sorted((self.get_table_prefix(x), x) for x in entities)
    logging.debug("Entities with table prefix are: {0}".format(str(entities)))

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = tuple(row_generator(group))
      new_row_keys = [str(ii[0]) for ii in group_rows]
      row_keys += new_row_keys

      for ii in group_rows:
        logging.debug("Trying to get root entity from entity key: {0}".\
          format(str(ii[0])))
        logging.debug("Root entity is: {0}".\
          format(self.get_root_key_from_entity_key(str(ii[0]))))
        logging.debug("Transaction hash is: {0}".format(str(txn_hash)))
        txn_id = txn_hash[self.get_root_key_from_entity_key(str(ii[0]))]
        row_values[str(ii[0])] = \
                           {dbconstants.APP_ENTITY_SCHEMA[0]:str(ii[1]), #ent
                           dbconstants.APP_ENTITY_SCHEMA[1]:str(txn_id)} #txnid

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      kind_group_rows = tuple(kind_row_generator(group))
      new_kind_keys = [str(ii[0]) for ii in kind_group_rows]
      kind_row_keys += new_kind_keys

      for ii in kind_group_rows:
        kind_row_values[str(ii[0])] = \
          {dbconstants.APP_KIND_SCHEMA[0]:str(ii[1])}


    # TODO do these in ||                        
    self.datastore_batch.batch_put_entity(dbconstants.APP_ENTITY_TABLE, 
                                          row_keys, 
                                          dbconstants.APP_ENTITY_SCHEMA, 
                                          row_values)    

    self.update_journal(row_keys, row_values, txn_hash)

    self.datastore_batch.batch_put_entity(dbconstants.APP_KIND_TABLE,
                                          kind_row_keys,
                                          dbconstants.APP_KIND_SCHEMA, 
                                          kind_row_values) 


  def insert_index_entries(self, entities):
    """ Inserts index entries for the supplied entities.

    Args:
      entities: A list of tuples of prefix and entities 
                to create index entries for.
    """

    entities = sorted((self.get_table_prefix(x), x) for x in entities)
 
    row_keys = []
    rev_row_keys = []
    row_values = {}
    rev_row_values = {}

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = self.get_index_kv_from_tuple(group, False)
      row_keys = [str(ii[0]) for ii in group_rows]
      for ii in group_rows:
        row_values[str(ii[0])] = {'reference': str(ii[1])}
 
    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      rev_group_rows = self.get_index_kv_from_tuple(group, True)
      rev_row_keys = [str(ii[0]) for ii in rev_group_rows]
      for ii in rev_group_rows:
        rev_row_values[str(ii[0])] = {'reference': str(ii[1])}

    # TODO  these in parallel
    self.datastore_batch.batch_put_entity(dbconstants.ASC_PROPERTY_TABLE, 
                          row_keys, 
                          dbconstants.PROPERTY_SCHEMA, 
                          row_values)

    self.datastore_batch.batch_put_entity(dbconstants.DSC_PROPERTY_TABLE, 
                          rev_row_keys,  
                          dbconstants.PROPERTY_SCHEMA,
                          rev_row_values)

  def acquire_next_id_from_db(self, prefix):
    """ Gets the next available ID for key assignment.

    Args: 
      prefix: A table namespace prefix
    Returns:
      next id available
    """  
    res  = self.datastore_batch.batch_get_entity(dbconstants.APP_ID_TABLE, 
                                                 [prefix], 
                                                 dbconstants.APP_ID_SCHEMA)
    if dbconstants.APP_ID_SCHEMA[0] in res[prefix]:
      return int(res[prefix][dbconstants.APP_ID_SCHEMA[0]])
    return self._FIRST_VALID_ALLOCATED_ID

  def allocate_ids(self, prefix, size, max_id=None, num_retries=0):
    """ Allocates IDs from either a local cache or the datastore. 

    Args:
      prefix: A table namespace prefix.
      size: Number of IDs to allocate.
      max_id: If given increase the next IDs to be greater than this value
      num_retries: The number of retries left to get an ID.
    Returns:
      tuple of start and end ids
    Raises: 
      ValueError: if size is less than or equal to 0
    """
    if size and max_id:
      raise ValueError("Both size and max cannot be set.")
    txnid = self.zookeeper.get_transaction_id(prefix)
    try:
      self.zookeeper.acquire_lock(prefix, txnid, self._ALLOCATE_ROOT_KEY)
      current_id = self.acquire_next_id_from_db(prefix)

      if size:
        next_id = current_id + size

      if max_id:
        next_id = max(current_id, max_id + 1)

      cell_values = {prefix: {dbconstants.APP_ID_SCHEMA[0]: str(next_id)}} 

      self.datastore_batch.batch_put_entity(dbconstants.APP_ID_TABLE, 
                           [prefix],  
                           dbconstants.APP_ID_SCHEMA,
                           cell_values)
    except ZKTransactionException, zk_exception:
      if not self.zookeeper.notify_failed_transaction(prefix, txnid):
        logging.error("Unable to invalidate transaction for {0} txnid: {1}"\
          .format(prefix, txnid))
      if num_retries > 0:
        return self.allocate_ids(prefix, size, max_id=max_id, 
          num_retries=num_retries - 1)
      else:
        raise zk_exception
    finally:
      self.zookeeper.release_lock(prefix, txnid)

    start = current_id
    end = next_id - 1

    return start, end

  def put_entities(self, app_id, entities, txn_hash):
    """ Updates indexes of existing entities, inserts new entities and 
        indexes for them.

    Args:
       app_id: The application ID.
       entities: List of entities.
       txn_hash: A mapping of root keys to transaction IDs.
    """
    sorted_entities = sorted((self.get_table_prefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(sorted_entities, lambda x: x[0]):
      keys = [e.key() for e in entities]
      self.delete_entities(app_id, keys, txn_hash, soft_delete=False)
      self.insert_entities(entities, txn_hash)
      self.insert_index_entries(entities)

  def delete_entities(self, app_id, keys, txn_hash, soft_delete=False):
    """ Deletes the entities and the indexes associated with them.

    Args:
       app_id: The application ID.
       keys: list of keys to be deleted.
       txn_hash: A mapping of root keys to transaction IDs.
       soft_delete: Boolean if we should soft delete entities.
                    Default is to not delete entities from the 
                    entity table (neither soft or hard). 
    """
    def row_generator(key_list):
      """ Generates a ruple of keys and encoded entities. """
      for prefix, k in key_list:
        yield (self.get_entity_key(prefix, k.path()),
               buffer(k.Encode()))

    def kind_row_generator(key_list):
      """ Generates key/values for the kind table. """
      for prefix, k in key_list:
        # yield a tuple of kind key and a reference to entity table
        yield (self.get_kind_key(prefix, k.path()),
               self.get_entity_key(prefix, k.path()))
 
    row_keys = []
    kind_keys = []

    entities = sorted((self.get_table_prefix(x), x) for x in keys)

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = tuple(row_generator(group))
      new_row_keys = [str(ii[0]) for ii in group_rows]
      row_keys += new_row_keys

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = tuple(kind_row_generator(group))
      new_row_keys = [str(ii[0]) for ii in group_rows]
      kind_keys += new_row_keys

    # Must fetch the entities to get the keys of indexes before deleting
    ret = self.datastore_batch.batch_get_entity(dbconstants.APP_ENTITY_TABLE, 
                                                row_keys,
                                                dbconstants.APP_ENTITY_SCHEMA)

    self.register_old_entities(ret, txn_hash, app_id)

    if soft_delete:
      row_values = {}
      for rk in row_keys:
        root_key = self.get_root_key_from_entity_key(rk)
        row_values[rk] = {dbconstants.APP_ENTITY_SCHEMA[0]:
                                TOMBSTONE, 
                          dbconstants.APP_ENTITY_SCHEMA[1]:
                                str(txn_hash[root_key])
                         }
      #TODO do these in ||
      self.datastore_batch.batch_put_entity(dbconstants.APP_ENTITY_TABLE, 
                                          row_keys, 
                                          dbconstants.APP_ENTITY_SCHEMA, 
                                          row_values)    
      self.update_journal(row_keys, row_values, txn_hash)

    self.datastore_batch.batch_delete(dbconstants.APP_KIND_TABLE,
                                      kind_keys, 
                                      column_names=dbconstants.APP_KIND_SCHEMA)

    entities = []
    for row_key in ret:
      # Entities may not exist if this is the first put
      if dbconstants.APP_ENTITY_SCHEMA[0] in ret[row_key] and\
           not ret[row_key][dbconstants.APP_ENTITY_SCHEMA[0]].\
           startswith(TOMBSTONE):
        ent = entity_pb.EntityProto()
        ent.ParseFromString(ret[row_key][dbconstants.APP_ENTITY_SCHEMA[0]])
        entities.append(ent)

    self.delete_index_entries(entities)

  def get_journal_key(self, row_key, version):
    """ Creates a string for a journal key.
  
    Args:
      row_key: The entity key for which we want to create a journal key.
      version: The version of the entity we are going to save.
    Returns:
      A string representing a journal key.
    """
    row_key += "/"
    zero_padded_version = ("0" * (ID_KEY_LENGTH - len(str(version)))) +\
                           str(version)
    row_key += zero_padded_version
    return row_key

  def update_journal(self, row_keys, row_values, txn_hash):
    """ Save new versions of entities to the journal.
    
    Args: 
      row_keys: A list of keys we will be updating.
      row_values: Dictionary of values we are storing into the journal.
      txn_hash: A hash mapping root keys to transaction IDs.
    Raises:
      
    """
    journal_keys = []
    journal_values = {}
    for row_key in row_keys:
      root_key = self.get_root_key_from_entity_key(row_key)
      journal_key = self.get_journal_key(row_key, txn_hash[root_key])
      journal_keys.append(journal_key)
      column = dbconstants.JOURNAL_SCHEMA[0]
      value = row_values[row_key]\
              [dbconstants.APP_ENTITY_SCHEMA[0]] # encoded entity
      journal_values[journal_key] = {column: value}

    self.datastore_batch.batch_put_entity(dbconstants.JOURNAL_TABLE,
                          journal_keys,
                          dbconstants.JOURNAL_SCHEMA,
                          journal_values)

  def register_old_entities(self, old_entities, txn_hash, app_id):
    """ Tell ZooKeeper about the old versions to enable rollback
        if needed.
    Args:
      old_entities: A database result from the APP_ENTITY_TABLE.
                    {'key':{'encoded_entity':'v1', 'txnid':'v2'}
      txn_hash: A dictionary mapping root keys to txn ids.
      app_id: The application identifier.
    Raises:
      ZKTransactionException: If we are unable to register a key/entity.
    """
    for row_key in old_entities:
      if dbconstants.APP_ENTITY_SCHEMA[1] in old_entities[row_key]:
        prev_version = long(old_entities[row_key]\
            [dbconstants.APP_ENTITY_SCHEMA[1]])
        # Validate and get the correct version for each key
        root_key = self.get_root_key_from_entity_key(row_key)
        valid_prev_version = self.zookeeper.get_valid_transaction_id(
                                    app_id, prev_version, row_key)
        # Guard against re-registering the rollback version if 
        # we're updating the same key repeatedly in a transaction.
        if txn_hash[root_key] != valid_prev_version:
          self.zookeeper.register_updated_key(app_id, txn_hash[root_key], 
                                        valid_prev_version, row_key) 

  def dynamic_put(self, app_id, put_request, put_response):
    """ Stores and entity and its indexes in the datastore.
    
    Args:
      app_id: Application ID.
      put_request: Request with entities to store.
      put_response: The response sent back to the app server.
    Raises:
      ZKTransactionException: If we are unable to acquire/release ZooKeeper locks.
    """
    entities = put_request.entity_list()
    for entity in entities:
      self.validate_key(entity.key())

      for prop in itertools.chain(entity.property_list(),
                                  entity.raw_property_list()):
        if prop.value().has_uservalue():
          uid = md5.new(prop.value().uservalue().email().lower()).digest()
          uid = '1' + ''.join(['%02d' % ord(x) for x in uid])[:20]
          prop.mutable_value().mutable_uservalue().set_obfuscated_gaiaid(uid)

      last_path = entity.key().path().element_list()[-1]
      if last_path.id() == 0 and not last_path.has_name():
        try: 
          id_, _ = self.allocate_ids(self.get_table_prefix(entity.key()), 1,
            num_retries=3)
        except ZKTransactionException, zk_exception:
          logging.error("Unable to attain a new ID for {0}"\
            .format(str(entity.key())))
          raise zk_exception

        last_path.set_id(id_)

        group = entity.mutable_entity_group()
        root = entity.key().path().element(0)
        group.add_element().CopyFrom(root)
    # This has maps transaction IDs to root keys
    txn_hash = {}
    try:
      if put_request.has_transaction():
        txn_hash = self.acquire_locks_for_trans(entities, 
                        put_request.transaction().handle())
      else:
        txn_hash = self.acquire_locks_for_nontrans(app_id, entities) 

      self.put_entities(app_id, entities, txn_hash)

      if not put_request.has_transaction():
        self.release_locks_for_nontrans(app_id, entities, txn_hash)
      put_response.key_list().extend([e.key() for e in entities])
    except ZKTransactionException, zkte:
      logging.info("Concurrent transaction exception for app id {0} with " \
        "info {1}".format(app_id, str(zkte)))
      for root_key in txn_hash:
        self.zookeeper.notify_failed_transaction(app_id, txn_hash[root_key])
      raise zkte

  def get_root_key_from_entity_key(self, entity_key):
    """ Extract the root key from an entity key. We 
        remove any excess children from a string to get to
        the root key.
    
    Args:
      entity_key: A string or Key object representing a row key.
    Returns:
      The root key extracted from the row key.
    Raises:
      TypeError: If the type is not supported.
    """
    if isinstance(entity_key, str):
      tokens = entity_key.split('!')
      return tokens[0] + '!'
    elif isinstance(entity_key, entity_pb.Reference):
      app_id = entity_key.app()
      path = entity_key.path()
      element_list = path.element_list()
      return self.get_root_key(app_id, entity_key.name_space(), element_list)
    else:
      raise TypeError("Unable to get root key from given type of %s" % \
                      entity_key.__class__)  

  def acquire_locks_for_nontrans(self, app_id, entities):
    """ Acquires locks for non-transaction operations. 

    Acquires locks and transaction handlers for each entity group in the set of 
    entities.  It is possible that multiple entities share the same group, and 
    hence they can use the same lock when being updated. The reason we get locks 
    for puts in non-transactional puts is that it prevents race conditions of 
    existing transactions that are on-going. It maintains ACID semantics.
    Args:
      app_id: The application ID.
      entities: A list of entities (either entity_pb.EntityProto or a 
                entity_pb.Reference) that we want to acquire locks for.
    Returns:
      A hash of root keys mapping to transaction IDs.
    Raises:
     TypeError: If args are the wrong type.
    """
    # Key tuples are comprised of the table prefix and entity key.
    key_tuples = []
    txn_hash = {} 
    if not isinstance(entities, list):
      raise TypeError("Expected a list and got %s" % entities.__class__)
    for ent in entities:
      if isinstance(ent, entity_pb.Reference):
        key_tuples.append((self.get_table_prefix(ent), 
          self.get_root_key_from_entity_key(ent)))
      elif isinstance(ent, entity_pb.EntityProto):
        key_tuples.append((self.get_table_prefix(ent.key()), 
          self.get_root_key_from_entity_key(ent.key())))
      else:
        raise TypeError("Excepted either a reference or an EntityProto, "\
          "got {0}".format(ent.__class__))

    # Remove all duplicate (prefix/root keys) tuples.
    key_tuples = list(set(key_tuples))
    try:
      for key_tuple in key_tuples: 
        txnid = self.setup_transaction(app_id, is_xg=False)
        txn_hash[key_tuple[1]] = txnid
        self.zookeeper.acquire_lock(key_tuple[0], txnid, key_tuple[1])
    except ZKTransactionException, zkte:
      logging.info("Concurrent transaction exception for app id {0} with " \
        "info {1}".format(app_id, str(zkte)))
      for key_tuple in txn_hash:
        self.zookeeper.notify_failed_transaction(app_id, txn_hash[key_tuple[0]])
      raise zkte
    return txn_hash
      
  def get_root_key(self, app_id, ns, ancestor_list):
    """ Gets the root key string from an ancestor listing.
   
    Args:
      app_id: The app ID of the listing.
      ns: The namespace of the entity.
      ancestor_list: The ancestry of a given entity.
    Returns:
      A string representing the root key of an entity.
    """
    prefix = self.get_table_prefix((app_id, ns))
    first_ent = ancestor_list[0]
    if first_ent.has_name():
      key_id = first_ent.name()
    elif first_ent.has_id():
      # make sure ids are ordered lexigraphically by making sure they 
      # are of set size i.e. 2 > 0003 but 0002 < 0003
      key_id = str(first_ent.id()).zfill(ID_KEY_LENGTH)
    return prefix + self._NAMESPACE_SEPARATOR + \
           first_ent.type() + ":" + key_id + "!"

  def is_instance_wrapper(self, obj, expected_type):
    """ A wrapper for isinstance for mocking purposes. 

    Return whether an object is an instance of a class or of a subclass thereof.
    With a type as second argument, return whether that is the object's type.

    Args:
      obj: The object to check.
      expected_type: A instance type we are comparing obj's type to.
    Returns: 
      True if obj is of type expected_type, False otherwise. 
    """
    return isinstance(obj, expected_type) 
 
  def acquire_locks_for_trans(self, entities, txnid):
    """ Acquires locks for entities for one particular entity group. 
 
    Args:
      entities: A list of entities (entity_pb.EntityProto or entity_pb.Reference)
                for which are are getting a lock for.
      txnid: The transaction ID handler.
    Returns:
      A hash mapping root keys to transaction IDs.
    Raises:
      ZKTransactionException: If lock is not obtainable.
      TypeError: If args are of incorrect types.
    """
    # Key tuples are the prefix and the root key for which we're getting locks.
    key_tuples = []
    txn_hash = {}
    if not self.is_instance_wrapper(entities, list):
      raise TypeError("Expected a list and got %s" % entities.__class__)
    for ent in entities:
      if self.is_instance_wrapper(ent, entity_pb.Reference):
        key_tuples.append((self.get_table_prefix(ent), 
          self.get_root_key_from_entity_key(ent)))
      elif self.is_instance_wrapper(ent, entity_pb.EntityProto):
        key_tuples.append((self.get_table_prefix(ent.key()),
          self.get_root_key_from_entity_key(ent.key())))
      else:
        raise TypeError("Excepted either a reference or an EntityProto"
           "got {0}".format(ent.__class__))

    if entities == []:
      return {}

    if self.is_instance_wrapper(entities[0], entity_pb.Reference):
      app_id = entities[0].app()
    else:
      app_id = entities[0].key().app()

    # Remove all duplicate root keys.
    key_tuples = list(set(key_tuples))
    try:
      for key_tuple in key_tuples:
        txn_hash[key_tuple[0]] = txnid
        self.zookeeper.acquire_lock(key_tuple[0], txnid, key_tuple[1])
    except ZKTransactionException, zkte:
      logging.info("Concurrent transaction exception for app id {0} with " \
        "info {1}".format(app_id, str(zkte)))
      for root_key in txn_hash:
        self.zookeeper.notify_failed_transaction(app_id, txn_hash[root_key])
      raise zkte
    return txn_hash

  def release_locks_for_nontrans(self, app_id, entities, txn_hash):
    """  Releases locks for non-transactional puts.
  
    Args:
      entities: List of entities for which we are releasing locks. Can
                be either entity_pb.EntityProto or entity_pb.Reference.
      txn_hash: A hash mapping root keys to transaction IDs.
    Raises:
      ZKTransactionException: If we are unable to release locks.
    """
    root_keys = []
    for ent in entities:
      if isinstance(ent, entity_pb.EntityProto):
        ent = ent.key()
      root_keys.append(self.get_root_key_from_entity_key(ent))

    # Remove all duplicate root keys
    root_keys = list(set(root_keys))
    for root_key in root_keys: 
      txnid = txn_hash[root_key]
      self.zookeeper.release_lock(app_id, txnid)

  def validated_result(self, app_id, db_results, current_ongoing_txn=0):
    """ Takes database results from the entity table and returns
        an updated result if any of the entities were using 
        blacklisted transaction IDs. 
   
    Args:
      app_id: The application ID whose results we are validating.
      db_results: Database result from the entity table.
      current_ongoing_txn: Current transaction ID, 0 if not in a transaction.
    Returns:
      A modified copy of db_results whose values have been validated.
    Raises:
      TypeError: If db_results is not the right type.
    """
    if isinstance(db_results, dict): 
      return self.validated_dict_result(app_id, 
                                        db_results, 
                                        current_ongoing_txn=0)
    elif isinstance(db_results, list):
      return self.validated_list_result(app_id,  
                                        db_results,
                                        current_ongoing_txn=0)
    else:
      raise TypeError("db_results should be either a list or dict")

  def validated_list_result(self, app_id, db_results, current_ongoing_txn=0):
    """
        Takes database results from the entity table and returns
        an updated result list (came from a query) if any of the 
        entities were using blacklisted transaction IDs. 
   
    Args:
      app_id: The application ID whose results we are validating.
      db_results: Database result from the entity table.
      current_ongoing_txn: Current transaction ID, 0 if not in a transaction.
    Returns:
      A modified copy of db_results whose values have been validated.

    """
    journal_result_map = {}
    journal_keys = []
    # Get all the valid versions of journal entries if needed.
    for index, dict_entry in enumerate(db_results):
      row_key = dict_entry.keys()[0]
      current_version = \
          long(dict_entry[row_key][dbconstants.APP_ENTITY_SCHEMA[1]])
      trans_id = self.zookeeper.get_valid_transaction_id(\
                             app_id, current_version, row_key)
      if current_ongoing_txn != 0 and \
           current_version == current_ongoing_txn:
        # This value has been updated from within an ongoing transaction and
        # hence can be seen from within this scope for serializability.
        continue
      if current_version != trans_id:
        journal_key = self.get_journal_key(row_key, trans_id)
        journal_keys.append(journal_key)
        # Index is used here for lookup when replacing back into db_results.
        journal_result_map[journal_key] = (index, row_key, trans_id)

    journal_entities = self.datastore_batch.batch_get_entity(
                            dbconstants.JOURNAL_TABLE,
                            journal_keys,
                            dbconstants.JOURNAL_SCHEMA)

    if not journal_result_map: 
      return db_results


    for journal_key in journal_result_map:
      index, row_key, trans_id = journal_result_map[journal_key]
      if dbconstants.JOURNAL_SCHEMA[0] in journal_entities[journal_key]:
        db_results[index][row_key] = {
          dbconstants.APP_ENTITY_SCHEMA[0]: 
                  journal_entities[journal_key]\
                                  [dbconstants.JOURNAL_SCHEMA[0]], 
          dbconstants.APP_ENTITY_SCHEMA[1]: 
                  str(trans_id)
        }
      else:
        # There was no previous journal because the first put on this 
        # row was apart of a bad transaction, hence we set this key to 
        # be empty.
        db_results[index][row_key] = {}
    return db_results


  def validated_dict_result(self, app_id, db_results, current_ongoing_txn=0):
    """
        Takes database results from the entity table and returns
        an updated result dictionary if any of the entities were using 
        blacklisted transaction IDs. 
   
    Args:
      app_id: The application ID whose results we are validating.
      db_results: Database result from the entity table.
      current_ongoing_txn: Current transaction ID, 0 if not in a transaction.
    Returns:
      A modified copy of db_results whose values have been validated.
    """
    journal_result_map = {}
    journal_keys = []
    delete_keys = []
    for row_key in db_results:
      if dbconstants.APP_ENTITY_SCHEMA[1] not in db_results[row_key]:
        continue
      current_version = long(db_results[row_key]\
                             [dbconstants.APP_ENTITY_SCHEMA[1]])
      trans_id = self.zookeeper.get_valid_transaction_id(\
                             app_id, current_version, row_key)
      if current_ongoing_txn != 0 and \
           current_version == current_ongoing_txn:
        # This value has been updated from within an ongoing transaction and
        # hence can be seen from within this scope for serializability.
        continue
      elif current_version != trans_id:
        journal_key = self.get_journal_key(row_key, trans_id)
        journal_keys.append(journal_key)
        journal_result_map[journal_key] = (row_key, trans_id)
        if trans_id == 0:
          delete_keys.append(row_key)

    if not journal_result_map: 
      return db_results

    journal_entities = self.datastore_batch.batch_get_entity(
                            dbconstants.JOURNAL_TABLE,
                            journal_keys,
                            dbconstants.JOURNAL_SCHEMA)
    for journal_key in journal_result_map:
      row_key, trans_id = journal_result_map[journal_key]
      if trans_id == 0:
        # Zero id's are entities which do not yet exist.
        del db_results[row_key]
      else:
        db_results[row_key] = {
          dbconstants.APP_ENTITY_SCHEMA[0]: 
                  journal_entities[journal_key]\
                                  [dbconstants.JOURNAL_SCHEMA[0]], 
          dbconstants.APP_ENTITY_SCHEMA[1]: 
                  str(trans_id)
        }
    return db_results

  def remove_tombstoned_entities(self, result):
    """ Removed any keys which have tombstoned entities.
    
    Args:
      result: A datastore result dictionary.
    Returns:
      A datastore result with tombstoned entities purged.
    """
    if isinstance(result, dict):
      final_result = {}
      for item in result:
        if dbconstants.APP_ENTITY_SCHEMA[0] not in result[item]:
          continue
        if not result[item][dbconstants.APP_ENTITY_SCHEMA[0]].\
               startswith(TOMBSTONE):
          final_result[item] = result[item]
      return final_result
    elif isinstance(result, list):
      final_result = []
      for item in result:
        key = item.keys()[0]
        if dbconstants.APP_ENTITY_SCHEMA[0] not in item[key]:
          continue
        # Skip over any tombstoned items.
        if not item[key][dbconstants.APP_ENTITY_SCHEMA[0]].\
               startswith(TOMBSTONE):
          final_result.append(item)
      return final_result
    else: 
      raise TypeError("Expected a dict or list for result")

  def fetch_keys(self, key_list, current_txnid=0):
    """ Given a list of keys fetch the entities.
    
    Args:
      key_list: A list of keys to fetch.
      current_txnid: Handle of current transaction if there is one.
    Returns:
      A tuple of entities from the datastore and key list.
    """
    row_keys = []
    for key in key_list:
      self.validate_app_id(key.app())
      index_key = str(self.__encode_index_pb(key.path()))
      prefix = self.get_table_prefix(key)
      row_keys.append(prefix + '/' + index_key)
    result = self.datastore_batch.batch_get_entity(
                       dbconstants.APP_ENTITY_TABLE, 
                       row_keys, 
                       dbconstants.APP_ENTITY_SCHEMA) 
    if len(key_list) != 0:
      result = self.validated_result(key_list[0].app(), 
                  result, current_ongoing_txn=current_txnid)
    result = self.remove_tombstoned_entities(result)
    return (result, row_keys)

  def dynamic_get(self, app_id, get_request, get_response):
    """ Fetch keys from the datastore.
    
    Args: 
       app_id: The application ID.
       get_request: Request with list of keys.
       get_response: Response to application server.
    Raises:
      ZKTransactionException: If a lock was unable to get acquired.
    """ 
    keys = get_request.key_list()
    txnid = 0
    if get_request.has_transaction():
      prefix = self.get_table_prefix(keys[0])
      root_key = self.get_root_key_from_entity_key(keys[0])
      txnid = get_request.transaction().handle()
      try:
        self.zookeeper.acquire_lock(prefix, txnid, root_key)
      except ZKTransactionException, zkte:
        logging.info("Concurrent transaction exception for app id {0} with " \
          "transaction id {1}, and info {2}".format(app_id, txnid, str(zkte)))
        self.zookeeper.notify_failed_transaction(app_id, txnid)
        raise zkte
   
    results, row_keys = self.fetch_keys(keys, current_txnid=txnid)
    for r in row_keys:
      group = get_response.add_entity() 
      if r in results and dbconstants.APP_ENTITY_SCHEMA[0] in results[r]:
        group.mutable_entity().CopyFrom(
          entity_pb.EntityProto(results[r][dbconstants.APP_ENTITY_SCHEMA[0]]))

  def dynamic_delete(self, app_id, delete_request):
    """ Deletes a set of rows.
    
    Args: 
      app_id: The application ID.
      delete_request: Request with a list of keys.
    """
    txn_hash = {}
    keys = delete_request.key_list()
    if not keys:
      return

    if delete_request.has_transaction():
      txn_hash = self.acquire_locks_for_trans(keys, 
                      delete_request.transaction().handle())
    else:
      txn_hash = self.acquire_locks_for_nontrans(app_id, keys) 

    self.delete_entities(app_id,
                         delete_request.key_list(),
                         txn_hash,
                         soft_delete=True)
    if not delete_request.has_transaction():
      self.release_locks_for_nontrans(app_id, keys, txn_hash)
 
  def generate_filter_info(self, filters):
    """Transform a list of filters into a more usable form.

    Args:
      filters: A list of filter PBs.
    Returns:
      A dict mapping property names to lists of (op, value) tuples.
    """

    def reference_property_to_reference(refprop):
      """ Creates a Reference from a ReferenceProperty. """
      ref = entity_pb.Reference()
      ref.set_app(refprop.app())
      if refprop.has_name_space():
        ref.set_name_space(refprop.name_space())
      for pathelem in refprop.pathelement_list():
        ref.mutable_path().add_element().CopyFrom(pathelem)
      return ref

    filter_info = {}
    for filt in filters:
      prop = filt.property(0)
      value = prop.value()
      if prop.name() == '__key__':
        value = reference_property_to_reference(value.referencevalue())
        value = value.path()
      filter_info.setdefault(prop.name(), []).append((filt.op(), 
                                   self.__encode_index_pb(value)))
    return filter_info
  
  def generate_order_info(self, orders):
    """Transform a list of orders into a more usable form which 
       is a tuple of properties and ordering directions.

    Args:
      orders: A list of order PBs.
    Returns:
      A list of (property, direction) tuples.
    """
    orders = [(order.property(), order.direction()) for order in orders]
    if orders and orders[-1] == ('__key__', datastore_pb.Query_Order.ASCENDING):
      orders.pop()
    return orders

  def __get_start_key(self, prefix, prop_name, order, last_result):
    """ Builds the start key for cursor query.

    Args: 
       prefix: The start key prefix (app id and namespace).
       prop_name: property name of the filter.
       order: sort order.
       last_result: last result encoded in cursor.
    """
    e = last_result
    if not prop_name and not order:
      return str(prefix + '/' + str(self.__encode_index_pb(e.key().path())))
     
    if e.property_list():
      plist = e.property_list()
    else:   
      rkey = prefix + '/' + str(self.__encode_index_pb(e.key().path()))
      ret = self.datastore_batch.batch_get_entity(dbconstants.APP_ENTITY_TABLE, 
                                             [rkey], 
                                             dbconstants.APP_ENTITY_SCHEMA)

      ret = self.remove_tombstoned_entities(ret)

      if dbconstants.APP_ENTITY_SCHEMA[0] in ret[rkey]:
        ent = entity_pb.EntityProto(ret[rkey][dbconstants.APP_ENTITY_SCHEMA[0]])
        plist = ent.property_list() 

    for p in plist:
      if p.name() == prop_name:
        break

    val = str(self.__encode_index_pb(p.value()))
    # remove first binary char for correct lexigraphical ordering
    val = str(val[1:])

    if order == datastore_pb.Query_Order.DESCENDING:
      val = helper_functions.reverse_lex(val)        
    params = [prefix,
              self.get_entity_kind(e), 
              p.name(), 
              val, 
              str(self.__encode_index_pb(e.key().path()))]

    return self.get_index_key_from_params(params)

  def __fetch_entities(self, refs):
    """ Given the results from a table scan, get the references.
    
    Args: 
      refs: key/value pairs where the values contain a reference to 
            the entitiy table.
    Returns:
      Entities retrieved from entity table.
    """
    if len(refs) == 0:
      return []
    keys = [item.keys()[0] for item in refs]
    rowkeys = []    
    for index, ent in enumerate(refs):
      key = keys[index]
      ent = ent[key]['reference']
      rowkeys.append(ent)
  
    result = self.datastore_batch.batch_get_entity(
                                  dbconstants.APP_ENTITY_TABLE, 
                                  rowkeys,
                                  dbconstants.APP_ENTITY_SCHEMA)
    result = self.remove_tombstoned_entities(result)
    entities = []
    keys = result.keys()
    for key in rowkeys:
      if key in result and dbconstants.APP_ENTITY_SCHEMA[0] in result[key]:
        entities.append(result[key][dbconstants.APP_ENTITY_SCHEMA[0]])

    return entities 

  def __extract_entities(self, kv):
    """ Given a result from a range query on the Entity table return a 
        list of encoded entities.

    Args:
      kv: Key and values from a range query on the entity table.
    Returns:
      The extracted entities.
    """
    keys = [item.keys()[0] for item in kv]
    results = []    
    for index, entity in enumerate(kv):
      key = keys[index]
      entity = entity[key][dbconstants.APP_ENTITY_SCHEMA[0]]
      results.append(entity)

    return results

  def ordered_ancestor_query(self, query, filter_info, order_info):
    """ Performs an ordered ancestor query. It grabs all entities of a 
        given ancestor and then orders in memory.
    
    Args:
      query: The query to run.
      filter_info: Tuple with filter operators and values
      order_info: Tuple with property name and the sort order.
    Returns:
      A list of entities.
    Raises:
      ZKTransactionException: If a lock could not be acquired.
    """ 
    ancestor = query.ancestor()
    prefix = self.get_table_prefix(query)
    path = buffer(prefix + '/') + self.__encode_index_pb(ancestor.path())
    txn_id = 0
    if query.has_transaction(): 
      txn_id = query.transaction().handle()   
      root_key = self.get_root_key_from_entity_key(ancestor)
      try:
        prefix = self.get_table_prefix(query)
        self.zookeeper.acquire_lock(prefix, txn_id, root_key)
      except ZKTransactionException, zkte:
        logging.info("Concurrent transaction exception for app id {0}, " \
          "transaction id {1}, info {2}".format(query.app(), txn_id, str(zkte)))
        self.zookeeper.notify_failed_transaction(query.app(), txn_id)
        raise zkte

    startrow = path
    endrow = path + self._TERM_STRING

    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY

    limit = self._MAXIMUM_RESULTS
    unordered = self.fetch_from_entity_table(startrow,
                                             endrow,
                                             limit, 
                                             0, 
                                             start_inclusive, 
                                             end_inclusive, 
                                             query, 
                                             txn_id)
    # TODO apply __key__ from filter info 
    # TODO apply compiled cursor if given
    kind = None
    if query.has_kind():
      kind = query.kind()
    if query.has_limit():
      limit = min(query.limit(), self._MAXIMUM_RESULTS)
    return self.__multiorder_results(unordered, order_info, kind)[:limit]
 
  def ancestor_query(self, query, filter_info, order_info):
    """ Performs ancestor queries which is where you select 
        entities based on a particular root entitiy. 
      
    Args: 
      query: The query to run.
      filter_info: Tuple with filter operators and values.
      order_info: Tuple with property name and the sort order.
    Returns:
      A list of entities.
    Raises:
      ZKTransactionException: If a lock could not be acquired.
    """       
    ancestor = query.ancestor()
    prefix = self.get_table_prefix(query)
    path = buffer(prefix + '/') + self.__encode_index_pb(ancestor.path())
    txn_id = 0
    if query.has_transaction(): 
      txn_id = query.transaction().handle()   
      root_key = self.get_root_key_from_entity_key(ancestor)
      try:
        self.zookeeper.acquire_lock(prefix, txn_id, root_key)
      except ZKTransactionException, zkte:
        logging.info("Concurrent transaction exception for app id {0}, " \
          "transaction id {1}, info {2}".format(query.app(), txn_id, str(zkte)))
        self.zookeeper.notify_failed_transaction(query.app(), txn_id)
        raise zkte

    startrow = path
    endrow = path + self._TERM_STRING

    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY

    if '__key__' in filter_info:
      op = filter_info['__key__'][0][0]
      __key__ = str(filter_info['__key__'][0][1])
      if op and op == datastore_pb.Query_Filter.EQUAL:
        startrow = prefix + '/' + __key__
        endrow = prefix + '/' + __key__
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN:
        start_inclusive = self._DISABLE_INCLUSIVITY
        startrow = prefix + '/' + __key__ 
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        startrow = prefix + '/' + __key__
      elif op and op == datastore_pb.Query_Filter.LESS_THAN:
        endrow = prefix + '/'  + __key__
        end_inclusive = self._DISABLE_INCLUSIVITY
      elif op and op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        endrow = prefix + '/' + __key__ 

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = cassandra_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, None, None, last_result)
      start_inclusive = self._DISABLE_INCLUSIVITY

    limit = query.limit() or self._MAXIMUM_RESULTS
    results = self.fetch_from_entity_table(startrow,
                                        endrow,
                                        limit, 
                                        0, 
                                        start_inclusive, 
                                        end_inclusive, 
                                        query, 
                                        txn_id)
    kind = None
    if query.kind():
      kind = query.kind()

    return self.__multiorder_results(results, order_info, kind)

  def fetch_from_entity_table(self, 
                              startrow,
                              endrow,
                              limit, 
                              offset, 
                              start_inclusive, 
                              end_inclusive, 
                              query, 
                              txn_id):
    """
    Fetches entities from the entity table given a query and a set of parameters.
    It will validate the results and remove tombstoned items. 
     
    Args:
       startrow: The key from which we start a range query.
       endrow: The end key that terminates a range query.
       limit: The maximum number of items to return from a query.
       offset: The number of entities we want removed from the front of the result.
       start_inclusive: Boolean if we should include the start key in the result.
       end_inclusive: Boolean if we should include the end key in the result. 
       query: The query we are currently running.
       txn_id: The current transaction ID if there is one, it is 0 if there is not.
    Returns:
       A validated database result.
    """
    final_result = []
    while 1: 
      result = self.datastore_batch.range_query(dbconstants.APP_ENTITY_TABLE, 
                                              dbconstants.APP_ENTITY_SCHEMA, 
                                              startrow, 
                                              endrow, 
                                              limit, 
                                              offset=0, 
                                              start_inclusive=start_inclusive, 
                                              end_inclusive=end_inclusive)
      prev_len = len(result)
      last_result = None
      if result:
        last_result = result[-1].keys()[0]
      else: 
        break

      result = self.validated_result(query.app(), result, 
                                     current_ongoing_txn=txn_id)

      result = self.remove_tombstoned_entities(result)

      final_result += result

      if len(result) != prev_len:
        startrow = last_result
        start_inclusive = self._DISABLE_INCLUSIVITY
        limit = limit - len(result)
        continue 
      else:
        break

    return self.__extract_entities(final_result)


  def kindless_query(self, query, filter_info, order_info):
    """ Performs kindless queries where queries are performed 
        on the entity table and go across kinds.
      
    Args: 
      query: The query to run.
      filter_info: Tuple with filter operators and values.
      order_info: Tuple with property name and the sort order.
    Returns:
      Entities that match the query.
    """       
    prefix = self.get_table_prefix(query)

    __key__ = str(filter_info['__key__'][0][1])
    op = filter_info['__key__'][0][0]

    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY

    startrow = prefix + '/' + __key__ + self._TERM_STRING
    endrow = prefix + '/'  + self._TERM_STRING
    if op and op == datastore_pb.Query_Filter.EQUAL:
      startrow = prefix + '/' + __key__
      endrow = prefix + '/' + __key__
    elif op and op == datastore_pb.Query_Filter.GREATER_THAN:
      start_inclusive = self._DISABLE_INCLUSIVITY
      startrow = prefix + '/' + __key__ 
      endrow = prefix + '/'  + self._TERM_STRING
      end_inclusive = self._DISABLE_INCLUSIVITY
    elif op and op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
      startrow = prefix + '/' + __key__
      endrow = prefix + '/'  + self._TERM_STRING
      end_inclusive = self._DISABLE_INCLUSIVITY
    elif op and op == datastore_pb.Query_Filter.LESS_THAN:
      startrow = prefix + '/'  
      endrow = prefix + '/'  + __key__
      end_inclusive = self._DISABLE_INCLUSIVITY
    elif op and op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
      startrow = prefix + '/' 
      endrow = prefix + '/' + __key__ 

    if not order_info:
      order = None
      prop_name = None
    
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = cassandra_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, prop_name, order, last_result)
      start_inclusive = self._DISABLE_INCLUSIVITY

    limit = query.limit() or self._MAXIMUM_RESULTS
    return self.fetch_from_entity_table(startrow,
                                        endrow,
                                        limit, 
                                        0, 
                                        start_inclusive, 
                                        end_inclusive, 
                                        query, 
                                        0)
  
  def reverse_path(self, key):
    """ Use this function for reversing the key ancestry order. 
        Needed for kind queries.
   
    Args:
      key: A string key which needs reversing.
    Returns:
      A string key which can be used on the kind table.
    """ 
    tokens = key.split('!')
    tokens.reverse() 
    key = '!'.join(tokens)[1:] + '!'
    return key

  def kind_query_range(self, query, filter_info, order_info):
    """ Gets start and end keys for kind queries, along with
        inclusivity of those keys.
      
    Args: 
      query: The query to run.
      filter_info: __key__ filter.
      order_info: ordering for __key__. 
    Returns:
      A tuple of the start row, end row, if its start inclusive,
      and if its end inclusive
    """       
    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY
    prefix = self.get_table_prefix(query)
    startrow = prefix + '/' + query.kind() + ':'     
    endrow = prefix + '/' + query.kind() + ':' + self._TERM_STRING
    if '__key__' not in filter_info:
      return startrow, endrow, start_inclusive, end_inclusive

    for key_filter in filter_info['__key__']:
      op = key_filter[0]
      __key__ = str(key_filter[1])
      # The key is built to index the Entity table rather than the 
      # kind table. We reverse the ordering of the ancestry
      __key__ = self.reverse_path(__key__)
      if op and op == datastore_pb.Query_Filter.EQUAL:
        startrow = prefix + '/' + __key__
        endrow = prefix + '/' + __key__
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN:
        start_inclusive = self._DISABLE_INCLUSIVITY
        startrow = prefix + '/' + __key__ 
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        startrow = prefix + '/' + __key__
      elif op and op == datastore_pb.Query_Filter.LESS_THAN:
        endrow = prefix + '/'  + __key__
        end_inclusive = self._DISABLE_INCLUSIVITY
      elif op and op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        endrow = prefix + '/' + __key__ 
    return startrow, endrow, start_inclusive, end_inclusive
   
  def __kind_query(self, query, filter_info, order_info):
    """ Performs kind only queries, kind and ancestor, and ancestor queries
        https://developers.google.com/appengine/docs/python/datastore/queries.

    Args:
      query: The query to run.
      filter_info: tuple with filter operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      An ordered list of entities matching the query.
    """
    # Detect quickly if this is a kind query or not.
    for fi in filter_info:
      if fi != "__key__":
        return None
    
    order = None
    prop_name = None

    if query.has_ancestor() and len(order_info) > 0:
      return self.ordered_ancestor_query(query, filter_info, order_info)
    if query.has_ancestor():
      return self.ancestor_query(query, filter_info, order_info)
    elif not query.has_kind():
      return self.kindless_query(query, filter_info, order_info)
    
    startrow, endrow, start_inclusive, end_inclusive = \
          self.kind_query_range(query, filter_info, order_info)

    if startrow == None or endrow == None:
      return None
    
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = cassandra_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      prefix = self.get_table_prefix(query)
      startrow = self.get_kind_key(prefix, last_result.key().path())
      start_inclusive = self._DISABLE_INCLUSIVITY

    limit = query.limit() or self._MAXIMUM_RESULTS
    result = self.datastore_batch.range_query(dbconstants.APP_KIND_TABLE, 
                                              dbconstants.APP_KIND_SCHEMA, 
                                              startrow, 
                                              endrow, 
                                              limit, 
                                              offset=0, 
                                              start_inclusive=start_inclusive, 
                                              end_inclusive=end_inclusive)
    return self.__fetch_entities(result)

  def __single_property_query(self, query, filter_info, order_info):
    """Performs queries satisfiable by the Single_Property tables.

    Args:
      query: The query to run.
      filter_info: tuple with filter operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      List of entities retrieved from the given query.
    """
    property_names = set(filter_info.keys())
    property_names.update(x[0] for x in order_info)
    property_names.discard('__key__')
    if len(property_names) != 1:
      return None

    property_name = property_names.pop()
    filter_ops = filter_info.get(property_name, [])
    if len([1 for o, _ in filter_ops
            if o == datastore_pb.Query_Filter.EQUAL]) > 1:
      return None

    if len(order_info) > 1 or (order_info and order_info[0][0] == '__key__'):
      return None

    if query.has_ancestor():
      return None

    if not query.has_kind():
      return None

    if order_info:
      if order_info[0][0] == property_name:
        direction = order_info[0][1]
    else:
      direction = datastore_pb.Query_Order.ASCENDING

    prefix = self.get_table_prefix(query)
 

    limit = query.limit() or self._MAXIMUM_RESULTS

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = cassandra_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, 
                                    property_name,
                                    direction,
                                    last_result)
    else:
      startrow = None

    references = self.__apply_filters(filter_ops, 
                               order_info, 
                               property_name, 
                               query.kind(), 
                               prefix, 
                               limit, 
                               0, 
                               startrow)
    return self.__fetch_entities(references)
    
  def __apply_filters(self, 
                     filter_ops, 
                     order_info, 
                     property_name, 
                     kind, 
                     prefix, 
                     limit, 
                     offset, 
                     startrow,
                     force_start_key_exclusive=False): 
    """ Applies property filters in the query.

    Args:
      filter_ops: Tuple with property filter operator and value.
      order_info: Tuple with property name and sort order.
      kind: Kind of the entity.
      prefix: Prefix for the table.
      limit: Number of results.
      offset: Number of results to skip.
      startrow: Start key for the range scan.
      force_start_key_exclusive: Do not include the start key.
    Results:
      Returns a list of entity keys.
    Raises:
      NotImplementedError: For unsupported queries.
      AppScaleMisconfiguredQuery: Bad filters or orderings.
    """ 
    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY

    endrow = None 
    column_names = dbconstants.PROPERTY_SCHEMA

    if order_info:
      if order_info[0][0] == property_name:
        direction = order_info[0][1]
    else:
      direction = datastore_pb.Query_Order.ASCENDING

    if direction == datastore_pb.Query_Order.ASCENDING:
      table_name = dbconstants.ASC_PROPERTY_TABLE
    else: 
      table_name = dbconstants.DSC_PROPERTY_TABLE
  
    if startrow: 
      start_inclusive = self._DISABLE_INCLUSIVITY 

    # This query is returning based on order on a specfic property name 
    # The start key (if not already supplied) depends on the property
    # name and does not take into consideration its value. The end key
    # is based on the terminating string.
    if len(filter_ops) == 0 and (order_info and len(order_info) == 1):
      end_inclusive = self._ENABLE_INCLUSIVITY
      start_inclusive = self._ENABLE_INCLUSIVITY

      if not startrow:
        params = [prefix, kind, property_name, None]
        startrow = self.get_index_key_from_params(params)

      params = [prefix, kind, property_name, self._TERM_STRING, None]
      endrow = self.get_index_key_from_params(params)
      if force_start_key_exclusive:
        start_inclusive = False
      return self.datastore_batch.range_query(table_name, 
                                          column_names, 
                                          startrow, 
                                          endrow, 
                                          limit, 
                                          offset=0, 
                                          start_inclusive=start_inclusive, 
                                          end_inclusive=end_inclusive)      

    #TODO byte stuff value for '/' character? Since it's an escape 
    # character and we might have issues if data contains this char
    # This query has a value it bases the query on for a property name
    # The difference between operators is what the end and start key are
    if len(filter_ops) == 1:
      oper = filter_ops[0][0]
      value = str(filter_ops[0][1])

      # Strip off the first char of encoding
      value = str(value[1:]) 

      if direction == datastore_pb.Query_Order.DESCENDING: 
        value = helper_functions.reverse_lex(value)

      if oper == datastore_pb.Query_Filter.EQUAL:
        start_value = value 
        end_value = value + self._TERM_STRING
      elif oper == datastore_pb.Query_Filter.LESS_THAN:
        start_value = None
        end_value = value + '/'
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = value + self._TERM_STRING
          end_value = self._TERM_STRING
      elif oper == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        start_value = None
        end_value = value + '/' + self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = value + '/'
          end_value = self._TERM_STRING
      elif oper == datastore_pb.Query_Filter.GREATER_THAN:
        start_value = value + self._TERM_STRING
        end_value = self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = None
          end_value = value + '/' 
      elif oper == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        start_value = value + '/'
        end_value = self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = None
          end_value = value + '/' +  self._TERM_STRING
      else:
        raise NotImplementedError("Unsupported query of operation %s" % \
             datastore_pb.Query_Filter.Operator_Name(oper))

      if not startrow:
        params = [prefix, kind, property_name, start_value]
        startrow = self.get_index_key_from_params(params)
        start_inclusive = self._DISABLE_INCLUSIVITY
      params = [prefix, kind, property_name, end_value]
      endrow = self.get_index_key_from_params(params)

      if force_start_key_exclusive:
        start_inclusive = False

      ret = self.datastore_batch.range_query(table_name, 
                                          column_names, 
                                          startrow, 
                                          endrow, 
                                          limit, 
                                          offset=0, 
                                          start_inclusive=start_inclusive, 
                                          end_inclusive=end_inclusive)      

      return ret 

    # Here we have two filters and so we set the start and end key to 
    # get the given value within those ranges. 
    if len(filter_ops) > 1:
      if filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN or \
         filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        oper1 = filter_ops[0][0]
        oper2 = filter_ops[1][0]
        value1 = str(filter_ops[0][1])
        value1 = str(value1[1:])
        value2 = str(filter_ops[1][1])
        value2 = str(value2[1:])
      else:
        oper1 = filter_ops[1][0]
        oper2 = filter_ops[0][0]
        value1 = str(filter_ops[1][1])
        value1 = str(value1[1:])
        value2 = str(filter_ops[0][1])
        value2 = str(value2[1:])

      if direction == datastore_pb.Query_Order.ASCENDING:
        table_name = dbconstants.ASC_PROPERTY_TABLE
        # The first operator will always be either > or >=
        if startrow:
          start_inclusive = self._DISABLE_INCLUSIVITY
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN:
          params = [prefix, kind, property_name, value1 + '/' + \
                    self._TERM_STRING]
          startrow = self.get_index_key_from_params(params)
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value1 + '/']
          startrow = self.get_index_key_from_params(params)
        else:
          raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

        # The second operator will be either < or <=
        if oper2 == datastore_pb.Query_Filter.LESS_THAN:    
          params = [prefix, kind, property_name, value2 + '/']
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._DISABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value2 + '/' + \
                    self._TERM_STRING]
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._ENABLE_INCLUSIVITY
        else:
          raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering") 
      
      if direction == datastore_pb.Query_Order.DESCENDING:
        table_name = dbconstants.DSC_PROPERTY_TABLE
        value1 = helper_functions.reverse_lex(value1)
        value2 = helper_functions.reverse_lex(value2) 

        if oper1 == datastore_pb.Query_Filter.GREATER_THAN:   
          params = [prefix, kind, property_name, value1 + '/']
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._DISABLE_INCLUSIVITY
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value1 + '/' + \
                    self._TERM_STRING]
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._ENABLE_INCLUSIVITY

        if startrow:
          start_inclusive = self._DISABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN:
          params = [prefix, kind, property_name, value2 + '/' + \
                    self._TERM_STRING]
          startrow = self.get_index_key_from_params(params)
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value2 + '/']
          startrow = self.get_index_key_from_params(params)
        
      if force_start_key_exclusive:
        start_inclusive = False

      return self.datastore_batch.range_query(table_name, 
                                          column_names, 
                                          startrow, 
                                          endrow, 
                                          limit, 
                                          offset=0, 
                                          start_inclusive=start_inclusive, 
                                          end_inclusive=end_inclusive)      
         
    return []

  def __composite_query(self, query, filter_info, order_info):  
    """Performs Composite queries which is a combination of 
       multiple properties to query on.

    Args:
      query: The query to run.
      filter_info: tuple with filter operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      List of entities retrieved from the given query.
    """
    if order_info and order_info[0][0] == '__key__':
      return None

    if query.has_ancestor():
      return None

    if not query.has_kind():
      return None

    def set_prop_names(filt_info):
      """ Sets the property names. """
      pnames = set(filt_info.keys())
      pnames.update(x[0] for x in order_info)
      pnames.discard('__key__')
      pnames = list(pnames)

      pname = None
      for p in filt_info.keys():
        f = filt_info[p]
        if f[0][0] != datastore_pb.Query_Filter.EQUAL: 
          pname = p     
      return pname, pnames 

    property_name, property_names = set_prop_names(filter_info)

    if len(property_names) <= 1:
      return None

    if not property_name:
      property_name = property_names.pop()

    filter_ops = filter_info.get(property_name, [])
    order_ops = []
    
    for i in order_info:
      if i[0] == property_name:
        order_ops = [i]
        break
    if order_ops:
      if order_ops[0][0] == property_name:
        direction = order_ops[0][1]
    else:
      direction = datastore_pb.Query_Order.ASCENDING
    
    count = self._MAX_COMPOSITE_WINDOW
    kind = query.kind()

    limit = query.limit() or self._MAXIMUM_RESULTS

    offset = query.offset()
    prefix = self.get_table_prefix(query)

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = cassandra_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, 
                                    property_name,
                                    direction,
                                    last_result)
    else:
      startrow = None
    result = []     
    # We loop and collect enough to fill the limit or until there are 
    # no more matching entities. The first filter is what we apply 
    # direct to the datastore, followed by in memory filters
    # Research is required on figuring out what is the 
    # best filter to apply via range queries. 
    while len(result) < (limit + offset):
      temp_res = self.__apply_filters(filter_ops, 
                                   order_ops, 
                                   property_name, 
                                   kind, 
                                   prefix, 
                                   count, 
                                   0, 
                                   startrow,
                                   force_start_key_exclusive=True)
      if not temp_res: 
        break

      ent_res = self.__fetch_entities(temp_res)

      # Create a copy from which we filter out
      filtered_entities = ent_res[:]

      # Apply in-memory filters for each property
      for ent in ent_res:
        e = entity_pb.EntityProto(ent)
        prop_list = e.property_list()
        for prop in property_names:
          temp_filt = filter_info.get(prop, [])

          cur_prop = None
          for each in prop_list:
            if each.name() == prop:
              cur_prop = each
              break

          # Filter each property by the given value, only handling EQUAL
          if not prop:
            filtered_entities.remove(ent)
          elif len(temp_filt) == 1:         
            oper = temp_filt[0][0]
            value = str(temp_filt[0][1])
            if oper == datastore_pb.Query_Filter.EQUAL:
              if cur_prop and \
                   str(self.__encode_index_pb(cur_prop.value())) != value:
                if ent in filtered_entities: 
                  filtered_entities.remove(ent)   
     
      result += filtered_entities  
      startrow = temp_res[-1].keys()[0]

    if len(order_info) > 1:
      result = self.__multiorder_results(result, order_info, None) 

    return result 

  def __multiorder_results(self, result, order_info, kind):
    """ Takes results and applies ordering based on properties and 
        whether it should be ascending or decending. Filters out 
        any entities which do not match the given kind, if given.

      Args: 
        result: unordered results.
        order_info: given ordering of properties.
        kind: The kind to filter on if given.
      Returns:
        A list of ordered entities.
    """
    # TODO:
    # We can not fully filter past one filter without getting
    # the entire table to make sure results are in the correct order. 
    # Composites must be implemented the correct way with specialized 
    # indexes to get the correct result.
    # The effect is that entities at the edge of each batch have a high 
    # chance of being out of order with our current implementation.

    # Put all the values appended based on order info into a dictionary,
    # The key being the values appended and the value being the index
    if not result:
      return []

    if not order_info and not kind:
      return result

    vals = {}
    for e in result:
      key = "/"
      e = entity_pb.EntityProto(e)
      # Skip this entitiy if it does not match the given kind.
      last_path = e.key().path().element_list()[-1]
      if kind and last_path.type() != kind:
        continue
     
      prop_list = e.property_list()
      for ii in order_info:
        ord_prop = ii[0]
        ord_dir = ii[1]
        for each in prop_list:
          if each.name() == ord_prop:
            if ord_dir == datastore_pb.Query_Order.DESCENDING:
              key = str(key+ '/' + helper_functions.reverse_lex(
                                   str(each.value())))
            else:
              key = str(key + '/' + str(each.value()))
            break
      # Add a unique identifier at the end because indexes can be the same.
      key = key + str(e)
      vals[key] = e
    keys = sorted(vals.keys())
    sorted_vals = [vals[ii] for ii in keys]
    result = [e.Encode() for e in sorted_vals]
    return result

  # These are the three different types of queries attempted. Queries 
  # can be identified by their filters and orderings.
  # TODO: Queries have hints which help in picking which strategy to do first.
  _QUERY_STRATEGIES = [
      __single_property_query,   
      __kind_query,
      __composite_query,
  ]


  def __get_query_results(self, query):
    """Applies the strategy for the provided query.

    Args:    
      query: A datastore_pb.Query protocol buffer.
    Returns:
      Result set.
    """
    if query.has_transaction() and not query.has_ancestor():
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          'Only ancestor queries are allowed inside transactions.')

    num_components = len(query.filter_list()) + len(query.order_list())
    if query.has_ancestor():
      num_components += 1
    if num_components > self._MAX_QUERY_COMPONENTS:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          ('query is too large. may not have more than %s filters'
           ' + sort orders ancestor total' % self._MAX_QUERY_COMPONENTS))

    app_id = query.app()
    self.validate_app_id(app_id)
    filters, orders = datastore_index.Normalize(query.filter_list(),
                                                query.order_list(), [])
    filter_info = self.generate_filter_info(filters)
    order_info = self.generate_order_info(orders)
    for strategy in DatastoreDistributed._QUERY_STRATEGIES:
      results = strategy(self, query, filter_info, order_info)
      if results:
        break

    # TODO keys only queries. 
    # They work but pass the entire entity back to the AppServer
    if query.has_keys_only():
      pass
    return results
  
  def _dynamic_run_query(self, query, query_result):
    """Populates the query result and use that query result to 
       encode a cursor.

    Args:
      query: The query to run.
      query_result: The response given to the application server.
    """
    result = self.__get_query_results(query)
    count = 0
    offset = query.offset()
    if result:
      query_result.set_skipped_results(len(result) - offset)
      count = len(result)
      result = result[offset:]
      for index, ii in enumerate(result):
        result[index] = entity_pb.EntityProto(ii) 

    cur = cassandra_stub_util.QueryCursor(query, result)
    cur.PopulateQueryResult(count, query.offset(), query_result) 

  def setup_transaction(self, app_id, is_xg):
    """ Gets a transaction ID for a new transaction.

    Args:
      app_id: The application for which we are getting a new transaction ID.
      is_xg: A bool that indicates if this transaction operates over multiple
        entity groups.
    Returns:
      A long representing a unique transaction ID.
    """
    return self.zookeeper.get_transaction_id(app_id, is_xg)

  def commit_transaction(self, app_id, http_request_data):
    """ Handles the commit phase of a transaction.

    Args:
      app_id: The application ID requesting the transaction commit.
      http_request_data: The encoded request of datastore_pb.Transaction.
    Returns:
      An encoded protocol buffer commit response.
    """
    commitres_pb = datastore_pb.CommitResponse()
    transaction_pb = datastore_pb.Transaction(http_request_data)
    txn_id = transaction_pb.handle()
    try:
      self.zookeeper.release_lock(app_id, txn_id)
      return (commitres_pb.Encode(), 0, "")
    except ZKTransactionException, zkte:
      logging.info("Concurrent transaction exception for app id {0}, " \
        "transaction id {1}, info {2}".format(app_id, txn_id, str(zkte)))
      self.zookeeper.notify_failed_transaction(app_id, txn_id)
      return (commitres_pb.Encode(), 
              datastore_pb.Error.PERMISSION_DENIED, 
              "Unable to commit for this transaction %s" % str(zkte))

  def rollback_transaction(self, app_id, http_request_data):
    """ Handles the rollback phase of a transaction.

    Args:
      app_id: The application ID requesting the rollback.
      http_request_data: The encoded request, a datstore_pb.Transaction.
    Returns:
      An encoded protocol buffer void response.
    """
    txn = datastore_pb.Transaction(http_request_data)
    logging.info("Doing a rollback on transaction id {0} for app id {1}"
      .format(txn.handle(), app_id))
    try:
      self.zookeeper.notify_failed_transaction(app_id, txn.handle())
      return (api_base_pb.VoidProto().Encode(), 0, "")
    except ZKTransactionException, zkte:
      logging.info("Concurrent transaction exception for app id {0}, " \
        "transaction id {1}, info {2}".format(app_id, txn.handle(), str(zkte)))
      return (api_base_pb.VoidProto().Encode(), 
              datastore_pb.Error.PERMISSION_DENIED, 
              "Unable to rollback for this transaction: %s" % str(zkte))

class MainHandler(tornado.web.RequestHandler):
  """
  Defines what to do when the webserver receives different types of 
  HTTP requests.
  """

  def unknown_request(self, app_id, http_request_data, pb_type):
    """ Function which handles unknown protocol buffers.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer
    Raises:
      Raises exception.
    """ 
    raise NotImplementedError("Unknown request of operation %s"%pb_type)
  
  @tornado.web.asynchronous
  def post(self):
    """ Function which handles POST requests. Data of the request is 
        the request from the AppServer in an encoded protocol buffer 
        format.
    """
    request = self.request
    http_request_data = request.body
    pb_type = request.headers['protocolbuffertype']
    app_data = request.headers['appdata']
    app_data  = app_data.split(':')

    if len(app_data) == 4:
      app_id, user_email, nick_name, auth_domain = app_data
      os.environ['AUTH_DOMAIN'] = auth_domain
      os.environ['USER_EMAIL'] = user_email
      os.environ['USER_NICKNAME'] = nick_name
      os.environ['APPLICATION_ID'] = app_id
    elif len(app_data) == 1:
      app_id = app_data[0]
      os.environ['APPLICATION_ID'] = app_id
    else:
      return

    if pb_type == "Request":
      self.remote_request(app_id, http_request_data)
    else:
      self.unknown_request(app_id, http_request_data, pb_type)
    self.finish()
  
  @tornado.web.asynchronous
  def get(self):
    """ Handles get request for the web server. Returns that it is currently
        up in json.
    """
    self.write('{"status":"up"}')
    self.finish() 

  def remote_request(self, app_id, http_request_data):
    """ Receives a remote request to which it should give the correct 
        response. The http_request_data holds an encoded protocol buffer
        of a certain type. Each type has a particular response type. 
    
    Args:
      app_id: The application ID that is sending this request.
      http_request_data: Encoded protocol buffer.
    """
    apirequest = remote_api_pb.Request()
    apirequest.ParseFromString(http_request_data)
    apiresponse = remote_api_pb.Response()
    response = None
    errcode = 0
    errdetail = ""
    apperror_pb = None
    if not apirequest.has_method(): 
      errcode = datastore_pb.Error.BAD_REQUEST
      errdetail = "Method was not set in request"
      apirequest.set_method("NOT_FOUND")
    if not apirequest.has_request():
      errcode = datastore_pb.Error.BAD_REQUEST
      errdetail = "Request missing in call"
      apirequest.set_method("NOT_FOUND")
      apirequest.clear_request()
    method = apirequest.method()
    http_request_data = apirequest.request()

    if method == "Put":
      response, errcode, errdetail = self.put_request(app_id, 
                                                 http_request_data)
    elif method == "Get":
      response, errcode, errdetail = self.get_request(app_id, 
                                                 http_request_data)
    elif method == "Delete": 
      response, errcode, errdetail = self.delete_request(app_id, 
                                                    http_request_data)
    elif method == "RunQuery":
      response, errcode, errdetail = self.run_query(http_request_data)
    elif method == "BeginTransaction":
      response, errcode, errdetail = self.begin_transaction_request(
                                                      app_id, http_request_data)
    elif method == "Commit":
      response, errcode, errdetail = self.commit_transaction_request(
                                                      app_id,
                                                      http_request_data)
    elif method == "Rollback":
      response, errcode, errdetail = self.rollback_transaction_request( 
                                                        app_id,
                                                        http_request_data)
    elif method == "AllocateIds":
      response, errcode, errdetail = self.allocate_ids_request(
                                                        app_id,
                                                        http_request_data)
    elif method == "CreateIndex":
      errcode = 0
      errdetail = ""
      response = api_base_pb.Integer64Proto()
      response.set_value(0)
      response = response.Encode()

    elif method == "GetIndices":
      response = datastore_pb.CompositeIndices().Encode()
      errcode = 0
      errdetail = ""

    elif method == "UpdateIndex":
      response = api_base_pb.VoidProto().Encode()
      errcode = 0
      errdetail = ""

    elif method == "DeleteIndex":
      response = api_base_pb.VoidProto().Encode()
      errcode = 0
      errdetail = ""

    else:
      errcode = datastore_pb.Error.BAD_REQUEST 
      errdetail = "Unknown datastore message" 
      
    apiresponse.set_response(response)
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)

    self.write(apiresponse.Encode())

  def begin_transaction_request(self, app_id, http_request_data):
    """ Handles the intial request to start a transaction. Replies with 
        a unique identifier to handle this transaction in future requests.
  
    Args:
      app_id: The application ID requesting the transaction.
      http_request_data: The encoded request.
    Returns:
      An encoded transaction protocol buffer with a unique handler.
    """
    global datastore_access
    begin_transaction_req_pb = datastore_pb.BeginTransactionRequest(
      http_request_data)
    multiple_eg = False
    if begin_transaction_req_pb.has_allow_multiple_eg():
      multiple_eg = begin_transaction_req_pb.allow_multiple_eg()

    transaction_pb = datastore_pb.Transaction()
    handle = datastore_access.setup_transaction(app_id, multiple_eg)
    transaction_pb.set_app(app_id)
    transaction_pb.set_handle(handle)
    return (transaction_pb.Encode(), 0, "")

  def commit_transaction_request(self, app_id, http_request_data):
    """ Handles the commit phase of a transaction.

    Args:
      app_id: The application ID requesting the transaction commit.
      http_request_data: The encoded request of datastore_pb.Transaction.
    Returns:
      An encoded protocol buffer commit response.
    """
    global datastore_access
    return datastore_access.commit_transaction(app_id, http_request_data)

  def rollback_transaction_request(self, app_id, http_request_data):
    """ Handles the rollback phase of a transaction.

    Args:
      app_id: The application ID requesting the rollback.
      http_request_data: The encoded request.
    Returns:
      An encoded protocol buffer void response.
    """
    global datastore_access
    try:
      return datastore_access.rollback_transaction(app_id, http_request_data)
    except Exception, exception:
      logging.info("Error trying to rollback with exception {0}".format(
        str(exception)))
      return(api_base_pb.VoidProto().Encode(), 
             datastore_pb.Error.PERMISSION_DENIED, 
             "Unable to rollback for this transaction")

  def run_query(self, http_request_data):
    """ High level function for running queries.

    Args:
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      Returns an encoded query response.
    """
    global datastore_access
    query = datastore_pb.Query(http_request_data)
    clone_qr_pb = datastore_pb.QueryResult()
    datastore_access._dynamic_run_query(query, clone_qr_pb)
    return (clone_qr_pb.Encode(), 0, "")

  def allocate_ids_request(self, app_id, http_request_data):
    """ High level function for getting unique identifiers for entities.

    Args:
       app_id: Name of the application.
       http_request_data: Stores the protocol buffer request from the 
               AppServer.
    Returns: 
       Returns an encoded response.
    Raises:
       NotImplementedError: when requesting a max id.
    """
    global datastore_access
    request = datastore_pb.AllocateIdsRequest(http_request_data)
    response = datastore_pb.AllocateIdsResponse()
    reference = request.model_key()

    max_id = request.max()
    prefix = datastore_access.get_table_prefix(reference) 
    size = request.size()

    start, end = datastore_access.allocate_ids(prefix, size, max_id=max_id)
    response.set_start(start)
    response.set_end(end)
    return (response.Encode(), 0, "")

  def put_request(self, app_id, http_request_data):
    """ High level function for doing puts.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      Returns an encoded put response.
    """ 
    global datastore_access
    putreq_pb = datastore_pb.PutRequest(http_request_data)
    putresp_pb = datastore_pb.PutResponse()
 
    try:
      datastore_access.dynamic_put(app_id, putreq_pb, putresp_pb)
    except ZKTransactionException, zkte:
      logging.info("Concurrent transaction exception for app id {0}, " \
        "info {1}".format(app_id, str(zkte)))
      return (putresp_pb.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on put.")
      
    return (putresp_pb.Encode(), 0, "")
    
  def get_request(self, app_id, http_request_data):
    """ High level function for doing gets.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      An encoded get response.
    """ 
    global datastore_access
    getreq_pb = datastore_pb.GetRequest(http_request_data)
    getresp_pb = datastore_pb.GetResponse()
    datastore_access.dynamic_get(app_id, getreq_pb, getresp_pb)
    return (getresp_pb.Encode(), 0, "")

  def delete_request(self, app_id, http_request_data):
    """ High level function for doing deletes.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the AppServer.
    Returns:
      An encoded delete response.
    """ 
    global datastore_access
    delreq_pb = datastore_pb.DeleteRequest( http_request_data )
    delresp_pb = api_base_pb.VoidProto() 
    try:
      datastore_access.dynamic_delete(app_id, delreq_pb)
    except ZKTransactionException, zkte:
      logging.info("Concurrent transaction exception for app id {0}, " \
        "info {1}".format(app_id, str(zkte)))
      return (delresp_pb.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on delete.")
    return (delresp_pb.Encode(), 0, "")

def usage():
  """ Prints the usage for this web service. """
  print "AppScale Server"
  print
  print "Options:"
  print "\t--type=<" + ','.join(VALID_DATASTORES) +  ">"
  print "\t--no_encryption"
  print "\t--port"
  print "\t--zoo_keeper <zk nodes>"

pb_application = tornado.web.Application([
    (r"/*", MainHandler),
])

def main(argv):
  """ Starts a web service for handing datastore requests. """
  global datastore_access
  zookeeper_locations = ""

  db_info = appscale_info.get_db_info()
  db_type = db_info[':table']
  port = DEFAULT_SSL_PORT
  is_encrypted = True

  try:
    opts, args = getopt.getopt( argv, "t:p:n:z:",
                               ["type=",
                                "port",
                                "no_encryption",
                                "zoo_keeper"] )
  except getopt.GetoptError:
    usage()
    sys.exit(1)
  
  for opt, arg in opts:
    if  opt in ("-t", "--type"):
      db_type = arg
      print "Datastore type: ", db_type
    elif opt in ("-p", "--port"):
      port = int(arg)
    elif opt in ("-n", "--no_encryption"):
      is_encrypted = False
    elif opt in ("-z", "--zoo_keeper"):
      zookeeper_locations = arg

  if db_type not in VALID_DATASTORES:
    print "This datastore is not supported for this version of the AppScale\
          datastore API:" + db_type
    exit(1)
 
  datastore_batch = appscale_datastore_batch.DatastoreFactory.\
                                             getDatastore(db_type)
  zookeeper = zk.ZKTransaction(host=zookeeper_locations)
  datastore_access = DatastoreDistributed(datastore_batch, 
                                          zookeeper=zookeeper)
  if port == DEFAULT_SSL_PORT and not is_encrypted:
    port = DEFAULT_PORT

  server = tornado.httpserver.HTTPServer(pb_application)
  server.listen(port)

  ds_groomer = groomer.DatastoreGroomer(zookeeper, db_type, LOCAL_DATASTORE)
  ds_groomer.start()

  while 1:
    try:
      # Start Server #
      tornado.ioloop.IOLoop.instance().start()
    except SSL.SSLError:
      # This happens when connections timeout, there is a just a bad
      # SSL connection such as it does not use SSL when expected. 
      pass
    except KeyboardInterrupt:
      print "Server interrupted by user, terminating..."
      zookeeper.close()
      exit(1)

if __name__ == '__main__':
  main(sys.argv[1:])
