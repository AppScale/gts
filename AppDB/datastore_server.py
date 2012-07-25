#!/usr/bin/python
#
# Author: 
# Navraj Chohan (nlake44@gmail.com)
# Navyasri Canumalla (navyasri@cs.ucsb.edu)
# See LICENSE file

import __builtin__
import datetime
import getopt
import itertools
import md5
import os
import threading
import types
import random
import SOAPpy
import sys
import socket
import time

import tornado.httpserver
import tornado.ioloop
import tornado.web

import appscale_logger
import appscale_datastore
import appscale_datastore_batch
import helper_functions

from google.appengine.api import api_base_pb
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.api import users
from google.appengine.datastore import datastore_pb
from google.appengine.datastore import datastore_index
from google.appengine.datastore import datastore_stub_util
from google.appengine.runtime import apiproxy_errors
from google.appengine.datastore import entity_pb
from google.appengine.ext.remote_api import remote_api_pb
from google.appengine.datastore import cassandra_stub_util
from google.appengine.datastore import sortable_pb_encoder

from google.net.proto import ProtocolBuffer

from drop_privileges import *
from SocketServer import BaseServer
from M2Crypto import SSL
from dbconstants import *

# Buffer type used for key storage in the datastore
buffer = __builtin__.buffer

app_datastore = []

entity_pb.Reference.__hash__ = lambda self: hash(self.Encode())
datastore_pb.Query.__hash__ = lambda self: hash(self.Encode())

# Max number of results for a query
_MAXIMUM_RESULTS = 1000000

# The most you can offset a result from a query
_MAX_QUERY_OFFSET = 1000

# The number of entries looked at when doing a composite query
# It will keep looking at this size window when getting the result
_MAX_COMPOSITE_WINDOW = 1000

_MAX_QUERY_COMPONENTS = 63

# IDs are acquired in block sizes of this
_BLOCK_SIZE = 10000

# This is the largest block of IDs a user can request
_MAX_REQUESTED_ID_BLOCK = 1000

# For enabling and disabling range inclusivity
_ENABLE = True
_DISABLE = False

_NAMESPACE_SEPARATOR = '/'

# This is the terminating string for range queries
_TERM_STRING = chr(255) * 500

_OPERATOR_MAP = {
    datastore_pb.Query_Filter.LESS_THAN: '<',
    datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL: '<=',
    datastore_pb.Query_Filter.EQUAL: '=',
    datastore_pb.Query_Filter.GREATER_THAN: '>',
    datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL: '>=',
}

_ORDER_MAP = {
    datastore_pb.Query_Order.ASCENDING: 'ASC',
    datastore_pb.Query_Order.DESCENDING: 'DESC',
}


class DatastoreDistributed():
  """Persistent stub for the Python datastore API.
  """

  def __init__(self, datastore_batch):
    """
       Constructor.
     
     Args:
       datastore_batch: a reference to the batch datastore interface 
    """
    # Each entry contains a tuple (last_accessed_timestamp, namespace)
    # The key is the <app_id>___<namespace>
    self.__namespaces = []

    # Each entry contains a triple (last_accessed_timestamp, start, end)
    # The key is the <app_id>___<namespace>___<kind>
    # IDs are inclusive
    self.__id_map = {}

    # Each entry contains a tuple (last_accessed_timestamp, index_name)
    # The key is the <app_id>___<namespace>___<kind>___<index>
    self.__indexes = {}

    #TODO
    # lock for namespace and indexes during periodic garbage collection
    self.__lock = threading.Lock()

    # initialize a clean up thread
    self.__start_gc_thread()
 
    # datastore accessor
    self.datastore_batch = datastore_batch 

  def __start_gc_thread(self):
    """ Scans through indexes and namespaces, removed ones which have not
        been accessed in the past day
    """

    #TODO
    pass

  @staticmethod
  def __GetEntityKind(key):
    """ Returns the Kind of the Entity

    Args:
        key: the key path of entity
    Returns:
        kind of the entity
    """

    if isinstance(key, entity_pb.EntityProto):
      key = key.key()
    return key.path().element_list()[-1].type()

  def __GetEntityKey(self, prefix, pb):
    """ Returns the key for the entity table
    
    Args:
        prefix: per-app name and namespace
        pb: index name
    Returns:
        Key for entity table
    """
    return buffer(prefix + _NAMESPACE_SEPARATOR) + self.__EncodeIndexPB(pb) 

  def __GetKindKey(self, prefix, key_path):
    """ Returns a key for the kind table
    
    Args:
        prefix: per-app name and namespace
        key_path: key path to build row key with
    Returns:
        Row key for kind table
    """
    def _encode_path(pb):
      # reverse of index paths because child kind must come first
      path = []
      all_reversed = pb.element_list()[::-1]
      for e in all_reversed:
        if e.has_name():
          id = e.name()
        elif e.has_id():
          id = str(e.id()).zfill(10)
        path.append('%s:%s' % (e.type(), id))
      val = '!'.join(path)
      val += '!'
      return val
    return prefix + _NAMESPACE_SEPARATOR + _encode_path(key_path) 
    
  @staticmethod
  def __EncodeIndexPB(pb):
    """ Returns an encoded buffer
  
    Args:
        pb: The protocol buffer to encode    
    Returns:
        encoded pb
    """

    def _encode_path(pb):
      path = []
      for e in pb.element_list():
        if e.has_name():
          id = e.name()
        elif e.has_id():
          id = str(e.id()).zfill(10)
        path.append('%s:%s' % (e.type(), id))
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

  def ValidateAppId(self, app_id):
    """ Verify that this is the stub for app_id.

    Args:
      app_id: An application ID.

    Raises:
      datastore_errors.BadRequestError: if this is not the stub for app_id.
    """

    assert app_id


  def ValidateKey(self, key):
    """ Validate this key.

    Args:
      key: entity_pb.Reference

    Raises:
      datastore_errors.BadRequestError: if the key is invalid
    """

    assert isinstance(key, entity_pb.Reference)

    self.ValidateAppId(key.app())

    for elem in key.path().element_list():
      if elem.has_id() == elem.has_name():
        raise datastore_errors.BadRequestError(
            'each key path element should have id or name but not both: %r'
            % key)

  def GetIndexKey(self, app_id, name_space, kind, index_name):
    """ Returns key string for storing namespaces
    Args:
      app_id: The app ID.
      name_space: The per-app namespace name.
      kind: The per-app kind name.
      index_name: The per-app index name.
    """

    return app_id + "___" + name_space + "___" + kind + "___" + index_name

  def __ConfigureNamespace(self, prefix, app_id, name_space):
    """ Stores a key for the given namespac

    Args:
      prefix: The namespace prefix to configure.
      app_id: The app ID.
      name_space: The per-app namespace name.
    """
    
    vals = {}
    row_key = prefix
    vals[row_key] = {"namespaces":name_space}
    self.datastore_batch.batch_put_entity(APP_NAMESPACE_TABLE, 
                          [row_key], 
                          APP_NAMESPACE_SCHEMA, 
                          vals)
    return True


  def GetTablePrefix(self, data):
    """ Returns the namespace prefix for a query.

    Args:
      data: An Entity, Key or Query PB, or an (app_id, ns) tuple.
    Returns:
      A valid table prefix
    """
    def formatTableName(tableName):
      import re
      return re.sub("[^\w\d_]","",tableName)

    if isinstance(data, entity_pb.EntityProto):
      data = data.key()

    if not isinstance(data, tuple):
      data = (data.app(), data.name_space())

    prefix = ('%s___%s' % data).replace('"', '""')
    prefix = formatTableName(prefix)

    if data not in self.__namespaces:
      if self.__ConfigureNamespace(prefix, *data):
        self.__namespaces.append(data)

    return prefix

  def __GetIndexKey(self, params):
    """Returns the index key
    Args:
       params: a list of strings to be concatenated to form the key made of:
              prefix, kind, property name, and path
    Returns:
       a string
    """
    assert len(params) == 5 or len(params) == 4

    if params[-1] == None:
       # strip off the last None item
       key = '/'.join(params[:-1]) + '/'
    else:
       key = '/'.join(params) 
    return key

  def GetIndexKVFromTuple(self, tuple_list, reverse=False):
    """ Returns keys/value of indexes for a set of entities
 
    Args: 
       tuple_list: A list of tuples of prefix and pb entities
       reverse: if these keys are for the descending table
    Returns:
       A list of keys and values of indexes
    """
    def RowGenerator(entities,rev):
      all_rows = []
      for prefix, e in entities:
        for p in e.property_list():
          val = str(self.__EncodeIndexPB(p.value()))
          # Remove the first binary character
          val = str(val[1:])

          if rev:
            val = helper_functions.reverseLex(val)

          params = [prefix, 
                    self.__GetEntityKind(e), 
                    p.name(), 
                    val, 
                    str(self.__EncodeIndexPB(e.key().path()))]

          index_key = self.__GetIndexKey(params)
          p_vals = [index_key, 
                    buffer(prefix + '/') + \
                    self.__EncodeIndexPB(e.key().path())] 
          all_rows.append(p_vals)
      return tuple(ii for ii in all_rows)
    return RowGenerator(tuple_list, reverse)

  def DeleteIndexEntries(self, entities):
    """ Deletes the entities in the DB

    Args:
       entities: A list of entities for which their 
                 indexes are to be deleted
    """

    if len(entities) == 0: return

    entities_tuple = sorted((self.GetTablePrefix(x), x) for x in entities)
    asc_index_keys = self.GetIndexKVFromTuple(entities_tuple, 
                                                     reverse=False)
    desc_index_keys = self.GetIndexKVFromTuple(entities_tuple, 
                                                     reverse=True)
    # Remove the value, just get keys
    asc_index_keys = [x[0] for x in asc_index_keys] 
    desc_index_keys = [x[0] for x in desc_index_keys] 
    # TODO Consider doing these in parallel with threads
    self.datastore_batch.batch_delete(ASC_PROPERTY_TABLE, asc_index_keys)
    self.datastore_batch.batch_delete(DSC_PROPERTY_TABLE, desc_index_keys)

  def InsertEntities(self, entities):
    """Inserts or updates entities in the DB.
    Args:      
      entities: A list of entities to store.
    """

    def RowGenerator(entities):
      for prefix, e in entities:
        yield (self.__GetEntityKey(prefix, e.key().path()),
               buffer(e.Encode()))

    def KindRowGenerator(entities):
      for prefix, e in entities:
        # yield a tuple of kind key and a reference to entity table
        yield (self.__GetKindKey(prefix, e.key().path()),
               self.__GetEntityKey(prefix, e.key().path()))
    row_values = {}
    row_keys = []

    kind_row_keys = []
    kind_row_values = {}

    entities = sorted((self.GetTablePrefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = tuple(RowGenerator(group))
      new_row_keys = [str(ii[0]) for ii in group_rows]
      row_keys += new_row_keys
      for ii in group_rows:
        row_values[str(ii[0])] = {APP_ENTITY_SCHEMA[0]:str(ii[1]), #ent
                           APP_ENTITY_SCHEMA[1]:"0"} #txnid

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      kind_group_rows = tuple(KindRowGenerator(group))
      new_kind_keys = [str(ii[0]) for ii in kind_group_rows]
      kind_row_keys += new_kind_keys

      for ii in kind_group_rows:
        kind_row_values[str(ii[0])] = {APP_KIND_SCHEMA[0]:str(ii[1])}


    # TODO do these in ||                        
    self.datastore_batch.batch_put_entity(APP_ENTITY_TABLE, 
                                          row_keys, 
                                          APP_ENTITY_SCHEMA, 
                                          row_values)    

    self.datastore_batch.batch_put_entity(APP_KIND_TABLE,
                                          kind_row_keys,
                                          APP_KIND_SCHEMA, 
                                          kind_row_values) 

  def InsertIndexEntries(self, entities):
    """ Inserts index entries for the supplied entities.

    Args:
      entities: A list of tuples of prefix and entities 
                to create index entries for.
    """

    entities = sorted((self.GetTablePrefix(x), x) for x in entities)
    asc_index_keys = self.GetIndexKVFromTuple(entities, reverse=False)
    desc_index_keys = self.GetIndexKVFromTuple(entities, reverse=True)
 
    row_keys = []
    rev_row_keys = []
    row_values = {}
    rev_row_values = {}

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = self.GetIndexKVFromTuple(group,False)
      row_keys = [str(ii[0]) for ii in group_rows]
      for ii in group_rows:
        row_values[str(ii[0])] = {'reference':str(ii[1])}

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      rev_group_rows = self.GetIndexKVFromTuple(group,True)
      rev_row_keys = [str(ii[0]) for ii in rev_group_rows]
      for ii in rev_group_rows:
        rev_row_values[str(ii[0])] = {'reference':str(ii[1])}

    # TODO  these in parallel
    self.datastore_batch.batch_put_entity(ASC_PROPERTY_TABLE, 
                          row_keys, 
                          PROPERTY_SCHEMA, 
                          row_values)

    self.datastore_batch.batch_put_entity(DSC_PROPERTY_TABLE, 
                          rev_row_keys,  
                          PROPERTY_SCHEMA,
                          rev_row_values)

  def __AcquireIdBlockFromDB(self, prefix):
    """ Gets a block of keys from the DB

    Args: 
      prefix: A table namespace prefix
    Returns:
      next_id 
    """  
    res  = self.datastore_batch.batch_get_entity(APP_ID_TABLE, 
                                                 [prefix], 
                                                 APP_ID_SCHEMA)
    if APP_ID_SCHEMA[0] in res[prefix]:
      return int(res[prefix][APP_ID_SCHEMA[0]])
    return 0

  def __IncrementIdInDB(self, prefix):
    """ Updates the counter for a prefix to the DB

    Args: 
      prefix: A table namespace prefix
    Returns: 
      next_block id
    """
    # TODO needs to be transactional
    current_block = self.__AcquireIdBlockFromDB(prefix)
    next_block = 0
    if current_block:
      next_block = current_block + 1
    else: 
      next_block = 1

    cell_values = {prefix:{APP_ID_SCHEMA[0]:str(next_block)}} 

    res = self.datastore_batch.batch_put_entity(APP_ID_TABLE, 
                          [prefix],  
                          APP_ID_SCHEMA,
                          cell_values)
    return next_block * _BLOCK_SIZE

  def AllocateIds(self, prefix, size):
    """ Allocates IDs.

    Args:
      prefix: A table namespace prefix.
      size: Number of IDs to allocate.
    Returns:
      start and end ids: The beginning of a range of size IDs
    """
    assert size > 0
    next_id, end_id = self.__id_map.get(prefix, (0, 0))
    if next_id == end_id or (end_id and (next_id + size > end_id)):
      # Acquire a new block of ids, throw out the old ones
      next_id = self.__IncrementIdInDB(prefix)
      end_id = next_id + _BLOCK_SIZE - 1
       
    start = next_id 
    end = next_id + size - 1

    self.__id_map[prefix] = (next_id + size, end_id)
    return start, end

  def PutEntities(self, entities):
    """ Updates indexes of existing entities, inserts new entities and 
        indexes for them
    Args:
       entities: list of entities
    """
    ents = sorted((self.GetTablePrefix(x), x) for x in entities)
    for prefix, group in itertools.groupby(ents, lambda x: x[0]):
      keys = [e.key() for e in entities]
      self.DeleteEntities(keys)
      self.InsertEntities(entities)
      self.InsertIndexEntries(entities)

  def DeleteEntities(self, keys):
    """ Deletes the entities and the indexes associated with them.
    Args:
       keys: list of keys to be deleted
    """
    def RowGenerator(key_list):
      for prefix, k in key_list:
        yield (self.__GetEntityKey(prefix, k.path()),
               buffer(k.Encode()))

    def KindRowGenerator(key_list):
      for prefix, k in key_list:
        # yield a tuple of kind key and a reference to entity table
        yield (self.__GetKindKey(prefix, k.path()),
               self.__GetEntityKey(prefix, k.path()))
 
    row_keys = []
    kind_keys = []

    entities = sorted((self.GetTablePrefix(x), x) for x in keys)

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = tuple(RowGenerator(group))
      new_row_keys = [str(ii[0]) for ii in group_rows]
      row_keys += new_row_keys

    for prefix, group in itertools.groupby(entities, lambda x: x[0]):
      group_rows = tuple(KindRowGenerator(group))
      new_row_keys = [str(ii[0]) for ii in group_rows]
      kind_keys += new_row_keys

    # Must fetch the entities to get the keys of indexes before deleting
    ret = self.datastore_batch.batch_get_entity(APP_ENTITY_TABLE, 
                                                row_keys,
                                                APP_ENTITY_SCHEMA)

    #TODO do these in ||
    self.datastore_batch.batch_delete(APP_ENTITY_TABLE, 
                                      row_keys)

    self.datastore_batch.batch_delete(APP_KIND_TABLE,
                                      kind_keys)

    entities = []
    for row_key in ret:
      # Entities may not exist if this is the first put
      if 'entity' in ret[row_key]:
        ent = entity_pb.EntityProto()
        ent.ParseFromString(ret[row_key]['entity'])
        entities.append(ent)

    self.DeleteIndexEntries(entities)

  def _Dynamic_Put(self, app_id, put_request, put_response):
    """ Stores and entity and its indexes in the datastore
    
    Args:
      app_id: Application ID
      put_request: Request with entities to store
      put_response: The response sent back to the app server
    """

    entities = put_request.entity_list()
    keys = [e.key() for e in entities]
    for entity in entities:
      self.ValidateKey(entity.key())

      for prop in itertools.chain(entity.property_list(),
                                  entity.raw_property_list()):
        if prop.value().has_uservalue():
          uid = md5.new(prop.value().uservalue().email().lower()).digest()
          uid = '1' + ''.join(['%02d' % ord(x) for x in uid])[:20]
          prop.mutable_value().mutable_uservalue().set_obfuscated_gaiaid(uid)

      assert entity.has_key()
      assert entity.key().path().element_size() > 0
      
      last_path = entity.key().path().element_list()[-1]
      if last_path.id() == 0 and not last_path.has_name():
 
        id_, ignored = self.AllocateIds(self.GetTablePrefix(entity.key()), 1)
        last_path.set_id(id_)

        assert entity.entity_group().element_size() == 0
        group = entity.mutable_entity_group()
        root = entity.key().path().element(0)
        group.add_element().CopyFrom(root)

      else:
        assert (entity.has_entity_group() and
                entity.entity_group().element_size() > 0)

    self.PutEntities(entities)
    put_response.key_list().extend([e.key() for e in entities])

  def FetchKeys(self, key_list):
    """ Given a list of keys fetch the entities
    
    Args:
      key_list: A list of keys to fetch
    Returns:
      A tuple of entities from the datastore and key list
    """
    row_keys = []
    for key in key_list:
      self.ValidateAppId(key.app())
      index_key = str(self.__EncodeIndexPB(key.path()))
      prefix = self.GetTablePrefix(key)
      row_keys.append(prefix + '/' + index_key)
    result = self.datastore_batch.batch_get_entity(APP_ENTITY_TABLE, 
                                                 row_keys, 
                                                 APP_ENTITY_SCHEMA) 
    return (result, row_keys)

  def _Dynamic_Get(self, _, get_request, get_response):
    """ Fetch keys from the datastore
    
    Args: 
       get_request: Request with list of keys
       get_response: Response to application server
    """ 

    keys = get_request.key_list()
    results, row_keys = self.FetchKeys(keys) 
    for r in row_keys:
      if r in results and 'entity' in results[r]:
        group = get_response.add_entity() 
        group.mutable_entity().CopyFrom(
               entity_pb.EntityProto(results[r]['entity']))

  def _Dynamic_Delete(self, app_id, delete_request, delete_response):
      keys = delete_request.key_list()
      self.DeleteEntities(delete_request.key_list())
 
  def GenerateFilterInfo(self, filters, query):
    """ Public wrapper for tetsing
    """
    self.__GenerateFilterInfo(filters, query)

  def __GenerateFilterInfo(self, filters, query):
    """Transform a list of filters into a more usable form.

    Args:
      filters: A list of filter PBs.
      query: The query to generate filter info for.
    Returns:
      A dict mapping property names to lists of (op, value) tuples.
    """

    def ReferencePropertyToReference(refprop):
      ref = entity_pb.Reference()
      ref.set_app(refprop.app())
      if refprop.has_name_space():
        ref.set_name_space(refprop.name_space())
      for pathelem in refprop.pathelement_list():
        ref.mutable_path().add_element().CopyFrom(pathelem)
      return ref

    filter_info = {}
    for filt in filters:
      assert filt.property_size() == 1
      prop = filt.property(0)
      value = prop.value()
      if prop.name() == '__key__':
        value = ReferencePropertyToReference(value.referencevalue())
        assert value.app() == query.app()
        assert value.name_space() == query.name_space()
        value = value.path()
      filter_info.setdefault(prop.name(), []).append((filt.op(), 
                                   self.__EncodeIndexPB(value)))
    return filter_info
  
  def GenerateOrderInfo(self, orders):
    """ Public wrapper for testing
    """
    self.__GenerateOrderInfo(orders)
   
  def __GenerateOrderInfo(self, orders):
    """Transform a list of orders into a more usable form.

    Args:
      orders: A list of order PBs.
    Returns:
      A list of (property, direction) tuples.
    """
    orders = [(order.property(), order.direction()) for order in orders]
    if orders and orders[-1] == ('__key__', datastore_pb.Query_Order.ASCENDING):
      orders.pop()
    return orders

  def __GetStartKey(self, prefix, prop_name, order, last_result):
    """ Builds the start key for cursor query

    Args: 
        prop_name: property name of the filter 
        order: sort order 
        last_result: last result encoded in cursor
    """
    e = last_result
    start_key = None
    if not prop_name and not order:
        return str(prefix + '/' + self.__EncodeIndexPB(e.key().path())) 
     
    if e.property_list():
      plist = e.property_list()
    else:   
      rkey = prefix + '/' + str(self.__EncodeIndexPB(e.key().path()))
      ret = datastore_batch.batch_get_entity(APP_ENTITY_TABLE, 
                                             [rkey], 
                                             APP_ENTITY_SCHEMA)
      if 'entity' in ret[rkey]:
        ent = entity_pb.EntityProto(ret[rkey]['entity'])
        plist = ent.property_list() 

    for p in plist:
      if p.name() == prop_name:
        break

    val = str(self.__EncodeIndexPB(p.value()))
    # remove first binary char
    val = str(val[1:])

    if order == datastore_pb.Query_Order.DESCENDING:
      val = helper_functions.reverseLex(val)        
    params = [prefix,
              self.__GetEntityKind(e), 
              p.name(), 
              val, 
              str(self.__EncodeIndexPB(e.key().path()))]

    return self.__GetIndexKey(params)

  def __FetchEntities(self, refs):
    """ Given the results from a table scan, get the references
    
    Args: 
      refs: key/value pairs where the values contain a reference to 
            the entitiy table
    """
    keys = [item.keys()[0] for item in refs]
    rowkeys = []    
    for index, ent in enumerate(refs):
      key = keys[index]
      ent = ent[key]['reference']
      rowkeys.append(ent)

    result = self.datastore_batch.batch_get_entity(APP_ENTITY_TABLE, 
                                                   rowkeys,
                                                   APP_ENTITY_SCHEMA)
    entities = []
    keys = result.keys()
    for key in keys:
      if 'entity' in result[key]:
        entities.append(result[key]['entity'])

    return entities 

  def __ExtractEntities(self, kv):
    """ Given a result from a range query on the Entity table return a 
        list of encoded entities
    Args:
      kv: Key and values from a range query on the entity table
    """
    keys = [item.keys()[0] for item in kv]
    results = []    
    for index, ent in enumerate(kv):
      key = keys[index]
      ent = ent[key]['entity']
      results.append(ent)

    return results

    
  def __AncestorQuery(self, query, filter_info, order_info):
    """ Performs ancestor queries
      
    Args: 
      query: query
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      start and end row keys
    """       
    ancestor = query.ancestor()
    prefix = self.GetTablePrefix(query)
    path = buffer(prefix + '/') + self.__EncodeIndexPB(ancestor.path())
    startrow = path
    endrow =  path + _TERM_STRING

    end_inclusive = _ENABLE
    start_inclusive = _ENABLE

    if '__key__' in filter_info:
      startrow = prefix + '/' + str(filter_info['__key__'][0][1])
      start_inclusive = _DISABLE


    column_names = ['reference']
    if not order_info:
      order = None
      prop_name = None
    
    # TODO test this 
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
       cursor = cassandra_stub_util.ListCursor(query)
       last_result = cursor._GetLastResult()
       startrow = self.__GetStartKey(prefix, prop_name, order, last_result)
       start_inclusive = _DISABLE

    if query.has_limit() and query.limit():
      limit = query.limit()
    else:
      limit = _MAXIMUM_RESULTS

    offset = query.offset()
  
    result = self.datastore_batch.range_query(APP_ENTITY_TABLE, 
                                              APP_ENTITY_SCHEMA, 
                                              startrow, 
                                              endrow, 
                                              limit, 
                                              offset=offset, 
                                              start_inclusive=start_inclusive, 
                                              end_inclusive=end_inclusive)
    return self.__ExtractEntities(result)

  def __KindlessQuery(self, query, filter_info, order_info):
    """ Performs kindless queries
      
    Args: 
      query: query
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      Entities that match the query
    """       
    prefix = self.GetTablePrefix(query)
    __key__ = str(filter_info['__key__'][0][1])
    for filt in query.filter_list():
      op = filt.op
    startrow = prefix + '/' + __key__
    endrow = prefix + '/'  + _TERM_STRING

    end_inclusive = _ENABLE
    start_inclusive = _ENABLE
    if not order_info:
      order = None
      prop_name = None
    
    # TODO test this 
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
       cursor = cassandra_stub_util.ListCursor(query)
       last_result = cursor._GetLastResult()
       startrow = self.__GetStartKey(prefix, prop_name, order, last_result)
       start_inclusive = _DISABLE

    if query.has_limit() and query.limit():
      limit = query.limit()
    else:
      limit = _MAXIMUM_RESULTS

    offset = query.offset()
  
    result = self.datastore_batch.range_query(APP_ENTITY_TABLE, 
                                              APP_ENTITY_SCHEMA, 
                                              startrow, 
                                              endrow, 
                                              limit, 
                                              offset=offset, 
                                              start_inclusive=start_inclusive, 
                                              end_inclusive=end_inclusive)

    return self.__ExtractEntities(result)

  def __KindQueryRange(self, query, filter_info, order_info):
    """ Gets start and end keys for kind queries
      
    Args: 
      query: query
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      Entities that match the query
    """       
    prefix = self.GetTablePrefix(query)
    startrow = prefix + '/' + query.kind() + ':'     
    endrow = prefix + '/' + query.kind() + ':' + _TERM_STRING
    return startrow, endrow

  def KindQuery(self, query, filter_info, order_info):
    """ Public wrapper for testing 
    """
    return self.__KindQuery(query, filter_info, order_info)
    
  def __KindQuery(self, query, filter_info, order_info):
    """ Performs kind only queries, kind and ancestor, and ancestor queries
        https://developers.google.com/appengine/docs/python/datastore/queries
    Args:
      query: query
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      list of results
    """

    # Detect quicky if this is a kind query or not
    for fi in filter_info:
      if fi != "__key__":
        return 

    if order_info:
      if len(order_info) > 0: return None
    elif query.has_ancestor():
      return self.__AncestorQuery(query, filter_info, order_info)
    elif not query.has_kind():
      return self.__KindlessQuery(query, filter_info, order_info)

    
    startrow, endrow = self.__KindQueryRange(query, 
                                             filter_info, 
                                             order_info)

    if startrow == None:
      return None

    end_inclusive = _ENABLE
    start_inclusive = _ENABLE
    if not order_info:
      order = None
      prop_name = None
    
    # TODO test cursor support
    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
       cursor = cassandra_stub_util.ListCursor(query)
       last_result = cursor._GetLastResult()
       startrow = self.__GetStartKey(prefix, prop_name, order, last_result)
       start_inclusive = _DISABLE

    if query.has_limit() and query.limit():
      limit = query.limit()
    else:
      limit = _MAXIMUM_RESULTS

    offset = query.offset()
  
    result = self.datastore_batch.range_query(APP_KIND_TABLE, 
                                              APP_KIND_SCHEMA, 
                                              startrow, 
                                              endrow, 
                                              limit, 
                                              offset=offset, 
                                              start_inclusive=start_inclusive, 
                                              end_inclusive=end_inclusive)
    return self.__FetchEntities(result)

  def __SinglePropertyQuery(self, query, filter_info, order_info):
    """Performs queries satisfiable by the Single_Property tables
    Args:
      query: query
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      list of results
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

    prefix = self.GetTablePrefix(query)
 
    offset = query.offset()
    if query.has_limit() and query.limit():
      limit = query.limit()
    else:
      limit = _MAXIMUM_RESULTS

    kind = query.kind()

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
      cursor = cassandra_stub_util.ListCursor(query)
      last_result = cursor._GetLastResult()
      startrow = self.__GetStartKey(prefix, 
                                    property_name,
                                    direction,
                                    last_result)
    else:
      startrow = None

    references = self.__ApplyFilters(filter_ops, 
                               order_info, 
                               property_name, 
                               query.kind(), 
                               prefix, 
                               limit, 
                               offset, 
                               startrow)
    return self.__FetchEntities(references)

    
  def __ApplyFilters(self, 
                     filter_ops, 
                     order_info, 
                     property_name, 
                     kind, 
                     prefix, 
                     limit, 
                     offset, 
                     startrow): 
    """Apply property filters in the query
    Args:
       filter_ops: tuple with property filter operator and value
       order_info: tuple with property name and sort order
       kind: Kind of the entity
       prefix: prefix for the table
       limit: number of results
       offset: number of results to skip
       startrow: start key for the range scan
    Results:
       Returns a list of index keys 
    """ 
    
    end_inclusive = _ENABLE
    start_inclusive = _ENABLE

    endrow = None 
    column_names = PROPERTY_SCHEMA

    if order_info:
      if order_info[0][0] == property_name:
         direction = order_info[0][1]
    else:
      direction = datastore_pb.Query_Order.ASCENDING

    if direction == datastore_pb.Query_Order.ASCENDING:
      table_name = ASC_PROPERTY_TABLE
    else: 
      table_name = DSC_PROPERTY_TABLE
  
    if startrow: start_inclusive = _DISABLE 

    # This query is returning based on order on a specfic property name 
    # The start key (if not already supplied) depends on the property
    # name and does not take into consideration its value. The end key
    # is based on the terminating string.
    if len(filter_ops) == 0 and (order_info and len(order_info) == 1):
      end_inclusive = _ENABLE
      start_inclusive = _ENABLE

      if not startrow:
        params = [prefix, kind, property_name, None]
        startrow = self.__GetIndexKey(params)

      params = [prefix, kind, property_name, _TERM_STRING, None]
      endrow = self.__GetIndexKey(params)

      return self.datastore_batch.range_query(table_name, 
                                          column_names, 
                                          startrow, 
                                          endrow, 
                                          limit, 
                                          offset=offset, 
                                          start_inclusive=start_inclusive, 
                                          end_inclusive=end_inclusive)      

    #TODO byte stuff value for '/' character?

    # This query has a value it bases the query on for a property name
    # The difference between operators is what the end and start key are
    if len(filter_ops) == 1:
      oper = filter_ops[0][0]
      value = str(filter_ops[0][1])

      # Strip off the first char of encoding
      value = str(value[1:]) 

      if direction == datastore_pb.Query_Order.DESCENDING: 
        value = helper_functions.reverseLex(value)

      if oper == datastore_pb.Query_Filter.EQUAL:
        start_value = value 
        end_value = value + _TERM_STRING

      elif oper == datastore_pb.Query_Filter.LESS_THAN:
        start_value = None
        end_value = value + '/'
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = value + _TERM_STRING
          end_value = _TERM_STRING

      elif oper == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
        start_value = None
        end_value = value + '/' + _TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = value + '/'
          end_value = _TERM_STRING
      elif oper == datastore_pb.Query_Filter.GREATER_THAN:
        start_value = value + _TERM_STRING
        end_value = _TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = None
          end_value = value + '/' 

      elif oper == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
        start_value = value + '/'
        end_value = _TERM_STRING
        if direction == datastore_pb.Query_Order.DESCENDING:
          start_value = None
          end_value = value + '/' +  _TERM_STRING
      elif oper == datastore_pb.Query_Filter.IN:
        raise Exception("IN queries are not implemented")
      elif oper == datastore_pb.Query_Filter.EXIST:
        raise Exception("EXIST queries are not implemented")
      else:
        raise Exception("Unknow query of operation %d"%oper)

      if not startrow:
        params = [prefix, kind, property_name, start_value]
        startrow = self.__GetIndexKey(params)
        start_inclusive = _DISABLE

      params = [prefix, kind, property_name, end_value]
      endrow = self.__GetIndexKey(params)

      return self.datastore_batch.range_query(table_name, 
                                          column_names, 
                                          startrow, 
                                          endrow, 
                                          limit, 
                                          offset=offset, 
                                          start_inclusive=start_inclusive, 
                                          end_inclusive=end_inclusive)      

       
    if len(filter_ops)>1:
      if filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN or filter_ops[0][0] == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
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
         table_name = ASC_PROPERTY_TABLE
         if oper1 == datastore_pb.Query_Filter.GREATER_THAN:
                start_inclusive = _DISABLE
                if startrow:
                   start_inclusive = _DISABLE
                else:
                   params = [kind, property_name, value1, _TERM_STRING]
                   startrow = self.__GetIndexKey(params)
                if oper2 == datastore_pb.Query_Filter.LESS_THAN:    
                   params = [kind, property_name, value2, None]
                   endrow = self.__GetIndexKey(params)
                   end_inclusive = _DISABLE
                if oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
                   params = [kind, property_name, value2, None]
                   endrow = self.__GetIndexKey(params)
                   end_inclusive = _ENABLE
         if oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
                start_inclusive = _ENABLE
                if startrow:
                   start_inclusive = _DISABLE
                else:
                   params = [kind, property_name, value1, _TERM_STRING]
                   startrow = self.__GetIndexKey(params)
               
                if oper2 == datastore_pb.Query_Filter.LESS_THAN:
                   params = [kind, property_name, value2, None]
                   endrow = self.__GetIndexKey(params)
                   end_inclusive = _DISABLE
                if oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
                   params = [kind, property_name, value2, None]
                   endrow = self.__GetIndexKey(params)
                   end_inclusive = _ENABLE


         result = cass.range_query( table_name, column_names, limit, offset, startrow, endrow,start_inclusive, end_inclusive)
         if oper1 == datastore_pb.Query_Filter.EQUAL and oper2 == datastore_pb.Query_Filter.EQUAL:
                
                keys = [self.__GetIndexKey([kind, property_name, value1, None]), self.__GetIndexKey([kind, property_name, value2, None])]
                result =  cass.batch_get_entity(table_name,keys,column_names)
       
      if direction == datastore_pb.Query_Order.DESCENDING:
         table_name = DSC_PROPERTY_TABLE
         value1 = helper_functions_cass.reverseLex(value1)
         value2 = helper_functions_cass.reverseLex(value2) 
         if oper1 == datastore_pb.Query_Filter.GREATER_THAN:   
                params = [kind, property_name, value1, None]
                endrow = self.__GetIndexKey(params)
                end_inclusive = _DISABLE
                if oper2 == datastore_pb.Query_Filter.LESS_THAN:
                   start_inclusive = _DISABLE
                   if startrow:
                      start_inclusive = _DISABLE
                   else:  
                      params = [kind, property_name, value2, None]
                      startroe = self.__GetIndexKey(params)
                if filter_ops[1][0] == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
                   start_inclusive = _ENABLE
                   if startrow:
                      start_inclusive = _DISABLE
                   else:
                      params = [kind, property_name, value2, None]
                      startrow = self.__GetIndexKey(params)
                   
         if oper1 == datastore_pb.Query_Filter.GREATER_THAN_OR_EQUAL:
                params = [kind, property_name, value1, None]
                endrow = self.__GetIndexKey(params)
                end_inclusive = _ENABLE
                if oper2 == datastore_pb.Query_Filter.LESS_THAN:
                   start_inclusive = _DISABLE
                   if startrow:
                      start_inclusive = _DISABLE
                   else:
                      params = [kind, property_name, value2, _TERM_STRING]
                      startrow = self.__GetIndexKey(params)
                if oper2 == datastore_pb.Query_Filter.LESS_THAN_OR_EQUAL:
                   start_inclusive = _ENABLE
                   if startrow:
                      start_inclusive = _DISABLE
                   else:
                      params = [kind, property_name, value2, _TERM_STRING]
                      startrow = self.__GetIndexKey(params)
                   
         res = cass.range_query(table_name, column_names, limit, offset, startrow, endrow, start_inclusive, end_inclusive)
         if oper1 == datastore_pb.Query_Filter.EQUAL and oper2 == datastore_pb.Query_Filter.EQUAL:
                keys = [self.__GetIndexKey([kind, property_name, value1, None]), self.__GetIndexKey([kind, property_name, value2, None])]
                res =  cass.batch_get_entity(table_name,keys,column_names)          
         result =[] 
         for r in res:
           i = r[0]
           l = i.split("/")
           l[2] = helper_functions_cass.reverseLex(l[2])
           key = "/".join(l)
           result.append((key,r[1]))
          
    return result

  def __CompositeQuery(self, query, filter_info, order_info):  
    """Performs Composite queries 
    Args:
      query: query
      filter_info: tuple with filter operators and values
      order_info: tuple with property name and the sort order
    Returns:
      list of results
    """

    if order_info and order_info[0][0] == '__key__':
      return None

    if query.has_ancestor():
      return None

    if not query.has_kind():
      return None

    property_names = set(filter_info.keys())
    property_names.update(x[0] for x in order_info)
    order_names = [x[0] for x in order_info]
    property_names.discard('__key__')
    property_names = list(property_names)
    if len(property_names) <= 1:
      return None
    property_name = None
    for p in filter_info.keys():
        f = filter_info[p]
        if f[0][0] != datastore_pb.Query_Filter.EQUAL: 
           property_name = p     
           property_names.remove(p)
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
    
    count = _MAX_COMPOSITE_WINDOW
    off = 0              
    kind = query.kind()
    if query.has_limit() and query.limit(): 
       limit = query.limit()
    else:
       limit = _MAXIMUM_RESULTS
    offset = query.offset()
    prefix = self.GetTablePrefix(query)

    if query.has_compiled_cursor() and query.compiled_cursor().position_size():
            cursor = cassandra_stub_util.ListCursor(query)
            last_result = cursor._GetLastResult()
            startrow = self.__GetStartKey(prefix, property_name,direction,last_result)
    else:
        startrow = None

    result = []     
    temp_res = self.__ApplyFilters(filter_ops, order_ops, property_name, kind, prefix, count, off, startrow)

    while len(result) < (limit+offset) and temp_res:
       temp_keys = [r[0] for r in temp_res]
       table_name = prefix + 'Entities'
       column_names = ['reference']
       ent_keys = [r[1] for r in temp_res]
       ent_res = cass.batch_get_entity(table_name, ent_keys, column_names)
       while len(property_names) != 0:
         prop = property_names.pop()
         temp_filt = filter_info.get(prop,[])
         keys = [r[0] for r in ent_res]  
         for r in ent_res:
             e = entity_pb.EntityProto(r[1])
             prop_list = e.property_list()
             for each in prop_list:
                 if each.name() == prop:
                    pr = each
                    break
             if len(temp_filt) == 1:         
                oper = temp_filt[0][0]
                value = str(temp_filt[0][1])
                if oper == datastore_pb.Query_Filter.EQUAL:
                   v = str(self.__EncodeIndexPB(pr.value()))                
                   if v == value:
                      result.append(e)
             elif len(temp_filt) < 1:
                result.append(e)
       startrow = temp_keys[-1]
       temp_res = self.__ApplyFilters(filter_ops, order_ops, property_name, kind, prefix, count, off, startrow) 
    results = []
    if result:
      result = result[offset:]
      if order_info:
         order_info.remove(order_ops[0])
      vals = []
      for i in order_info:    
        ord_prop = i[0]
        ord_dir = i[1]
        for e in result:
            prop_list = e.property_list()
            for each in prop_list:
                if each.name() == ord_prop:
                    vals.append((each.value(),e))
                    break
        if ord_dir == datastore_pb.Query_Order.DESCENDING:
           sorted_vals = sorted(vals, key = lambda v:v[0])
           sorted_vals.reverse()
        else:
           sorted_vals = sorted(vals, key = lambda v:v[0])
        result = [s[1] for s in sorted_vals]
      #if query.has_keys_only():
      #  results = [str(self.__EncodeIndexPB(e.key().path())) for e in result]
      #else:
      results = [str(buffer(x.Encode())) for x in result]  
    return results 


  _QUERY_STRATEGIES = [
      __SinglePropertyQuery,   
      __KindQuery,
      __CompositeQuery,
  ]

  def __GetQueryResults(self, query):
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
    if num_components > _MAX_QUERY_COMPONENTS:
      raise apiproxy_errors.ApplicationError(
          datastore_pb.Error.BAD_REQUEST,
          ('query is too large. may not have more than %s filters'
           ' + sort orders ancestor total' % _MAX_QUERY_COMPONENTS))

    app_id = query.app()
    self.ValidateAppId(app_id)
    filters, orders = datastore_index.Normalize(query.filter_list(),
                                                query.order_list())
    filter_info = self.__GenerateFilterInfo(filters, query)
    order_info = self.__GenerateOrderInfo(orders)
    for strategy in DatastoreDistributed._QUERY_STRATEGIES:
      results = strategy(self, query, filter_info, order_info)
      if results:
        break

    # TODO keys only queries
  
  #else:
     # raise apiproxy_errors.ApplicationError(
      #    datastore_pb.Error.BAD_REQUEST,
       #   'No strategy found to satisfy query.')
    return results
  
  def _Dynamic_Run_Query(self, app_id, query, query_result):
    """Populates the query result which in turn encodes cursor"""
    result = self.__GetQueryResults(query)
    count = 0
    if result:
      for index,ii in enumerate(result):
        result[index] = entity_pb.EntityProto(ii)
      count = len(result)
     
    cur = cassandra_stub_util.QueryCursor(query, result)
    cur.PopulateQueryResult(count, query.offset(), query_result) 
      
logger = appscale_logger.getLogger("pb_server")

class MainHandler(tornado.web.RequestHandler):
  """
  Defines what to do when the webserver receives different types of 
  HTTP requests.
  """

  @tornado.web.asynchronous
  def get(self):
    self.write("{'status':'up'}")
    self.finish() 

  def remote_request(self, app_id, http_request_data):
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
    elif method == "CreateIndex":
      errcode = 0
      errdetail = ""
      response = api_base_pb.Integer64Proto()
      response.set_value(0)
      response = response.Encode()
      #logger.debug(errdetail)

    elif method == "GetIndices":
      response = datastore_pb.CompositeIndices().Encode()
      errcode = 0
      errdetail = ""
      #logger.debug(errdetail)

    elif method == "UpdateIndex":
      response = api_base_pb.VoidProto().Encode()
      errcode = 0
      errdetail = ""
      #logger.debug(errdetail)

    elif method == "DeleteIndex":
      response = api_base_pb.VoidProto().Encode()
      errcode = 0
      errdetail = ""
      #logger.debug(errdetail)

    else:
      errcode = datastore_pb.Error.BAD_REQUEST 
      errdetail = "Unknown datastore message" 
      #logger.debug(errdetail)
    
      
    apiresponse.set_response(response)
    if errcode != 0:
      apperror_pb = apiresponse.mutable_application_error()
      apperror_pb.set_code(errcode)
      apperror_pb.set_detail(errdetail)
    if errcode != 0:
      print "REPLY",method," AT TIME",time.time()
      print "errcode:",errcode
      print "errdetail:",errdetail
    self.write(apiresponse.Encode() )    

  def begin_transaction_request(self, app_id, http_request_data):
    transaction_pb = datastore_pb.Transaction()
    handle = 0
    #print "Begin Trans Handle:",handle
    handle = app_datastore.setupTransaction(app_id)
    transaction_pb.set_app(app_id)
    transaction_pb.set_handle(handle)
    return (transaction_pb.Encode(), 0, "")

  def commit_transaction_request(self, app_id, http_request_data):
    transaction_pb = datastore_pb.Transaction(http_request_data)
    txn_id = transaction_pb.handle()
    commitres_pb = datastore_pb.CommitResponse()
    try:
      app_datastore._Dynamic_Commit(app_id, transaction_pb, commitres_pb)
    except:
      return (commitres_pb.Encode(), datastore_pb.Error.PERMISSION_DENIED, "Unable to commit for this transaction")
    return (commitres_pb.Encode(), 0, "")

  def rollback_transaction_request(self, app_id, http_request_data):
    transaction_pb = datastore_pb.Transaction(http_request_data)
    handle = transaction_pb.handle()
    try:
      app_datastore._Dynamic_Rollback(app_id, transaction_pb, None)
    except:
      return(api_base_pb.VoidProto().Encode(), datastore_pb.Error.PERMISSION_DENIED, "Unable to rollback for this transaction")
    return (api_base_pb.VoidProto().Encode(), 0, "")

  def run_query(self, app_id, http_request_data):

    global app_datastore
    query = datastore_pb.Query(http_request_data)
    # Pack Results into a clone of QueryResult #
    clone_qr_pb = datastore_pb.QueryResult()
    app_datastore._Dynamic_Run_Query(app_id, query, clone_qr_pb)
    return (clone_qr_pb.Encode(), 0, "")


  def put_request(self, app_id, http_request_data):
    global app_datastore
    start_time = time.time() 
    putreq_pb = datastore_pb.PutRequest(http_request_data)
    putresp_pb = datastore_pb.PutResponse( )
    app_datastore._Dynamic_Put(app_id, putreq_pb, putresp_pb)
    return (putresp_pb.Encode(), 0, "")
    
  def get_request(self, app_id, http_request_data):
    global app_datastore
    getreq_pb = datastore_pb.GetRequest(http_request_data)
    logger.debug("GET_REQUEST: %s" % getreq_pb)
    getresp_pb = datastore_pb.GetResponse()
    app_datastore._Dynamic_Get(app_id, getreq_pb, getresp_pb)
    return (getresp_pb.Encode(), 0, "")

  def delete_request(self, app_id, http_request_data):
    global app_datastore
    logger.debug("DeleteRequest Received...")
    delreq_pb = datastore_pb.DeleteRequest( http_request_data )
    logger.debug("DELETE_REQUEST: %s" % delreq_pb)
    delresp_pb = api_base_pb.VoidProto() 
    app_datastore._Dynamic_Delete(app_id, delreq_pb, delresp_pb)
    return (delresp_pb.Encode(), 0, "")

  def void_proto(self, app_id, http_request_data):
    resp_pb = api_base_pb.VoidProto() 
    print "Got void"
    logger.debug("VOID_RESPONSE: %s to void" % resp_pb)
    return (resp_pb.Encode(), 0, "" )
  
  def str_proto(self, app_id, http_request_data):
    str_pb = api_base_pb.StringProto( http_request_data )
    composite_pb = datastore_pb.CompositeIndices()
    print "Got a string proto"
    print str_pb
    logger.debug("String proto received: %s"%str_pb)
    logger.debug("CompositeIndex response to string: %s" % composite_pb)
    return (composite_pb.Encode(), 0, "" )    
  
  def int64_proto(self, app_id, http_request_data):
    int64_pb = api_base_pb.Integer64Proto( http_request_data ) 
    resp_pb = api_base_pb.VoidProto()
    print "Got a int 64"
    print int64_pb
    logger.debug("Int64 proto received: %s"%int64_pb)
    logger.debug("VOID_RESPONSE to int64: %s" % resp_pb)
    return (resp_pb.Encode(), 0, "")
 
  def compositeindex_proto(self, app_id, http_request_data):
    compindex_pb = entity_pb.CompositeIndex( http_request_data)
    resp_pb = api_base_pb.VoidProto()
    print "Got Composite Index"
    #print compindex_pb
    logger.debug("CompositeIndex proto recieved: %s"%str(compindex_pb))
    logger.debug("VOID_RESPONSE to composite index: %s" % resp_pb)
    return (resp_pb.Encode(), 0, "")


  ##############
  # OTHER TYPE #
  ##############
  def unknown_request(self, app_id, http_request_data, pb_type):
    logger.debug("Received Unknown Protocol Buffer %s" % pb_type )
    print "ERROR: Received Unknown Protocol Buffer <" + pb_type +">.",
    print "Nothing has been implemented to handle this Protocol Buffer type."
    print "http request data:"
    print http_request_data 
    print "http done"
    self.void_proto(app_id, http_request_data)

  
  #########################
  # POST Request Handling #
  #########################

  @tornado.web.asynchronous
  def post( self ):
    request = self.request
    http_request_data = request.body
    pb_type = request.headers['protocolbuffertype']
    app_data = request.headers['appdata']
    app_data  = app_data.split(':')
    #logger.debug("POST len: %d" % len(app_data))

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
      #logger.debug("UNABLE TO EXTRACT APPLICATION DATA")
      return

    if pb_type == "Request":
      self.remote_request(app_id, http_request_data)
    else:
      self.unknown_request(app_id, http_request_data, pb_type)
    self.finish()

def usage():
  print "AppScale Server"
  print
  print "Options:"
  print "\t--type=<hypertable, hbase, cassandra, mysql, mongodb>"
  print "\t--no_encryption"
  print "\t--port"
  print "\t--zoo_keeper <zk nodes>"

pb_application = tornado.web.Application([
    (r"/*", MainHandler),
])

def main(argv):
  global app_datastore
  global zoo_keeper_locations
  global zoo_keeper_real
  global zoo_keeper_stub

  VALID_DATASTORES = []
  DEFAULT_SSL_PORT = 8443
  DEFAULT_PORT = 4080

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
      print "Datastore type: ",db_type
    elif opt in ("-p", "--port"):
      port = int(arg)
    elif opt in ("-n", "--no_encryption"):
      isEncrypted = False
    elif opt in ("-z", "--zoo_keeper"):
      zoo_keeper_locations = arg
 
  datastore_batch = appscale_datastore_batch.DatastoreFactory.getDatastore(db_type)
  app_datastore = DatastoreDistributed(datastore_batch)

  VALID_DATASTORES = appscale_datastore_batch.DatastoreFactory.valid_datastores()

  if db_type not in VALID_DATASTORES:
    print "Unknown datastore "+ db_type
    exit(1)

  #zoo_keeper_real = zk.ZKTransaction(zoo_keeper_locations)
  #zoo_keeper_stub = zk_stub.ZKTransaction(zoo_keeper_locations)

  if port == DEFAULT_SSL_PORT and not isEncrypted:
    port = DEFAULT_PORT

  server = tornado.httpserver.HTTPServer(pb_application)
  server.listen(port)

  while 1:
    try:
      # Start Server #
      tornado.ioloop.IOLoop.instance().start()
    except SSL.SSLError:
      pass
      #logger.debug("\n\nUnexcepted input for AppScale-Secure-Server")
    except KeyboardInterrupt:
      #server.socket.close() 
      print "Server interrupted by user, terminating..."
      exit(1)

if __name__ == '__main__':
  #cProfile.run("main(sys.argv[1:])")
  main(sys.argv[1:])
