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

"""
Author: Navraj Chohan <nlake44@gmail.com>
Modifications for AppScale
Implementation of Blobstore stub storage based on the datastore

Contains implementation of blobstore_stub.BlobStorage that writes
blobs into the AppScale backends. Blobs are split into chunks of 
1MB segments. 

"""

from google.appengine.ext.blobstore.blobstore import BlobReader
from google.appengine.api import blobstore
from google.appengine.api.blobstore import blobstore_stub
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api import datastore_types
from google.appengine.runtime import apiproxy_errors
from google.appengine.api.blobstore import blobstore_service_pb

__all__ = ['DatastoreBlobStorage']

# The datastore kind used for storing chunks of a blob
_BLOB_CHUNK_KIND_ = "__BlobChunk__"

class DatastoreBlobStorage(blobstore_stub.BlobStorage):
  """Storage mechanism for storing blob data in datastore."""

  def __init__(self, app_id):
    """Constructor.

    Args:
      app_id: App id to store blobs on behalf of.
    """
    self._app_id = app_id

  @classmethod
  def _BlobKey(cls, blob_key):
    """Normalize to instance of BlobKey.
 
    Args:
      blob_key: A blob key of a blob to store.
    Returns:
      A normalized blob key of class BlobKey.
    """
    if not isinstance(blob_key, blobstore.BlobKey):
      return blobstore.BlobKey(unicode(blob_key))
    return blob_key

  def StoreBlob(self, blob_key, blob_stream):
    """Store blob stream to the datastore.

    Args:
      blob_key: Blob key of blob to store.
      blob_stream: Stream or stream-like object that will generate blob content.
    """
    blob_key = self._BlobKey(blob_key)
    block_count = 0
    while True:
      block = blob_stream.read(blobstore.MAX_BLOB_FETCH_SIZE)
      if not block:
        break
      entity = datastore.Entity(_BLOB_CHUNK_KIND_, 
                                name=str(blob_key) + "__" + str(block_count), 
                                namespace='')
      entity.update({'block': datastore_types.Blob(block)})
      datastore.Put(entity)
      block_count += 1

  def OpenBlob(self, blob_key):
    """Open blob file for streaming.

    Args:
      blob_key: Blob-key of existing blob to open for reading.

    Returns:
      Open file stream for reading blob from the datastore.
    """
    return BlobReader(blob_key, blobstore.MAX_BLOB_FETCH_SIZE, 0)

  def DeleteBlob(self, blob_key):
    """Delete blob data from the datastore.

    Args:
      blob_key: Blob-key of existing blob to delete.
    Raises:
      ApplicationError: When a blob is not found or unable to be read.  
    """
    blob_info_key = datastore.Key.from_path(blobstore.BLOB_INFO_KIND,
                                            str(blob_key),
                                            namespace='')
    try:
      blob_info = datastore.Get(blob_info_key)
    except datastore_errors.EntityNotFoundError:
      raise apiproxy_errors.ApplicationError(
          blobstore_service_pb.BlobstoreServiceError.BLOB_NOT_FOUND)

    block_count = blob_info["size"]/blobstore.MAX_BLOB_FETCH_SIZE
    block_set = []
    try:
      while block_count >= 0:
        entity = datastore.Entity(_BLOB_CHUNK_KIND_, 
                                  name=str(blob_key)+"__"+str(block_count), 
                                  namespace='')
        block_set.append(entity) 
        block_count -= 1
      datastore.Delete(block_set)
      datastore.Delete(blob_info_key)
    except:
      raise apiproxy_errors.ApplicationError(
          blobstore_service_pb.BlobstoreServiceError.BLOB_NOT_FOUND)
