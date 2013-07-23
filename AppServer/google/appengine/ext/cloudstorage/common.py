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














"""Helpers shared by cloudstorage_stub and cloudstorage_api."""









__all__ = ['CS_XML_NS',
           'CSFileStat',
           'dt_str_to_posix',
           'LOCAL_API_HOST',
           'local_run',
           'get_access_token',
           'get_metadata',
           'http_time_to_posix',
           'memory_usage',
           'posix_time_to_http',
           'posix_to_dt_str',
           'set_access_token',
           'validate_options',
           'validate_bucket_path',
           'validate_file_path',
          ]



import calendar
import datetime
from email import utils as email_utils
import logging
import os
import re

try:
  from google.appengine.api import runtime
except ImportError:
  from google.appengine.api import runtime


_CS_BUCKET_REGEX = re.compile(r'/[a-z0-9\.\-_]{3,}$')
_CS_FULLPATH_REGEX = re.compile(r'/[a-z0-9\.\-_]{3,}/.*')
_CS_OPTIONS = ('x-goog-acl',
               'x-goog-meta-')

CS_XML_NS = 'http://doc.s3.amazonaws.com/2006-03-01'

LOCAL_API_HOST = 'gcs-magicstring.appspot.com'

_access_token = ''


def set_access_token(access_token):
  """Set the shared access token to authenticate with Cloud Storage.

  When set, the library will always attempt to communicate with the
  real Cloud Storage with this token even when running on dev appserver.
  Note the token could expire so it's up to you to renew it.

  When absent, the library will automatically request and refresh a token
  on appserver, or when on dev appserver, talk to a Cloud Storage
  stub.

  Args:
    access_token: you can get one by run 'gsutil -d ls' and copy the
      str after 'Bearer'.
  """
  global _access_token
  _access_token = access_token


def get_access_token():
  """Returns the shared access token."""
  return _access_token


class CSFileStat(object):
  """Container for CS file stat."""

  def __init__(self,
               filename,
               st_size,
               etag,
               st_ctime,
               content_type=None,
               metadata=None):
    """Initialize.

    Args:
      filename: a Google Storage filename of form '/bucket/filename'.
      st_size: file size in bytes. long compatible.
      etag: hex digest of the md5 hash of the file's content. str.
      st_ctime: posix file creation time. float compatible.
      content_type: content type. str.
      metadata: a str->str dict of user specified metadata from the
        x-goog-meta header, e.g. {'x-goog-meta-foo': 'foo'}.
    """
    self.filename = filename
    self.st_size = long(st_size)
    self.st_ctime = float(st_ctime)
    if etag[0] == '"' and etag[-1] == '"':
      etag = etag[1:-1]
    self.etag = etag
    self.content_type = content_type
    self.metadata = metadata

  def __repr__(self):
    return (
        '(filename: %(filename)s, st_size: %(st_size)s, '
        'st_ctime: %(st_ctime)s, etag: %(etag)s, '
        'content_type: %(content_type)s, '
        'metadata: %(metadata)s)' %
        dict(filename=self.filename,
             st_size=self.st_size,
             st_ctime=self.st_ctime,
             etag=self.etag,
             content_type=self.content_type,
             metadata=self.metadata))


def get_metadata(headers):
  """Get user defined metadata from HTTP response headers."""
  return dict((k, v) for k, v in headers.iteritems()
              if k.startswith('x-goog-meta-'))


def validate_bucket_path(path):
  """Validate a Google Storage bucket path.

  Args:
    path: a Google Storage bucket path. It should have form '/bucket'.
    is_bucket: whether this is a bucket path or file path.

  Raises:
    ValueError: if path is invalid.
  """
  _validate_path(path)
  if not _CS_BUCKET_REGEX.match(path):
    raise ValueError('Bucket should have format /bucket '
                     'but got %s' % path)


def validate_file_path(path):
  """Validate a Google Storage file path.

  Args:
    path: a Google Storage file path. It should have form '/bucket/filename'.

  Raises:
    ValueError: if path is invalid.
  """
  _validate_path(path)
  if not _CS_FULLPATH_REGEX.match(path):
    raise ValueError('Path should have format /bucket/filename '
                     'but got %s' % path)


def _validate_path(path):
  """Basic validation of Google Storage paths.

  Args:
    path: a Google Storage path. It should have form '/bucket/filename'
      or '/bucket'.

  Raises:
    ValueError: if path is invalid.
    TypeError: if path is not of type basestring.
  """
  if not path:
    raise ValueError('Path is empty')
  if not isinstance(path, basestring):
    raise TypeError('Path should be a string but is %s (%s).' %
                    (path.__class__, path))


def validate_options(options):
  """Validate Cloud Storage options.

  Args:
    options: a str->basestring dict of options to pass to Cloud Storage.

  Raises:
    ValueError: if option is not supported.
    TypeError: if option is not of type str or value of an option
      is not of type basestring.
  """
  if not options:
    return

  for k, v in options.iteritems():
    if not isinstance(k, str):
      raise TypeError('option %r should be a str.' % k)
    if not any(k.startswith(valid) for valid in _CS_OPTIONS):
      raise ValueError('option %s is not supported.' % k)
    if not isinstance(v, basestring):
      raise TypeError('value %r for option %s should be of type basestring.' %
                      v, k)


def http_time_to_posix(http_time):
  """Convert HTTP time format to posix time.

  See http://www.w3.org/Protocols/rfc2616/rfc2616-sec3.html#sec3.3.1
  for http time format.

  Args:
    http_time: time in RFC 2616 format. e.g.
      "Mon, 20 Nov 1995 19:12:08 GMT".

  Returns:
    A float of secs from unix epoch.
  """
  if http_time is not None:
    return email_utils.mktime_tz(email_utils.parsedate_tz(http_time))


def posix_time_to_http(posix_time):
  """Convert posix time to HTML header time format.

  Args:
    posix_time: unix time.

  Returns:
    A datatime str in RFC 2616 format.
  """
  if posix_time:
    return email_utils.formatdate(posix_time, usegmt=True)



_DT_FORMAT = '%Y-%m-%dT%H:%M:%S'


def dt_str_to_posix(dt_str):
  """format str to posix.

  datetime str is of format %Y-%m-%dT%H:%M:%S.%fZ,
  e.g. 2013-04-12T00:22:27.978Z. According to ISO 8601, T is a separator
  between date and time when they are on the same line.
  Z indicates UTC (zero meridian).

  A pointer: http://www.cl.cam.ac.uk/~mgk25/iso-time.html

  This is used to parse LastModified node from GCS's GET bucket XML response.

  Args:
    dt_str: A datetime str.

  Returns:
    A float of secs from unix epoch. By posix definition, epoch is midnight
    1970/1/1 UTC.
  """
  parsable, _ = dt_str.split('.')
  dt = datetime.datetime.strptime(parsable, _DT_FORMAT)
  return calendar.timegm(dt.utctimetuple())


def posix_to_dt_str(posix):
  """Reverse of str_to_datetime.

  This is used by GCS stub to generate GET bucket XML response.

  Args:
    posix: A float of secs from unix epoch.

  Returns:
    A datetime str.
  """
  dt = datetime.datetime.utcfromtimestamp(posix)
  dt_str = dt.strftime(_DT_FORMAT)
  return dt_str + '.000Z'


def local_run():
  """Whether running in dev appserver."""
  return ('SERVER_SOFTWARE' not in os.environ or
          os.environ['SERVER_SOFTWARE'].startswith('Development'))


def memory_usage(method):
  """Log memory usage before and after a method."""
  def wrapper(*args, **kwargs):
    logging.info('Memory before method %s is %s.',
                 method.__name__, runtime.memory_usage().current())
    result = method(*args, **kwargs)
    logging.info('Memory after method %s is %s',
                 method.__name__, runtime.memory_usage().current())
    return result
  return wrapper
