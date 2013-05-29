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




"""Blobstore support classes.

Classes:

  DownloadRewriter:
    Rewriter responsible for transforming an application response to one
    that serves a blob to the user.

  CreateUploadDispatcher:
    Creates a dispatcher that is added to dispatcher chain.  Handles uploads
    by storing blobs rewriting requests and returning a redirect.
"""



import cgi
import cStringIO
import logging
import mimetools
import re

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import blobstore
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.api.files import file_service_stub
from google.appengine.tools import dev_appserver_upload



UPLOAD_URL_PATH = '_ah/upload/'


UPLOAD_URL_PATTERN = '/%s(.*)' % UPLOAD_URL_PATH


AUTO_MIME_TYPE = 'application/vnd.google.appengine.auto'


ERROR_RESPONSE_TEMPLATE = """
<html>
  <head>
    <title>%(response_code)d %(response_string)s</title>
  </head>
  <body text=#000000 bgcolor=#ffffff>
    <h1>Error: %(response_string)s</h1>
    <h2>%(response_text)s</h2>
  </body>
</html>
"""


def GetBlobStorage():
  """Get blob-storage from api-proxy stub map.

  Returns:
    BlobStorage instance as registered with blobstore API in stub map.
  """
  return apiproxy_stub_map.apiproxy.GetStub('blobstore').storage


def ParseRangeHeader(range_header):
  """Parse HTTP Range header.

  Args:
    range_header: A str representing the value of a range header as retrived
      from Range or X-AppEngine-BlobRange.

  Returns:
    Tuple (start, end):
      start: Start index of blob to retrieve.  May be negative index.
      end: None or end index.  End index is exclusive.
    (None, None) if there is a parse error.
  """
  if not range_header:
    return None, None
  try:

    range_type, ranges = range_header.split('=', 1)
    if range_type != 'bytes':
      return None, None
    ranges = ranges.lstrip()
    if ',' in ranges:
      return None, None
    end = None
    if ranges.startswith('-'):
      start = int(ranges)
      if start == 0:
        return None, None
    else:
      split_range = ranges.split('-', 1)
      start = int(split_range[0])
      if len(split_range) == 2 and split_range[1].strip():
        end = int(split_range[1]) + 1
        if start > end:
          return None, None
    return start, end
  except ValueError:
    return None, None


def _GetGoogleStorageFileMetadata(blob_key):
  """Retreive metadata about a GS blob from the blob_key.

  Args:
    blob_key: The BlobKey of the blob.

  Returns:
    Tuple (size, content_type, open_key):
      size: The size of the blob.
      content_type: The content type of the blob.
      open_key: The key used as an argument to BlobStorage to open the blob
        for reading.
    (None, None, None) if the blob metadata was not found.
  """
  try:
    gs_info = datastore.Get(
        datastore.Key.from_path(file_service_stub.GS_INFO_KIND,
                                blob_key,
                                namespace=''))
    return gs_info['size'], gs_info['content_type'], gs_info['storage_key']
  except datastore_errors.EntityNotFoundError:
    return None, None, None


def _GetBlobstoreMetadata(blob_key):
  """Retreive metadata about a blobstore blob from the blob_key.

  Args:
    blob_key: The BlobKey of the blob.

  Returns:
    Tuple (size, content_type, open_key):
      size: The size of the blob.
      content_type: The content type of the blob.
      open_key: The key used as an argument to BlobStorage to open the blob
        for reading.
    (None, None, None) if the blob metadata was not found.
  """
  try:
    blob_info = datastore.Get(
        datastore.Key.from_path(blobstore.BLOB_INFO_KIND,
                                blob_key,
                                namespace=''))
    return blob_info['size'], blob_info['content_type'], blob_key
  except datastore_errors.EntityNotFoundError:
    return None, None, None


def _GetBlobMetadata(blob_key):
  """Retrieve the metadata about a blob from the blob_key.

  Args:
    blob_key: The BlobKey of the blob.

  Returns:
    Tuple (size, content_type, open_key):
      size: The size of the blob.
      content_type: The content type of the blob.
      open_key: The key used as an argument to BlobStorage to open the blob
        for reading.
    (None, None, None) if the blob metadata was not found.
  """
  size, content_type, open_key = _GetGoogleStorageFileMetadata(blob_key)
  if size is None:
    size, content_type, open_key = _GetBlobstoreMetadata(blob_key)
  return size, content_type, open_key


def _SetRangeRequestNotSatisfiable(response, blob_size):
  """Short circuit response and return 416 error.

  Args:
    response: Response object to be rewritten.
    blob_size: The size of the blob.
  """
  response.status_code = 416
  response.status_message = 'Requested Range Not Satisfiable'
  response.body = cStringIO.StringIO('')
  response.headers['Content-Length'] = '0'
  response.headers['Content-Range'] = '*/%d' % blob_size
  del response.headers['Content-Type']


def DownloadRewriter(response, request_headers):
  """Intercepts blob download key and rewrites response with large download.

  Checks for the X-AppEngine-BlobKey header in the response.  If found, it will
  discard the body of the request and replace it with the blob content
  indicated.

  If a valid blob is not found, it will send a 404 to the client.

  If the application itself provides a content-type header, it will override
  the content-type stored in the action blob.

  If blobstore.BLOB_RANGE_HEADER header is provided, blob will be partially
  served.  If Range is present, and not blobstore.BLOB_RANGE_HEADER, will use
  Range instead.

  Args:
    response: Response object to be rewritten.
    request_headers: Original request headers.  Looks for 'Range' header to copy
      to response.
  """
  blob_key = response.headers.getheader(blobstore.BLOB_KEY_HEADER)
  if blob_key:
    del response.headers[blobstore.BLOB_KEY_HEADER]

    blob_size, blob_content_type, blob_open_key = _GetBlobMetadata(blob_key)

    range_header = response.headers.getheader(blobstore.BLOB_RANGE_HEADER)
    if range_header is not None:
      del response.headers[blobstore.BLOB_RANGE_HEADER]
    else:
      range_header = request_headers.getheader('Range')



    if (blob_size is not None and blob_content_type is not None and
        response.status_code == 200):
      content_length = blob_size
      start = 0
      end = content_length

      if range_header:
        start, end = ParseRangeHeader(range_header)
        if start is None:
          _SetRangeRequestNotSatisfiable(response, blob_size)
          return
        else:
          if start < 0:
            start = max(blob_size + start, 0)
          elif start >= blob_size:
            _SetRangeRequestNotSatisfiable(response, blob_size)
            return
          if end is not None:
            end = min(end, blob_size)
          else:
            end = blob_size
          content_length = min(end, blob_size) - start
          end = start + content_length
          response.status_code = 206
          response.status_message = 'Partial Content'
          response.headers['Content-Range'] = 'bytes %d-%d/%d' % (
              start, end - 1, blob_size)

      blob_stream = GetBlobStorage().OpenBlob(blob_open_key)
      blob_stream.seek(start)
      response.body = cStringIO.StringIO(blob_stream.read(content_length))
      response.headers['Content-Length'] = str(content_length)

      content_type = response.headers.getheader('Content-Type')
      if not content_type or content_type == AUTO_MIME_TYPE:
        response.headers['Content-Type'] = blob_content_type
      response.large_response = True

    else:

      if response.status_code != 200:
        logging.error('Blob-serving response with status %d, expected 200.',
                      response.status_code)
      else:
        logging.error('Could not find blob with key %s.', blob_key)

      response.status_code = 500
      response.status_message = 'Internal Error'
      response.body = cStringIO.StringIO()

      if response.headers.getheader('content-type'):
        del response.headers['content-type']
      response.headers['Content-Length'] = '0'


def CreateUploadDispatcher(get_blob_storage=GetBlobStorage):
  """Function to create upload dispatcher.

  Returns:
    New dispatcher capable of handling large blob uploads.
  """


  from google.appengine.tools import dev_appserver

  class UploadDispatcher(dev_appserver.URLDispatcher):
    """Dispatcher that handles uploads."""

    def __init__(self):
      """Constructor.

      Args:
        blob_storage: A BlobStorage instance.
      """
      self.__cgi_handler = dev_appserver_upload.UploadCGIHandler(
          get_blob_storage())



    def Dispatch(self,
                 request,
                 outfile,
                 base_env_dict=None):
      """Handle post dispatch.

      This dispatcher will handle all uploaded files in the POST request, store
      the results in the blob-storage, close the upload session and transform
      the original request in to one where the uploaded files have external
      bodies.

      Returns:
        New AppServerRequest indicating request forward to upload success
        handler.
      """

      if base_env_dict['REQUEST_METHOD'] != 'POST':
        outfile.write('Status: 400\n\n')
        return


      upload_key = re.match(UPLOAD_URL_PATTERN, request.relative_url).group(1)
      try:
        upload_session = datastore.Get(upload_key)
      except datastore_errors.EntityNotFoundError:
        upload_session = None

      if upload_session:
        success_path = upload_session['success_path']
        max_bytes_per_blob = upload_session['max_bytes_per_blob']
        max_bytes_total = upload_session['max_bytes_total']
        bucket_name = upload_session.get('gs_bucket_name', None)

        upload_form = cgi.FieldStorage(fp=request.infile,
                                       headers=request.headers,
                                       environ=base_env_dict)

        try:


          mime_message_string = self.__cgi_handler.GenerateMIMEMessageString(
              upload_form,
              max_bytes_per_blob=max_bytes_per_blob,
              max_bytes_total=max_bytes_total,
              bucket_name=bucket_name)

          datastore.Delete(upload_session)
          self.current_session = upload_session


          header_end = mime_message_string.find('\n\n') + 1
          content_start = header_end + 1
          header_text = mime_message_string[:header_end].replace('\n', '\r\n')
          content_text = mime_message_string[content_start:].replace('\n',
                                                                     '\r\n')


          complete_headers = ('%s'
                              'Content-Length: %d\r\n'
                              '\r\n') % (header_text, len(content_text))

          return dev_appserver.AppServerRequest(
              success_path,
              None,
              mimetools.Message(cStringIO.StringIO(complete_headers)),
              cStringIO.StringIO(content_text),
              force_admin=True)
        except dev_appserver_upload.InvalidMIMETypeFormatError:
          outfile.write('Status: 400\n\n')
        except dev_appserver_upload.UploadEntityTooLargeError:
          outfile.write('Status: 413\n\n')
          response = ERROR_RESPONSE_TEMPLATE % {
              'response_code': 413,
              'response_string': 'Request Entity Too Large',
              'response_text': 'Your client issued a request that was too '
              'large.'}
          outfile.write(response)
        except dev_appserver_upload.FilenameOrContentTypeTooLargeError, ex:
          outfile.write('Status: 400\n\n')
          response = ERROR_RESPONSE_TEMPLATE % {
              'response_code': 400,
              'response_string': 'Bad Request',
              'response_text': str(ex)}
          outfile.write(response)
      else:
        logging.error('Could not find session for %s', upload_key)
        outfile.write('Status: 404\n\n')


    def EndRedirect(self, dispatched_output, original_output):
      """Handle the end of upload complete notification.

      Makes sure the application upload handler returned an appropriate status
      code.
      """
      response = dev_appserver.RewriteResponse(dispatched_output)
      logging.info('Upload handler returned %d', response.status_code)
      outfile = cStringIO.StringIO()
      outfile.write('Status: %s\n' % response.status_code)

      if response.body and len(response.body.read()) > 0:
        response.body.seek(0)
        outfile.write(response.body.read())
      else:
        outfile.write(''.join(response.headers.headers))

      outfile.seek(0)
      dev_appserver.URLDispatcher.EndRedirect(self,
                                              outfile,
                                              original_output)

  return UploadDispatcher()
