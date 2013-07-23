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
"""Exposes methods to control servers and versions of an app."""

__all__ = [
            'Error',
            'InvalidServerError',
            'InvalidVersionError',
            'InvalidInstancesError',
            'UnexpectedStateError',
            'TransientError',

            'get_current_server_name',
            'get_current_version_name',
            'get_current_instance_id',
            'get_servers',
            'get_versions',
            'get_default_version',
            'get_num_instances',
            'set_num_instances',
            'start_server',
            'stop_server',
            'get_hostname',
           ]


import os

from google.appengine.api import apiproxy_stub_map
from google.appengine.api.servers import servers_service_pb
from google.appengine.runtime import apiproxy_errors


class Error(Exception):
  """Base-class for errors in this module."""


class InvalidServerError(Error):
  """The given server is not known to the system."""


class InvalidVersionError(Error):
  """The given server version is not known to the system."""


class InvalidInstancesError(Error):
  """The given instances value is not valid."""


class UnexpectedStateError(Error):
  """An unexpected current state was found when starting/stopping a server."""


class TransientError(Error):
  """A transient error was encountered, please retry the operation."""


def _split_version_id(full_version_id):
  """Return server and version.

  Args:
    full_version_id: Value in the format that is set in the 'CURRENT_VERSION_ID'
      environment var.  I.e. 'server:server_version.minor_version'.

  Returns:
    (server, server_version) tuple, or (None, server_version) if this is the
    default server.
  """


  server_and_version = full_version_id.split('.')[0]
  result = server_and_version.split(':')
  if len(result) == 2:
    return (result[0], result[1])
  else:
    return (None, result[0])


def get_current_server_name():
  """Returns the server name of the current instance.

  If this is version "v1" of server "server5" for app "my-app", this function
  will return "server5".
  """
  server = _split_version_id(os.environ['CURRENT_VERSION_ID'])[0]
  if not server:


    return 'default'
  return server


def get_current_version_name():
  """Returns the version of the current instance.

  If this is version "v1" of server "server5" for app "my-app", this function
  will return "v1".
  """

  return _split_version_id(os.environ['CURRENT_VERSION_ID'])[1]


def get_current_instance_id():
  """Returns the id of the current instance.

  If this is instance 2 of version "v1" of server "server5" for app "my-app",
  this function will return "2".

  This is only valid for manually-scheduled servers, None will be returned for
  automatically-scaled servers.

  Returns:
    String containing the id of the instance, or None if this is not a
    manually-scaled server.
  """
  return os.environ.get('INSTANCE_ID', None)



def get_servers():
  """Returns a list of all servers for the application.

  Returns:
    List of strings containing the names of servers associated with this
      application.  The 'default' server will be included if it exists, as will
      the name of the server that is associated with the instance that calls
      this function.
  """
  req = servers_service_pb.GetServersRequest()
  resp = servers_service_pb.GetServersResponse()
  apiproxy_stub_map.MakeSyncCall('servers', 'GetServers', req, resp)


  return list(resp.server_list())


def get_versions(server=None):
  """Returns a list of versions for a given server.

  Args:
    server: Server to retrieve version for, if None then the current server will
      be used.

  Returns:
    List of strings containing the names of versions associated with the server.
    The current version will also be included in this list.

  Raises:
    InvalidServerError if the given server isn't valid, TransientError if there
    is an issue fetching the information.
  """
  req = servers_service_pb.GetVersionsRequest()
  if server:
    req.set_server(server)
  resp = servers_service_pb.GetVersionsResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('servers', 'GetVersions', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_SERVER):
      raise InvalidServerError()
    elif (e.application_error ==
          servers_service_pb.ServersServiceError.TRANSIENT_ERROR):
      raise TransientError()
    else:
      raise Error()



  return list(resp.version_list())


def get_default_version(server=None):
  """Returns the name of the default version for the server.

  Args:
    server: Server to retrieve the default version for, if None then the current
      server will be used.

  Returns:
    String containing the name of the default version of the server.

  Raises:
    InvalidServerError if the given server is not valid, InvalidVersionError if
    no default version could be found.
  """
  req = servers_service_pb.GetDefaultVersionRequest()
  if server:
    req.set_server(server)
  resp = servers_service_pb.GetDefaultVersionResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('servers', 'GetDefaultVersion', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_SERVER):
      raise InvalidServerError()
    if (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    else:
      raise Error()

  return resp.version()


def get_num_instances(server=None, version=None):
  """Return the number of instances that are set for the given server version.

  This is only valid for fixed servers, an error will be raised for
  automatically-scheduled servers.  Support for automatically-servers may be
  supported in the future.

  Args:
    server: String containing the name of the server to fetch this info for, if
      None the server of the current instance will be used.
    version: String containing the name of the version to fetch this info for,
      if None the version of the current instance will be used.  If that version
      does not exist in the other server, then an InvalidVersionError is raised.

  Raises:
    InvalidVersionError on invalid input.
  """
  req = servers_service_pb.GetNumInstancesRequest()
  if server:
    req.set_server(server)
  if version:
    req.set_version(version)
  resp = servers_service_pb.GetNumInstancesResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('servers', 'GetNumInstances', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    else:
      raise Error()

  return resp.instances()


def set_num_instances(instances, server=None, version=None):
  """Sets the number of instances on the server and version.

  Args:
    instances: The number of instances to set.
    server: The server to set the number of instances for, if None the current
      server will be used.
    version: The version set the number of instances for, if None the current
      version will be used.

  Raises:
    InvalidVersionError if the given server version isn't valid, TransientError
    if there is an issue persisting the change.
    TypeError if the given instances type is invalid.
  """
  if not isinstance(instances, (long, int)):
    raise TypeError("'instances' arg must be of type long or int.")
  req = servers_service_pb.SetNumInstancesRequest()
  req.set_instances(instances)
  if server:
    req.set_server(server)
  if version:
    req.set_version(version)
  resp = servers_service_pb.SetNumInstancesResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('servers', 'SetNumInstances', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    elif (e.application_error ==
          servers_service_pb.ServersServiceError.TRANSIENT_ERROR):
      raise TransientError()
    else:
      raise Error()


def start_server(server, version):
  """Start all instances for the given version of the server.

  Args:
    server: String containing the name of the server to affect.
    version: String containing the name of the version of the server to start.

  Raises:
    InvalidVersionError if the given server version is invalid.
    UnexpectedStateError if the server is already started, or cannot be started.
    TransientError if there is a problem persisting the change.
  """
  req = servers_service_pb.StartServerRequest()
  req.set_server(server)
  req.set_version(version)
  resp = servers_service_pb.StartServerResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('servers', 'StartServer', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    elif (e.application_error ==
        servers_service_pb.ServersServiceError.UNEXPECTED_STATE):
      raise UnexpectedStateError()
    elif (e.application_error ==
          servers_service_pb.ServersServiceError.TRANSIENT_ERROR):
      raise TransientError()
    else:
      raise Error()


def stop_server(server=None, version=None):
  """Stops all instances for the given version of the server.

  Args:
    server: The server to affect, if None the current server is used.
    version: The version of the given server to affect, if None the current
      version is used.

  Raises:
    InvalidVersionError if the given server version is invalid.
    UnexpectedStateError if the server is already stopped, or cannot be stopped.
    TransientError if there is a problem persisting the change.
  """
  req = servers_service_pb.StopServerRequest()
  if server:
    req.set_server(server)
  if version:
    req.set_version(version)
  resp = servers_service_pb.StopServerResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('servers', 'StopServer', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    elif (e.application_error ==
        servers_service_pb.ServersServiceError.UNEXPECTED_STATE):
      raise UnexpectedStateError()
    elif (e.application_error ==
          servers_service_pb.ServersServiceError.TRANSIENT_ERROR):
      raise TransientError()
    else:
      raise Error()


def get_hostname(server=None, version=None, instance=None):
  """Returns a hostname to use to contact the server.

  Args:
    server: Name of server, if None, take server of the current instance.
    version: Name of version, if version is None then either use the version of
      the current instance if that version exists for the target server,
      otherwise use the default version of the target server.
    instance: Instance to construct a hostname for, if instance is None, a
      loadbalanced hostname for the server will be returned.  If the target
      server is not a fixed server, then instance is not considered valid.

  Returns:
    A valid canonical hostname that can be used to communicate with the given
    server/version/instance.  E.g. 0.v1.server5.myapp.appspot.com

  Raises:
    InvalidServerError if the given serverversion is invalid.
    InvalidInstancesError if the given instance value is invalid.
    TypeError if the given instance type is invalid.
  """
  req = servers_service_pb.GetHostnameRequest()
  if server:
    req.set_server(server)
  if version:
    req.set_version(version)
  if instance:
    if not isinstance(instance, (basestring, long, int)):
      raise TypeError(
          "'instance' arg must be of type basestring, long or int.")
    req.set_instance('%s' % instance)
  resp = servers_service_pb.GetHostnameResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('servers', 'GetHostname', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_SERVER):
      raise InvalidServerError()
    elif (e.application_error ==
        servers_service_pb.ServersServiceError.INVALID_INSTANCES):
      raise InvalidInstancesError()
    else:
      raise Error()

  return resp.hostname()
