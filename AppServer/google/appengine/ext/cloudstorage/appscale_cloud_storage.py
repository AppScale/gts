""" Implements a Cloud Storage stub using an AppScale Cloud Storage server. """
import base64
import httplib
import urlparse

import requests

from google.appengine.ext.cloudstorage import common


class InternalError(Exception):
  """ Indicates that there was a problem fulfilling an API request. """
  pass


class AppScaleCloudStorageStub(object):
  """ A Cloud Storage stub implementation.

  Uses an AppScale Cloud Storage server to store files.

  Note: this Cloud Storage stub is designed to work with
  apphosting.ext.cloudstorage.storage_api.py.
  It only implements the part of GCS storage_api.py uses, and its interface
  maps to GCS XML APIs.
  """

  def __init__(self, acs_location):
    """Initialize.

    Args:
      acs_location: The location of an AppScale Cloud Storage server.
    """
    self.location = acs_location

  def post_start_creation(self, filename, options):
    """Start object creation with a POST.

    This uses the resumable upload XML API.

    Args:
      filename: gs filename of form /bucket/filename.
      options: a dict containing all user specified request headers.
        e.g. {'content-type': 'foo', 'x-goog-meta-bar': 'bar'}.

    Returns:
      a token used for continuing upload. Also used as blobkey to store
    the content.
    """
    common.validate_file_path(filename)

    url = ''.join([self.location, filename])
    options['x-goog-resumable'] = 'start'

    response = requests.post(url, headers=options)

    # The API should response to the initial create call with a 201.
    if response.status_code != httplib.CREATED:
      raise InternalError(response.text)

    location = response.headers.get('Location')
    if location is None:
      raise InternalError('Missing location from response')

    query = urlparse.urlparse(location).query
    try:
      token = urlparse.parse_qs(query)['upload_id']
    except KeyError:
      raise InternalError('Upload ID missing from response')

    # To keep this class stateless, include the filename with the token.
    return base64.b64encode(':'.join([filename, token]))

  def put_continue_creation(self, token, content, content_range, last=False):
    """Continue object upload with PUTs.

    This uses the resumable upload XML API.

    Args:
      token: upload token returned by post_start_creation.
      content: object content.
      content_range: a (start, end) tuple specifying the content range of this
        chunk. Both are inclusive according to XML API.
      last: True if this is the last chunk of file content.

    Raises:
      ValueError: if token is invalid.
    """
    filename, token = base64.b64decode(token).split(':', 1)

    url = ''.join([self.location, filename, '?upload_id=', token])

    start, end = content_range
    total_size = '*'
    if last:
      total_size = end + 1
    range_header = 'bytes {}-{}/{}'.format(start, end, total_size)
    headers = {'Content-Length': len(content),
               'Content-Range': range_header}

    response = requests.put(url, headers=headers)

    # The API uses "308 Resume Incomplete" when the client needs to submit
    # more chunks to complete the blob.
    if not last and response.status_code != 308:
      raise InternalError(response.text)

    if last and response.status_code not in (httplib.OK, httplib.CREATED):
      raise InternalError(response.text)

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
    raise NotImplementedError()

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

    url = ''.join([self.location, filename])
    headers = {}
    if start != 0 or end is not None:
      headers['Range'] = 'bytes={}-{}'.format(start, end or '')

    response = requests.get(url, headers=headers)
    return response.content

  def head_object(self, filename):
    """Get file stat with a HEAD.

    Args:
      filename: gs filename of form '/bucket/filename'

    Returns:
      A CSFileStat object containing file stat. None if file doesn't exist.
    """
    raise NotImplementedError()

  def delete_object(self, filename):
    """Delete file with a DELETE.

    Args:
      filename: gs filename of form '/bucket/filename'

    Returns:
      True if file is deleted. False if file doesn't exist.
    """
    common.validate_file_path(filename)

    url = ''.join([self.location, filename])
    response = requests.delete(url)

    # The API uses a 204 to indicate that the delete was successful.
    if response.status_code == httplib.NO_CONTENT:
      return True

    if response.status_code == httplib.NOT_FOUND:
      return False

    raise InternalError(response.text)
