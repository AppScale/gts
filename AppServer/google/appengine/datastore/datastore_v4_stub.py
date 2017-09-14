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




"""Implementation of the datastore_v4 API that forwards to the v3 service."""













from google.appengine.api import apiproxy_stub
from google.appengine.api import apiproxy_stub_map
from google.appengine.datastore import datastore_pbs
from google.appengine.datastore import datastore_v4_pb
from google.appengine.datastore import datastore_v4_validator
from google.appengine.runtime import apiproxy_errors


SERVICE_NAME = 'datastore_v4'
V3_SERVICE_NAME = 'datastore_v3'


class DatastoreV4Stub(apiproxy_stub.APIProxyStub):
  """Implementation of the datastore_v4 API that forwards to the v3 service."""


  THREADSAFE = False

  def __init__(self, app_id):
    apiproxy_stub.APIProxyStub.__init__(self, SERVICE_NAME)
    self.__app_id = app_id
    self.__entity_converter = datastore_pbs.get_entity_converter()
    self.__service_validator = datastore_v4_validator.get_service_validator()

  def _Dynamic_AllocateIds(self, req, resp):
    v3_stub = apiproxy_stub_map.apiproxy.GetStub(V3_SERVICE_NAME)
    try:
      self.__service_validator.validate_allocate_ids_req(req)

      if req.allocate_list():
        v3_refs = self.__entity_converter.v4_to_v3_references(
            req.allocate_list())

        v3_full_refs = v3_stub._AllocateIds(v3_refs)
        resp.allocated_list().extend(
            self.__entity_converter.v3_to_v4_keys(v3_full_refs))
      elif req.reserve_list():
        v3_refs = self.__entity_converter.v4_to_v3_references(
            req.reserve_list())

        v3_stub._AllocateIds(v3_refs)
    except datastore_pbs.InvalidConversionError, e:
      raise apiproxy_errors.ApplicationError(
          datastore_v4_pb.Error.BAD_REQUEST, str(e))
    except datastore_v4_validator.ValidationError, e:
      raise apiproxy_errors.ApplicationError(
          datastore_v4_pb.Error.BAD_REQUEST, str(e))

  def __make_v3_call(self, method, v3_req, v3_resp):
    apiproxy_stub_map.MakeSyncCall(V3_SERVICE_NAME, method, v3_req, v3_resp)
