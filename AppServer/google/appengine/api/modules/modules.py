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
"""Exposes methods to control modules and versions of an app."""

__all__ = [
            'Error',
            'InvalidModuleError',
            'InvalidVersionError',
            'InvalidInstancesError',
            'UnexpectedStateError',
            'TransientError',

            'get_current_module_name',
            'get_current_version_name',
            'get_current_instance_id',
            'get_modules',
            'get_versions',
            'get_default_version',
            'get_num_instances',
            'set_num_instances',
            'start_module',
            'stop_module',
            'get_hostname',
           ]


import logging
import os

from google.appengine.api import apiproxy_stub_map
from google.appengine.api.modules import modules_service_pb
from google.appengine.runtime import apiproxy_errors


class Error(Exception):
  """Base-class for errors in this module."""


class InvalidModuleError(Error):
  """The given module is not known to the system."""


class InvalidVersionError(Error):
  """The given module version is not known to the system."""


class InvalidInstancesError(Error):
  """The given instances value is not valid."""


class UnexpectedStateError(Error):
  """An unexpected current state was found when starting/stopping a module."""


class TransientError(Error):
  """A transient error was encountered, please retry the operation."""


def _split_version_id(full_version_id):
  """Return module and version.

  Args:
    full_version_id: Value in the format that is set in the 'CURRENT_VERSION_ID'
      environment var.  I.e. 'module:module_version.minor_version'.

  Returns:
    (module, module_version) tuple, or (None, module_version) if this is the
    default module.
  """


  module_and_version = full_version_id.split('.')[0]
  result = module_and_version.split(':')
  if len(result) == 2:
    return (result[0], result[1])
  else:
    return (None, result[0])


def get_current_module_name():
  """Returns the module name of the current instance.

  If this is version "v1" of module "module5" for app "my-app", this function
  will return "module5".
  """
  return os.environ['CURRENT_MODULE_ID']


def get_current_version_name():
  """Returns the version of the current instance.

  If this is version "v1" of module "module5" for app "my-app", this function
  will return "v1".
  """

  return os.environ['CURRENT_VERSION_ID'].split('.')[0]


def get_current_instance_id():
  """Returns the id of the current instance.

  If this is instance 2 of version "v1" of module "module5" for app "my-app",
  this function will return "2".

  This is only valid for manually-scheduled modules, None will be returned for
  automatically-scaled modules.

  Returns:
    String containing the id of the instance, or None if this is not a
    manually-scaled module.
  """
  return os.environ.get('INSTANCE_ID', None)


def _GetRpc():
  return apiproxy_stub_map.UserRPC('modules')


def _MakeAsyncCall(method, request, response, get_result_hook):
  rpc = _GetRpc()
  rpc.make_call(method, request, response, get_result_hook)
  return rpc


_MODULE_SERVICE_ERROR_MAP = {
    modules_service_pb.ModulesServiceError.INVALID_INSTANCES:
        InvalidInstancesError,
    modules_service_pb.ModulesServiceError.INVALID_MODULE:
        InvalidModuleError,
    modules_service_pb.ModulesServiceError.INVALID_VERSION:
        InvalidVersionError,
    modules_service_pb.ModulesServiceError.TRANSIENT_ERROR:
        TransientError,
    modules_service_pb.ModulesServiceError.UNEXPECTED_STATE:
        UnexpectedStateError
}


def _CheckAsyncResult(rpc,
                      expected_application_errors,
                      ignored_application_errors):
  try:
    rpc.check_success()
  except apiproxy_errors.ApplicationError, e:
    if e.application_error in ignored_application_errors:
      logging.info(ignored_application_errors.get(e.application_error))
      return
    if e.application_error in expected_application_errors:
      mapped_error = _MODULE_SERVICE_ERROR_MAP.get(e.application_error)
      if mapped_error:
        raise mapped_error()
    raise Error(e)


def get_modules():
  """Returns a list of all modules for the application.

  Returns:
    List of strings containing the names of modules associated with this
      application.  The 'default' module will be included if it exists, as will
      the name of the module that is associated with the instance that calls
      this function.
  """
  req = modules_service_pb.GetModulesRequest()
  resp = modules_service_pb.GetModulesResponse()
  apiproxy_stub_map.MakeSyncCall('modules', 'GetModules', req, resp)


  return list(resp.module_list())


def get_versions(module=None):
  """Returns a list of versions for a given module.

  Args:
    module: Module to retrieve version for, if None then the current module will
      be used.

  Returns:
    List of strings containing the names of versions associated with the module.
    The current version will also be included in this list.

  Raises:
    InvalidModuleError if the given module isn't valid, TransientError if there
    is an issue fetching the information.
  """
  req = modules_service_pb.GetVersionsRequest()
  if module:
    req.set_module(module)
  resp = modules_service_pb.GetVersionsResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('modules', 'GetVersions', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_MODULE):
      raise InvalidModuleError()
    elif (e.application_error ==
          modules_service_pb.ModulesServiceError.TRANSIENT_ERROR):
      raise TransientError()
    else:
      raise Error()



  return list(resp.version_list())


def get_default_version(module=None):
  """Returns the name of the default version for the module.

  Args:
    module: Module to retrieve the default version for, if None then the current
      module will be used.

  Returns:
    String containing the name of the default version of the module.

  Raises:
    InvalidModuleError if the given module is not valid, InvalidVersionError if
    no default version could be found.
  """
  req = modules_service_pb.GetDefaultVersionRequest()
  if module:
    req.set_module(module)
  resp = modules_service_pb.GetDefaultVersionResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('modules', 'GetDefaultVersion', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_MODULE):
      raise InvalidModuleError()
    if (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    else:
      raise Error()

  return resp.version()


def get_num_instances(module=None, version=None):
  """Return the number of instances that are set for the given module version.

  This is only valid for fixed modules, an error will be raised for
  automatically-scaled modules.  Support for automatically-scaled modules may be
  supported in the future.

  Args:
    module: String containing the name of the module to fetch this info for, if
      None the module of the current instance will be used.
    version: String containing the name of the version to fetch this info for,
      if None the version of the current instance will be used.  If that version
      does not exist in the other module, then an InvalidVersionError is raised.

  Raises:
    InvalidVersionError on invalid input.
  """
  req = modules_service_pb.GetNumInstancesRequest()
  if module:
    req.set_module(module)
  if version:
    req.set_version(version)
  resp = modules_service_pb.GetNumInstancesResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('modules', 'GetNumInstances', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    else:
      raise Error()

  return resp.instances()


def set_num_instances(instances, module=None, version=None):
  """Sets the number of instances on the module and version.

  Args:
    instances: The number of instances to set.
    module: The module to set the number of instances for, if None the current
      module will be used.
    version: The version set the number of instances for, if None the current
      version will be used.

  Raises:
    InvalidVersionError if the given module version isn't valid, TransientError
    if there is an issue persisting the change.
    TypeError if the given instances type is invalid.
  """
  if not isinstance(instances, (long, int)):
    raise TypeError("'instances' arg must be of type long or int.")
  req = modules_service_pb.SetNumInstancesRequest()
  req.set_instances(instances)
  if module:
    req.set_module(module)
  if version:
    req.set_version(version)
  resp = modules_service_pb.SetNumInstancesResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('modules', 'SetNumInstances', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    elif (e.application_error ==
          modules_service_pb.ModulesServiceError.TRANSIENT_ERROR):
      raise TransientError()
    else:
      raise Error()


def start_module(module, version):
  """Start all instances for the given version of the module.

  Args:
    module: String containing the name of the module to affect.
    version: String containing the name of the version of the module to start.

  Raises:
    InvalidVersionError if the given module version is invalid.
    UnexpectedStateError if the module is already started, or cannot be started.
    TransientError if there is a problem persisting the change.
  """
  req = modules_service_pb.StartModuleRequest()
  req.set_module(module)
  req.set_version(version)
  resp = modules_service_pb.StartModuleResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('modules', 'StartModule', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    elif (e.application_error ==
        modules_service_pb.ModulesServiceError.UNEXPECTED_STATE):
      raise UnexpectedStateError()
    elif (e.application_error ==
          modules_service_pb.ModulesServiceError.TRANSIENT_ERROR):
      raise TransientError()
    else:
      raise Error()


def stop_module(module=None, version=None):
  """Stops all instances for the given version of the module.

  Args:
    module: The module to affect, if None the current module is used.
    version: The version of the given module to affect, if None the current
      version is used.

  Raises:
    InvalidVersionError if the given module version is invalid.
    UnexpectedStateError if the module is already stopped, or cannot be stopped.
    TransientError if there is a problem persisting the change.
  """
  req = modules_service_pb.StopModuleRequest()
  if module:
    req.set_module(module)
  if version:
    req.set_version(version)
  resp = modules_service_pb.StopModuleResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('modules', 'StopModule', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_VERSION):
      raise InvalidVersionError()
    elif (e.application_error ==
        modules_service_pb.ModulesServiceError.UNEXPECTED_STATE):
      raise UnexpectedStateError()
    elif (e.application_error ==
          modules_service_pb.ModulesServiceError.TRANSIENT_ERROR):
      raise TransientError()
    else:
      raise Error()


def get_hostname(module=None, version=None, instance=None):
  """Returns a hostname to use to contact the module.

  Args:
    module: Name of module, if None, take module of the current instance.
    version: Name of version, if version is None then either use the version of
      the current instance if that version exists for the target module,
      otherwise use the default version of the target module.
    instance: Instance to construct a hostname for, if instance is None, a
      loadbalanced hostname for the module will be returned.  If the target
      module is not a fixed module, then instance is not considered valid.

  Returns:
    A valid canonical hostname that can be used to communicate with the given
    module/version/instance.  E.g. 0.v1.module5.myapp.appspot.com

  Raises:
    InvalidModuleError if the given moduleversion is invalid.
    InvalidInstancesError if the given instance value is invalid.
    TypeError if the given instance type is invalid.
  """
  req = modules_service_pb.GetHostnameRequest()
  if module:
    req.set_module(module)
  if version:
    req.set_version(version)
  if instance:
    if not isinstance(instance, (basestring, long, int)):
      raise TypeError(
          "'instance' arg must be of type basestring, long or int.")
    req.set_instance('%s' % instance)
  resp = modules_service_pb.GetHostnameResponse()
  try:
    apiproxy_stub_map.MakeSyncCall('modules', 'GetHostname', req, resp)
  except apiproxy_errors.ApplicationError, e:
    if (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_MODULE):
      raise InvalidModuleError()
    elif (e.application_error ==
        modules_service_pb.ModulesServiceError.INVALID_INSTANCES):
      raise InvalidInstancesError()
    else:
      raise Error()

  return resp.hostname()
