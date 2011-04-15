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




"""Handler library for Blobstore API.

Contains handlers to help with uploading and downloading blobs.

Public Classes:
  BlobstoreDownloadHandler: Has helper method for easily sending blobs
    to client.
  BlobstoreUploadHandler: Handler for receiving upload notification requests.

Public Exceptions (indentation indications class hierarchy):
  Error: Base class for service handler errors.
    RangeFormatError: Raised when Range header has invalid format.
      UnsupportedRangeFormatError: Raised when range header has valid format
        but a particular feature or unit type is not supported.
"""








import cgi
import cStringIO
import re
import sys

from google.appengine.ext import blobstore
from google.appengine.ext import webapp

from webob import byterange


__all__ = [
    'Error',
    'RangeFormatError',
    'UnsupportedRangeFormatError',

    'BlobstoreDownloadHandler',
    'BlobstoreUploadHandler',
]


_CONTENT_DISPOSITION_FORMAT = 'attachment; filename="%s"'

_SEND_BLOB_PARAMETERS = frozenset(['use_range'])

_RANGE_NUMERIC_FORMAT = r'([0-9]*)-([0-9]*)'
_RANGE_FORMAT = r'([a-zA-Z]+)=%s' % _RANGE_NUMERIC_FORMAT
_RANGE_FORMAT_REGEX = re.compile('^%s$' % _RANGE_FORMAT)
_UNSUPPORTED_RANGE_FORMAT_REGEX = re.compile(
    '^%s(?:,%s)+$' % (_RANGE_FORMAT, _RANGE_NUMERIC_FORMAT))
_BYTES_UNIT = 'bytes'


class Error(Exception):
  """Base class for all errors in blobstore handlers module."""


class RangeFormatError(webapp.Error):
  """Raised when Range header incorrectly formatted."""


class UnsupportedRangeFormatError(RangeFormatError):
  """Raised when Range format is correct, but not supported."""


def _check_ranges(start, end, use_range_set, use_range, range_header):
  """Set the range header.

  Args:
    start: As passed in from send_blob.
    end: As passed in from send_blob.
    use_range_set: Use range was explcilty set during call to send_blob.
    use_range: As passed in from send blob.
    range_header: Range header as received in HTTP request.

  Returns:
    Range header appropriate for placing in blobstore.BLOB_RANGE_HEADER.

  Raises:
    ValueError if parameters are incorrect.  This happens:
      - start > end.
      - start < 0 and end is also provided.
      - end < 0
      - If index provided AND using the HTTP header, they don't match.
        This is a safeguard.
  """
  if end is not None and start is None:
    raise ValueError('May not specify end value without start.')


  use_indexes = start is not None
  if use_indexes:
    if end is not None:


      if start > end:
        raise ValueError('start must be < end.')

    range_indexes = byterange.Range.serialize_bytes(_BYTES_UNIT, [(start, end)])


  if use_range_set and use_range and use_indexes:
    if range_header != range_indexes:
      raise ValueError('May not provide non-equivalent range indexes and '
                       'range headers: (header) %s != (indexes) %s'
                       % (range_header, range_indexes))


  if use_range and range_header is not None:
    return range_header
  elif use_indexes:
    return range_indexes
  else:
    return None


class BlobstoreDownloadHandler(webapp.RequestHandler):
  """Base class for creating handlers that may send blobs to users."""


  __use_range_unset = object()
  def send_blob(self,
                blob_key_or_info,
                content_type=None,
                save_as=None,
                start=None,
                end=None,
                **kwargs):
    """Send a blob-response based on a blob_key.

    Sets the correct response header for serving a blob.  If BlobInfo
    is provided and no content_type specified, will set request content type
    to BlobInfo's content type.

    Args:
      blob_key_or_info: BlobKey or BlobInfo record to serve.
      content_type: Content-type to override when known.
      save_as: If True, and BlobInfo record is provided, use BlobInfos
        filename to save-as.  If string is provided, use string as filename.
        If None or False, do not send as attachment.
      start: Start index of content-range to send.
      end: End index of content-range to send.  End index is inclusive.
      use_range: Use provided content range from requests Range header.
        Mutually exclusive to start and end.

    Raises:
      ValueError on invalid save_as parameter.
    """
    if set(kwargs) - _SEND_BLOB_PARAMETERS:
      invalid_keywords = []
      for keyword in kwargs:
        if keyword not in _SEND_BLOB_PARAMETERS:
          invalid_keywords.append(keyword)
      if len(invalid_keywords) == 1:
        raise TypeError('send_blob got unexpected keyword argument %s.'
                        % invalid_keywords[0])
      else:
        raise TypeError('send_blob got unexpected keyword arguments: %s'
                        % sorted(invalid_keywords))



    use_range = kwargs.get('use_range', self.__use_range_unset)
    use_range_set = use_range is not self.__use_range_unset

    range_header = _check_ranges(start,
                                 end,
                                 use_range_set,
                                 use_range,
                                 self.request.headers.get('range', None))

    if range_header is not None:
      self.response.headers[blobstore.BLOB_RANGE_HEADER] = range_header

    if isinstance(blob_key_or_info, blobstore.BlobInfo):
      blob_key = blob_key_or_info.key()
      blob_info = blob_key_or_info
    else:
      blob_key = blob_key_or_info
      blob_info = None

    self.response.headers[blobstore.BLOB_KEY_HEADER] = str(blob_key)

    if content_type:
      if isinstance(content_type, unicode):
        content_type = content_type.encode('utf-8')
      self.response.headers['Content-Type'] = content_type
    else:


      del self.response.headers['Content-Type']

    def send_attachment(filename):
      if isinstance(filename, unicode):
        filename = filename.encode('utf-8')
      self.response.headers['Content-Disposition'] = (
          _CONTENT_DISPOSITION_FORMAT % filename)

    if save_as:
      if isinstance(save_as, basestring):
        send_attachment(save_as)
      elif blob_info and save_as is True:
        send_attachment(blob_info.filename)
      else:
        if not blob_info:
          raise ValueError('Expected BlobInfo value for blob_key_or_info.')
        else:
          raise ValueError('Unexpected value for save_as.')

    self.response.clear()

  def get_range(self):
    """Get range from header if it exists.

    Returns:
      Tuple (start, end):
        start: Start index.  None if there is None.
        end: End index.  None if there is None.
      None if there is no request header.

    Raises:
      UnsupportedRangeFormatError: If the range format in the header is
        valid, but not supported.
      RangeFormatError: If the range format in the header is not valid.
    """
    range_header = self.request.headers.get('range', None)
    if range_header is None:
      return None

    try:



      original_stdout = sys.stdout
      sys.stdout = cStringIO.StringIO()
      try:
        parsed_range = byterange.Range.parse_bytes(range_header)
      finally:
        sys.stdout = original_stdout
    except TypeError, err:
      raise RangeFormatError('Invalid range header: %s' % err)
    if parsed_range is None:
      raise RangeFormatError('Invalid range header: %s' % range_header)

    units, ranges = parsed_range
    if len(ranges) != 1:
      raise UnsupportedRangeFormatError(
          'Unable to support multiple range values in Range header.')

    if units != _BYTES_UNIT:
      raise UnsupportedRangeFormatError(
          'Invalid unit in range header type: %s', range_header)

    return ranges[0]


class BlobstoreUploadHandler(webapp.RequestHandler):
  """Base class for creation blob upload handlers."""

  def __init__(self):
    super(BlobstoreUploadHandler, self).__init__()
    self.__uploads = None

  def get_uploads(self, field_name=None):
    """Get uploads sent to this handler.

    Args:
      field_name: Only select uploads that were sent as a specific field.

    Returns:
      A list of BlobInfo records corresponding to each upload.
      Empty list if there are no blob-info records for field_name.
    """
    if self.__uploads is None:
      self.__uploads = {}
      for key, value in self.request.params.items():
        if isinstance(value, cgi.FieldStorage):
          if 'blob-key' in value.type_options:
            self.__uploads.setdefault(key, []).append(
                blobstore.parse_blob_info(value))

    if field_name:
      try:
        return list(self.__uploads[field_name])
      except KeyError:
        return []
    else:
      results = []
      for uploads in self.__uploads.itervalues():
        results += uploads
      return results
