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
import sys

from google.appengine.api import apiproxy_stub_map
from google.appengine.api import blobstore
from google.appengine.api import datastore
from google.appengine.api import datastore_errors
from google.appengine.tools import dev_appserver_upload

from webob import byterange



UPLOAD_URL_PATH = '_ah/upload/'


UPLOAD_URL_PATTERN = '/%s(.*)' % UPLOAD_URL_PATH


def GetBlobStorage():
  """Get blob-storage from api-proxy stub map.

  Returns:
    BlobStorage instance as registered with blobstore API in stub map.
  """
  return apiproxy_stub_map.apiproxy.GetStub('blobstore').storage


def ParseRangeHeader(range_header):
  """Parse HTTP Range header.

  Args:
    range_header: Range header as retrived from Range or X-AppEngine-BlobRange.

  Returns:
    Tuple (start, end):
      start: Start index of blob to retrieve.  May be negative index.
      end: None or end index.  End index is inclusive.
    (None, None) if there is a parse error.
  """
  if not range_header:
    return None, None


  original_stdout = sys.stdout
  sys.stdout = cStringIO.StringIO()
  try:
    parsed_range = byterange.Range.parse_bytes(range_header)
  finally:
    sys.stdout = original_stdout
  if parsed_range:
    range_tuple = parsed_range[1]
    if len(range_tuple) == 1:
      return range_tuple[0]
  return None, None


class _FixedContentRange(byterange.ContentRange):
  """Corrected version of byterange.ContentRange class.

  The version of byterange.ContentRange that comes with the SDK has
  a bug that has since been corrected in newer versions.  It treats
  content ranges as if they are specified as end-index exclusive.
  Content ranges are meant to be inclusive.  This sub-class partially
  fixes the bug in order to allow content-range header parsing.

  The fix works by adding 1 to the stop parameter in the constructor.
  This is necessary to handle content-ranges where the start index
  is equal to the end index.
  """

  def __init__(self, start, stop, length):
    stop = stop + 1
    super(_FixedContentRange, self).__init__(start, stop, length)


def ParseContentRangeHeader(content_range_header):
  """Parse HTTP Content-Range header.

  Args:
    content_range_header: Content-Range header.

  Returns:
    Tuple (start, end):
      start: Start index of blob to retrieve.  May be negative index.
      end: None or end index.  End index is inclusive.
    (None, None) if there is a parse error.
  """
  if not content_range_header:
    return None
  parsed_content_range = _FixedContentRange.parse(content_range_header)
  if parsed_content_range:

    return parsed_content_range.start, parsed_content_range.stop
  return None, None


def DownloadRewriter(response, request_headers):
  """Intercepts blob download key and rewrites response with large download.

  Checks for the X-AppEngine-BlobKey header in the response.  If found, it will
  discard the body of the request and replace it with the blob content
  indicated.

  If a valid blob is not found, it will send a 404 to the client.

  If the application itself provides a content-type header, it will override
  the content-type stored in the action blob.

  If Content-Range header is provided, blob will be partially served.  The
  application can set blobstore.BLOB_RANGE_HEADER if the size of the blob is
  not known.  If Range is present, and not blobstore.BLOB_RANGE_HEADER, will
  use Range instead.

  Args:
    response: Response object to be rewritten.
    request_headers: Original request headers.  Looks for 'Range' header to copy
      to response.
  """
  blob_key = response.headers.getheader(blobstore.BLOB_KEY_HEADER)
  if blob_key:
    del response.headers[blobstore.BLOB_KEY_HEADER]


    try:
      blob_info = datastore.Get(
          datastore.Key.from_path(blobstore.BLOB_INFO_KIND,
                                  blob_key,
                                  namespace=''))

      content_range_header = response.headers.getheader('Content-Range')
      blob_size = blob_info['size']
      range_header = response.headers.getheader(blobstore.BLOB_RANGE_HEADER)
      if range_header is not None:
        del response.headers[blobstore.BLOB_RANGE_HEADER]
      else:
        range_header = request_headers.getheader('Range')

      def not_satisfiable():
        """Short circuit response and return 416 error."""
        response.status_code = 416
        response.status_message = 'Requested Range Not Satisfiable'
        response.body = cStringIO.StringIO('')
        response.headers['Content-Length'] = '0'
        del response.headers['Content-Type']
        del response.headers['Content-Range']

      if range_header:
        start, end = ParseRangeHeader(range_header)
        if start is not None:
          if end is None:
            if start >= 0:
              content_range_start = start
            else:
              content_range_start = blob_size + start
            content_range = byterange.ContentRange(
                content_range_start, blob_size - 1, blob_size)


            content_range.stop -= 1
            content_range_header = str(content_range)
          else:
            range = byterange.ContentRange(start, end, blob_size)


            range.stop -= 1
            content_range_header = str(range)
          response.headers['Content-Range'] = content_range_header
        else:
          not_satisfiable()
          return

      content_range = response.headers.getheader('Content-Range')
      content_length = blob_size
      start = 0
      end = content_length
      if content_range is not None:
        parsed_start, parsed_end = ParseContentRangeHeader(content_range)
        if parsed_start is not None:
          start = parsed_start
          content_range = byterange.ContentRange(start,
                                                 parsed_end,
                                                 blob_size)


          content_range.stop -= 1
          content_range.stop = min(content_range.stop, blob_size - 2)
          content_length = min(parsed_end, blob_size - 1) - start + 1
          response.headers['Content-Range'] = str(content_range)
        else:
          not_satisfiable()
          return

      blob_stream = GetBlobStorage().OpenBlob(blob_key)
      blob_stream.seek(start)
      response.body = cStringIO.StringIO(blob_stream.read(content_length))
      response.headers['Content-Length'] = str(content_length)

      if not response.headers.getheader('Content-Type'):
        response.headers['Content-Type'] = blob_info['content_type']
      response.large_response = True



    except datastore_errors.EntityNotFoundError:

      response.status_code = 500
      response.status_message = 'Internal Error'
      response.body = cStringIO.StringIO()

      if response.headers.getheader('status'):
        del response.headers['status']
      if response.headers.getheader('location'):
        del response.headers['location']
      if response.headers.getheader('content-type'):
        del response.headers['content-type']

      logging.error('Could not find blob with key %s.', blob_key)


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

        upload_form = cgi.FieldStorage(fp=request.infile,
                                       headers=request.headers,
                                       environ=base_env_dict)

        try:


          mime_message_string = self.__cgi_handler.GenerateMIMEMessageString(
              upload_form)
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
      else:
        logging.error('Could not find session for %s', upload_key)
        outfile.write('Status: 404\n\n')


    def EndRedirect(self, redirected_outfile, original_outfile):
      """Handle the end of upload complete notification.

      Makes sure the application upload handler returned an appropriate status
      code.
      """
      response = dev_appserver.RewriteResponse(redirected_outfile)
      logging.info('Upload handler returned %d', response.status_code)

      if (response.status_code in (301, 302, 303) and
          (not response.body or len(response.body.read()) == 0)):
        contentless_outfile = cStringIO.StringIO()


        contentless_outfile.write('Status: %s\n' % response.status_code)
        contentless_outfile.write(''.join(response.headers.headers))
        contentless_outfile.seek(0)
        dev_appserver.URLDispatcher.EndRedirect(self,
                                                contentless_outfile,
                                                original_outfile)
      else:
        logging.error(
            'Invalid upload handler response. Only 301, 302 and 303 '
            'statuses are permitted and it may not have a content body.')
        original_outfile.write('Status: 500\n\n')

  return UploadDispatcher()
