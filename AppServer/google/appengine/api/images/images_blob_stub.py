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
import os

from google.appengine.api import datastore





BLOB_SERVING_URL_KIND = "__BlobServingUrl__"


class ImagesBlobStub(object):
  """Stub version of the blob-related parts of the images API."""

  def __init__(self, host_prefix):
    """Stub implementation of blob-related parts of the images API.

    Args:
      host_prefix: the URL prefix (protocol://host) to prepend to image urls
        on a call to GetUrlBase.
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

    # Host prefix does not include a port, so retrieve it from the filesystem.
    full_prefix = self._host_prefix
    if full_prefix:
      version_info = os.environ.get('CURRENT_VERSION_ID', 'v1').split('.')[0]
      if ':' not in version_info:
        version_info = 'default:' + version_info

      service_id, version_id = version_info.split(':')
      version_key = '_'.join(
        [os.environ['APPLICATION_ID'], service_id, version_id])
      port_file_location = os.path.join(
        '/', 'etc', 'appscale', 'port-{}.txt'.format(version_key))
      with open(port_file_location) as port_file:
        port = port_file.read().strip()
      full_prefix = '{}:{}'.format(full_prefix, port)

    response.set_url("%s/_ah/img/%s" % (full_prefix, request.blob_key()))

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
