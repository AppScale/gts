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

import httplib

from .. import util


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

