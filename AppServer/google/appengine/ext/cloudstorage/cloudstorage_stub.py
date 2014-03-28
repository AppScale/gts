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
"""Stub for Google storage."""


import StringIO

from google.appengine.ext.cloudstorage import api_utils
from google.appengine.ext.cloudstorage import common
from google.appengine.ext.cloudstorage import errors
from google.appengine.ext.cloudstorage import cloudstorage_api as gcs

class CloudStorageStub(object):
  """Cloud Storage implementation.
  """

  def __init__(self, _):
    """Initialize.
    """
    pass

  def post_start_creation(self, filename, options):
    """Start object creation with a POST.

    This implements the resumable upload XML API.

    Args:
      filename: gs filename of form /bucket/filename.
      options: a dict containing all user specified request headers.
        e.g. {'content-type': 'foo', 'x-goog-meta-bar': 'bar'}.

    Returns:
      A file handler to the GCS object.
    """
    common.validate_file_path(filename)
    write_retry_params = api_utils.RetryParams(backoff_factor=1.1)
    content_type = 'text/plain'
    if 'content-type' in options:
      content_type = options['content-type']
      del options['content-type']
    token = gcs.open(filename,
                     'w',
                     content_type=content_type,
                     options=options,
                     retry_params=write_retry_params)
    return token

  def put_continue_creation(self, token, content, content_range, last=False):
    """Continue object upload with PUTs.

    This implements the resumable upload XML API.

    Args:
      token: upload token returned by post_start_creation.
      content: object content.
      content_range: a (start, end) tuple specifying the content range of this
        chunk. Both are inclusive according to XML API.
      last: True if this is the last chunk of file content.

    Raises:
      ValueError: if token is invalid.
    """
    if not token:
      raise ValueError('Invalid token')
    if content:
      start, end = content_range
      if len(content) != (end - start + 1):
        raise ValueError('Invalid content range %d-%d' % content_range)
      token.write(content)
    if last:
      self._end_creation(token)

  def _end_creation(self, token):
    """End object upload.

    Args:
      token: upload token returned by post_start_creation.

    Raises:
      ValueError: if token is invalid. Or file is corrupted during upload.

    """
    if not token:
      raise ValueError('Invalid token')

    token.close()

  def get_bucket(self,
                 bucketpath,
                 prefix,
                 marker,
                 max_keys):
    """Get bucket listing with a GET.

    Args:
      bucketpath: gs bucket path of form '/bucket'
      prefix: prefix to limit listing.
      marker: a str after which to start listing.
      max_keys: max size of listing.

    See https://developers.google.com/storage/docs/reference-methods#getbucket
    for details.

    Returns:
      A list of CSFileStat sorted by filename.
    """
    common.validate_bucket_path(bucketpath)
    return gcs.listbucket(bucketpath, prefix=prefix, marker=marker,
      max_keys=max_keys)

  def get_object(self, filename, start=0, end=None):
    """Get file content with a GET.

    Args:
      filename: gs filename of form '/bucket/filename'.
      start: start offset to request. Inclusive.
      end: end offset to request. Inclusive.

    Returns:
      The segment of file content requested.

    Raises:
      ValueError: if file doesn't exist.
    """
    gcs_file = gcs.open(filename)
    gcs_file.seek(start, end)
    contents = gcs_file.read() 
    gcs_file.close()
    return contents

  def head_object(self, filename):
    """Get file stat with a HEAD.

    Args:
      filename: gs filename of form '/bucket/filename'

    Returns:
      A CSFileStat object containing file stat. None if file doesn't exist.
    """
    try:
      return gcs.stat(filename)
    except errors.NotFoundError:
      return None 

  def delete_object(self, filename):
    """Delete file with a DELETE.

    Args:
      filename: gs filename of form '/bucket/filename'

    Returns:
      True if file is deleted. False if file doesn't exist.
    """
    common.validate_file_path(filename)
    try:
      gcs.delete(filename)
      return True
    except errors.NotFoundError:
      return False
 
