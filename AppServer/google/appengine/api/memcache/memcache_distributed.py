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
import hashlib
import os
import socket

import six
from pymemcache.exceptions import MemcacheError, MemcacheClientError
from pymemcache.client.hash import HashClient

from google.appengine.api import apiproxy_stub
from google.appengine.api.memcache import MAX_KEY_SIZE, memcache_service_pb
from google.appengine.runtime import apiproxy_errors

MemcacheSetResponse = memcache_service_pb.MemcacheSetResponse
MemcacheSetRequest = memcache_service_pb.MemcacheSetRequest
MemcacheIncrementRequest = memcache_service_pb.MemcacheIncrementRequest
MemcacheIncrementResponse = memcache_service_pb.MemcacheIncrementResponse
MemcacheDeleteResponse = memcache_service_pb.MemcacheDeleteResponse

# Exceptions that indicate a temporary issue with the backend.
TRANSIENT_ERRORS = (MemcacheError, socket.error, socket.timeout)

INVALID_VALUE = memcache_service_pb.MemcacheServiceError.INVALID_VALUE
UNSPECIFIED_ERROR = memcache_service_pb.MemcacheServiceError.UNSPECIFIED_ERROR

# The maximum value that memcached will increment to before wrapping around.
MAX_INCR = 2 ** 64 - 1

# The minimum value that memcached will decrement to.
MIN_DECR = 0

# Separates components of encoded memcached keys.
KEY_DELIMETER = b'\x01'

# Indicates that a memcache key was not hashed.
INTACT_MARKER = b'\x02'

# Indicates that a memcache key was hashed.
HASHED_MARKER = b'\x03'


def encode_key(project_id, namespace, key):
  """ Encodes a key for memcached.

  Args:
    project_id: A string specifying the project ID.
    namespace: A string specifying the namespace.
    key: A bytestring specifying the memcache key.
  Returns:
    A bytestring in the form of <project-id>\x01<namespace>\x01<encoded-key>
  Raises:
    ApplicationError if the key is too long.
  """
  if len(key) > MAX_KEY_SIZE:
    raise apiproxy_errors.ApplicationError(
      INVALID_VALUE, 'The key is too long: {}'.format(key))

  project_id = six.binary_type(project_id)
  namespace = six.binary_type(namespace)
  encoded_key = base64.b64encode(key)
  full_key = KEY_DELIMETER.join(
    [project_id, namespace, INTACT_MARKER + encoded_key])
  if len(full_key) <= MAX_KEY_SIZE:
    return full_key

  # GAE only rejects requests when the key length is too long. Since this
  # implementation's stored key includes a namespace prefix, the key is hashed
  # if necessary to comply with the memcached limit. The length of the key's
  # hex digest + the max project ID size + the max namespace size is still less
  # than the memcached limit.
  hashed_key = hashlib.sha1(key).hexdigest()
  return KEY_DELIMETER.join(
    [project_id, namespace, HASHED_MARKER + hashed_key])


def serializer(key, value_and_flags):
  """ Converts a value passed to pymemcache to one that memcached understands.

  Args:
    key: A bytestring specifying the encoded memcached key.
    value_and_flags: A tuple in the form of (value: bytestring, flags: int).
  Returns:
    A tuple in the form of (value: bytestring, flags: int).
  """
  return value_and_flags[0], value_and_flags[1]


def deserializer(key, value, flags):
  """ Converts a value from memcached to one that pymemcache will return.

  Args:
    key: A bytestring specifying the encoded memcached key.
    value: A bytestring specifying the value.
    flags: An int specifying the flags.
  Returns:
    A tuple in the form of (value: bytestring, flags: int).
  """
  return value, flags


class MemcacheService(apiproxy_stub.APIProxyStub):
  """Python only memcache service.

  This service keeps all data in any external servers running memcached.
  """
  # The memcached default port.
  MEMCACHE_PORT = 11211

  # An AppScale file which has a list of IPs running memcached.
  APPSCALE_MEMCACHE_FILE = "/etc/appscale/memcache_ips"

  def __init__(self, project_id, service_name='memcache'):
    """Initializer.

    Args:
      service_name: Service name expected for all calls.
    """
    super(MemcacheService, self).__init__(service_name)
    self._memcache = None
    self.setupMemcacheClient()
    self._methods = {MemcacheSetRequest.SET: self._memcache.set,
                     MemcacheSetRequest.ADD: self._memcache.add,
                     MemcacheSetRequest.REPLACE: self._memcache.replace,
                     MemcacheSetRequest.CAS: self._memcache.cas}
    self._project_id = project_id

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
    self._memcache = HashClient(
      memcaches, serializer=serializer, deserializer=deserializer,
      connect_timeout=5, timeout=1, use_pooling=True)

    # The GAE API expects return values for all mutate operations.
    for client in six.itervalues(self._memcache.clients):
      client.default_noreply = False

  def _Dynamic_Get(self, request, response):
    """Implementation of gets for memcache.
     
    Args:
      request: A MemcacheGetRequest protocol buffer.
      response: A MemcacheGetResponse protocol buffer.
    """
    # Remove duplicate keys.
    original_keys = {
      encode_key(self._project_id, request.name_space(), key): key
      for key in request.key_list()}

    try:
      backend_response = self._memcache.get_many(
        original_keys.keys(), gets=request.for_cas())
    except MemcacheClientError as error:
      raise apiproxy_errors.ApplicationError(INVALID_VALUE, str(error))
    except TRANSIENT_ERRORS as error:
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'Transient memcache error: {}'.format(error))

    for encoded_key, value_tuple in six.iteritems(backend_response):
      item = response.add_item()
      item.set_key(original_keys[encoded_key])
      if request.for_cas():
        item.set_cas_id(int(value_tuple[1]))
        value_tuple = value_tuple[0]

      item.set_value(value_tuple[0])
      item.set_flags(value_tuple[1])

  def _Dynamic_Set(self, request, response):
    """Implementation of sets for memcache. 

    Args:
      request: A MemcacheSetRequest.
      response: A MemcacheSetResponse.
    """
    namespace = request.name_space()
    if any(item.set_policy() not in self._methods
           for item in request.item_list()):
      raise apiproxy_errors.ApplicationError(
        INVALID_VALUE, 'Unsupported set_policy')

    if not all(item.has_cas_id() for item in request.item_list()
               if item.set_policy() == MemcacheSetRequest.CAS):
      raise apiproxy_errors.ApplicationError(
        INVALID_VALUE, 'All CAS items must have a cas_id')

    for item in request.item_list():
      try:
        encoded_key = encode_key(self._project_id, namespace, item.key())
      except apiproxy_errors.ApplicationError:
        response.add_set_status(MemcacheSetResponse.ERROR)
        continue

      args = {'key': encoded_key,
              'value': (item.value(), item.flags()),
              'expire': int(item.expiration_time())}
      is_cas = item.set_policy() == MemcacheSetRequest.CAS
      if is_cas:
        args['cas'] = six.binary_type(item.cas_id())

      try:
        backend_response = self._methods[item.set_policy()](**args)
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
      encoded_key = encode_key(self._project_id, request.name_space(),
                               item.key())
      try:
        key_existed = self._memcache.delete(encoded_key)
      except MemcacheClientError as error:
        raise apiproxy_errors.ApplicationError(INVALID_VALUE, str(error))
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
      An integer indicating the new value.
    Raises:
      ApplicationError if unable to perform the mutation.
    """
    encoded_key = encode_key(self._project_id, namespace, request.key())
    method = self._memcache.incr
    if request.direction() == MemcacheIncrementRequest.DECREMENT:
      method = self._memcache.decr

    try:
      response = method(encoded_key, request.delta())
    except MemcacheClientError as error:
      raise apiproxy_errors.ApplicationError(INVALID_VALUE, str(error))
    except TRANSIENT_ERRORS as error:
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'Transient memcache error: {}'.format(error))

    if response is None and not request.has_initial_value():
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'Key does not exist')

    if response is not None:
      return response

    # If the key was not present and an initial value was provided, perform
    # the mutation client-side and set the key if it still doesn't exist.
    flags = 0
    if request.has_initial_flags():
      flags = request.initial_flags()

    if request.direction() == MemcacheIncrementRequest.INCREMENT:
      updated_val = request.initial_value() + request.delta()
    else:
      updated_val = request.initial_value() - request.delta()

    updated_val = max(updated_val, 0) % (MAX_INCR + 1)
    try:
      response = self._memcache.add(
        encoded_key, (six.binary_type(updated_val), flags))
    except (TRANSIENT_ERRORS + (MemcacheClientError,)):
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'Unable to set initial value')

    if response is False:
      raise apiproxy_errors.ApplicationError(
        UNSPECIFIED_ERROR, 'Unable to set initial value')

    return updated_val

  def _Dynamic_Increment(self, request, response):
    """Implementation of increment for memcache.

    Args:
      request: A MemcacheIncrementRequest protocol buffer.
      response: A MemcacheIncrementResponse protocol buffer.
    """
    new_value = self._Increment(request.name_space(), request)
    response.set_new_value(new_value)

  def _Dynamic_BatchIncrement(self, request, response):
    """Implementation of batch increment for memcache.

    Args:
      request: A MemcacheBatchIncrementRequest protocol buffer.
      response: A MemcacheBatchIncrementResponse protocol buffer.
    """
    for request_item in request.item_list():
      item = response.add_item()
      try:
        new_value = self._Increment(request.name_space(), request_item)
      except apiproxy_errors.ApplicationError as error:
        if error.application_error == INVALID_VALUE:
          item.set_increment_status(MemcacheIncrementResponse.NOT_CHANGED)
        else:
          item.set_increment_status(MemcacheIncrementResponse.ERROR)

        continue

      item.set_increment_status(MemcacheIncrementResponse.OK)
      item.set_new_value(new_value)

  def _Dynamic_FlushAll(self, request, response):
    """Implementation of MemcacheService::FlushAll().

    Args:
      request: A MemcacheFlushRequest.
      response: A MemcacheFlushResponse.
    """
    # TODO: Prevent a project from clearing another project's namespace.
    self._memcache.flush_all()

  def _Dynamic_Stats(self, request, response):
    """Implementation of MemcacheService::Stats().
    
    Args:
      request: A MemcacheStatsRequest.
      response: A MemcacheStatsResponse.
    """
    # TODO: Gather stats for a project rather than the deployment.
    hits = 0
    misses = 0
    byte_hits = 0
    items = 0
    byte_count = 0
    oldest_item_age = 0
    for server in six.itervalues(self._memcache.clients):
      server_stats = server.stats()
      hits += server_stats.get('get_hits', 0)
      misses += server_stats.get('get_misses', 0)
      byte_hits += server_stats.get('bytes_read', 0)
      items += server_stats.get('curr_items', 0)
      byte_count += server_stats.get('bytes', 0)

      # Using the "age" field may not be correct here. The GAE docs claim this
      # should specify "how long in seconds since the oldest item in the cache
      # was accessed" rather than when it was created.
      item_stats = server.stats('items')
      oldest_server_item = max(age for key, age in six.iteritems(item_stats)
                               if key.endswith(':age'))
      oldest_item_age = max(oldest_item_age, oldest_server_item)

    stats = response.mutable_stats()
    stats.set_hits(hits)
    stats.set_misses(misses)
    stats.set_byte_hits(byte_hits)
    stats.set_items(items)
    stats.set_bytes(byte_count)
    stats.set_oldest_item_age(oldest_item_age)
