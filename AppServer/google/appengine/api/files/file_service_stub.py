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




"""Stubs for File service."""


import base64
import cgi
import datetime
import os
import random
import string
import StringIO
import tempfile
import time
import urllib
import urlparse

from google.appengine.api import apiproxy_stub
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api.files import blobstore as files_blobstore
from google.appengine.api.files import file_service_pb
from google.appengine.api.files import gs
from google.appengine.ext import blobstore
from google.appengine.runtime import apiproxy_errors
from google.appengine.tools import dev_appserver_upload


MAX_REQUEST_SIZE = 32 << 20



_now_function = datetime.datetime.now


def raise_error(error_code, error_detail=''):
  """Raise application error helper method."""
  raise apiproxy_errors.ApplicationError(error_code, error_detail=error_detail)


_BLOBSTORE_DIRECTORY = files_blobstore._BLOBSTORE_DIRECTORY
_GS_PREFIX = gs._GS_PREFIX
_GS_UPLOAD_PREFIX = _GS_PREFIX + 'writable:'



class _GoogleStorageUpload(tuple):
  """Stores information about a writable Google Storage file."""
  buf = property(lambda self: self[0])
  content_type = property(lambda self: self[1])
  key = property(lambda self: self[2])


class GoogleStorage(object):
  """Virtual google storage to be used by file api."""



  def _Upload(self, buf, content_type, key):
    return _GoogleStorageUpload([buf, content_type, key])

  def __init__(self):
    self.index = 0
    self.keys = {}
    self.uploads = {}
    self.finalized = set()

  def ParseIndex(self, filename):
    """Returns 123 from /gs/writable:123."""
    assert filename
    assert filename.startswith(_GS_UPLOAD_PREFIX)
    return filename[len(_GS_UPLOAD_PREFIX):]

  def has_upload(self, filename):
    """Checks if there is an upload at this filename."""
    return self.ParseIndex(filename) in self.uploads

  def has_key(self, filename):
    """Checks if there is a key at this filename."""
    return filename in self.keys

  def finalize(self, filename):
    """Marks file as finalized."""
    index = self.ParseIndex(filename)
    upload = self.uploads[index]
    self.keys[upload.key] = upload.buf
    self.finalized.add(index)
    self.uploads[index] = self._Upload(
        None, upload.content_type, upload.key)

  def is_finalized(self, filename):
    """Checks if file is already finalized."""
    index = self.ParseIndex(filename)
    assert index in self.uploads
    return index in self.finalized

  def start_upload(self, request):
    """Starts a new upload based on the specified CreateRequest."""

    mime_type = None
    gs_filename = request.filename()
    ignored_parameters = [
        gs._CACHE_CONTROL_PARAMETER,
        gs._CANNED_ACL_PARAMETER,
        gs._CONTENT_DISPOSITION_PARAMETER,
        gs._CONTENT_ENCODING_PARAMETER,
        ]

    for param in request.parameters_list():
      name = param.name()
      if name == gs._MIME_TYPE_PARAMETER:
        mime_type = param.value()
      elif (name in ignored_parameters or
            name.startswith(gs._USER_METADATA_PREFIX)):
        pass
      else:
        raise_error(file_service_pb.FileServiceErrors.INVALID_PARAMETER)

    if not mime_type:
      raise_error(file_service_pb.FileServiceErrors.INVALID_PARAMETER)
    elif not gs_filename:
      raise_error(file_service_pb.FileServiceErrors.INVALID_PARAMETER)

    self.index += 1
    self.uploads[str(self.index)] = self._Upload(
        StringIO.StringIO(), mime_type, gs_filename)
    return '%s%d' % (_GS_UPLOAD_PREFIX, self.index)

  def append(self, filename, data):
    """Appends data to the upload filename."""
    index = self.ParseIndex(filename)
    assert not self.is_finalized(filename)
    self.uploads[index].buf.write(data)

  def read(self, key, pos, max_data):
    """Reads max_data bytes from key starting at pos."""
    assert key in self.keys
    buf = self.keys[key]
    buf.seek(pos)
    return buf.read(max_data)


class GoogleStorageFile(object):
  """File object for '/gs/' files."""





  def __init__(self, open_request, file_storage):
    self.filename = open_request.filename()
    self.file_storage = file_storage
    self.open_mode = open_request.open_mode()

    content_type = open_request.content_type()

    if self.is_appending:

      if not self.filename.startswith(_GS_UPLOAD_PREFIX):
        raise_error(file_service_pb.FileServiceErrors.INVALID_FILE_NAME)
      elif not self.file_storage.has_upload(self.filename):
        raise_error(file_service_pb.FileServiceErrors.EXISTENCE_ERROR)
      elif self.file_storage.is_finalized(self.filename):
        raise_error(file_service_pb.FileServiceErrors.FINALIZATION_ERROR,
                    'File is already finalized')
    else:

      if not self.filename.startswith(_GS_PREFIX):
        raise_error(file_service_pb.FileServiceErrors.INVALID_FILE_NAME)
      elif self.filename.startswith(_GS_UPLOAD_PREFIX):

        raise_error(file_service_pb.FileServiceErrors.INVALID_FILE_NAME)
      elif not self.file_storage.has_key(self.filename):
        raise_error(file_service_pb.FileServiceErrors.EXISTENCE_ERROR)

    if content_type != file_service_pb.FileContentType.RAW:
      raise_error(file_service_pb.FileServiceErrors.WRONG_CONTENT_TYPE)

  @property
  def is_appending(self):
    """Checks if the file is opened for appending or reading."""
    return self.open_mode == file_service_pb.OpenRequest.APPEND

  def read(self, request, response):
    """Copies up to max_bytes starting at pos into response from filename."""
    if self.is_appending:
      raise_error(file_service_pb.FileServiceErrors.WRONG_OPEN_MODE)
    data = self.file_storage.read(
        self.filename, request.pos(), request.max_bytes())
    response.set_data(data)

  def append(self, request, response):
    """Appends data to filename."""
    if not self.is_appending:
      raise_error(file_service_pb.FileServiceErrors.WRONG_OPEN_MODE)
    self.file_storage.append(self.filename, request.data())

  def finalize(self):
    """Finalize a file.

    Copies temp file data to permanent location for reading.
    """
    if not self.is_appending:
      raise_error(file_service_pb.FileServiceErrors.WRONG_OPEN_MODE)
    elif self.file_storage.is_finalized(self.filename):
      raise_error(
          file_service_pb.FileServiceErrors.FINALIZATION_ERROR,
          'File is already finalized')
    self.file_storage.finalize(self.filename)


class BlobstoreStorage(object):
  """Virtual file storage to be used by file api.

  Abstracts away all aspects of logical and physical file organization of the
  API.
  """

  def __init__(self, blob_storage):
    """Constructor.

    Args:
      blob_storage: An instance of
      apphosting.api.blobstore.blobstore_stub.BlobStorage to use for blob
      integration.
    """
    self.blob_keys = {}
    self.blobstore_files = set()
    self.finalized_files = set()
    self.created_files = set()
    self.data_files = {}
    self.sequence_keys = {}
    self.blob_storage = blob_storage



    self.blob_content_types = {}

    self.blob_file_names = {}

  def finalize(self, filename):
    """Marks file as finalized."""
    if self.is_finalized(filename):
      raise_error(file_service_pb.FileServiceErrors.FINALIZATION_ERROR,
                  'File is already finalized')
    self.finalized_files.add(filename)

  def is_finalized(self, filename):
    """Checks if file is already finalized."""
    return filename in self.finalized_files

  def get_blob_key(self, ticket):
    """Gets blob key for blob creation ticket."""
    return self.blob_keys.get(ticket)

  def register_blob_key(self, ticket, blob_key):
    """Register blob key for a ticket."""
    self.blob_keys[ticket] = blob_key

  def has_blobstore_file(self, filename):
    """Checks if blobstore file was already created."""
    return filename in self.blobstore_files

  def add_blobstore_file(self, request):
    """Registers a created blob store file."""

    mime_type = None
    blob_filename = ''
    for param in request.parameters_list():
      name = param.name()
      if name == files_blobstore._MIME_TYPE_PARAMETER:
        mime_type = param.value()
      elif name == files_blobstore._BLOBINFO_UPLOADED_FILENAME_PARAMETER:
        blob_filename = param.value()
      else:
        raise_error(file_service_pb.FileServiceErrors.INVALID_PARAMETER)
    if mime_type is None:
      raise_error(file_service_pb.FileServiceErrors.INVALID_PARAMETER)

    random_str = ''.join(
        random.choice(string.ascii_uppercase + string.digits)
        for _ in range(64))
    filename = (_BLOBSTORE_DIRECTORY +
                files_blobstore._CREATION_HANDLE_PREFIX +
                base64.urlsafe_b64encode(random_str))
    self.blobstore_files.add(filename)
    self.blob_content_types[filename] = mime_type
    self.blob_file_names[filename] = blob_filename
    return filename

  def get_sequence_key(self, filename):
    """Get sequence key for a file."""
    return self.sequence_keys.get(filename, '')

  def set_sequence_key(self, filename, sequence_key):
    """Set sequence key for a file."""
    self.sequence_keys[filename] = sequence_key

  def save_blob(self, filename, blob_key):
    """Save filename temp data to a blobstore under given key."""
    f = self._get_data_file(filename)
    f.seek(0)
    self.blob_storage.StoreBlob(blob_key, f)
    f.seek(0, os.SEEK_END)
    size = f.tell()
    f.close()
    del self.data_files[filename]
    return size

  def _get_data_file(self, filename):
    """Get a temp data file for a file."""
    if not filename in self.data_files:
      f = tempfile.TemporaryFile()
      self.data_files[filename] = f
      return f
    return self.data_files[filename]

  def append(self, filename, data):
    """Append data to file."""
    self._get_data_file(filename).write(data)

  def get_content_type(self, filename):
    return self.blob_content_types[filename]

  def get_blob_file_name(self, filename):
    return self.blob_file_names[filename]


class BlobstoreFile(object):
  """File object for generic /blobstore/ file."""

  def __init__(self, open_request, file_storage):
    """Constructor.

    Args:
      open_request: An instance of open file request.
      file_storage: An instance of BlobstoreStorage.
    """
    self.filename = open_request.filename()
    self.file_storage = file_storage
    self.blob_reader = None
    self.content_type = None
    self.mime_content_type = None

    open_mode = open_request.open_mode()
    content_type = open_request.content_type()

    if not self.filename.startswith(_BLOBSTORE_DIRECTORY):
      if not self.file_storage.has_blobstore_file(self.filename):
        raise_error(file_service_pb.FileServiceErrors.INVALID_FILE_NAME)

    self.ticket = self.filename[len(_BLOBSTORE_DIRECTORY):]

    if open_mode == file_service_pb.OpenRequest.APPEND:
      if not self.file_storage.has_blobstore_file(self.filename):
        raise_error(file_service_pb.FileServiceErrors.EXISTENCE_ERROR)

      self.mime_content_type = self.file_storage.get_content_type(self.filename)
      self.blob_file_name = self.file_storage.get_blob_file_name(self.filename)
    else:
      blob_info = blobstore.BlobInfo.get(self.ticket)
      if not blob_info:
        raise_error(file_service_pb.FileServiceErrors.FINALIZATION_ERROR)
      self.blob_reader = blobstore.BlobReader(blob_info)
      self.mime_content_type = blob_info.content_type
    if content_type != file_service_pb.FileContentType.RAW:
      raise_error(file_service_pb.FileServiceErrors.WRONG_CONTENT_TYPE)

    if self.file_storage.is_finalized(self.filename):
      raise_error(file_service_pb.FileServiceErrors.FINALIZATION_ERROR,
                  'File is already finalized')

  def read(self, request, response):
    """Read data from file

    Args:
      request: An instance of file_service_pb.ReadRequest.
      response: An instance of file_service_pb.ReadResponse.
    """
    if not self.blob_reader:
      raise_error(file_service_pb.FileServiceErrors.WRONG_OPEN_MODE)
    self.blob_reader.seek(request.pos())
    response.set_data(self.blob_reader.read(request.max_bytes()))

  def append(self, request, response):
    """Append data to file.

    Args:
      request: An instance of file_service_pb.AppendRequest.
      response: An instance of file_service_pb.AppendResponse.
    """
    sequence_key = request.sequence_key()

    if sequence_key:
      current_sequence_key = self.file_storage.get_sequence_key(self.filename)
      if current_sequence_key and current_sequence_key >= sequence_key:
        raise_error(file_service_pb.FileServiceErrors.SEQUENCE_KEY_OUT_OF_ORDER,
                    error_detail=current_sequence_key)
      self.file_storage.set_sequence_key(self.filename, sequence_key)
    self.file_storage.append(self.filename, request.data())

  def finalize(self):
    """Finalize a file.

    Copies temp file data to the blobstore.
    """
    self.file_storage.finalize(self.filename)
    blob_key = dev_appserver_upload.GenerateBlobKey()
    self.file_storage.register_blob_key(self.ticket, blob_key)

    size = self.file_storage.save_blob(self.filename, blob_key)
    blob_info = datastore.Entity('__BlobInfo__',
                                   name=str(blob_key),
                                   namespace='')
    blob_info['content_type'] = self.mime_content_type
    blob_info['creation'] = _now_function()
    blob_info['filename'] = self.blob_file_name
    blob_info['size'] = size
    blob_info['creation_handle'] = self.ticket
    datastore.Put(blob_info)

    blob_file = datastore.Entity('__BlobFileIndex__',
                                 name=self.ticket,
                                 namespace='')
    blob_file['blob_key'] = str(blob_key)
    datastore.Put(blob_file)


class FileServiceStub(apiproxy_stub.APIProxyStub):
  """Python stub for file service."""

  def __init__(self, blob_storage):
    """Constructor."""
    super(FileServiceStub, self).__init__('file',
                                          max_request_size=MAX_REQUEST_SIZE)
    self.open_files = {}
    self.file_storage = BlobstoreStorage(blob_storage)
    self.gs_storage = GoogleStorage()

  def _Dynamic_Create(self, request, response):
    filesystem = request.filesystem()

    if request.has_filename() and filesystem != gs._GS_FILESYSTEM:
      raise_error(file_service_pb.FileServiceErrors.FILE_NAME_SPECIFIED)

    if filesystem == files_blobstore._BLOBSTORE_FILESYSTEM:
      response.set_filename(self.file_storage.add_blobstore_file(request))
    elif filesystem == gs._GS_FILESYSTEM:
      response.set_filename(self.gs_storage.start_upload(request))
    else:
      raise_error(file_service_pb.FileServiceErrors.UNSUPPORTED_FILE_SYSTEM)

  def _Dynamic_Open(self, request, response):
    """Handler for Open RPC call."""
    filename = request.filename()
    content_type = request.content_type()
    open_mode = request.open_mode()

    if request.exclusive_lock() and filename in self.open_files:
      raise_error(file_service_pb.FileServiceErrors.EXCLUSIVE_LOCK_FAILED)

    if filename.startswith(_BLOBSTORE_DIRECTORY):
      self.open_files[filename] = BlobstoreFile(request, self.file_storage)
    elif filename.startswith(_GS_PREFIX):
      self.open_files[filename] = GoogleStorageFile(request, self.gs_storage)
    else:
      raise_error(file_service_pb.FileServiceErrors.INVALID_FILE_NAME)

  def _Dynamic_Close(self, request, response):
    """Handler for Close RPC call."""
    filename = request.filename()
    finalize = request.finalize()

    if not filename in self.open_files:
      raise_error(file_service_pb.FileServiceErrors.FILE_NOT_OPENED)

    if finalize:
      self.open_files[filename].finalize()

    del self.open_files[filename]

  def _Dynamic_Read(self, request, response):
    """Handler for Read RPC call."""
    filename = request.filename()

    if not filename in self.open_files:
      raise_error(file_service_pb.FileServiceErrors.FILE_NOT_OPENED)

    self.open_files[filename].read(request, response)

  def _Dynamic_Append(self, request, response):
    """Handler for Append RPC call."""
    filename = request.filename()

    if not filename in self.open_files:
      raise_error(file_service_pb.FileServiceErrors.FILE_NOT_OPENED)

    self.open_files[filename].append(request, response)

  def _Dynamic_GetCapabilities(self, request, response):
    """Handler for GetCapabilities RPC call."""
    response.add_filesystem('blobstore')
    response.add_filesystem('gs')
    response.set_shuffle_available(False)
