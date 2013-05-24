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




import calendar
import datetime
import hashlib
import StringIO
import time

from google.appengine.api.blobstore import blobstore_stub
from google.appengine.ext import db
from google.appengine.ext.cloudstorage import common


class _AE_GCSFileInfo_(db.Model):
  """Store GCS specific info.

  GCS allows user to define arbitrary metadata via header x-goog-meta-foo: bar.
  These headers are returned when user does a GET or HEAD on the object.

  Key name is blobkey.
  """
  filename = db.StringProperty(required=True)
  finalized = db.BooleanProperty(required=True)



  raw_options = db.StringListProperty()


  size = db.IntegerProperty()

  creation = db.DateTimeProperty()
  content_type = db.ByteStringProperty()
  etag = db.ByteStringProperty()

  def get_options(self):
    return dict(o.split(':', 1) for o in self.raw_options)

  def set_options(self, options_dict):
    self.raw_options = [
        '%s:%s' % (k.lower(), v) for k, v in options_dict.iteritems()]
    if 'content-type' in options_dict:
      self.content_type = options_dict['content-type']


  options = property(get_options, set_options)

  @classmethod
  def kind(cls):

    return blobstore_stub._GS_INFO_KIND


class _AE_GCSPartialFile_(db.Model):
  """Store partial content for uploading files."""

  start = db.IntegerProperty(required=True)

  end = db.IntegerProperty(required=True)



  partial_content = db.TextProperty(required=True)


class CloudStorageStub(object):
  """Cloud Storage stub implementation.

  We use blobstore stub to store files. All metadata are stored
  in _AE_GCSFileInfo_.

  Note: this Cloud Storage stub is designed to work with
  apphosting.ext.cloudstorage.storage_api.py.
  It only implements the part of GCS storage_api.py uses, and its interface
  maps to GCS XML APIs.
  """

  def __init__(self, blob_storage):
    """Initialize.

    Args:
      blob_storage:
          apphosting.api.blobstore.blobstore_stub.BlobStorage instance
    """
    self.blob_storage = blob_storage

  def _filename_to_blobkey(self, filename):
    """Get blobkey for filename.

    Args:
      filename: gs filename of form /bucket/filename.

    Returns:
      blobinfo's datastore's key name, aka, blobkey.
    """
    common.validate_file_path(filename)

    return blobstore_stub.BlobstoreServiceStub.CreateEncodedGoogleStorageKey(
        filename)

  def post_start_creation(self, filename, options):
    """Start object creation with a POST.

    This implements the resumable upload XML API.

    Args:
      filename: gs filename of form /bucket/filename.
      options: a dict containing all user specified request headers.
        e.g. {'content-type': 'foo', 'x-goog-meta-bar': 'bar'}.

    Returns:
      a token used for continuing upload. Also used as blobkey to store
    the content.
    """
    common.validate_file_path(filename)
    token = self._filename_to_blobkey(filename)
    gcs_file = _AE_GCSFileInfo_.get_by_key_name(token)

    self._cleanup_old_file(gcs_file)
    new_file = _AE_GCSFileInfo_(key_name=token,
                                filename=filename,
                                finalized=False)
    new_file.options = options
    new_file.put()
    return token


  def _cleanup_old_file(self, gcs_file):
    """Clean up the old version of a file.

    The old version may or may not be finalized yet. Either way,
    when user tries to create a file that already exists, we delete the
    old version first.

    Args:
      gcs_file: an instance of _AE_GCSFileInfo_.
    """
    if gcs_file:
      if gcs_file.finalized:
        blobkey = gcs_file.key().name()
        self.blob_storage.DeleteBlob(blobkey)
      else:
        db.delete(_AE_GCSPartialFile_.all().ancestor(gcs_file))
      gcs_file.delete()

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
    gcs_file = _AE_GCSFileInfo_.get_by_key_name(token)
    if not gcs_file:
      raise ValueError('Invalid token')
    if content:
      start, end = content_range
      if len(content) != (end - start + 1):
        raise ValueError('Invalid content range %d-%d' % content_range)
      blobkey = '%s-%d-%d' % (token, content_range[0], content_range[1])
      self.blob_storage.StoreBlob(blobkey, StringIO.StringIO(content))
      new_content = _AE_GCSPartialFile_(parent=gcs_file,
                                        partial_content=blobkey,
                                        start=start,
                                        end=end + 1)
      new_content.put()
    if last:
      self._end_creation(token)

  def _end_creation(self, token):
    """End object upload.

    Args:
      token: upload token returned by post_start_creation.

    Raises:
      ValueError: if token is invalid. Or file is corrupted during upload.

    Save file content to blobstore. Save blobinfo and _AE_GCSFileInfo.
    """
    gcs_file = _AE_GCSFileInfo_.get_by_key_name(token)
    if not gcs_file:
      raise ValueError('Invalid token')

    error_msg, content = self._get_content(gcs_file)
    if error_msg:
      raise ValueError(error_msg)

    gcs_file.etag = hashlib.md5(content).hexdigest()
    gcs_file.creation = datetime.datetime.utcnow()
    gcs_file.size = len(content)

    self.blob_storage.StoreBlob(token, StringIO.StringIO(content))

    gcs_file.finalized = True
    gcs_file.put()

  @db.transactional
  def _get_content(self, gcs_file):
    """Aggregate all partial content of the gcs_file.

    Args:
      gcs_file: an instance of _AE_GCSFileInfo_.

    Returns:
      (error_msg, content) tuple. error_msg is set if the file is
      corrupted during upload. Otherwise content is set to the
      aggregation of all partial contents.
    """
    content = ''
    previous_end = 0
    error_msg = ''
    for partial in _AE_GCSPartialFile_.all().ancestor(gcs_file).order('start'):
      if not error_msg:
        if partial.start < previous_end:
          error_msg = 'File is corrupted due to missing chunks.'
        elif partial.start > previous_end:
          error_msg = 'File is corrupted due to overlapping chunks'
        previous_end = partial.end
        content += self.blob_storage.OpenBlob(partial.partial_content).read()
        self.blob_storage.DeleteBlob(partial.partial_content)
      partial.delete()
    if error_msg:
      gcs_file.delete()
      content = ''
    return error_msg, content

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
    q = _AE_GCSFileInfo_.all(namespace='')
    fully_qualified_prefix = '/'.join([bucketpath, prefix])
    if marker:
      q.filter('filename >', '/'.join([bucketpath, marker]))
    else:
      q.filter('filename >=', fully_qualified_prefix)
    result = []
    for info in q.run(limit=max_keys):
      if not info.filename.startswith(fully_qualified_prefix):
        break
      result.append(common.CSFileStat(
          filename=info.filename,
          st_size=info.size,
          st_ctime=calendar.timegm(info.creation.utctimetuple()),
          etag=info.etag))
    return result

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
    common.validate_file_path(filename)
    blobkey = self._filename_to_blobkey(filename)
    gsfileinfo = _AE_GCSFileInfo_.get_by_key_name(blobkey)
    if not gsfileinfo or not gsfileinfo.finalized:
      raise ValueError('File does not exist.')
    local_file = self.blob_storage.OpenBlob(blobkey)
    local_file.seek(start)
    if end:
      return local_file.read(end - start + 1)
    else:
      return local_file.read()

  def head_object(self, filename):
    """Get file stat with a HEAD.

    Args:
      filename: gs filename of form '/bucket/filename'

    Returns:
      A CSFileStat object containing file stat. None if file doesn't exist.
    """
    common.validate_file_path(filename)
    blobkey = self._filename_to_blobkey(filename)
    info = _AE_GCSFileInfo_.get_by_key_name(blobkey)
    if info and info.finalized:
      metadata = common.get_metadata(info.options)
      filestat = common.CSFileStat(
          filename=info.filename,
          st_size=info.size,
          etag=info.etag,
          st_ctime=calendar.timegm(info.creation.utctimetuple()),
          content_type=info.content_type,
          metadata=metadata)
      return filestat
    return None

  def delete_object(self, filename):
    """Delete file with a DELETE.

    Args:
      filename: gs filename of form '/bucket/filename'

    Returns:
      True if file is deleted. False if file doesn't exist.
    """
    common.validate_file_path(filename)
    blobkey = self._filename_to_blobkey(filename)
    gsfileinfo = _AE_GCSFileInfo_.get_by_key_name(blobkey)
    if not gsfileinfo:
      return False
    gsfileinfo.delete()
    self.blob_storage.DeleteBlob(blobkey)
    return True
