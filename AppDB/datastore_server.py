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
import md5
import os
import random
import sys
import threading

import tornado.httpserver
import tornado.ioloop
import tornado.web

import appscale_datastore_batch
import dbconstants
import helper_functions

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

  def __init__(self, datastore_batch):
    """
       Constructor.
     
     Args:
       datastore_batch: a reference to the batch datastore interface 
    """
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
        pb: protocol buffer for which we will encode the index name
    Returns:
        Key for entity table
    """
    return buffer(prefix + self._NAMESPACE_SEPARATOR) + \
                  self.__encode_index_pb(pb) 

  def get_kind_key(self, prefix, key_path):
    """ Returns a key for the kind table
    
    Args:
        prefix: app name and namespace string
        key_path: key path to build row key with
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
        key_id = str(e.id()).zfill(10)
      path.append('%s:%s' % (e.type(), key_id))
    encoded_path = '!'.join(path)
    encoded_path += '!'
    
    return prefix + self._NAMESPACE_SEPARATOR + encoded_path
    
  @staticmethod
  def __encode_index_pb(pb):
    """ Returns an encoded buffer
  
    Args:
        pb: The protocol buffer to encode    
    Returns:
        encoded pb
    """

    def _encode_path(pb):
      """ Takes a protocol buffer and returns the encoded path """

      path = []
      for e in pb.element_list():
        if e.has_name():
          key_id = e.name()
        elif e.has_id():
          key_id = str(e.id()).zfill(10)
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
      AppScaleBadArg: if name is not set
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
      Key string for storing namespaces
    """

    return app_id + "/" + name_space + "/" + kind + "/" + index_name

  def configure_namespace(self, prefix, app_id, name_space):
    """ Stores a key for the given namespace.

    Args:
      prefix: The namespace prefix to configure.
      app_id: The app ID.
      name_space: The per-app namespace name.
    """
    
    vals = {}
    row_key = prefix
    vals[row_key] = {"namespaces":name_space}
    self.datastore_batch.batch_put_entity(dbconstants.APP_NAMESPACE_TABLE, 
                          [row_key], 
                          dbconstants.APP_NAMESPACE_SCHEMA, 
                          vals)


  def get_table_prefix(self, data):
    """ Returns the namespace prefix for a query.

    Args:
      data: An Entity, Key or Query PB, or an (app_id, ns) tuple.
    Returns:
      A valid table prefix
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
    """Returns the index key from params
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
    """ Returns keys/value of indexes for a set of entities
 
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
    """ Deletes the entities in the DB

    Args:
       entities: A list of entities for which their 
                 indexes are to be deleted
    """

    if len(entities) == 0: return

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
    
  def insert_entities(self, entities):
    """Inserts or updates entities in the DB.
    Args:      
      entities: A list of entities to store.
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

    row_values = {}
    row_keys = []

    kind_row_keys = []
    kind_row_values = {}

    entities = sorted((self.get_table_prefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = tuple(row_generator(group))
      new_row_keys = [str(ii[0]) for ii in group_rows]
      row_keys += new_row_keys
      for ii in group_rows:
        row_values[str(ii[0])] = \
                           {dbconstants.APP_ENTITY_SCHEMA[0]:str(ii[1]), #ent
                           dbconstants.APP_ENTITY_SCHEMA[1]:"0"} #txnid

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      kind_group_rows = tuple(kind_row_generator(group))
      new_kind_keys = [str(ii[0]) for ii in kind_group_rows]
      kind_row_keys += new_kind_keys

      for ii in kind_group_rows:
        kind_row_values[str(ii[0])] = {dbconstants.APP_KIND_SCHEMA[0]:str(ii[1])}


    # TODO do these in ||                        
    self.datastore_batch.batch_put_entity(dbconstants.APP_ENTITY_TABLE, 
                                          row_keys, 
                                          dbconstants.APP_ENTITY_SCHEMA, 
                                          row_values)    

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

  def allocate_ids(self, prefix, size, max_id=None):
    """ Allocates IDs from either a local cache or the datastore. 

    Args:
      prefix: A table namespace prefix.
      size: Number of IDs to allocate.
      max_id: If given increase the next IDs to be greater than this value
    Returns:
      tuple of start and end ids
    Raises: 
      ValueError: if size is less than or equal to 0
    """

    if size and max_id:
      raise ValueError("Both size and max cannot be set.")

    current_id = self.acquire_next_id_from_db(prefix)

    if size:
      next_id = current_id + size

    if max_id:
      next_id = max(current_id, max_id + 1)

    cell_values = {prefix: {dbconstants.APP_ID_SCHEMA[0]: str(next_id)}} 

    res = self.datastore_batch.batch_put_entity(dbconstants.APP_ID_TABLE, 
                          [prefix],  
                          dbconstants.APP_ID_SCHEMA,
                          cell_values)

    start = current_id
    end = next_id - 1

    return start, end

  def put_entities(self, entities):
    """ Updates indexes of existing entities, inserts new entities and 
        indexes for them
    Args:
       entities: list of entities
    """
    sorted_entities = sorted((self.get_table_prefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(sorted_entities, lambda x: x[0]):
      keys = [e.key() for e in entities]
      self.delete_entities(keys)
      self.insert_entities(entities)
      self.insert_index_entries(entities)

  def delete_entities(self, keys):
    """ Deletes the entities and the indexes associated with them.
    Args:
       keys: list of keys to be deleted
    """
    def row_generator(key_list):
      for prefix, k in key_list:
        yield (self.get_entity_key(prefix, k.path()),
               buffer(k.Encode()))

    def kind_row_generator(key_list):
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

    #TODO do these in ||
    self.datastore_batch.batch_delete(dbconstants.APP_ENTITY_TABLE, 
                                      row_keys, 
                                      column_names=dbconstants.APP_ENTITY_SCHEMA)

    self.datastore_batch.batch_delete(dbconstants.APP_KIND_TABLE,
                                      kind_keys, 
                                      column_names=dbconstants.APP_KIND_SCHEMA)

    entities = []
    for row_key in ret:
      # Entities may not exist if this is the first put
      if 'entity' in ret[row_key]:
        ent = entity_pb.EntityProto()
        ent.ParseFromString(ret[row_key]['entity'])
        entities.append(ent)

    self.delete_index_entries(entities)

  def _dynamic_put(self, app_id, put_request, put_response):
    """ Stores and entity and its indexes in the datastore
    
    Args:
      app_id: Application ID
      put_request: Request with entities to store
      put_response: The response sent back to the app server
    """

    entities = put_request.entity_list()
    keys = [e.key() for e in entities]
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
 
        id_, ignored = self.allocate_ids(self.get_table_prefix(entity.key()), 1)
        last_path.set_id(id_)

        group = entity.mutable_entity_group()
        root = entity.key().path().element(0)
        group.add_element().CopyFrom(root)


    self.put_entities(entities)
    put_response.key_list().extend([e.key() for e in entities])

  def fetch_keys(self, key_list):
    """ Given a list of keys fetch the entities.
    
    Args:
      key_list: A list of keys to fetch
    Returns:
      A tuple of entities from the datastore and key list
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
    return (result, row_keys)

  def _dynamic_get(self, get_request, get_response):
    """ Fetch keys from the datastore.
    
    Args: 
       get_request: Request with list of keys
       get_response: Response to application server
    """ 

    keys = get_request.key_list()
    results, row_keys = self.fetch_keys(keys) 
    for r in row_keys:
      if r in results and 'entity' in results[r]:
        group = get_response.add_entity() 
        group.mutable_entity().CopyFrom(
               entity_pb.EntityProto(results[r]['entity']))

  def _dynamic_delete(self, delete_request, delete_response):
    """ Deletes a set of rows.
    
    Args: 
      delete_request: Request with a list of keys
      delete_response: Response to application server
    """
    keys = delete_request.key_list()
    self.delete_entities(delete_request.key_list())
 
  def generate_filter_info(self, filters, query):
    """Transform a list of filters into a more usable form.

    Args:
      filters: A list of filter PBs.
      query: The query to generate filter info for.
    Returns:
      A dict mapping property names to lists of (op, value) tuples.
    """

    def reference_property_to_reference(refprop):
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
    """ Builds the start key for cursor query

    Args: 
        prop_name: property name of the filter 
        order: sort order 
        last_result: last result encoded in cursor
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
      if 'entity' in ret[rkey]:
        ent = entity_pb.EntityProto(ret[rkey]['entity'])
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
    """ Given the results from a table scan, get the references
    
    Args: 
      refs: key/value pairs where the values contain a reference to 
            the entitiy table
    Returns:
      Entities retrieved from entity table
    """
    if len(refs) == 0:
      return []
    keys = [item.keys()[0] for item in refs]
    rowkeys = []    
    for index, ent in enumerate(refs):
      key = keys[index]
      ent = ent[key]['reference']
      rowkeys.append(ent)
  
    result = self.datastore_batch.batch_get_entity(dbconstants.APP_ENTITY_TABLE, 
                                                   rowkeys,
                                                   dbconstants.APP_ENTITY_SCHEMA)
    entities = []
    keys = result.keys()
    for key in rowkeys:
      if 'entity' in result[key]:
        entities.append(result[key]['entity'])

    return entities 

  def __extract_entities(self, kv):
    """ Given a result from a range query on the Entity table return a 
        list of encoded entities
    Args:
      kv: Key and values from a range query on the entity table
    Returns:
      The extracted entities
    """
    keys = [item.keys()[0] for item in kv]
    results = []    
    for index, entity in enumerate(kv):
      key = keys[index]
      entity = entity[key]['entity']
      results.append(entity)

    return results
    
  def __AncestorQuery(self, query, filter_info, order_info):
    """ Performs ancestor queries which is where you select 
        entities based on a particular root entitiy. 
      
    Args: 
      query: The query to run
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      start and end row keys
    """       
    ancestor = query.ancestor()
    prefix = self.get_table_prefix(query)
    path = buffer(prefix + '/') + self.__encode_index_pb(ancestor.path())
  
    if query.has_kind():
      path += query.kind() + ":"

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

    column_names = ['reference']
    if not order_info:
      order = None
      prop_name = None
    
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = cassandra_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__get_start_key(prefix, prop_name, order, last_result)
      start_inclusive = self._DISABLE_INCLUSIVITY

    limit = query.limit() or self._MAXIMUM_RESULTS

  
    result = self.datastore_batch.range_query(dbconstants.APP_ENTITY_TABLE, 
                                              dbconstants.APP_ENTITY_SCHEMA, 
                                              startrow, 
                                              endrow, 
                                              limit, 
                                              offset=0, 
                                              start_inclusive=start_inclusive, 
                                              end_inclusive=end_inclusive)
    return self.__extract_entities(result)

  def __KindlessQuery(self, query, filter_info, order_info):
    """ Performs kindless queries where queries are performed 
        on the entity table and go across kinds.
      
    Args: 
      query: The query to run
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      Entities that match the query
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
  
    result = self.datastore_batch.range_query(dbconstants.APP_ENTITY_TABLE, 
                                              dbconstants.APP_ENTITY_SCHEMA, 
                                              startrow, 
                                              endrow, 
                                              limit, 
                                              offset=0, 
                                              start_inclusive=start_inclusive, 
                                              end_inclusive=end_inclusive)

    return self.__extract_entities(result)

  def kind_query_range(self, query, filter_info, order_info):
    """ Gets start and end keys for kind queries
      
    Args: 
      query: The query to run
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      Entities that match the query
    """       
    prefix = self.get_table_prefix(query)
    startrow = prefix + '/' + query.kind() + ':'     
    endrow = prefix + '/' + query.kind() + ':' + self._TERM_STRING
    return startrow, endrow
   
  def __kind_query(self, query, filter_info, order_info):
    """ Performs kind only queries, kind and ancestor, and ancestor queries
        https://developers.google.com/appengine/docs/python/datastore/queries
    Args:
      query: The query to run
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      An ordered list of entities matching the query
    """

    # Detect quickly if this is a kind query or not
    for fi in filter_info:
      if fi != "__key__":
        return None

    if order_info:
      if len(order_info) > 0: return None
    elif query.has_ancestor():
      return self.__AncestorQuery(query, filter_info, order_info)
    elif not query.has_kind():
      return self.__KindlessQuery(query, filter_info, order_info)
    
    startrow, endrow = self.kind_query_range(query, 
                                             filter_info, 
                                             order_info)

    if startrow == None:
      return None

    end_inclusive = self._ENABLE_INCLUSIVITY
    start_inclusive = self._ENABLE_INCLUSIVITY
    if not order_info:
      order = None
      prop_name = None
    
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = cassandra_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      prefix = self.get_table_prefix(query)
      startrow = self.__get_start_key(prefix, prop_name, order, last_result)
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
    """Performs queries satisfiable by the Single_Property tables
    Args:
      query: The query to run
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      List of entities retrieved from the given query
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
    """
    Applies property filters in the query.
    Args:
      filter_ops: Tuple with property filter operator and value
      order_info: Tuple with property name and sort order
      kind: Kind of the entity
      prefix: Prefix for the table
      limit: Number of results
      offset: Number of results to skip
      startrow: Start key for the range scan
      force_start_key_exclusive: Do not include the start key
    Results:
      Returns a list of entity keys 
    Raises:
      NotImplementedError: For unsupported queries.
      AppScaleMisconfiguredQuery: Bad filters or orderings
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
  
    if startrow: start_inclusive = self._DISABLE_INCLUSIVITY 

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
      elif oper == datastore_pb.Query_Filter.IN:
        raise NotImplementedError("IN queries are not implemented")
      elif oper == datastore_pb.Query_Filter.EXIST:
        raise NotImplementedError("EXIST queries are not implemented")
      else:
        raise NotImplementedError("Unknown query of operation %d"%oper)

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
          params = [prefix, kind, property_name, value1 + '/' + self._TERM_STRING]
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
          params = [prefix, kind, property_name, value2 + '/' + self._TERM_STRING]
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
          params = [prefix, kind, property_name, value1 + '/' + self._TERM_STRING]
          endrow = self.get_index_key_from_params(params)
          end_inclusive = self._ENABLE_INCLUSIVITY

        if startrow:
          start_inclusive = self._DISABLE_INCLUSIVITY
        elif oper2 == datastore_pb.Query_Filter.LESS_THAN:
          params = [prefix, kind, property_name, value2 + '/' + self._TERM_STRING]
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
      query: The query to run
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      List of entities retrieved from the given query
    """
    if order_info and order_info[0][0] == '__key__':
      return None

    if query.has_ancestor():
      return None

    if not query.has_kind():
      return None

    def set_prop_names(filt_info):
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
              if cur_prop and str(self.__encode_index_pb(cur_prop.value())) != value:
                if ent in filtered_entities: filtered_entities.remove(ent)   
     
      result += filtered_entities  
      startrow = temp_res[-1].keys()[0]

    if len(order_info) > 1:
      result = self.__order_composite_results(result, order_info) 

    return result 

  def __order_composite_results(self, result, order_info):
    """ Takes results and applies ordering based on properties and 
        whether it should be ascending or decending.
      Args: 
        result: unordered results
        order_info: given ordering of properties
      Returns:
        A list of ordered entities
    """
    # We can not fully filter past one filter without getting
    # the entire table to make sure results are in the correct order. 
    # Composites must be implemented the correct way with specialized 
    # indexes to get the correct result.
    # The effect is that entities at the edge of each batch have a high 
    # chance of being out of order with our current implementation.

    # Put all the values appended based on order info into a dictionary,
    # The key being the values appended and the value being the index
    if not result: return []
    vals = {}
    for e in result:
      key = "/"
      e = entity_pb.EntityProto(e)
      prop_list = e.property_list()
      for ii in order_info:    
        ord_prop = ii[0]
        ord_dir = ii[1]
        for each in prop_list:
          if each.name() == ord_prop:
            if ord_dir == datastore_pb.Query_Order.DESCENDING:
              key = str(key+ '/' + helper_functions.reverse_lex(str(each.value())))
            else:
              key = str(key + '/' + str(each.value()))
            break
      vals[key] = e
    keys = sorted(vals.keys())
    sorted_vals = [vals[ii] for ii in keys]
    result = [e.Encode() for e in sorted_vals]
    return result

  # These are the three different types of queries attempted. Queries 
  # can be identified by their filters and orderings
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
      Result set
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
    filter_info = self.generate_filter_info(filters, query)
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
  
  def _dynamic_run_query(self, app_id, query, query_result):
    """Populates the query result and use that query result to 
       encode a cursor
    Args:
      app_id: The application ID
      query: The query to run
      query_result: The response given to the application server
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

  def setup_transaction(self, app_id) :
    """ Gets a transaction ID for a new transaction """
    _MAX_RAND = 1000000  # arbitary large number
    return random.randint(1, _MAX_RAND)


class MainHandler(tornado.web.RequestHandler):
  """
  Defines what to do when the webserver receives different types of 
  HTTP requests.
  """

  ##############
  # OTHER TYPE #
  ##############
  def unknown_request(self, app_id, http_request_data, pb_type):
    """ Function which handles unknown protocol buffers
    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Raises:
      Raises exception.
    """ 
    raise NotImplementedError("Unknown request of operation %s"%pb_type)
  
  #########################
  # POST Request Handling #
  #########################

  @tornado.web.asynchronous
  def post( self ):
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
  
  #########################
  # GET Request Handling  #
  #########################

  @tornado.web.asynchronous
  def get(self):
    """ Handles get request for the web server. Returns that it is currently
        up in json.
    """
    self.write("{'status':'up'}")
    self.finish() 

  def remote_request(self, app_id, http_request_data):
    """ Receives a remote request to which it should give the correct 
        response. The http_request_data holds an encoded protocol buffer
        of a certain type. Each type has a particular response type. 
    
    Args:
      app_id: The application ID that is sending this request
      http_request_data: Encoded protocol buffer 
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
      response, errcode, errdetail = self.run_query(app_id, 
                                          http_request_data)
    elif method == "BeginTransaction":
      response, errcode, errdetail = self.begin_transaction_request(app_id,
                                                      http_request_data)
    elif method == "Commit":
      response, errcode, errdetail = self.commit_transaction_request(app_id,
                                                      http_request_data)
    elif method == "Rollback":
      response, errcode, errdetail = self.rollback_transaction_request(app_id,
                                                        http_request_data)
    elif method == "AllocateIds":
      response, errcode, errdetail = self.allocate_ids_request(app_id,
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

    self.write(apiresponse.Encode() )    

  def begin_transaction_request(self, app_id, http_request_data):
    """ Handles the intial request to start a transaction. Replies with 
        a unique identifier to handle this transaction in future requests.
  
    Args:
      app_id: The application ID requesting the transaction
      http_request_data: The encoded request
    Returns:
      An encoded transaction protocol buffer with a unique handler
    """
    global datastore_access
    transaction_pb = datastore_pb.Transaction()
    handle = datastore_access.setup_transaction(app_id)
    transaction_pb.set_app(app_id)
    transaction_pb.set_handle(handle)
    return (transaction_pb.Encode(), 0, "")

  def commit_transaction_request(self, app_id, http_request_data):
    """ Handles the commit phase of a transaction

    Args:
      app_id: The application ID requesting the transaction commit
      http_request_data: The encoded request
    Returns:
      An encoded protocol buffer commit response
    """
    commitres_pb = datastore_pb.CommitResponse()
    # TODO implement transactions
    """
    transaction_pb = datastore_pb.Transaction(http_request_data)
    txn_id = transaction_pb.handle()
    try:
      self._Dynamic_Commit(app_id, transaction_pb, commitres_pb)
    except:
      return (commitres_pb.Encode(), 
              datastore_pb.Error.PERMISSION_DENIED, 
              "Unable to commit for this transaction")
    """
    return (commitres_pb.Encode(), 0, "")

  def rollback_transaction_request(self, app_id, http_request_data):
    """ Handles the rollback phase of a transaction

    Args:
      app_id: The application ID requesting the rollback
      http_request_data: The encoded request
    Returns:
      An encoded protocol buffer void response
    """
    # TODO implement transactions
    """
    transaction_pb = datastore_pb.Transaction(http_request_data)
    handle = transaction_pb.handle()
    try:
      self.datastore_access._Dynamic_Rollback(app_id, transaction_pb, None)
    except:
      return(api_base_pb.VoidProto().Encode(), 
             datastore_pb.Error.PERMISSION_DENIED, 
             "Unable to rollback for this transaction")
    """
    return (api_base_pb.VoidProto().Encode(), 0, "")

  def run_query(self, app_id, http_request_data):
    """ High level function for running queries
    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Returns:
      Returns an encoded query response
    """

    global datastore_access
    query = datastore_pb.Query(http_request_data)
    # Pack Results into a clone of QueryResult #
    clone_qr_pb = datastore_pb.QueryResult()
    datastore_access._dynamic_run_query(app_id, query, clone_qr_pb)
    return (clone_qr_pb.Encode(), 0, "")

  def allocate_ids_request(self, app_id, http_request_data):
    """ High level function for getting unique identifiers for entities.
    Args:
       app_id: Name of the application
       http_request_data: Stores the protocol buffer request from the AppServer
    Returns: 
       Returns an encoded response
    Raises:
       NotImplementedError: when requesting a max id
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
    """ High level function for doing puts
    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Returns:
      Returns an encoded put response
    """ 

    global datastore_access
    putreq_pb = datastore_pb.PutRequest(http_request_data)
    putresp_pb = datastore_pb.PutResponse( )
    datastore_access._dynamic_put(app_id, putreq_pb, putresp_pb)
    return (putresp_pb.Encode(), 0, "")
    
  def get_request(self, app_id, http_request_data):
    """ High level function for doing gets
    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Returns:
      Returns an encoded get response
    """ 

    global datastore_access
    getreq_pb = datastore_pb.GetRequest(http_request_data)
    getresp_pb = datastore_pb.GetResponse()
    datastore_access._dynamic_get(getreq_pb, getresp_pb)
    return (getresp_pb.Encode(), 0, "")

  def delete_request(self, app_id, http_request_data):
    """ High level function for doing deletes
    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Returns:
      Returns an encoded delete response
    """ 

    global datastore_access
    delreq_pb = datastore_pb.DeleteRequest( http_request_data )
    delresp_pb = api_base_pb.VoidProto() 
    datastore_access._dynamic_delete(delreq_pb, delresp_pb)
    return (delresp_pb.Encode(), 0, "")

  def void_proto(self, app_id, http_request_data):
    """ Function which handles void protocol buffers
    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Returns:
      Default message for void protocol buffers 
    """ 

    resp_pb = api_base_pb.VoidProto() 
    return (resp_pb.Encode(), 0, "" )
  
  def str_proto(self, app_id, http_request_data):
    """ Function which handles string protocol buffers
    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Returns:
      Default message for string protocol buffers which is a composite 
      response
    """ 

    str_pb = api_base_pb.StringProto( http_request_data )
    composite_pb = datastore_pb.CompositeIndices()
    return (composite_pb.Encode(), 0, "" )    
  
  def int64_proto(self, app_id, http_request_data):
    """ Function which handles integer protocol buffers. Application
        server expects a void protocol as an acknowledgement.

    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Returns:
      void protocol buffer
    """ 

    int64_pb = api_base_pb.Integer64Proto( http_request_data ) 
    resp_pb = api_base_pb.VoidProto()
    return (resp_pb.Encode(), 0, "")
 
  def compositeindex_proto(self, app_id, http_request_data):
    """ Function which handles composite index protocol buffers.

    Args:
      app_id: Name of the application 
      http_request_data: Stores the protocol buffer request from the AppServer
    Returns:
      Default message for string protocol buffers which is a void protocol 
      buffer
    """ 

    compindex_pb = entity_pb.CompositeIndex( http_request_data)
    resp_pb = api_base_pb.VoidProto()
    return (resp_pb.Encode(), 0, "")

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
  """ Starts a web service for handing datastore requests """
  global datastore_access
  zoo_keeper_locations = ""

  db_type = "cassandra"
  port = DEFAULT_SSL_PORT
  isEncrypted = True

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
      isEncrypted = False
    elif opt in ("-z", "--zoo_keeper"):
      zoo_keeper_locations = arg

  if db_type not in VALID_DATASTORES:
    print "This datastore is not supported for this version of the AppScale\
          datastore API:" + db_type
    exit(1)
 
  datastore_batch = appscale_datastore_batch.DatastoreFactory.getDatastore(db_type)
  datastore_access = DatastoreDistributed(datastore_batch)

  if port == DEFAULT_SSL_PORT and not isEncrypted:
    port = DEFAULT_PORT

  server = tornado.httpserver.HTTPServer(pb_application)
  server.listen(port)

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
      exit(1)

if __name__ == '__main__':
  main(sys.argv[1:])
