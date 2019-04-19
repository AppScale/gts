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

""" Non-stub version of the memcache API, keeping all data in memcached.
Uses the pymemcache library to interface with memcached.
"""
import base64
import cPickle
import logging
import hashlib
import os
import socket
import time

import six
from pymemcache.exceptions import MemcacheError, MemcacheClientError
from pymemcache.client.hash import HashClient

from google.appengine.api import apiproxy_stub
from google.appengine.api.memcache import memcache_service_pb
from google.appengine.runtime import apiproxy_errors

MemcacheSetResponse = memcache_service_pb.MemcacheSetResponse
MemcacheSetRequest = memcache_service_pb.MemcacheSetRequest
MemcacheIncrementRequest = memcache_service_pb.MemcacheIncrementRequest
MemcacheIncrementResponse = memcache_service_pb.MemcacheIncrementResponse
MemcacheDeleteResponse = memcache_service_pb.MemcacheDeleteResponse

from google.appengine.api.memcache import TYPE_INT
from google.appengine.api.memcache import TYPE_LONG
from google.appengine.api.memcache import MAX_KEY_SIZE

# Exceptions that indicate a temporary issue with the backend.
TRANSIENT_ERRORS = (MemcacheError, socket.error, socket.timeout)

INVALID_VALUE = memcache_service_pb.MemcacheServiceError.INVALID_VALUE
UNSPECIFIED_ERROR = memcache_service_pb.MemcacheServiceError.UNSPECIFIED_ERROR


class MemcacheService(apiproxy_stub.APIProxyStub):
  """Python only memcache service.

  This service keeps all data in any external servers running memcached.
  """
  # The memcached default port.
  MEMCACHE_PORT = 11211

  # An AppScale file which has a list of IPs running memcached.
  APPSCALE_MEMCACHE_FILE = "/etc/appscale/memcache_ips"

  def __init__(self, service_name='memcache'):
    """Initializer.

    Args:
      service_name: Service name expected for all calls.
    """
    super(MemcacheService, self).__init__(service_name)
    self._memcache = None
    self.setupMemcacheClient()

  def setupMemcacheClient(self):
    """ Sets up the memcache client. """
    if os.path.exists(self.APPSCALE_MEMCACHE_FILE):
      memcache_file = open(self.APPSCALE_MEMCACHE_FILE, "r")
      all_ips = memcache_file.read().split("\n")
      memcache_file.close()
    else:
      all_ips = ['localhost']

    memcaches = [(ip, self.MEMCACHE_PORT) for ip in all_ips if ip]
    memcaches.sort()    
    self._memcache = HashClient(memcaches, connect_timeout=5, timeout=1,
                                use_pooling=True)

    # The GAE API expects return values for all mutate operations.
    for client in six.itervalues(self._memcache.clients):
      client.default_noreply = False

  def _Dynamic_Get(self, request, response):
    """Implementation of gets for memcache.
     
    Args:
      request: A MemcacheGetRequest protocol buffer.
      response: A MemcacheGetResponse protocol buffer.
    """
    key_dict = {self._GetKey(request.name_space(), key): key
                for key in request.key_list()}
    try:
      backend_response = self._memcache.get_many(
        key_dict.keys(), gets=request.for_cas())
    except MemcacheClientError as error:
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'Bad request: {}'.format(error))
    except TRANSIENT_ERRORS as error:
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'Transient memcache error: {}'.format(error))

    for encoded_key, encoded_val in six.iteritems(backend_response):
      item = response.add_item()
      key = key_dict[encoded_key]
      item.set_key(key)
      if request.for_cas():
        item.set_cas_id(int(encoded_val[1]))
        encoded_val = encoded_val[0]

      flags, val = cPickle.loads(encoded_val)
      item.set_value(val)
      item.set_flags(flags)

  def _Dynamic_Set(self, request, response):
    """Implementation of sets for memcache. 

    Args:
      request: A MemcacheSetRequest.
      response: A MemcacheSetResponse.
    """
    client_methods = {MemcacheSetRequest.SET: self._memcache.set,
                      MemcacheSetRequest.ADD: self._memcache.add,
                      MemcacheSetRequest.REPLACE: self._memcache.replace,
                      MemcacheSetRequest.CAS: self._memcache.cas}
    namespace = request.name_space()
    invalid_policy = next((item.set_policy() for item in request.item_list()
                           if item.set_policy() not in client_methods), None)
    if invalid_policy is not None:
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'Unsupported set_policy'.format(invalid_policy))

    if not all(item.has_cas_id() for item in request.item_list()
               if item.set_policy() == MemcacheSetRequest.CAS):
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'All CAS items must have a cas_id')

    for item in request.item_list():
      encoded_key = self._GetKey(namespace, item.key())
      args = {'key': encoded_key,
              'value': cPickle.dumps([item.flags(), item.value()]),
              'expire': int(item.expiration_time())}
      is_cas = item.set_policy() == MemcacheSetRequest.CAS
      if is_cas:
        args['cas'] = six.binary_type(item.cas_id())

      try:
        backend_response = client_methods[item.set_policy()](**args)
      except (TRANSIENT_ERRORS + (MemcacheClientError,)):
        response.add_set_status(MemcacheSetResponse.ERROR)
        continue

      if backend_response:
        response.add_set_status(MemcacheSetResponse.STORED)
        continue

      if is_cas and backend_response is False:
        response.add_set_status(MemcacheSetResponse.EXISTS)
        continue

      response.add_set_status(MemcacheSetResponse.NOT_STORED)

  def _Dynamic_Delete(self, request, response):
    """Implementation of delete in memcache.

    Args:
      request: A MemcacheDeleteRequest protocol buffer.
      response: A MemcacheDeleteResponse protocol buffer.
    """
    for item in request.item_list():
      encoded_key = self._GetKey(request.name_space(), item.key())
      try:
        key_existed = self._memcache.delete(encoded_key)
      except MemcacheClientError as error:
        raise apiproxy_errors.ApplicationError(
          UNSPECIFIED_ERROR, 'Bad request: {}'.format(error))
      except TRANSIENT_ERRORS as error:
        raise apiproxy_errors.ApplicationError(
          UNSPECIFIED_ERROR, 'Transient memcache error: {}'.format(error))

      response.add_delete_status(MemcacheDeleteResponse.DELETED if key_existed
                                 else MemcacheDeleteResponse.NOT_FOUND)

  def _Increment(self, namespace, request):
    """Internal function for incrementing from a MemcacheIncrementRequest.

    Args:
      namespace: A string containing the namespace for the request,
        if any. Pass an empty string if there is no namespace.
      request: A MemcacheIncrementRequest instance.

    Returns:
      An integer or long if the offset was successful, None on error.
    """
    if not request.delta():
      return None

    key = self._GetKey(namespace, request.key())
    value, cas_id = self._memcache.gets(key)
    if value is None and not request.has_initial_value():
      return

    if value is None:
      flags = TYPE_INT
      if request.has_initial_flags():
        flags = request.initial_flags()

      initial_value = cPickle.dumps([flags, str(request.initial_value())])
      success = self._memcache.add(key, initial_value)
      if not success:
        return

      value, cas_id = self._memcache.gets(key)
      if value is None:
        return

    flags, stored_value = cPickle.loads(value)
    if flags == TYPE_INT:
      new_value = int(stored_value)
    elif flags == TYPE_LONG:
      new_value = long(stored_value)

    if request.direction() == MemcacheIncrementRequest.INCREMENT:
      new_value += request.delta()
    elif request.direction() == MemcacheIncrementRequest.DECREMENT:
      new_value = max(new_value-request.delta(), 0)

    new_stored_value = cPickle.dumps([flags, str(new_value)])
    try:
      response = self._memcache.cas(key, new_stored_value, cas_id)
    except (TRANSIENT_ERRORS + (MemcacheClientError,)) as error:
      logging.error(str(error))
      return None

    if not response:
      return

    return new_value

  def _Dynamic_Increment(self, request, response):
    """Implementation of increment for memcache.

    Args:
      request: A MemcacheIncrementRequest protocol buffer.
      response: A MemcacheIncrementResponse protocol buffer.
    """
    new_value = self._Increment(request.name_space(), request)
    if new_value is None:
      raise apiproxy_errors.ApplicationError(
        memcache_service_pb.MemcacheServiceError.UNSPECIFIED_ERROR)
    response.set_new_value(new_value)


  def _Dynamic_BatchIncrement(self, request, response):
    """Implementation of batch increment for memcache.

    Args:
      request: A MemcacheBatchIncrementRequest protocol buffer.
      response: A MemcacheBatchIncrementResponse protocol buffer.
    """
    namespace = request.name_space()
    for request_item in request.item_list():
      new_value = self._Increment(namespace, request_item)
      item = response.add_item()
      if new_value is None:
        item.set_increment_status(MemcacheIncrementResponse.NOT_CHANGED)
      else:
        item.set_increment_status(MemcacheIncrementResponse.OK)
        item.set_new_value(new_value)

  def _Dynamic_FlushAll(self, request, response):
    """Implementation of MemcacheService::FlushAll().

    Args:
      request: A MemcacheFlushRequest.
      response: A MemcacheFlushResponse.
    """
    self._memcache.flush_all()

  def _Dynamic_Stats(self, request, response):
    """Implementation of MemcacheService::Stats().
    
    Args:
      request: A MemcacheStatsRequest.
      response: A MemcacheStatsResponse.
    """
    stats = response.mutable_stats()
    
    num_servers = 0
    hits_total = 0
    misses_total = 0
    byte_hits_total = 0
    items_total = 0
    bytes_total = 0
    time_total = 0
   
    def get_stats_value(stats_dict, key, _type=int):
      """ Gets statisical values and makes sure the key is in the dict. """
      if key not in stats_dict:
        logging.warn("No stats for key '%s'." % key) 
      return _type(stats_dict.get(key, '0'))
   
    for server, server_stats in self._memcache.stats():
      num_servers += 1
      hits_total += get_stats_value(server_stats, 'get_hits')
      misses_total += get_stats_value(server_stats, 'get_misses')
      byte_hits_total += get_stats_value(server_stats, 'bytes_read') 
      items_total += get_stats_value(server_stats, 'curr_items') 
      bytes_total += get_stats_value(server_stats, 'bytes') 
      time_total += get_stats_value(server_stats, 'time', float) 
   
    stats.set_hits(hits_total)
    stats.set_misses(misses_total)
    stats.set_byte_hits(byte_hits_total)
    stats.set_items(items_total)
    stats.set_bytes(bytes_total)
   
    # With the Python 2.7 GAE runtime, it expects all fields here to be ints.
    # Python 2.5 was fine with this being a float, so callers in that runtime
    # may not be expecting an int.
    stats.set_oldest_item_age(int(time.time() - time_total / num_servers))
   
  def _GetKey(self, namespace, key):
    """Used to get the Memcache key. It is encoded because the sdk
    allows special characters but the Memcache client does not.
    
    The key is hashed if it is longer than the max key size. This may lead
    to collisions.
   
    Args:
      namespace: The namespace as provided by the application.
      key: The key as provided by the application.
    Returns:
      A base64 string __{appname}__{namespace}__{key}
    """
    appname = os.environ['APPNAME']
    internal_key = appname + "__" + namespace + "__" + key
    server_key = base64.b64encode(internal_key) 
    if len(server_key) > MAX_KEY_SIZE:
      server_key = hashlib.sha1(server_key).hexdigest() 
    return server_key
