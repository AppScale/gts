#!/usr/bin/env python
#
# Copyright 2011 Google Inc.
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

"""WSGI utilities

Small collection of helpful utilities for working with WSGI.
"""

__author__ = 'rafek@google.com (Rafe Kaplan)'

import cStringIO
import httplib
import re

from .. import util

__all__ = ['static_page',
           'error',
           'first_found',
]

_STATUS_PATTERN = re.compile('^(\d{3})\s')


@util.positional(1)
def static_page(content='',
                status='200 OK',
                content_type='text/html; charset=utf-8',
                headers=None):
  """Create a WSGI application that serves static content.

  A static page is one that will be the same every time it receives a request.
  It will always serve the same status, content and headers.

  Args:
    content: Content to serve in response to HTTP request.
    status: Status to serve in response to HTTP request.  If string, status
      is served as is without any error checking.  If integer, will look up
      status message.  Otherwise, parameter is tuple (status, description):
        status: Integer status of response.
        description: Brief text description of response.
    content_type: Convenient parameter for content-type header.  Will appear
      before any content-type header that appears in 'headers' parameter.
    headers: Dictionary of headers or iterable of tuples (name, value):
      name: String name of header.
      value: String value of header.

  Returns:
    WSGI application that serves static content.
  """
  if isinstance(status, (int, long)):
    status = '%d %s' % (status, httplib.responses.get(status, 'Unknown Error'))
  elif not isinstance(status, basestring):
    status = '%d %s' % tuple(status)

  if isinstance(headers, dict):
    headers = headers.iteritems()

  headers = [('content-length', str(len(content))),
             ('content-type', content_type),
            ] + list(headers or [])

  # Ensure all headers are str.
  for index, (key, value) in enumerate(headers):
    if isinstance(value, unicode):
      value = value.encode('utf-8')
      headers[index] = key, value

    if not isinstance(key, str):
      raise TypeError('Header key must be str, found: %r' % (key,))

    if not isinstance(value, str):
      raise TypeError(
          'Header %r must be type str or unicode, found: %r' % (key, value))

  def static_page_application(environ, start_response):
    start_response(status, headers)
    return [content]

  return static_page_application


@util.positional(2)
def error(status_code, status_message=None,
          content_type='text/plain; charset=utf-8',
          headers=None, content=None):
  """Create WSGI application that statically serves an error page.

  Creates a static error page specifically for non-200 HTTP responses.

  Browsers such as Internet Explorer will display their own error pages for
  error content responses smaller than 512 bytes.  For this reason all responses
  are right-padded up to 512 bytes.

  Error pages that are not provided will content will contain the standard HTTP
  status message as their content.

  Args:
    status_code: Integer status code of error.
    status_message: Status message.

  Returns:
    Static WSGI application that sends static error response.
  """
  if status_message is None:
    status_message = httplib.responses.get(status_code, 'Unknown Error')

  if content is None:
    content = status_message

  content = util.pad_string(content)

  return static_page(content,
                     status=(status_code, status_message),
                     content_type=content_type,
                     headers=headers)


def first_found(apps):
  """Serve the first application that does not response with 404 Not Found.

  If no application serves content, will respond with generic 404 Not Found.

  Args:
    apps: List of WSGI applications to search through.  Will serve the content
      of the first of these that does not return a 404 Not Found.  Applications
      in this list must not modify the environment or any objects in it if they
      do not match.  Applications that do not obey this restriction can create
      unpredictable results.

  Returns:
    Compound application that serves the contents of the first application that
    does not response with 404 Not Found.
  """
  apps = tuple(apps)
  not_found = error(httplib.NOT_FOUND)

  def first_found_app(environ, start_response):
    """Compound application returned from the first_found function."""
    final_result = {}  # Used in absence of Python local scoping.

    def first_found_start_response(status, response_headers):
      """Replacement for start_response as passed in to first_found_app.

      Called by each application in apps instead of the real start response.
      Checks the response status, and if anything other than 404, sets 'status'
      and 'response_headers' in final_result.
      """
      status_match = _STATUS_PATTERN.match(status)
      assert status_match, ('Status must be a string beginning '
                            'with 3 digit number. Found: %s' % status)
      status_code = status_match.group(0)
      if int(status_code) == httplib.NOT_FOUND:
        return

      final_result['status'] = status
      final_result['response_headers'] = response_headers

    for app in apps:
      response = app(environ, first_found_start_response)
      if final_result:
        start_response(final_result['status'], final_result['response_headers'])
        return response

    return not_found(environ, start_response)
  return first_found_app
