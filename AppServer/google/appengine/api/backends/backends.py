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



"""Backends API.

This API provides utility methods for working with backends.
"""









import os
import re

from google.appengine.api import app_identity

class Error(Exception):
  """Base class for exceptions in this module."""

class DefaultHostnameError(Error):
  """Raised if no default hostname is set in the environment."""

class InvalidBackendError(Error):
  """Raised if an invalid backend was provided."""
  pass

class InvalidInstanceError(Error):
  """Raised if an invalid instance was provided."""
  pass


def get_backend():
  """Get the name of the backend handling this request.

  Returns:
    string: The current backend, or None if this is not a backend.
  """
  return os.environ.get('BACKEND_ID', None)


def get_instance():
  """Get the instance number of the backend handling this request.

  Returns:
    int: The instance, in [0, instances-1], or None if this is not a backend.
  """
  instance = os.environ.get('INSTANCE_ID', None)
  if instance is not None:
    return int(instance)
  else:
    return None


def get_url(backend=None, instance=None, protocol='http'):
  """Returns a URL pointing to a backend or backend instance.

  This method works in both production and development environments.

  Args:
    backend: The name of the backend. If None, the current backend will be used.

    instance: An optoinal instance number. If provided, the URL will target
      the specific instance.  If absent, the URL will point to a load-balancing
      hostname for the backend.

    protocol: The protocol to use (default='http').

  Raises:
    InvalidBackendError
    InvalidInstanceError

  Returns:
    The URL of the backend or backend instance.
  """
  if backend is None:
    backend = get_backend()


  if _is_dev_environment():
    return _get_dev_url(backend, instance)


  hostname = get_hostname(backend, instance)
  return '%s://%s' % (protocol, hostname)


def get_hostname(backend=None, instance=None):
  """Returns the hostname for a backend or backend instance.

  Args:
    backend: The name of the backend. If None, the current backend will be used.

    instance: An optoinal instance number. If provided, the hostname will
      represent the specific instance. If absent, the hostname will represent
      the backend as a whole.

  Raises:
    InvalidBackendError
    InvalidInstanceError

  Returns:
    The hostname of the backend or backend instance.
  """
  if backend is None:
    backend = get_backend()


  if not isinstance(backend, (str, unicode)):
    raise InvalidBackendError('Invalid backend: %s' % backend)

  if not re.match('^[a-zA-Z0-9\-]+$', backend):
    raise InvalidBackendError('Invalid backend: %s' % backend)


  if instance is not None:
    try:
      instance = int(instance)
    except ValueError:
      raise InvalidInstanceError('instance must be an integer.')


  if _is_dev_environment():
    return _get_dev_hostname(backend, instance)

  hostname = app_identity.get_default_version_hostname()
  if hostname is None:
    raise DefaultHostnameError

  hostname = '%s.%s' % (backend, hostname)
  if instance is not None:
    hostname = '%d.%s' % (instance, hostname)
  return hostname


def _is_dev_environment():
  """Indicates whether this code is being run in the development environment."""
  return os.environ.get('SERVER_SOFTWARE', '').startswith('Development')


def _get_dev_url(backend, instance=None):
  """Returns the url of a backend [instance] in the dev_appserver.

  Args:
    backend: The name of the backend.
    instance: The backend instance number, in [0, instances-1].

  Returns:
    The url of the backend.
  """
  return 'http://%s' % _get_dev_hostname(backend, instance)


def _get_dev_hostname(backend, instance=None):
  """Returns the hostname of a backend [instance] in the dev_appserver.

  Args:
    backend: The name of the backend.
    instance: The backend instance number, in [0, instances-1].

  Returns:
    The hostname of the backend.
  """

  port = _get_dev_port(backend, instance)
  if not port:
    error = 'Backend not found: %s' % backend
    if instance is not None:
      error = '%s.%d' % (error, instance)
    raise InvalidBackendError(error)

  host = os.environ.get('SERVER_NAME', 'localhost')
  return '%s:%d' % (host, port)


def _get_dev_port(backend, instance=None):
  """Returns the port for a backend [instance] in the dev_appserver.

  Args:
    backend: The name of the backend.
    instance: The backend instance (optional).

  Returns:
    int: The backend port.
  """
  port = os.environ.get(_get_dev_port_var(backend, instance), None)
  if port:
    return int(port)
  else:
    return None


def _set_dev_port(port, backend, instance=None, env=os.environ):
  """Sets the port for a backend [instance] in the dev_appserver.

  Args:
    port: The port.
    backend: The name of the backend.
    instance: The backend instance (optional).
    env: The environment in which to set the port.
  """
  env[_get_dev_port_var(backend, instance)] = str(port)


def _get_dev_port_var(backend, instance=None):
  """Return the environment variable for a backend port.

  Backend ports are stored at GET_PORT_<backend> for backends
  and GET_PORT_<backend>.<instance> for individual instances.

  Args:
    backend: The name of the backend.
    instance: The backend instance (optional).

  Returns:
    string: The environment variable where the backend port is stored.
  """
  port_var = 'BACKEND_PORT.%s' % str(backend).lower()
  if instance is not None:
    port_var = '%s.%d' % (port_var, instance)
  return port_var
