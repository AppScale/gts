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
Uses the python-memcached library to interface with memcached.
"""
import base64
import cPickle
import logging
import memcache
import os
import time

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

class MemcacheService(apiproxy_stub.APIProxyStub):
  """Python only memcache service.

  This service keeps all data in any external servers running memcached.
  """
  # The memcached default port.
  MEMCACHE_PORT = "11211"

  # An AppScale file which has a list of IPs running memcached.
  APPSCALE_MEMCACHE_FILE = "/etc/appscale/memcache_ips"

  # The minimum frequency by which memcache clients will update their list of
  # clients that they connect to (which can change if AppScale scales up or
  # down).
  UPDATE_WINDOW = 60  # seconds

  def __init__(self, gettime=time.time, service_name='memcache'):
    """Initializer.

    Args:
      gettime: time.time()-like function used for testing.
      service_name: Service name expected for all calls.
    """
    super(MemcacheService, self).__init__(service_name)
    self._gettime = gettime
    self._memcache = None
    self.setupMemcacheClient()

  def setupMemcacheClient(self):
    """ Sets up the memcache client. """
    memcache_file = open(self.APPSCALE_MEMCACHE_FILE, "r")
    all_ips = memcache_file.read().split("\n")
    memcache_file.close()

    memcaches = [ip + ":" + self.MEMCACHE_PORT for ip in all_ips if ip != '']

    self._memcache = memcache.Client(memcaches, debug=0)

  def _Dynamic_Get(self, request, response):
    """Implementation of gets for memcache.
     
    Args:
      request: A MemcacheGetRequest protocol buffer.
      response: A MemcacheGetResponse protocol buffer.
    """
    for key in set(request.key_list()):
      internal_key = self._GetKey(request.name_space(), key)
      value = self._memcache.get(internal_key)
      logging.debug("GET: Key: %s value: %s" % (internal_key, value))
      if value is None:
        continue
      flags = 0
      stored_flags, cas_id, stored_value = cPickle.loads(value)
      flags |= stored_flags
      item = response.add_item()
      item.set_key(key)
      item.set_value(stored_value)
      item.set_flags(flags)
      if request.for_cas():
        item.set_cas_id(cas_id)

  def _Dynamic_Set(self, request, response):
    """Implementation of sets for memcache. 

    Args:
      request: A MemcacheSetRequest.
      response: A MemcacheSetResponse.
    """
    for item in request.item_list():
      key = self._GetKey(request.name_space(), item.key())
      set_policy = item.set_policy()
      old_entry = self._memcache.get(key)
      cas_id = 0
      if old_entry:
        _, cas_id, _ = cPickle.loads(old_entry)
      set_status = MemcacheSetResponse.NOT_STORED
      logging.debug("Key: %s value: %s" % (key, item.value()))

      if ((set_policy == MemcacheSetRequest.SET) or
        (set_policy == MemcacheSetRequest.ADD and old_entry is None) or
        (set_policy == MemcacheSetRequest.REPLACE and
        old_entry is not None)):

        if (old_entry is None or set_policy == MemcacheSetRequest.SET):
          set_status = MemcacheSetResponse.STORED

      elif (set_policy == MemcacheSetRequest.CAS and item.for_cas() and
        item.has_cas_id()):
        if old_entry is None:
          set_status = MemcacheSetResponse.NOT_STORED
        elif cas_id != item.cas_id():
          set_status = MemcacheSetResponse.EXISTS
        else:
          set_status = MemcacheSetResponse.STORED

      if (set_status == MemcacheSetResponse.STORED
        or set_policy == MemcacheSetRequest.REPLACE):

        set_value = cPickle.dumps(
          [item.flags(), cas_id + 1, item.value()])
        if set_policy == MemcacheSetRequest.REPLACE:
          self._memcache.replace(key, set_value)
        else:
          self._memcache.set(key, set_value, item.expiration_time())

      response.add_set_status(set_status)

  def _Dynamic_Delete(self, request, response):
    """Implementation of delete in memcache.

    Args:
      request: A MemcacheDeleteRequest protocol buffer.
      response: A MemcacheDeleteResponse protocol buffer.
    """
    for item in request.item_list():
      key = self._GetKey(request.name_space(), item.key())
      logging.debug("Memcache delete: Key: %s" % key)
      entry = self._memcache.get(key)
      delete_status = MemcacheDeleteResponse.DELETED

      if entry is None:
        delete_status = MemcacheDeleteResponse.NOT_FOUND
      else:
        self._memcache.delete(key)

      response.add_delete_status(delete_status)

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

    cas_id = 0

    key = self._GetKey(namespace, request.key())
    value = self._memcache.get(key)
    if value is None:
      if not request.has_initial_value():
        return None
      flags, cas_id, stored_value = (
        TYPE_INT, cas_id, str(request.initial_value()))
    else:
      flags, cas_id, stored_value = cPickle.loads(value)

    if flags == TYPE_INT:
      new_value = int(stored_value)
    elif flags == TYPE_LONG:
      new_value = long(stored_value)

    if request.direction() == MemcacheIncrementRequest.INCREMENT:
      new_value += request.delta()
    elif request.direction() == MemcacheIncrementRequest.DECREMENT:
      new_value -= request.delta()

    new_stored_value = cPickle.dumps([flags, cas_id + 1, str(new_value)])
    try:
      self._memcache.cas(key, new_stored_value)
    except Exception, e:
      logging.error(str(e))
      return None

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
   
    for server, server_stats in self._memcache.get_stats():
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
   
    stats.set_oldest_item_age(time.time() - time_total / num_servers)
   
  def _GetKey(self, namespace, key):
    """Used to get the Memcache key. It is encoded because the sdk
    allows special characters but the Memcache client does not.
       
    Args:
      namespace: The namespace as provided by the application.
      key: The key as provided by the application.
    Returns:
      A base64 string __{appname}__{namespace}__{key}
    """
    appname = os.environ['APPNAME']
    internal_key = appname + "__" + namespace + "__" + key
    return base64.b64encode(internal_key) 
