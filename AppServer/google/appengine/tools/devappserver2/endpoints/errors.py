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
"""Errors and exceptions used in the local Cloud Endpoints server."""




import json


__all__ = ['EnumRejectionError',
           'RequestRejectionError']

_INVALID_ENUM_TEMPLATE = 'Invalid string value: %r. Allowed values: %r'


class RequestRejectionError(Exception):
  """Base class for rejected requests.

  To be raised when parsing the request values and comparing them against the
  generated discovery document.
  """

  def message(self): raise NotImplementedError
  def errors(self): raise NotImplementedError

  def to_json(self):
    """JSON string representing the rejected value.

    Calling this will fail on the base class since it relies on Message and
    Errors being implemented on the class. It is up to a subclass to implement
    these methods.

    Returns:
      JSON string representing the rejected value.
    """
    return json.dumps({
        'error': {
            'errors': self.errors(),
            'code': 400,
            'message': self.message(),
        },
    })


class EnumRejectionError(RequestRejectionError):
  """Custom request rejection exception for enum values."""

  def __init__(self, parameter_name, value, allowed_values):
    """Constructor for EnumRejectionError.

    Args:
      parameter_name: String; the name of the enum parameter which had a value
        rejected.
      value: The actual value passed in for the enum. Usually string.
      allowed_values: List of strings allowed for the enum.
    """
    super(EnumRejectionError, self).__init__()
    self.parameter_name = parameter_name
    self.value = value
    self.allowed_values = allowed_values

  def message(self):
    """A descriptive message describing the error."""
    return _INVALID_ENUM_TEMPLATE % (self.value, self.allowed_values)


  def errors(self):
    """A list containing the errors associated with the rejection.

    Intended to mimic those returned from an API in production in Google's API
    infrastructure.

    Returns:
      A list with a single element that is a dictionary containing the error
        information.
    """
    return [
        {
            'domain': 'global',
            'reason': 'invalidParameter',
            'message': self.message(),
            'locationType': 'parameter',
            'location': self.parameter_name,
        },
    ]
