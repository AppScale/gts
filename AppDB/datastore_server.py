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
import random
import sys
import time

import tornado.httpserver
import tornado.ioloop
import tornado.web

import appscale_datastore_batch
import dbconstants
import groomer
import helper_functions

from zkappscale import zktransaction as zk
from zkappscale.zktransaction import ZKInternalException
from zkappscale.zktransaction import ZKTransactionException

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info

sys.path.append(os.path.join(os.path.dirname(__file__), "../AppServer"))
from google.appengine.api import api_base_pb
from google.appengine.api import datastore_errors

from google.appengine.datastore import appscale_stub_util
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.datastore import entity_pb
from google.appengine.datastore import sortable_pb_encoder

from google.appengine.runtime import apiproxy_errors

from google.appengine.ext import db
from google.appengine.ext.db.metadata import Namespace
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
VALID_DATASTORES = ['cassandra']

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

def reference_property_to_reference(refprop):
  """ Creates a Reference from a ReferenceProperty. 

  Args:
    refprop: A entity_pb.ReferenceProperty object.
  Returns:
    A entity_pb.Reference object. 
  """
  ref = entity_pb.Reference()
  ref.set_app(refprop.app())
  if refprop.has_name_space():
    ref.set_name_space(refprop.name_space())
  for pathelem in refprop.pathelement_list():
    ref.mutable_path().add_element().CopyFrom(pathelem)
  return ref


class DatastoreDistributed():
  """ AppScale persistent layer for the datastore API. It is the 
      replacement for the AppServers to persist their data into 
      a distributed datastore instead of a flat file.
  """
  # Max number of results for a query
  _MAXIMUM_RESULTS = 10000

  # The number of entries looked at when doing a composite query
  # It will keep looking at this size window when getting the result
  _MAX_COMPOSITE_WINDOW = 100000

  # Maximum amount of filter and orderings allowed within a query
  _MAX_QUERY_COMPONENTS = 63

  # For enabling and disabling range inclusivity
  _ENABLE_INCLUSIVITY = True
  _DISABLE_INCLUSIVITY = False

  # Delimiter between app names and namespace and the rest of an entity key
  _NAMESPACE_SEPARATOR = dbconstants.KEY_DELIMITER

  # Delimiter between parameters in index keys.
  _SEPARATOR = dbconstants.KEY_DELIMITER

  # This is the terminating string for range queries
  _TERM_STRING = chr(255) * 500

  # Smallest possible value that is considered non-null and indexable.
  MIN_INDEX_VALUE = (499 * '\x00') + '\x01'

  # When assigning the first allocated ID, give this value
  _FIRST_VALID_ALLOCATED_ID = 1

  # The key we use to lock for allocating new IDs
  _ALLOCATE_ROOT_KEY = "__allocate__"

  # Number of times to retry acquiring a lock for non transactions.
  NON_TRANS_LOCK_RETRY_COUNT = 5

  # How long to wait before retrying to grab a lock
  LOCK_RETRY_TIME = .5

  # Maximum number of allowed composite indexes any one application can
  # register.
  _MAX_NUM_INDEXES = 1000

  def __init__(self, datastore_batch, zookeeper=None):
    """
       Constructor.
     
     Args:
       datastore_batch: A reference to the batch datastore interface.
       zookeeper: A reference to the zookeeper interface.
    """
    logging.basicConfig(format='%(asctime)s %(levelname)s %(filename)s:' \
      '%(lineno)s %(message)s ', level=logging.ERROR)
    logging.debug("Started logging")

    # datastore accessor used by this class to do datastore operations.
    self.datastore_batch = datastore_batch 

    # zookeeper instance for accesing ZK functionality.
    self.zookeeper = zookeeper

  @staticmethod
  def get_entity_kind(key_path):
    """ Returns the Kind of the Entity. A Kind is like a type or a 
        particular class of entity.

    Args:
        key_path: A str, the key path of entity.
    Returns:
        A str, the kind of the entity.
    """
    if isinstance(key_path, entity_pb.EntityProto):
      key_path = key_path.key()
    return key_path.path().element_list()[-1].type()

  def get_limit(self, query):
    """ Returns the limit that should be used for the given query.
  
    Args:
      query: A datastore_pb.Query.
    Returns:
      An int, the limit to be used when accessing the datastore.
    """
    limit = self._MAXIMUM_RESULTS
    if query.has_limit():
      limit = min(query.limit(), self._MAXIMUM_RESULTS)
    if query.has_offset():
      limit = limit + query.offset() 
    if limit <= 0:
      limit = 1
    return limit

  def get_entity_key(self, prefix, pb):
    """ Returns the key for the entity table.
    
    Args:
        prefix: A str, the app name and namespace string
          example-- 'guestbook/mynamespace'.
        pb: Protocol buffer that we will encode the index name.
    Returns:
        A str, the key for entity table.
    """
    return buffer("{0}{1}{2}".format(prefix, self._NAMESPACE_SEPARATOR,
      self.__encode_index_pb(pb)))

  def get_meta_data_key(self, app_id, kind, postfix):
    """ Builds a key for the metadata table.
  
    Args:
      app_id: A string representing the application identifier.
      kind: A string representing the type the key is pointing to.
      postfix: A unique identifier for the given key.
    Returns:
      A string which can be used as a key to the metadata table.
    """
    return "{0}{3}{1}{3}{2}".format(app_id, kind, postfix, 
      dbconstants.KEY_DELIMITER)


  def get_kind_key(self, prefix, key_path):
    """ Returns a key for the kind table.
    
    Args:
        prefix: A str, the app name and namespace.
        key_path: A str, the key path to build row key with.
    Returns:
        A str, the row key for kind table.
    """
    path = []
    path.append(key_path.element_list()[-1].type())
    for e in key_path.element_list():
      if e.has_name():
        key_id = e.name()
      elif e.has_id():
        # make sure ids are ordered lexigraphically by making sure they 
        # are of set size i.e. 2 > 0003 but 0002 < 0003
        key_id = str(e.id()).zfill(ID_KEY_LENGTH)
      path.append("{0}:{1}".format(e.type(), key_id))
    encoded_path = dbconstants.KIND_SEPARATOR.join(path)
    encoded_path += dbconstants.KIND_SEPARATOR
    
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
      """ Takes a protocol buffer and returns the encoded path. """
      path = []
      for e in pb.element_list():
        if e.has_name():
          key_id = e.name()
        elif e.has_id():
          key_id = str(e.id()).zfill(ID_KEY_LENGTH)
        path.append("{0}:{1}".format(e.type(), key_id))
      val = dbconstants.KIND_SEPARATOR.join(path)
      val += dbconstants.KIND_SEPARATOR
      return val

    if isinstance(pb, entity_pb.PropertyValue) and pb.has_uservalue():
      userval = entity_pb.PropertyValue()
      userval.mutable_uservalue().set_email(pb.uservalue().email())
      userval.mutable_uservalue().set_auth_domain("")
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
            'Each key path element should have id or name but not both: {0}' \
            .format(key))

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
    return "{0}{4}{1}{5}{2}{5}{3}".format(app_id, name_space, kind, index_name, 
      self._NAMESPACE_SEPARATOR, dbconstants.KEY_DELIMITER)

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

    prefix = "{0}{2}{1}".format(data[0], data[1], 
      self._SEPARATOR).replace('"', '""')

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
      key = self._SEPARATOR.join(params[:-1]) + self._SEPARATOR
    else:
      key = self._SEPARATOR.join(params)
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

        if reverse:
          val = helper_functions.reverse_lex(val)

        params = [prefix, 
                  self.get_entity_kind(e), 
                  p.name(), 
                  val, 
                  str(self.__encode_index_pb(e.key().path()))]

        index_key = self.get_index_key_from_params(params)
        p_vals = [index_key,
                  buffer(prefix + self._SEPARATOR) + \
                  self.__encode_index_pb(e.key().path())] 
        all_rows.append(p_vals)
    return tuple(ii for ii in all_rows)

  def delete_composite_indexes(self, entities, composite_indexes):
    """ Deletes the composite indexes in the DB for the given entities.

    Args:
       entities: A list of EntityProto for which their indexes are to be 
         deleted.
       compsite_indexes: A list of datastore_pb.CompositeIndex.
    """
    if len(entities) == 0: 
      return

    row_keys = []
    for ent in entities:
      for index_def in composite_indexes:
        kind = self.get_entity_kind(ent.key())
        if index_def.definition().entity_type() != kind:
          continue
        composite_index_key = self.get_composite_index_key(index_def, ent)  
        row_keys.append(composite_index_key)

    self.datastore_batch.batch_delete(dbconstants.COMPOSITE_TABLE, 
                                      row_keys, 
                                      column_names=dbconstants.COMPOSITE_SCHEMA)
 
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
        try:
          txn_id = txn_hash[self.get_root_key_from_entity_key(str(ii[0]))]
          row_values[str(ii[0])] = \
            {dbconstants.APP_ENTITY_SCHEMA[0]:str(ii[1]), #ent
            dbconstants.APP_ENTITY_SCHEMA[1]:str(txn_id)} #txnid
        except KeyError, key_error:
          logging.error("Key we are trying to get the root: {0}".\
            format(str(ii[0])))
          logging.error("Root key we got: {0}".\
            format(self.get_root_key_from_entity_key(str(ii[0]))))
          raise key_error
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

  def get_composite_index_key(self, index, entity):
    """ Creates a key to the composite index table for a given entity.

    Keys are built as such: 
      app_id/ns/composite_id/ancestor/valuevaluevalue..../entity_key
    Components explained:
    ns: The namespace of the entity.
    composite_id: The composite ID assigned to this index upon creation.
    ancestor: The root ancestor path (only if the query this index is for 
      has an ancestor)
    value(s): The string representation of mulitiple properties.
    entity_key: The entity key (full path) used as a means of having a unique
      identifier. This prevents two entities with the same values from
      colliding. 

    Args:
      index: A datstore_pb.CompositeIndex.
      entity: A entity_pb.EntityProto.
    Returns:
      A string representing a key to the composite table.
    """ 
    composite_id = index.id()
    definition = index.definition()
    app_id = entity.key().app()
    name_space = entity.key().name_space()
    ent_key = self.__encode_index_pb(entity.key().path())
    pre_comp_index_key = "{0}{1}{2}{4}{3}{4}".format(app_id, 
      self._NAMESPACE_SEPARATOR, name_space, composite_id, self._SEPARATOR)
    if definition.ancestor() == 1:
      ancestor = self.get_root_key_from_entity_key(str(ent_key))
      pre_comp_index_key += "{0}{1}".format(ancestor, self._SEPARATOR) 

    value_dict = {}
    for prop in entity.property_list():
      value_dict[prop.name()]  = str(self.__encode_index_pb(prop.value()))

    index_value = ""
    for prop in definition.property_list():
      name = prop.name()
      value = ''
      if name in value_dict:
        value = value_dict[name]
      elif name == "__key__":
        value = self.__encode_index_pb(entity.key().path())
      if prop.direction() == entity_pb.Index_Property.DESCENDING:
        value = helper_functions.reverse_lex(value)
      # Should there be a separator between values?
      index_value += str(value)

    # We append the ent key to have unique keys if entities happen
    # to share the same index values (and ancestor).
    composite_key = "{0}{1}{2}{3}".format(pre_comp_index_key, index_value,
      self._SEPARATOR, ent_key)
    return composite_key
  
  def insert_composite_indexes(self, entities, composite_indexes):
    """ Creates composite indexes for a set of entities.

    Args:
      entities: A list entities.
      composite_indexes: A list of datastore_pb.CompositeIndex.
    """
    if not composite_indexes:
      return
    row_keys = []
    row_values = {}
    # Create default composite index for all entities. Here we take each
    # of the properties in one 
    for ent in entities:
      for index_def in composite_indexes:
        # Skip any indexes if the kind does not match.
        kind = self.get_entity_kind(ent.key())
        if index_def.definition().entity_type() != kind:
          continue
  
        # Get the composite index key.
        composite_index_key = self.get_composite_index_key(index_def, ent)  
        row_keys.append(composite_index_key)

        # Get the reference value for the composite table.
        entity_key = str(self.__encode_index_pb(ent.key().path()))
        prefix = self.get_table_prefix(ent.key())
        reference = "{0}{1}{2}".format(prefix, self._SEPARATOR,  entity_key)
        row_values[composite_index_key] = {'reference': reference}
        # TODO: must deal with all combinations of indexes. 
        # See exploding indexes: 
        # https://developers.google.com/appengine/docs/python/datastore/indexes

    self.datastore_batch.batch_put_entity(dbconstants.COMPOSITE_TABLE, 
                                          row_keys, 
                                          dbconstants.COMPOSITE_SCHEMA,
                                          row_values)
     
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
      row_keys += [str(ii[0]) for ii in group_rows]
      for ii in group_rows:
        row_values[str(ii[0])] = {'reference': str(ii[1])}
 
    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      rev_group_rows = self.get_index_kv_from_tuple(group, True)
      rev_row_keys += [str(ii[0]) for ii in rev_group_rows]
      for ii in rev_group_rows:
        rev_row_values[str(ii[0])] = {'reference': str(ii[1])}
    
    # TODO update all indexes in parallel
    self.datastore_batch.batch_put_entity(dbconstants.ASC_PROPERTY_TABLE, 
                          row_keys, 
                          dbconstants.PROPERTY_SCHEMA, 
                          row_values)

    self.datastore_batch.batch_put_entity(dbconstants.DSC_PROPERTY_TABLE, 
                          rev_row_keys,  
                          dbconstants.PROPERTY_SCHEMA,
                          rev_row_values)

  def get_indices(self, app_id):
    """ Gets the indices of the given application.

    Args:
       app_id: Name of the application.
    Returns: 
       Returns a list of encoded entity_pb.CompositeIndex objects.
    """
    start_key = self.get_meta_data_key(app_id, "index", "")
    end_key = self.get_meta_data_key(app_id, "index", self._TERM_STRING)
    result = self.datastore_batch.range_query(dbconstants.METADATA_TABLE,
                                                dbconstants.METADATA_SCHEMA,
                                                start_key,
                                                end_key,
                                                self._MAX_NUM_INDEXES,
                                                offset=0,
                                                start_inclusive=True,
                                                end_inclusive=True)
    list_result = []
    for list_item in result:
      for key, value in list_item.iteritems():
        list_result.append(value['data']) 
    return list_result

  def delete_composite_index_metadata(self, app_id, index):
    """ Deletes a index for the given application identifier.
  
    Args:
      app_id: A string representing the application identifier.
      index: A entity_pb.CompositeIndex object.
    """
    index_keys = []
    composite_id = index.id() 
    index_keys.append(self.get_meta_data_key(app_id, "index", composite_id))
    self.datastore_batch.batch_delete(dbconstants.METADATA_TABLE,
                                      index_keys, 
                                      column_names=dbconstants.METADATA_TABLE)

  def create_composite_index(self, app_id, index):
    """ Stores a new index for the given application identifier.
  
    Args:
      app_id: A string representing the application identifier.
      index: A entity_pb.CompositeIndex object.
    Returns:
      A unique number representing the composite index ID.
    """
    # Generate a random number based on time of creation.
    rand = int(str(int(time.time())) + str(random.randint(0, 999999)))
    index.set_id(rand)
    encoded_entity = index.Encode()
    row_key = self.get_meta_data_key(app_id, "index", rand)
    row_keys = [row_key]
    row_values = {}
    row_values[row_key] = {dbconstants.METADATA_SCHEMA[0]: encoded_entity}
    self.datastore_batch.batch_put_entity(dbconstants.METADATA_TABLE, 
                                          row_keys, 
                                          dbconstants.METADATA_SCHEMA, 
                                          row_values)    
    return rand 

  def allocate_ids(self, app_id, size, max_id=None, num_retries=0):
    """ Allocates IDs from either a local cache or the datastore. 

    Args:
      app_id: A str representing the application identifer.
      size: Number of IDs to allocate.
      max_id: If given increase the next IDs to be greater than this value.
      num_retries: The number of retries left to get an ID.
    Returns:
      Tuple of start and end ids.
    Raises: 
      ValueError: If size is less than or equal to 0.
      ZKTransactionException: If we are unable to increment the ID counter.
    """
    if size and max_id:
      raise ValueError("Both size and max cannot be set.")
    try:
      prev = 0
      current = 0
      if size:
        prev, current = self.zookeeper.increment_and_get_counter(
          "/{0}/counter".format(app_id), size)
      elif max_id: 
        prev, current = self.zookeeper.increment_and_get_counter(
          "/{0}/counter".format(app_id), 0)
        if current < max_id:
          prev, current = self.zookeeper.increment_and_get_counter(
            "/{0}/counter".format(app_id), max_id - current + 1)
          
    except ZKTransactionException, zk_exception:
      if num_retries > 0:
        logging.warning("Having to retry on allocate ids for {0}" \
          .format(app_id))
        return self.allocate_ids(app_id, size, max_id=max_id, 
          num_retries=num_retries - 1)
      else:
        raise zk_exception

    return prev + 1, current

  def put_entities(self, app_id, entities, txn_hash, composite_indexes=None):
    """ Updates indexes of existing entities, inserts new entities and 
        indexes for them.

    Args:
      app_id: The application ID.
      entities: List of entities.
      txn_hash: A mapping of root keys to transaction IDs.
      composite_indexes: A list of entity_pb.CompositeIndex.
    """
    sorted_entities = sorted((self.get_table_prefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(sorted_entities, lambda x: x[0]):
      keys = [e.key() for e in entities]
      # Delete the old entities and indexes.
      self.delete_entities(app_id, keys, txn_hash, soft_delete=False, 
        composite_indexes=composite_indexes)

      # Insert the new entities and indexes.
      self.insert_entities(entities, txn_hash)
      self.insert_index_entries(entities)
      self.insert_composite_indexes(entities, composite_indexes)

  def delete_entities(self, app_id, keys, txn_hash, soft_delete=False, 
    composite_indexes=[]):
    """ Deletes the entities and the indexes associated with them.

    Args:
      app_id: The application ID.
      keys: list of keys to be deleted.
      txn_hash: A mapping of root keys to transaction IDs.
      soft_delete: Boolean if we should soft delete entities.
                   Default is to not delete entities from the 
                   entity table (neither soft or hard). 
      composite_indexes: A list of CompositeIndex objects. 
    """
    def row_generator(key_list):
      """ Generates a ruple of keys and encoded entities. """
      for prefix, k in key_list:
        yield (self.get_entity_key(prefix, k.path()),
               buffer(k.Encode()))

    def kind_row_generator(key_list):
      """ Generates key/values for the kind table. """
      for prefix, k in key_list:
        # Yield a tuple of kind key and a reference to entity table.
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

    # Must fetch the entities to get the keys of indexes before deleting.
    ret = self.datastore_batch.batch_get_entity(dbconstants.APP_ENTITY_TABLE, 
      row_keys, dbconstants.APP_ENTITY_SCHEMA)

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
      # Entities may not exist if this is the first put.
      if dbconstants.APP_ENTITY_SCHEMA[0] in ret[row_key] and \
           not ret[row_key][dbconstants.APP_ENTITY_SCHEMA[0]]. \
           startswith(TOMBSTONE):
        ent = entity_pb.EntityProto()
        ent.ParseFromString(ret[row_key][dbconstants.APP_ENTITY_SCHEMA[0]])
        entities.append(ent)

    # Delete associated indexes.
    self.delete_index_entries(entities)
    if composite_indexes:
      self.delete_composite_indexes(entities, composite_indexes)

  def get_journal_key(self, row_key, version):
    """ Creates a string for a journal key.
  
    Args:
      row_key: The entity key for which we want to create a journal key.
      version: The version of the entity we are going to save.
    Returns:
      A string representing a journal key.
    """
    row_key += self._SEPARATOR
    zero_padded_version = ("0" * (ID_KEY_LENGTH - len(str(version)))) + \
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
      value = row_values[row_key] \
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
        prev_version = long(old_entities[row_key] \
            [dbconstants.APP_ENTITY_SCHEMA[1]])
        # Validate and get the correct version for each key.
        root_key = self.get_root_key_from_entity_key(row_key)
        valid_prev_version = self.zookeeper.get_valid_transaction_id(
          app_id, prev_version, row_key)
        # Guard against re-registering the rollback version if 
        # we're updating the same key repeatedly in a transaction.
        if txn_hash[root_key] != valid_prev_version:
          try:
            self.zookeeper.register_updated_key(app_id, txn_hash[root_key], 
              valid_prev_version, row_key) 
          except ZKInternalException:
            raise ZKTransactionException("Unable to register key for " \
              "old entities {0}, txn_hash {1}, and app id {2}".format(
              old_entities, txn_hash, app_id))

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

    num_of_required_ids = 0
    for entity in entities:
      last_path = entity.key().path().element_list()[-1]
      if last_path.id() == 0 and not last_path.has_name():
        num_of_required_ids += 1

    start_id = None
    if num_of_required_ids > 0:
      start_id, _ = self.allocate_ids(app_id, num_of_required_ids, 
        num_retries=3)

    id_counter = 0
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
        last_path.set_id(start_id + id_counter)
        id_counter += 1
        group = entity.mutable_entity_group()
        root = entity.key().path().element(0)
        group.add_element().CopyFrom(root)

    # This hash maps transaction IDs to root keys.
    txn_hash = {}
    try:
      if put_request.has_transaction():
        txn_hash = self.acquire_locks_for_trans(entities, 
                        put_request.transaction().handle())
      else:
        txn_hash = self.acquire_locks_for_nontrans(app_id, entities, 
          retries=self.NON_TRANS_LOCK_RETRY_COUNT) 
      self.put_entities(app_id, entities, txn_hash, 
        composite_indexes=put_request.composite_index_list())
      if not put_request.has_transaction():
        self.release_locks_for_nontrans(app_id, entities, txn_hash)
      put_response.key_list().extend([e.key() for e in entities])
    except ZKTransactionException, zkte:
      logging.warning("Concurrent transaction exception for app id {0} with " \
        "info {1}".format(app_id, str(zkte)))
      for root_key in txn_hash:
        self.zookeeper.notify_failed_transaction(app_id, txn_hash[root_key])
      raise zkte
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.exception("Connection issue with datastore for app id {0}, " \
        "info {1}".format(app_id, str(dbce)))
      for root_key in txn_hash:
        self.zookeeper.notify_failed_transaction(app_id, txn_hash[root_key])
      raise dbce


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
      tokens = entity_key.split(dbconstants.KIND_SEPARATOR)
      return tokens[0] + dbconstants.KIND_SEPARATOR
    elif isinstance(entity_key, entity_pb.Reference):
      app_id = entity_key.app()
      path = entity_key.path()
      element_list = path.element_list()
      return self.get_root_key(app_id, entity_key.name_space(), element_list)
    else:
      raise TypeError("Unable to get root key from given type of %s" % \
                      entity_key.__class__)  

  def acquire_locks_for_nontrans(self, app_id, entities, retries=0):
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
    root_keys = []
    txn_hash = {} 
    if not isinstance(entities, list):
      raise TypeError("Expected a list and got {0}".format(entities.__class__))
    for ent in entities:
      if isinstance(ent, entity_pb.Reference):
        root_keys.append(self.get_root_key_from_entity_key(ent))
      elif isinstance(ent, entity_pb.EntityProto):
        root_keys.append(self.get_root_key_from_entity_key(ent.key()))
      else:
        raise TypeError("Excepted either a reference or an EntityProto, "\
          "got {0}".format(ent.__class__))

    # Remove all duplicate root keys.
    root_keys = list(set(root_keys))
    try:
      for root_key in root_keys:
        txnid = self.setup_transaction(app_id, is_xg=False)
        txn_hash[root_key] = txnid
        self.zookeeper.acquire_lock(app_id, txnid, root_key)
    except ZKTransactionException, zkte:
      logging.warning("Concurrent transaction exception for app id {0} with " \
        "info {1}".format(app_id, str(zkte)))
      if retries > 0:
        logging.warning("Trying again to acquire lock" \
          "info {1} with retry #{2}".format(app_id, str(zkte), retries))
        time.sleep(self.LOCK_RETRY_TIME)
        return dict(self.acquire_locks_for_nontrans(app_id, entities,
          retries-1).items() + txn_hash.items())
      for key in txn_hash:
        self.zookeeper.notify_failed_transaction(app_id, txn_hash[key])
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
      # Make sure ids are ordered lexigraphically by making sure they 
      # are of set size i.e. 2 > 0003 but 0002 < 0003.
      key_id = str(first_ent.id()).zfill(ID_KEY_LENGTH)
    return "{0}{1}{2}:{3}{4}".format(prefix, self._NAMESPACE_SEPARATOR, 
      first_ent.type(), key_id, dbconstants.KIND_SEPARATOR)

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
    root_keys = []
    txn_hash = {}
    if not self.is_instance_wrapper(entities, list):
      raise TypeError("Expected a list and got {0}".format(entities.__class__))
    for ent in entities:
      if self.is_instance_wrapper(ent, entity_pb.Reference):
        root_keys.append(self.get_root_key_from_entity_key(ent))
      elif self.is_instance_wrapper(ent, entity_pb.EntityProto):
        root_keys.append(self.get_root_key_from_entity_key(ent.key()))
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
    root_keys = list(set(root_keys))
    try:
      for root_key in root_keys:
        txn_hash[root_key] = txnid
        self.zookeeper.acquire_lock(app_id, txnid, root_key)
    except ZKTransactionException, zkte:
      logging.warning("Concurrent transaction exception for app id {0} with " \
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
      return self.validated_dict_result(app_id, db_results, 
        current_ongoing_txn=0)
    elif isinstance(db_results, list):
      return self.validated_list_result(app_id, db_results, 
        current_ongoing_txn=0)
    else:
      raise TypeError("db_results should be either a list or dict")

  def validated_list_result(self, app_id, db_results, current_ongoing_txn=0):
    """ Takes database results from the entity table and returns
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
            journal_entities[journal_key][dbconstants.JOURNAL_SCHEMA[0]], 
          dbconstants.APP_ENTITY_SCHEMA[1]: str(trans_id)
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
      current_version = long(db_results[row_key] \
        [dbconstants.APP_ENTITY_SCHEMA[1]])
      trans_id = self.zookeeper.get_valid_transaction_id( \
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
      dbconstants.JOURNAL_TABLE, journal_keys, dbconstants.JOURNAL_SCHEMA)
    for journal_key in journal_result_map:
      row_key, trans_id = journal_result_map[journal_key]
      if trans_id == 0:
        # Zero id's are entities which do not yet exist.
        del db_results[row_key]
      else:
        db_results[row_key] = {
          dbconstants.APP_ENTITY_SCHEMA[0]: 
            journal_entities[journal_key][dbconstants.JOURNAL_SCHEMA[0]], 
          dbconstants.APP_ENTITY_SCHEMA[1]: str(trans_id)
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
        if not result[item][dbconstants.APP_ENTITY_SCHEMA[0]]. \
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
      row_keys.append("{0}{2}{1}".format(prefix, index_key, self._SEPARATOR))
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
        self.zookeeper.acquire_lock(app_id, txnid, root_key)
      except ZKTransactionException, zkte:
        logging.warning("Concurrent transaction exception for app id {0} " \
          "with transaction id {1}, and info {2}".format(app_id, txnid, 
          str(zkte)))
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

    ent_kinds = []
    for key in delete_request.key_list():
      last_path = key.path().element_list()[-1]
      if last_path.type() not in ent_kinds:
        ent_kinds.append(last_path.type())

    if delete_request.has_transaction():
      txn_hash = self.acquire_locks_for_trans(keys, 
        delete_request.transaction().handle())
    else:
      txn_hash = self.acquire_locks_for_nontrans(app_id, keys, 
        retries=self.NON_TRANS_LOCK_RETRY_COUNT) 

    # We use the marked changes field to signify if we should 
    # look up composite indexes because delete request do not
    # include that information.
    composite_indexes = []
    filtered_indexes = []
    if delete_request.has_mark_changes():
      all_composite_indexes = self.get_indices(app_id)
      for index in all_composite_indexes:
        new_index = entity_pb.CompositeIndex()
        new_index.ParseFromString(index)
        composite_indexes.append(new_index)
      # Only get composites of the correct kinds.
      for index in composite_indexes:
        if index.definition().entity_type() in ent_kinds:
          filtered_indexes.append(index)
 
    self.delete_entities(app_id, delete_request.key_list(), txn_hash, 
      composite_indexes=filtered_indexes, soft_delete=True)

    if not delete_request.has_transaction():
      self.release_locks_for_nontrans(app_id, keys, txn_hash)
 
  def generate_filter_info(self, filters):
    """Transform a list of filters into a more usable form.

    Args:
      filters: A list of filter PBs.
    Returns:
      A dict mapping property names to lists of (op, value) tuples.
    """
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
      return "{0}{2}{1}".format(prefix, 
        self.__encode_index_pb(e.key().path()), self._SEPARATOR)
     
    if e.property_list():
      plist = e.property_list()
    else:   
      rkey = "{0}{2}{1}".format(prefix, 
        self.__encode_index_pb(e.key().path()), self._SEPARATOR)
      ret = self.datastore_batch.batch_get_entity(dbconstants.APP_ENTITY_TABLE, 
        [rkey], dbconstants.APP_ENTITY_SCHEMA)

      ret = self.remove_tombstoned_entities(ret)

      if dbconstants.APP_ENTITY_SCHEMA[0] in ret[rkey]:
        ent = entity_pb.EntityProto(ret[rkey][dbconstants.APP_ENTITY_SCHEMA[0]])
        plist = ent.property_list() 

    for p in plist:
      if p.name() == prop_name:
        break

    val = str(self.__encode_index_pb(p.value()))

    if order == datastore_pb.Query_Order.DESCENDING:
      val = helper_functions.reverse_lex(val)        
    params = [prefix, self.get_entity_kind(e), p.name(), val, 
      str(self.__encode_index_pb(e.key().path()))]
    return self.get_index_key_from_params(params)

  def is_zigzag_merge_join(self, query, filter_info, order_info):
    """ Checks to see if the current query can be executed as a zigzag
    merge join.

    Args:
      query: A datastore_pb.Query.
      filter_info: dict of property names mapping to tuples of filter 
        operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      True if it qualifies as a zigzag merge join, and false otherwise.
    """
    #if query.has_ancestor():
    #  return False

    filter_info = self.remove_exists_filters(filter_info)

    order_properties = []
    for order in order_info:
      order_properties.append(order[0])

    property_names = []
    for property_name in filter_info:
      filt = filter_info[property_name]
      # There should only be one filter property for a given property.
      if len(filt) > 1:
        return False
      property_names.append(property_name)
      # We only handle equality filters for zigzag merge join queries.
      if filt[0][0] != datastore_pb.Query_Filter.EQUAL: 
        return False

    if len(filter_info) < 2:
      return False

    # Check to make sure no property names show up twice.
    # Casting a copy of the list to a set will remove duplicates, 
    # and then we check to make sure it is still consistent with the 
    # previous list.
    if list(set(property_names[:])) != property_names:
      return False

    for order_property_name in order_properties:
      if order_property_name not in property_names:
        return False

    return True

  def __fetch_entities_from_row_list(self, rowkeys, app_id):
    """ Given a list of keys fetch the entities from the entity table.
    
    Args:
      rowkeys: A list of strings which are keys to the entitiy table.
      app_id: A string, the application identifier.
    Returns:
      A list of entities.
    """
    result = self.datastore_batch.batch_get_entity(
      dbconstants.APP_ENTITY_TABLE, rowkeys, dbconstants.APP_ENTITY_SCHEMA)
    result = self.validated_result(app_id, result)
    result = self.remove_tombstoned_entities(result)
    entities = []
    keys = result.keys()
    for key in rowkeys:
      if key in result and dbconstants.APP_ENTITY_SCHEMA[0] in result[key]:
        entities.append(result[key][dbconstants.APP_ENTITY_SCHEMA[0]])
    return entities 

  def __fetch_entities(self, refs, app_id):
    """ Given the results from a table scan, get the references.
    
    Args: 
      refs: key/value pairs where the values contain a reference to 
            the entitiy table.
      app_id: A string, the application identifier.
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
    return self.__fetch_entities_from_row_list(rowkeys, app_id)

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
    path = buffer(prefix + self._SEPARATOR) + \
      self.__encode_index_pb(ancestor.path())
    txn_id = 0
    if query.has_transaction():
      txn_id = query.transaction().handle()   
      root_key = self.get_root_key_from_entity_key(ancestor)
      try:
        prefix = self.get_table_prefix(query)
        self.zookeeper.acquire_lock(query.app(), txn_id, root_key)
      except ZKTransactionException, zkte:
        logging.warning("Concurrent transaction exception for app id {0}, " \
          "transaction id {1}, info {2}".format(query.app(), txn_id, str(zkte)))
        self.zookeeper.notify_failed_transaction(query.app(), txn_id)
        raise zkte

    startrow = path
    endrow = path + self._TERM_STRING
    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, None, None, last_result)
      start_inclusive = self._DISABLE_INCLUSIVITY

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
    limit = self.get_limit(query)
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
    path = buffer(prefix + self._SEPARATOR) + \
      self.__encode_index_pb(ancestor.path())
    txn_id = 0
    if query.has_transaction(): 
      txn_id = query.transaction().handle()   
      root_key = self.get_root_key_from_entity_key(ancestor)
      try:
        self.zookeeper.acquire_lock(query.app(), txn_id, root_key)
      except ZKTransactionException, zkte:
        logging.warning("Concurrent transaction exception for app id {0}, " \
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
        startrow = prefix + self._SEPARATOR + __key__
        endrow = prefix + self._SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN:
        start_inclusive = self._DISABLE_INCLUSIVITY
        startrow = prefix + self._SEPARATOR + __key__ 
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        startrow = prefix + self._SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.LESS_THAN:
        endrow = prefix + self._SEPARATOR  + __key__
        end_inclusive = self._DISABLE_INCLUSIVITY
      elif op and op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        endrow = prefix + self._SEPARATOR + __key__ 

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, None, None, last_result)
      start_inclusive = self._DISABLE_INCLUSIVITY

    if startrow > endrow:
      return []

    limit = self.get_limit(query)
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

    if '__key__' in filter_info:
      __key__ = str(filter_info['__key__'][0][1])
      op = filter_info['__key__'][0][0]
    else:
      __key__ = ''
      op = None

    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY

    startrow = prefix + self._SEPARATOR + __key__
    endrow = prefix + self._SEPARATOR + self._TERM_STRING

    if op and op == datastore_pb.Query_Filter.EQUAL:
      startrow = prefix + self._SEPARATOR + __key__
      endrow = prefix + self._SEPARATOR + __key__
    elif op and op == datastore_pb.Query_Filter.GREATER_THAN:
      start_inclusive = self._DISABLE_INCLUSIVITY
      startrow = prefix + self._SEPARATOR + __key__ 
      endrow = prefix + self._SEPARATOR + self._TERM_STRING
      end_inclusive = self._DISABLE_INCLUSIVITY
    elif op and op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
      startrow = prefix + self._SEPARATOR + __key__
      endrow = prefix + self._SEPARATOR + self._TERM_STRING
      end_inclusive = self._DISABLE_INCLUSIVITY
    elif op and op == datastore_pb.Query_Filter.LESS_THAN:
      startrow = prefix + self._SEPARATOR  
      endrow = prefix + self._SEPARATOR + __key__
      end_inclusive = self._DISABLE_INCLUSIVITY
    elif op and op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
      startrow = prefix + self._SEPARATOR 
      endrow = prefix + self._SEPARATOR + __key__ 

    if not order_info:
      order = None
      prop_name = None
    
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, prop_name, order, last_result)
      start_inclusive = self._DISABLE_INCLUSIVITY

    limit = self.get_limit(query)
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
    tokens = key.split(dbconstants.KIND_SEPARATOR)
    tokens.reverse() 
    key = dbconstants.KIND_SEPARATOR.join(tokens)[1:] + \
      dbconstants.KIND_SEPARATOR
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
    ancestor_filter = ""
    if query.has_ancestor():
      ancestor = query.ancestor()
      ancestor_filter = self.__encode_index_pb(ancestor.path())      
    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY
    prefix = self.get_table_prefix(query)
    startrow = prefix + self._SEPARATOR + query.kind() + \
      dbconstants.KIND_SEPARATOR + \
      str(ancestor_filter)
    endrow = prefix + self._SEPARATOR + query.kind() + \
      dbconstants.KIND_SEPARATOR + \
      str(ancestor_filter) + \
      self._TERM_STRING
    if '__key__' not in filter_info:
      return startrow, endrow, start_inclusive, end_inclusive

    for key_filter in filter_info['__key__']:
      op = key_filter[0]
      __key__ = str(key_filter[1])
      if op and op == datastore_pb.Query_Filter.EQUAL:
        startrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
        endrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN:
        start_inclusive = self._DISABLE_INCLUSIVITY
        startrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__ 
      elif op and op == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        startrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
      elif op and op == datastore_pb.Query_Filter.LESS_THAN:
        endrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__
        end_inclusive = self._DISABLE_INCLUSIVITY
      elif op and op == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        endrow = prefix + self._SEPARATOR + query.kind() + \
          dbconstants.KIND_SEPARATOR + __key__ 
    return startrow, endrow, start_inclusive, end_inclusive

  def namespace_query(self):
    """ Performs a metadata namespace query.
 
    Returns:
      A list of entity protos holding Namespace kinds.
    """
    #TODO implement where we return all active namespaces.
    default_namespace = Namespace(id=1)
    protobuf = db.model_to_protobuf(default_namespace)
    return [protobuf.Encode()]

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
    filter_info = self.remove_exists_filters(filter_info)
    # Detect quickly if this is a kind query or not.
    for fi in filter_info:
      if fi != "__key__":
        return None
    
    order = None
    prop_name = None
    if query.has_ancestor() and len(order_info) > 0:
      return self.ordered_ancestor_query(query, filter_info, order_info)
    if query.has_ancestor() and not query.has_kind():
      return self.ancestor_query(query, filter_info, order_info)
    elif not query.has_kind():
      return self.kindless_query(query, filter_info, order_info)
    elif query.kind() == "__namespace__":
      return self.namespace_query()
 
    startrow, endrow, start_inclusive, end_inclusive = \
          self.kind_query_range(query, filter_info, order_info)
    if startrow == None or endrow == None:
      return None
    
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      prefix = self.get_table_prefix(query)
      startrow = self.get_kind_key(prefix, last_result.key().path())
      start_inclusive = self._DISABLE_INCLUSIVITY
    limit = self.get_limit(query)
    if startrow > endrow:
      return []

    result = self.datastore_batch.range_query(dbconstants.APP_KIND_TABLE, 
                                              dbconstants.APP_KIND_SCHEMA, 
                                              startrow, 
                                              endrow, 
                                              limit, 
                                              offset=0, 
                                              start_inclusive=start_inclusive, 
                                              end_inclusive=end_inclusive)
    return self.__fetch_entities(result, query.app())

  def remove_exists_filters(self, filter_info):
    """ We don't have native support for projection queries, so remove
    any filters that have EXISTS filters.
  
    Args:
      filter_info: dict of property names mapping to tuples of filter 
        operators and values.
    Returns:
      A filter info dictionary without any EXIST filters.
    """
    filtered = {}
    for key in filter_info.keys():
      if filter_info[key][0][0] == datastore_pb.Query_Filter.EXISTS:
        continue
      else:
        filtered[key] = filter_info[key]
    return filtered

  def __single_property_query(self, query, filter_info, order_info):
    """Performs queries satisfiable by the Single_Property tables.

    Args:
      query: The query to run.
      filter_info: tuple with filter operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      List of entities retrieved from the given query.
    """
    filter_info = self.remove_exists_filters(filter_info)
    ancestor = None
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

    # If there is an ancestor in the query, it can only have a single 
    # equality filter, otherwise there is no way to build the start
    # and end key.
    if query.has_ancestor() and len(filter_ops) > 0 and \
      filter_ops[0][0] != datastore_pb.Query_Filter.EQUAL:
      return None

    if query.has_ancestor():
      ancestor = query.ancestor()

    if not query.has_kind():
      return None

    if order_info:
      if order_info[0][0] == property_name:
        direction = order_info[0][1]
    else:
      direction = datastore_pb.Query_Order.ASCENDING

    prefix = self.get_table_prefix(query)

    limit = self.get_limit(query) 

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, property_name, direction, 
        last_result)
    else:
      startrow = None
   
    end_compiled_cursor = None
    if query.has_end_compiled_cursor():
      end_compiled_cursor = query.end_compiled_cursor()

    references = self.__apply_filters(filter_ops, 
                               order_info, 
                               property_name, 
                               query.kind(), 
                               prefix, 
                               limit, 
                               0, 
                               startrow,
                               ancestor=ancestor,
                               query=query,
                               end_compiled_cursor=end_compiled_cursor)

    return self.__fetch_entities(references, query.app())
    
  def __apply_filters(self, 
                     filter_ops, 
                     order_info, 
                     property_name, 
                     kind, 
                     prefix, 
                     limit, 
                     offset, 
                     startrow,
                     force_start_key_exclusive=False,
                     ancestor=None,
                     query=None,
                     end_compiled_cursor=None):
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
      ancestor: Optional query ancestor.
      query: Query object for debugging.
      end_compiled_cursor: A compiled cursor to resume a query.
    Results:
      Returns a list of entity keys.
    Raises:
      NotImplementedError: For unsupported queries.
      AppScaleMisconfiguredQuery: Bad filters or orderings.
    """
    ancestor_filter = None
    if ancestor:
      ancestor_filter = str(self.__encode_index_pb(ancestor.path()))

    end_inclusive = True
    start_inclusive = True

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
      start_inclusive = False

    if end_compiled_cursor:
      position = end_compiled_cursor.position(0)
      index_value = position.indexvalue(0)
      property_name = index_value.property()
      value = index_value.value()
      value = str(self.__encode_index_pb(value))
      key_path = None
      if position.has_key():
        key_path = str(self.__encode_index_pb(position.key().path()))
      params = [prefix, kind, property_name, value, key_path]
      endrow = self.get_index_key_from_params(params)
    # This query is returning based on order on a specfic property name 
    # The start key (if not already supplied) depends on the property
    # name and does not take into consideration its value. The end key
    # is based on the terminating string.
    if len(filter_ops) == 0 and (order_info and len(order_info) == 1):
      if not startrow:
        params = [prefix, kind, property_name, ancestor_filter]
        startrow = self.get_index_key_from_params(params)
      if not endrow:
        params = [prefix, kind, property_name, self._TERM_STRING, None]
        endrow = self.get_index_key_from_params(params)
      if force_start_key_exclusive:
        start_inclusive = False
      result = self.datastore_batch.range_query(table_name, 
                                          column_names, 
                                          startrow, 
                                          endrow, 
                                          limit, 
                                          offset=0, 
                                          start_inclusive=start_inclusive, 
                                          end_inclusive=end_inclusive)      
      return result

    # This query has a value it bases the query on for a property name
    # The difference between operators is what the end and start key are.
    if len(filter_ops) == 1:
      oper = filter_ops[0][0]
      value = str(filter_ops[0][1])

      if direction == datastore_pb.Query_Order.DESCENDING: 
        value = helper_functions.reverse_lex(value)

      if oper == datastore_pb.Query_Filter.EQUAL:
        if ancestor:
          start_value = value + self._SEPARATOR + ancestor_filter
          end_value = value + self._TERM_STRING
        else:
          start_value = value 
          end_value = value + self._TERM_STRING
      elif oper == datastore_pb.Query_Filter.LESS_THAN:
        start_value = None
        end_value = value
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = value + self._TERM_STRING
          end_value = self._TERM_STRING
      elif oper == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        start_value = None
        end_value = value + self._SEPARATOR + self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = value
          end_value = self._TERM_STRING
      elif oper == datastore_pb.Query_Filter.GREATER_THAN:
        if value == '':
          start_value = self._SEPARATOR + self._TERM_STRING
        else:
          start_value = value + self._TERM_STRING
        end_value = self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = None
          end_value = value + self._SEPARATOR 
      elif oper == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        start_value = value
        end_value = self._TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = None
          end_value = value + self._SEPARATOR +  self._TERM_STRING
      else:
        raise NotImplementedError("Unsupported query of operation {0}".format(
          datastore_pb.Query_Filter.Operator_Name(oper)))

      if not startrow:
        params = [prefix, kind, property_name, start_value]
        startrow = self.get_index_key_from_params(params)
        start_inclusive = self._DISABLE_INCLUSIVITY
      if not endrow:
        params = [prefix, kind, property_name, end_value]
        endrow = self.get_index_key_from_params(params)

      if force_start_key_exclusive:
        start_inclusive = False

      if startrow > endrow:
        logging.error("Start row is greater than end row :{0} versus {1}".\
          format(startrow, endrow))
        return []

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
      if filter_ops[0][0] == datastore_pb.Query_Filter.EQUAL or \
        filter_ops[1][0] == datastore_pb.Query_Filter.EQUAL:
        # If one of the filters is EQUAL, set start and end key
        # to the same value.
        if filter_ops[0][0] == datastore_pb.Query_Filter.EQUAL:
          value1 = filter_ops[0][1]
          value2 = filter_ops[1][1]
          oper1 = filter_ops[0][0]
          oper2 = filter_ops[1][0]
        else:
          value1 = filter_ops[1][1]
          value2 = filter_ops[0][1]
          oper1 = filter_ops[1][0]
          oper2 = filter_ops[0][0]
        # Checking to see if filters/values are correct bounds.
        # value1 and oper1 are the EQUALS filter values.
        if oper2 == datastore_pb.Query_Filter.LESS_THAN:
          if value2 > value1 == False:
            return []
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
          if value2 >= value1 == False:
            return []
        elif oper2 == datastore_pb.Query_Filter.GREATER_THAN:
          if value2 < value1 == False:
            return []
        elif oper2 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
          if value2 <= value1 == False:
            return []
        start_inclusive = self._ENABLE_INCLUSIVITY
        end_inclusive = self._DISABLE_INCLUSIVITY
        params = [prefix, kind, property_name, value1 + self._SEPARATOR]
        if not startrow:
          startrow = self.get_index_key_from_params(params)
        else:
          start_inclusive = self._DISABLE_INCLUSIVITY
        if not endrow:
          params = [prefix, kind, property_name, value1 + \
            self._SEPARATOR + self._TERM_STRING]
          endrow = self.get_index_key_from_params(params)
	
        ret = self.datastore_batch.range_query(table_name,
                                         column_names,
                                         startrow,
                                         endrow,
                                         limit,
                                         offset=0,
                                         start_inclusive=start_inclusive,
                                         end_inclusive=end_inclusive) 
        return ret 
      if filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN or \
         filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        oper1 = filter_ops[0][0]
        oper2 = filter_ops[1][0]
        value1 = str(filter_ops[0][1])
        value2 = str(filter_ops[1][1])
      else:
        oper1 = filter_ops[1][0]
        oper2 = filter_ops[0][0]
        value1 = str(filter_ops[1][1])
        value2 = str(filter_ops[0][1])

      if direction == datastore_pb.Query_Order.ASCENDING:
        table_name = dbconstants.ASC_PROPERTY_TABLE
        # The first operator will always be either > or >=.
        if startrow:
          start_inclusive = self._DISABLE_INCLUSIVITY
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN:
          params = [prefix, kind, property_name, value1 + self._SEPARATOR + \
                    self._TERM_STRING]
          startrow = self.get_index_key_from_params(params)
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value1 ]
          startrow = self.get_index_key_from_params(params)
        else:
          raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

        # The second operator will be either < or <=.
        if endrow:
          end_inclusive = self._ENABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN:    
          params = [prefix, kind, property_name, value2]
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._DISABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value2 + self._SEPARATOR + \
                    self._TERM_STRING]
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._ENABLE_INCLUSIVITY
        else:
          raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering") 
      
      if direction == datastore_pb.Query_Order.DESCENDING:
        table_name = dbconstants.DSC_PROPERTY_TABLE
        value1 = helper_functions.reverse_lex(value1)
        value2 = helper_functions.reverse_lex(value2) 

        if endrow:
          end_inclusive = self._ENABLE_INCLUSIVITY
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN:   
          params = [prefix, kind, property_name, value1]
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._DISABLE_INCLUSIVITY
        elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value1 + self._SEPARATOR + \
                    self._TERM_STRING]
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._ENABLE_INCLUSIVITY

        if startrow:
          start_inclusive = self._DISABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN:
          params = [prefix, kind, property_name, value2 + self._SEPARATOR + \
                    self._TERM_STRING]
          startrow = self.get_index_key_from_params(params)
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
          params = [prefix, kind, property_name, value2]
          startrow = self.get_index_key_from_params(params)
        
      if force_start_key_exclusive:
        start_inclusive = False
      if startrow > endrow:
        return []

      return self.datastore_batch.range_query(table_name, 
                                          column_names, 
                                          startrow, 
                                          endrow, 
                                          limit, 
                                          offset=0, 
                                          start_inclusive=start_inclusive, 
                                          end_inclusive=end_inclusive)      
         
    return []

  def zigzag_merge_join(self, query, filter_info, order_info):
    """ Performs a composite query for queries which have multiple 
    equality filters. Uses a varient of the zigzag join merge algorithm.

    This method is used if there are only equality filters present. 
    If there are inequality filters, orders on properties which are not also 
    apart of a filter, or ancestors, this method does 
    not apply.  Existing single property indexes are used and it does not 
    require the user to establish composite indexes ahead of time.
    See http://www.youtube.com/watch?v=AgaL6NGpkB8 for Google's 
    implementation.

    Args:
      query: A datastore_pb.Query.
      filter_info: dict of property names mapping to tuples of filter 
        operators and values.
      order_info: tuple with property name and the sort order.
    Returns:
      List of entities retrieved from the given query.
    """ 
    if not self.is_zigzag_merge_join(query, filter_info, order_info):
      return None
    kind = query.kind()  
    prefix = self.get_table_prefix(query)
    limit = self.get_limit(query)

    count = self._MAX_COMPOSITE_WINDOW
    start_key = ""
    result_list = []
    force_exclusive = False
    more_results = True
    ancestor = None
    if query.has_ancestor():
      ancestor = query.ancestor()

    while more_results:
      reference_counter_hash = {}
      temp_res = {}
      # We use what we learned from the previous scans to skip over any keys 
      # that we know will not be a match.
      startrow = "" 
      # TODO Do these in parallel and measure speedup.
      # I've tried a thread wrapper before but due to the function having
      # self attributes it's nontrivial.
      for prop_name in filter_info.keys():
        filter_ops = filter_info.get(prop_name, [])
        if start_key:
          # Grab the reference key which is after the last delimiter. 
          value = str(filter_ops[0][1])
          reference_key = start_key.split(self._SEPARATOR)[-1]
          params = [prefix, kind, prop_name, value, reference_key]
          startrow = self.get_index_key_from_params(params)

        if not startrow and query.has_compiled_cursor() and \
          query.compiled_cursor().position_size():
          cursor = appscale_stub_util.ListCursor(query)
          last_result = cursor._GetLastResult()
          startrow = self.__get_start_key(prefix, 
            prop_name,
            datastore_pb.Query_Order.ASCENDING,
            last_result)

  
        # We use equality filters only so order ops should always be ASC. 
        order_ops = []
        for i in order_info:
          if i[0] == prop_name:
            order_ops = [i]
            break
        temp_res[prop_name] = self.__apply_filters(filter_ops, 
          order_ops, 
          prop_name, 
          kind, 
          prefix, 
          count, 
          0, 
          startrow,
          force_start_key_exclusive=force_exclusive,
          ancestor=ancestor)
      # We do reference counting and consider any reference which matches the 
      # number of properties to be a match. Any others are discarded but it 
      # possible they show up on subsequent scans. 
      last_keys_of_scans = {}
      for prop_name in temp_res:
        for indexes in temp_res[prop_name]:
          for reference in indexes: 
            reference_key = indexes[reference]['reference']
            if reference_key in reference_counter_hash:
              reference_counter_hash[reference_key] += 1
            else:
              reference_counter_hash[reference_key] = 1
          # Of the set of entity scans we use the earliest of the set as the
          # starting point of scans to follow. This makes sure we do not miss 
          # overlapping results because different properties had different 
          # distributions of keys. The index value gives us the key to 
          # the entity table (what the index points to).
          index_key = indexes.keys()[0]
          index_value = indexes[index_key]['reference']
          last_keys_of_scans[prop_name] = index_value

      # We are looking for the earliest (alphabetically) of the set of last 
      # keys. This tells us where to start our next scans. And from where 
      # we can remove potential results.
      start_key = ""
      starting_prop_name = ""
      for prop_name in last_keys_of_scans:
        last_key = last_keys_of_scans[prop_name]
        if not start_key or last_key < start_key: 
          start_key = last_key
          starting_prop_name = prop_name
      # Purge keys which did not intersect from all equality filters and those
      # which are past the earliest reference shared by all property names 
      # (start_key variable). 
      keys_to_delete = []
      for key in reference_counter_hash:
        if reference_counter_hash[key] != len(filter_info.keys()):
          keys_to_delete.append(key)
      # You cannot loop on a dictionary and delete from it at the same time.
      # Hence why the deletes happen here.
      for key in keys_to_delete:
        del reference_counter_hash[key]

      result_list.extend(reference_counter_hash.keys())
      # If the property we are setting the start key did not get the requested 
      # amount of entities then we can stop scanning, as there are no more 
      # entities to scan from that property.
      for prop_name in temp_res:
        if len(temp_res[prop_name]) < count and prop_name == starting_prop_name:
          more_results = False

        # If any property no longer has any more items, this query is done.
        if len(temp_res[prop_name]) == 0:
          more_results = False 

      # If we reached our limit of result entities, then we are done.
      if len(result_list) >= limit:
        more_results = False

      # Do not include the first key in subsequent scans because we have 
      # already accounted for the given entity.
      if start_key in result_list:
        force_exclusive = True

    result_list.sort()
    result_set = self.__fetch_entities_from_row_list(result_list, query.app())
    return result_set

  def does_composite_index_exist(self, query):
    """ Checks to see if the query has a composite index that can implement
    the given query. 

    Args:
      query: A datastore_pb.Query.
    Returns:
      True if the composite exists, False otherwise.
    """
    return query.composite_index_size() > 0

  def get_range_composite_query(self, query, filter_info):
    """ Gets the start and end key of a composite query. 

    Args:
      query: A datastore_pb.Query object.
      filter_info: A dictionary mapping property names to tuples of filter
        operators and values. 
      composite_id: An int, the composite index ID,
    Returns:
      A tuple of strings, the start and end key for the composite table.
    """
    start_key = ''
    end_key = ''
    composite_index = query.composite_index_list()[0]
    index_id = composite_index.id()
    definition = composite_index.definition()
    app_id = query.app()
    name_space = ''
    if query.has_name_space():
      name_space = query.name_space() 
    # Calculate the prekey for both the start and end key.
    pre_comp_index_key = "{0}{1}{2}{4}{3}{4}".format(app_id,
      self._NAMESPACE_SEPARATOR, name_space, index_id, self._SEPARATOR)

    if definition.ancestor() == 1:
      ancestor_str = self.__encode_index_pb(query.ancestor().path())
      pre_comp_index_key += "{0}{1}".format(ancestor_str, self._SEPARATOR) 

    index_value = ""
    equality_value = ""
    oper = datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL
    direction = datastore_pb.Query_Order.ASCENDING
    for prop in definition.property_list():
      if prop.name() in filter_info and filter_info[prop.name()][0][0] == \
        datastore_pb.Query_Filter.EXISTS:
        # We don't do anything with EXISTS filters.
        continue
      value = ''
      if prop.name() in filter_info:
        # Get the last filter. If there are more than 1, it is a equality 
        # filter. And an equality fitler trumps other types of filters.
        value = str(filter_info[prop.name()][-1][1])
        if prop.direction() == entity_pb.Index_Property.DESCENDING:
          value = helper_functions.reverse_lex(value)

        if filter_info[prop.name()][-1][0] == datastore_pb.Query_Filter.EQUAL:
          equality_value += value 
          oper = filter_info[prop.name()][-1][0]
        elif filter_info[prop.name()][-1][0] == \
          datastore_pb.Query_Filter.EXISTS:
          # We currently do not handle projection queries.
          pass
        else:
          # Figure out what operator we will use. Default to greater than or 
          # equal to if there are no filter operators that tell us 
          # otherwise. The last filter that is not an EXISTS filter is 
          # what operator we will use, as dictated by the composite index 
          # definition.
          oper = filter_info[prop.name()][-1][0]
    
          # TODO support list property queries.
          # Separate logic is required if we have multiple filters for a single
          # property.
          # Only run this if all filters are between 1 and 4. It is possible to
          # have equality and nonequality filters for list properties which is
          # not supported in AppScale.
          all_filter_ops = [ii[0] for ii in filter_info[prop.name()]]
          if len(all_filter_ops) > 1 and datastore_pb.Query_Filter.EQUAL not \
            in all_filter_ops:
            return self.composite_multiple_filter_prop(
              filter_info[prop.name()], equality_value, pre_comp_index_key,
              prop.direction())

      index_value += str(value)

      # The last property dictates the direction.
      direction = prop.direction()

    start_value = ''
    end_value = ''
    if oper == datastore_pb.Query_Filter.LESS_THAN:
      start_value = equality_value
      end_value = index_value 
      if direction == datastore_pb.Query_Order.DESCENDING:
        start_value = index_value + self._TERM_STRING
        end_value = equality_value + self._TERM_STRING
    elif oper == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
      start_value = equality_value
      end_value = index_value + self._SEPARATOR + self._TERM_STRING
      if direction == datastore_pb.Query_Order.DESCENDING:
        start_value = index_value
        end_value = equality_value + self._TERM_STRING
    elif oper == datastore_pb.Query_Filter.GREATER_THAN:
      if index_value == '':
        start_value = self._SEPARATOR + self._TERM_STRING
      else:
        start_value = index_value + self._TERM_STRING
      end_value = equality_value + self._TERM_STRING
      if direction == datastore_pb.Query_Order.DESCENDING:
        start_value = equality_value
        end_value = index_value
    elif oper == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
      start_value = index_value
      end_value = equality_value + self._TERM_STRING
      if direction == datastore_pb.Query_Order.DESCENDING:
        start_value = equality_value
        end_value = index_value + self._TERM_STRING
    elif oper  == datastore_pb.Query_Filter.EQUAL:
      start_value = index_value 
      end_value = index_value + self._TERM_STRING
    else:
      raise ValueError("Unsuported operator {0} for composite query".\
        format(oper))
    start_key = "{0}{1}".format(pre_comp_index_key, start_value)
    end_key = "{0}{1}".format(pre_comp_index_key, end_value)

    return start_key, end_key


  def composite_multiple_filter_prop(self, filter_ops, equality_value,
    pre_comp_index_key, direction):
    """Returns the start and end keys for a composite query which has multiple
       filters for a single property, and potentially multiple equality
       filters.

    Args:  
      filter_ops: dictionary mapping the inequality filter to operators and 
        values.
      equality_value: A string used for the start and end key which is derived
        from equality filter values.
      pre_comp_index_key: A string, contains pre-values for start and end keys.
      direction: datastore_pb.Query_Order telling the direction of the scan.
    Returns:
      The end and start key for doing a composite query.
    """
    oper1 = None
    oper2 = None
    value1 = None
    value2 = None
    start_key = ""
    end_key = ""
    if filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN or \
      filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
      oper1 = filter_ops[0][0]
      oper2 = filter_ops[1][0]
      value1 = str(filter_ops[0][1])
      value2 = str(filter_ops[1][1])
    else:
      oper1 = filter_ops[1][0]
      oper2 = filter_ops[0][0]
      value1 = str(filter_ops[1][1])
      value2 = str(filter_ops[0][1])

    if direction == datastore_pb.Query_Order.ASCENDING:
      # The first operator will always be either > or >=.
      if oper1 == datastore_pb.Query_Filter.GREATER_THAN:
        start_value = equality_value + value1 + self._SEPARATOR + \
          self._TERM_STRING
      elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        start_value = equality_value + value1
      else:
        raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering")

      # The second operator will be either < or <=.
      if oper2 == datastore_pb.Query_Filter.LESS_THAN:    
        end_value = equality_value + value2 
      elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        end_value = equality_value + value2 + self._SEPARATOR + \
          self._TERM_STRING
      else:
        raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering") 
    
    if direction == datastore_pb.Query_Order.DESCENDING:
      value1 = helper_functions.reverse_lex(value1)
      value2 = helper_functions.reverse_lex(value2) 
      if oper1 == datastore_pb.Query_Filter.GREATER_THAN:   
        end_value = equality_value + value1 
      elif oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        end_value = equality_value + value1 + self._SEPARATOR + \
          self._TERM_STRING
      else:
        raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering") 

      if oper2 == datastore_pb.Query_Filter.LESS_THAN:
        start_value = equality_value + value2 + self._SEPARATOR + \
          self._TERM_STRING
      elif oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        start_value = equality_value + value2
      else:
        raise dbconstants.AppScaleMisconfiguredQuery("Bad filter ordering") 

    start_key = "{0}{1}".format(pre_comp_index_key, start_value)
    end_key = "{0}{1}".format(pre_comp_index_key, end_value)
    return start_key, end_key 

  def composite_v2(self, query, filter_info):
    """Performs composite queries using a range query against
       the composite table. Faster than in-memory filters, but requires
       indexes to be built upon each put.

    Args:
      query: The query to run.
      filter_info: dictionary mapping property names to tuples of 
        filter operators and values.
    Returns:
      List of entities retrieved from the given query.
    """
    startrow, endrow = self.get_range_composite_query(query, filter_info)

    # Override the start_key with a cursor if given.
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = appscale_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      composite_index = query.composite_index_list()[0]
      startrow = self.get_composite_index_key(composite_index, last_result)  

    table_name = dbconstants.COMPOSITE_TABLE
    column_names = dbconstants.COMPOSITE_SCHEMA
    limit = self.get_limit(query)
    offset = query.offset()
    index_result = self.datastore_batch.range_query(table_name, 
                                             column_names, 
                                             startrow, 
                                             endrow, 
                                             limit, 
                                             offset=offset, 
                                             start_inclusive=True,
                                             end_inclusive=True)
    return self.__fetch_entities(index_result, query.app())

  def __composite_query(self, query, filter_info, _):  
    """Performs Composite queries which is a combination of 
       multiple properties to query on.

    Args:
      query: The query to run.
      filter_info: dictionary mapping property names to tuples of 
        filter operators and values.
    Returns:
      List of entities retrieved from the given query.
    """
    if self.does_composite_index_exist(query):
      return self.composite_v2(query, filter_info)

    logging.error("No composite ID was found for query {0}.".format(query))
    raise apiproxy_errors.ApplicationError(
      datastore_pb.Error.NEED_INDEX,
      'No composite index provided')

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
      key = self._SEPARATOR
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
              key = str(key+ self._SEPARATOR + helper_functions.reverse_lex(
                str(each.value())))
            else:
              key = str(key + self._SEPARATOR + str(each.value()))
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
      zigzag_merge_join,
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
          ('query is too large. may not have more than {0} filters'
           ' + sort orders ancestor total'.format(self._MAX_QUERY_COMPONENTS)))

    app_id = query.app()
    self.validate_app_id(app_id)
    filters, orders = datastore_index.Normalize(query.filter_list(),
                                                query.order_list(), [])
    filter_info = self.generate_filter_info(filters)
    order_info = self.generate_order_info(orders)

    # We do the composite check first because its easy to determine if a query
    # has a composite index.
    results = None
    if query.composite_index_size() > 0:
      return self.__composite_query(query, filter_info, order_info)

    for strategy in DatastoreDistributed._QUERY_STRATEGIES:
      results = strategy(self, query, filter_info, order_info)
      if results or results == []:
        return results

    return []
  
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

    cur = appscale_stub_util.QueryCursor(query, result)
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
    except ZKInternalException, zkie:
      logging.error("ZK internal exception for app id {0}, " \
        "info {1}".format(app_id, str(zkie)))
      return (commitres_pb.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except ZKTransactionException, zkte:
      logging.error("Concurrent transaction exception for app id {0}, " \
        "transaction id {1}, info {2}".format(app_id, txn_id, str(zkte)))
      self.zookeeper.notify_failed_transaction(app_id, txn_id)
      return (commitres_pb.Encode(), 
              datastore_pb.Error.PERMISSION_DENIED, 
              "Unable to commit for this transaction {0}".format(zkte))

  def rollback_transaction(self, app_id, http_request_data):
    """ Handles the rollback phase of a transaction.

    Args:
      app_id: The application ID requesting the rollback.
      http_request_data: The encoded request, a datstore_pb.Transaction.
    Returns:
      An encoded protocol buffer void response.
    """
    txn = datastore_pb.Transaction(http_request_data)
    logging.error("Doing a rollback on transaction id {0} for app id {1}"
      .format(txn.handle(), app_id))
    try:
      self.zookeeper.notify_failed_transaction(app_id, txn.handle())
      return (api_base_pb.VoidProto().Encode(), 0, "")
    except ZKTransactionException, zkte:
      logging.error("Concurrent transaction exception for app id {0}, " \
        "transaction id {1}, info {2}".format(app_id, txn.handle(), str(zkte)))
      return (api_base_pb.VoidProto().Encode(), 
              datastore_pb.Error.PERMISSION_DENIED, 
              "Unable to rollback for this transaction: {0}".format(str(zkte)))

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
    raise NotImplementedError("Unknown request of operation {0}" \
      .format(pb_type))
  
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
    logging.info("Request type:{0}".format(method))
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
      response, errcode, errdetail = self.create_index_request(app_id,
                                                        http_request_data)
    elif method == "GetIndices":
      response, errcode, errdetail = self.get_indices_request(app_id)
    elif method == "UpdateIndex":
      response = api_base_pb.VoidProto().Encode()
      errcode = 0
      errdetail = ""
    elif method == "DeleteIndex":
      response, errcode, errdetail = self.delete_index_request(app_id, 
                                                       http_request_data)
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

    handle = None
    transaction_pb = datastore_pb.Transaction()
    try:
      handle = datastore_access.setup_transaction(app_id, multiple_eg)
    except ZKInternalException, zkie:
      logging.error("ZK internal exception for app id {0}, " \
        "info {1}".format(app_id, str(zkie)))
      return (transaction_pb.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")

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
    except ZKInternalException, zkie:
      logging.error("ZK internal exception for app id {0}, " \
        "info {1}".format(app_id, str(zkie)))
      return (api_base_pb.VoidProto().Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except Exception, exception:
      logging.error("Error trying to rollback with exception {0}".format(
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
    try:
      datastore_access._dynamic_run_query(query, clone_qr_pb)
    except ZKInternalException, zkie:
      logging.error("ZK internal exception for app id {0}, " \
        "info {1}".format(query.app(), str(zkie)))
      clone_qr_pb.set_more_results(False)
      return (clone_qr_pb.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except ZKTransactionException, zkte:
      logging.error("Concurrent transaction exception for app id {0}, " \
        "info {1}".format(query.app(), str(zkte)))
      clone_qr_pb.set_more_results(False)
      return (clone_qr_pb.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on put.")
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.error("Connection issue with datastore for app id {0}, " \
        "info {1}".format(query.app(), str(dbce)))
      clone_qr_pb.set_more_results(False)
      return (clone_qr_pb.Encode(),
             datastore_pb.Error.INTERNAL_ERROR,
             "Datastore connection error on run_query request.")
    return (clone_qr_pb.Encode(), 0, "")

  def create_index_request(self, app_id, http_request_data):
    """ High level function for creating composite indexes.

    Args:
       app_id: Name of the application.
       http_request_data: Stores the protocol buffer request from the 
               AppServer.
    Returns: 
       Returns an encoded response.
    """
    global datastore_access
    request = entity_pb.CompositeIndex(http_request_data)
    response = api_base_pb.Integer64Proto()
    try:
      index_id = datastore_access.create_composite_index(app_id, request)
      response.set_value(index_id)
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.error("Connection issue with datastore for app id {0}, " \
        "info {1}".format(app_id, str(dbce)))
      response.set_value(0)
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on create index request.")
    return (response.Encode(), 0, "")

  def delete_index_request(self, app_id, http_request_data):
    """ Deletes a composite index for a given application.
  
    Args:
      app_id: Name of the application.
      http_request_data: A serialized CompositeIndices item
    Returns:
      A Tuple of an encoded entity_pb.VoidProto, error code, and 
      error explanation.
    """
    global datastore_access
    request = entity_pb.CompositeIndex(http_request_data)
    response = api_base_pb.VoidProto()
    try: 
      datastore_access.delete_composite_index_metadata(app_id, request)
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.error("Connection issue with datastore for app id {0}, " \
        "info {1}".format(app_id, str(dbce)))
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on delete index request.")
    return (response.Encode(), 0, "")
    
  def get_indices_request(self, app_id):
    """ Gets the indices of the given application.

    Args:
      app_id: Name of the application.
      http_request_data: Stores the protocol buffer request from the 
               AppServer.
    Returns: 
      A Tuple of an encoded response, error code, and error explanation.
    """
    global datastore_access
    response = datastore_pb.CompositeIndices()
    try:
      indices = datastore_access.get_indices(app_id)
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.error("Connection issue with datastore for app id {0}, " \
        "info {1}".format(app_id, str(dbce)))
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on get indices request.")
    for index in indices:
      new_index = response.add_index()
      new_index.ParseFromString(index)
    return (response.Encode(), 0, "")

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

    max_id = int(request.max())
    size = int(request.size())
    start = end = 0
    try:
      start, end = datastore_access.allocate_ids(app_id, size, max_id=max_id)
    except ZKInternalException, zkie:
      logging.error("ZK internal exception for app id {0}, " \
        "info {1}".format(app_id, str(zkie)))
      return (response.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except ZKTransactionException, zkte:
      logging.error("Concurrent transaction exception for app id {0}, " \
        "info {1}".format(app_id, str(zkte)))
      return (response.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on allocate id request.")
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.error("Connection issue with datastore for app id {0}, " \
        "info {1}".format(app_id, str(dbce)))
      return (response.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on allocate id request.")


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
    except ZKInternalException, zkie:
      logging.error("ZK internal exception for app id {0}, " \
        "info {1}".format(app_id, str(zkie)))
      return (putresp_pb.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except ZKTransactionException, zkte:
      logging.error("Concurrent transaction exception for app id {0}, " \
        "info {1}".format(app_id, str(zkte)))
      return (putresp_pb.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on put.")
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.error("Connection issue with datastore for app id {0}, " \
        "info {1}".format(app_id, str(dbce)))
      return (putresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on put.")

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
    try:
      datastore_access.dynamic_get(app_id, getreq_pb, getresp_pb)
    except ZKInternalException, zkie:
      logging.error("ZK internal exception for app id {0}, " \
        "info {1}".format(app_id, str(zkie)))
      return (getresp_pb.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except ZKTransactionException, zkte:
      logging.error("Concurrent transaction exception for app id {0}, " \
        "info {1}".format(app_id, str(zkte)))
      return (getresp_pb.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on get.")
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.error("Connection issue with datastore for app id {0}, " \
        "info {1}".format(app_id, str(dbce)))
      return (getresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on get.")

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
    except ZKInternalException, zkie:
      logging.error("ZK internal exception for app id {0}, " \
        "info {1}".format(app_id, str(zkie)))
      return (delresp_pb.Encode(), 
              datastore_pb.Error.INTERNAL_ERROR, 
              "Internal error with ZooKeeper connection.")
    except ZKTransactionException, zkte:
      logging.error("Concurrent transaction exception for app id {0}, " \
        "info {1}".format(app_id, str(zkte)))
      return (delresp_pb.Encode(), 
              datastore_pb.Error.CONCURRENT_TRANSACTION, 
              "Concurrent transaction exception on delete.")
    except dbconstants.AppScaleDBConnectionError, dbce:
      logging.error("Connection issue with datastore for app id {0}, " \
        "info {1}".format(app_id, str(dbce)))
      return (delresp_pb.Encode(),
              datastore_pb.Error.INTERNAL_ERROR,
              "Datastore connection error on delete.")


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
