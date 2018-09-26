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
"""Error handling and exceptions used in the local Cloud Endpoints server."""




import httplib
import json
import logging


__all__ = ['BackendError',
           'EnumRejectionError',
           'RequestError',
           'RequestRejectionError']

_INVALID_ENUM_TEMPLATE = 'Invalid string value: %r. Allowed values: %r'


class RequestError(Exception):
  """Base class for errors that happen while processing a request."""

  # Most error reasons are a straightforward conversion from the HTTP response
  # string to a more compact name.  But there are exceptions.  This maps
  # the exceptions.
  __ERROR_REASON_EXCEPTIONS = {
      httplib.OK: 'ok',
      httplib.PAYMENT_REQUIRED: 'user402',
      httplib.METHOD_NOT_ALLOWED: 'httpMethodNotAllowed',
      httplib.GONE: 'deleted',
      httplib.PRECONDITION_FAILED: 'conditionNotMet',
      httplib.REQUEST_ENTITY_TOO_LARGE: 'uploadTooLarge',
      httplib.INTERNAL_SERVER_ERROR: 'internalError',
      httplib.SERVICE_UNAVAILABLE: 'backendError',
      }

  def http_status(self):
    """HTTP status code and message associated with this error.

    Subclasses must implement this, returning a string with the status
    code number and status text for the error.

    Example: "400 Bad Request"

    Raises:
      NotImplementedError: Subclasses must override this function.
    """
    raise NotImplementedError

  def message(self):
    """Text message explaining the error.

    Subclasses must implement this, returning a string that explains the
    error.

    Raises:
      NotImplementedError: Subclasses must override this function.
    """
    raise NotImplementedError

  def reason(self):
    """Get the reason for the error.

    Error reason is a custom string in the Cloud Endpoints server.  When
    possible, this should match the reason that the live server will generate,
    based on the error's status code.  If this returns None, the error formatter
    will attempt to generate a reason from the status code.

    Returns:
      None, by default.  Subclasses can override this if they have a specific
      error reason.
    """
    return None

  def extra_fields(self):
    """Return a dict of extra fields to add to the error response.

    Some errors have additional information.  This provides a way for subclasses
    to provide that information.

    Returns:
      None, by default.  Subclasses can return a dict with values to add
      to the error response.
    """
    return None

  def _get_status_code_and_error_reason(self):
    """Get the error reason string and HTTP status code from this request error.

    Error reason is a custom string in the Cloud Endpoints server.  This is
    a rough approximation of what the server will return.  For most errors,
    this should be accurate, but there are no guarantees.

    Returns:
      A tuple containing (status_code, reason), where 'status_code' is an
      integer indicating the HTTP status, and 'reason' string with the short
      reason for the error.
    """
    try:
      status_code = int(self.http_status().split(' ', 1)[0])
    except TypeError:
      logging.warning('Unable to find status code in HTTP status %r.',
                      self.http_status())
      status_code = 500
    reason = self.reason() or self.__ERROR_REASON_EXCEPTIONS.get(status_code)
    if not reason:
      http_response = httplib.responses.get(status_code, '')
      reason = http_response[0:1].lower() + http_response[1:].replace(' ', '')

    return status_code, reason

  def __format_error(self, error_list_tag):
    """Format this error into a JSON response.

    Args:
      error_list_tag: A string specifying the name of the tag to use for the
        error list.

    Returns:
      A dict containing the reformatted JSON error response.
    """
    status_code, reason = self._get_status_code_and_error_reason()
    error = {'domain': 'global',
             'reason': reason,
             'message': self.message()}
    error.update(self.extra_fields() or {})
    return {'error': {error_list_tag: [error],
                      'code': status_code,
                      'message': self.message()}}

  def rest_error(self):
    """Format this error into a response to a REST request.

    Returns:
      A string containing the reformatted error response.
    """
    error_json = self.__format_error('errors')
    return json.dumps(error_json, indent=1, sort_keys=True)

  def rpc_error(self):
    """Format this error into a response to a JSON RPC request.


    Returns:
      A dict containing the reformatted JSON error response.
    """
    return self.__format_error('data')


class RequestRejectionError(RequestError):
  """Base class for invalid/rejected requests.

  To be raised when parsing the request values and comparing them against the
  generated discovery document.
  """

  def http_status(self):
    return '400 Bad Request'



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

  def reason(self):
    """Returns the server's reason for this error.

    Returns:
      A string containing a short error reason.
    """
    return 'invalidParameter'

  def extra_fields(self):
    """Returns extra fields to add to the error response.

    Returns:
      A dict containing extra fields to add to the error response.
    """
    return {'locationType': 'parameter',
            'location': self.parameter_name}


class BackendError(RequestError):
  """Exception raised when the backend SPI returns an error code."""

  def __init__(self, response):
    super(BackendError, self).__init__()
    self._status = response.status

    try:
      error_json = json.loads(response.content)
      self._message = error_json.get('error_message')
    except TypeError:
      self._message = response.content

  def http_status(self):
    """Return the HTTP status code and message for this error.

    Returns:
      A string containing the status code and message for this error.
    """
    return self._status

  def message(self):
    """Return a descriptive message for this error.

    Returns:
      A string containing a descriptive message for this error.
    """
    return self._message
