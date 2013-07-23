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
"""Stub implementation of the servers service."""

from google.appengine.api import apiproxy_stub
from google.appengine.api import request_info
from google.appengine.api.servers import servers_service_pb
from google.appengine.runtime import apiproxy_errors


class ServersServiceStub(apiproxy_stub.APIProxyStub):

  _ACCEPTS_REQUEST_ID = True

  def __init__(self, request_data):
    super(ServersServiceStub, self).__init__('servers',
                                             request_data=request_data)

  def _GetServerFromRequest(self, request, request_id):
    dispatcher = self.request_data.get_dispatcher()
    if request.has_server():
      server = request.server()
    else:
      server = self.request_data.get_server(request_id)
    return server, dispatcher

  def _GetServerAndVersionFromRequest(self, request, request_id):
    server, dispatcher = self._GetServerFromRequest(request, request_id)
    if request.has_version():
      version = request.version()
    else:
      version = self.request_data.get_version(request_id)
      if version not in dispatcher.get_versions(server):
        version = dispatcher.get_default_version(server)
    return server, version, dispatcher

  def _Dynamic_GetServers(self, request, response, request_id):
    dispatcher = self.request_data.get_dispatcher()
    for server in dispatcher.get_server_names():
      response.add_server(server)

  def _Dynamic_GetVersions(self, request, response, request_id):
    server, dispatcher = self._GetServerFromRequest(request, request_id)
    try:
      for version in dispatcher.get_versions(server):
        response.add_version(version)
    except request_info.ServerDoesNotExistError:
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.INVALID_SERVER)

  def _Dynamic_GetDefaultVersion(self, request, response, request_id):
    server, dispatcher = self._GetServerFromRequest(request, request_id)
    try:
      response.set_version(dispatcher.get_default_version(server))
    except request_info.ServerDoesNotExistError:
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.INVALID_SERVER)

  def _Dynamic_GetNumInstances(self, request, response, request_id):
    try:
      server, version, dispatcher = self._GetServerAndVersionFromRequest(
          request, request_id)
      response.set_instances(dispatcher.get_num_instances(server, version))
    except (request_info.ServerDoesNotExistError,
            request_info.VersionDoesNotExistError,
            request_info.NotSupportedWithAutoScalingError):
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.INVALID_VERSION)

  def _Dynamic_SetNumInstances(self, request, response, request_id):
    try:
      server, version, dispatcher = self._GetServerAndVersionFromRequest(
          request, request_id)
      dispatcher.set_num_instances(server, version, request.instances())
    except (request_info.ServerDoesNotExistError,
            request_info.VersionDoesNotExistError,
            request_info.NotSupportedWithAutoScalingError):
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.INVALID_VERSION)

  def _Dynamic_StartServer(self, request, response, request_id):
    server = request.server()
    version = request.version()
    dispatcher = self.request_data.get_dispatcher()
    try:
      dispatcher.start_server(server, version)
    except (request_info.ServerDoesNotExistError,
            request_info.VersionDoesNotExistError,
            request_info.NotSupportedWithAutoScalingError):
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.INVALID_VERSION)
    except request_info.ServerAlreadyStartedError:
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.UNEXPECTED_STATE)

  def _Dynamic_StopServer(self, request, response, request_id):
    try:
      server, version, dispatcher = self._GetServerAndVersionFromRequest(
          request, request_id)
      dispatcher.stop_server(server, version)
    except (request_info.ServerDoesNotExistError,
            request_info.VersionDoesNotExistError,
            request_info.NotSupportedWithAutoScalingError):
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.INVALID_VERSION)
    except request_info.ServerAlreadyStoppedError:
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.UNEXPECTED_STATE)

  def _Dynamic_GetHostname(self, request, response, request_id):
    if request.has_instance():
      instance = request.instance()
    else:
      instance = None
    try:
      server, version, dispatcher = self._GetServerAndVersionFromRequest(
          request, request_id)
      response.set_hostname(dispatcher.get_hostname(server, version, instance))
    except (request_info.ServerDoesNotExistError,
            request_info.VersionDoesNotExistError):
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.INVALID_SERVER)
    except request_info.InvalidInstanceIdError:
      raise apiproxy_errors.ApplicationError(
          servers_service_pb.ServersServiceError.INVALID_INSTANCES)
