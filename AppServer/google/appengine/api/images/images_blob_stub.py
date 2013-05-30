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




"""Stub version of the blob-related parts of the images API."""







import logging

from google.appengine.api import datastore





BLOB_SERVING_URL_KIND = "__BlobServingUrl__"


class ImagesBlobStub(object):
  """Stub version of the blob-related parts of the images API."""

  def __init__(self, host_prefix):
    """Stub implementation of blob-related parts of the images API.

    Args:
      host_prefix: the URL prefix (protocol://host:port) to preprend to
        image urls on a call to GetUrlBase.
    """
    self._host_prefix = host_prefix

  def GetUrlBase(self, request, response):
    """Trivial implementation of ImagesService::GetUrlBase.

    Args:
      request: ImagesGetUrlBaseRequest, contains a blobkey to an image
      response: ImagesGetUrlBaseResponse, contains a url to serve the image
    """
    if request.create_secure_url():
      logging.info("Secure URLs will not be created using the development "
                   "application server.")

    entity_info = datastore.Entity(BLOB_SERVING_URL_KIND,
                                   name=request.blob_key(),
                                   namespace="")
    entity_info["blob_key"] = request.blob_key()
    datastore.Put(entity_info)

    response.set_url("%s/_ah/img/%s" % (self._host_prefix, request.blob_key()))

  def DeleteUrlBase(self, request, response):
    """Trivial implementation of ImagesService::DeleteUrlBase.

    Args:
      request: ImagesDeleteUrlBaseRequest, contains a blobkey to an image.
      response: ImagesDeleteUrlBaseResonse - currently unused.
    """
    key = datastore.Key.from_path(BLOB_SERVING_URL_KIND,
                                  request.blob_key(),
                                  namespace="")
    datastore.Delete(key)
