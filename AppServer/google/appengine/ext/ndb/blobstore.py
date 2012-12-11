"""NDB interface for Blobstore.

This currently builds on google.appengine.ext.blobstore and provides a
similar API.  The main API differences:

- BlobInfo is an actual Model subclass rather than a pseudo-model class.
  To query, use BlobInfo.query() and its documented properties.  Other
  changes:
  - The kind is '__BlobInfo__' (BLOB_INFO_KIND).
  - key() is a method returning a BlobKey instance.
  - put() and friends are disabled.
  - Added class methods get() and friends.
  - Added instance methods delete() and friends, and open().

- Instead of BlobReferenceProperty, there's BlobKeyProperty.

- There is no create_rpc() function.  Instead, functions and methods
  take keyword arguments to specify deadline, callback, and (in some
  case) datastore options.

- APIs (get() and delete()) that in ext.blobstore take either a blob
  key or a list of blob keys are split into two: one that takes a blob
  key and one that takes a list of blob keys, the latter having a name
  ending in _multi.

- The following APIs have a synchronous and an async version:
  - BlobInfo.get()
  - BlobInfo.delete()
  - create_upload_url()
  - get()
  - get_multi()
  - delete()
  - delete_multi()
  - fetch_data()
"""

# TODO: Should delete() and friends accept BlobInfos too?
# TODO: Don't have redundant function/method versions of APIs?
# TODO: Refactor ext.blobstore to reduce duplication of code.

import base64
import email

from .google_imports import api_blobstore as blobstore
from .google_imports import ext_blobstore

from . import model
from . import tasklets

__all__ = ['BLOB_INFO_KIND',
           'BLOB_KEY_HEADER',
           'BLOB_MIGRATION_KIND',
           'BLOB_RANGE_HEADER',
           'BlobFetchSizeTooLargeError',
           'BlobInfo',
           'BlobInfoParseError',
           'BlobKey',
           'BlobNotFoundError',
           'BlobKeyProperty',
           'BlobReader',
           'DataIndexOutOfRangeError',
           'PermissionDeniedError',
           'Error',
           'InternalError',
           'MAX_BLOB_FETCH_SIZE',
           'UPLOAD_INFO_CREATION_HEADER',
           'create_upload_url',
           'create_upload_url_async',
           'delete',
           'delete_async',
           'delete_multi',
           'delete_multi_async',
           'fetch_data',
           'fetch_data_async',
           'get',
           'get_async',
           'get_multi',
           'get_multi_async',
           'parse_blob_info']

# Exceptions are all imported.
Error = blobstore.Error
InternalError = blobstore.InternalError
BlobFetchSizeTooLargeError = blobstore.BlobFetchSizeTooLargeError
BlobNotFoundError = blobstore.BlobNotFoundError
_CreationFormatError = blobstore._CreationFormatError
DataIndexOutOfRangeError = blobstore.DataIndexOutOfRangeError
PermissionDeniedError = blobstore.PermissionDeniedError
BlobInfoParseError = ext_blobstore.BlobInfoParseError

# So is BlobKey.
BlobKey = blobstore.BlobKey

# And the constants.
BLOB_INFO_KIND = blobstore.BLOB_INFO_KIND
BLOB_MIGRATION_KIND = blobstore.BLOB_MIGRATION_KIND
BLOB_KEY_HEADER = blobstore.BLOB_KEY_HEADER
BLOB_RANGE_HEADER = blobstore.BLOB_RANGE_HEADER
MAX_BLOB_FETCH_SIZE = blobstore.MAX_BLOB_FETCH_SIZE
UPLOAD_INFO_CREATION_HEADER = blobstore.UPLOAD_INFO_CREATION_HEADER

# Re-export BlobKeyProperty from ndb.model for completeness.
BlobKeyProperty = model.BlobKeyProperty


class BlobInfo(model.Model):
  """Information about blobs in Blobstore.

  This is a Model subclass that has been doctored to be unwritable.

  Properties:
  - content_type: Content type of blob.
  - creation: Creation date of blob, when it was uploaded.
  - filename: Filename user selected from their machine.
  - size: Size of uncompressed blob.
  - md5_hash: The md5 hash value of the uploaded blob (in hex).

  Additional API:

  Class methods:
  - get(): retrieve a BlobInfo by key
  - get_multi(): retrieve a list of BlobInfos by keys
  - get_async(), get_multi_async(): async version of get() and get_multi()

  Instance methods:
  - delete(): delete this blob
  - delete_async(): async version of delete()
  - key(): return the BlobKey for this blob
  - open(): return a BlobReader instance for this blob

  Because BlobInfo instances are synchronized with Blobstore, the class
  cache policies are off.

  Do not subclass this class.
  """

  _use_cache = False
  _use_memcache = False

  content_type = model.StringProperty()
  creation = model.DateTimeProperty()
  filename = model.StringProperty()
  size = model.IntegerProperty()
  md5_hash = model.StringProperty()

  @classmethod
  def _get_kind(cls):
    """Override this to match the datastore entities written by Blobstore."""
    return BLOB_INFO_KIND  # __BlobInfo__

  @classmethod
  def get(cls, blob_key, **ctx_options):
    """Retrieve a BlobInfo by key.

    Args:
      blob_key: A blob key.  This may be a str, unicode or BlobKey instance.
      **ctx_options: Context options for Model().get_by_id().

    Returns:
      A BlobInfo entity associated with the provided key,  If there was
      no such entity, returns None.
    """
    fut = cls.get_async(blob_key, **ctx_options)
    return fut.get_result()

  @classmethod
  def get_async(cls, blob_key, **ctx_options):
    """Async version of get()."""
    if not isinstance(blob_key, (BlobKey, basestring)):
      raise TypeError('Expected blob key, got %r' % (blob_key,))
    if 'parent' in ctx_options:
      raise TypeError('Parent is not supported')
    return cls.get_by_id_async(str(blob_key), **ctx_options)

  @classmethod
  def get_multi(cls, blob_keys, **ctx_options):
    """Multi-key version of get().

    Args:
      blob_keys: A list of blob keys.
      **ctx_options: Context options for Model().get_by_id().

    Returns:
      A list whose items are each either a BlobInfo entity or None.
    """
    futs = cls.get_multi_async(blob_keys, **ctx_options)
    return [fut.get_result() for fut in futs]

  @classmethod
  def get_multi_async(cls, blob_keys, **ctx_options):
    """Async version of get_multi()."""
    for blob_key in blob_keys:
      if not isinstance(blob_key, (BlobKey, basestring)):
        raise TypeError('Expected blob key, got %r' % (blob_key,))
    if 'parent' in ctx_options:
      raise TypeError('Parent is not supported')
    blob_key_strs = map(str, blob_keys)
    keys = [model.Key(BLOB_INFO_KIND, id) for id in blob_key_strs]
    return model.get_multi_async(keys, **ctx_options)

  def _put_async(self, **ctx_options):
    """Cheap way to make BlobInfo entities read-only."""
    raise TypeError('BlobInfo is read-only')
  put_async = _put_async

  def key(self):
    """Get key for blob.

    Returns:
      BlobKey instance that identifies this blob.
    """
    # TODO: Cache this?
    return BlobKey(self._key.id())

  def delete(self, **options):
    """Permanently delete this blob from Blobstore.

    Args:
      **options: Options for create_rpc().
    """
    fut = delete_async(self.key(), **options)
    fut.get_result()

  def delete_async(self, **options):
    """Async version of delete()."""
    return delete_async(self.key(), **options)  # A Future!

  def open(self, *args, **kwds):
    """Returns a BlobReader for this blob.

    Args:
      *args, **kwargs: Passed to BlobReader constructor.

    Returns:
      A BlobReader instance.
    """
    return BlobReader(self, *args, **kwds)


get = BlobInfo.get
get_async = BlobInfo.get_async
get_multi = BlobInfo.get_multi
get_multi_async = BlobInfo.get_multi_async


def delete(blob_key, **options):
  """Delete a blob from Blobstore.

  Args:
    blob_key: A blob key.  This may be a str, unicode or BlobKey instance.
    **options: Options for create_rpc().
  """
  fut = delete_async(blob_key, **options)
  return fut.get_result()


@tasklets.tasklet
def delete_async(blob_key, **options):
  """Async version of delete()."""
  if not isinstance(blob_key, (basestring, BlobKey)):
    raise TypeError('Expected blob key, got %r' % (blob_key,))
  rpc = blobstore.create_rpc(**options)
  yield blobstore.delete_async(blob_key, rpc=rpc)


def delete_multi(blob_keys, **options):
  """Delete blobs from Blobstore.

  Args:
    blob_keys: A list of blob keys.
    **options: Options for create_rpc().
  """
  fut = delete_multi_async(blob_keys, **options)
  fut.get_result()


@tasklets.tasklet
def delete_multi_async(blob_keys, **options):
  """Async version of delete_multi()."""
  if isinstance(blob_keys, (basestring, BlobKey)):
    raise TypeError('Expected a list, got %r' % (blob_key,))
  rpc = blobstore.create_rpc(**options)
  yield blobstore.delete_async(blob_keys, rpc=rpc)


def create_upload_url(success_path,
                      max_bytes_per_blob=None,
                      max_bytes_total=None,
                      **options):
  """Create upload URL for POST form.

  Args:
    success_path: Path within application to call when POST is successful
      and upload is complete.
    max_bytes_per_blob: The maximum size in bytes that any one blob in the
      upload can be or None for no maximum size.
    max_bytes_total: The maximum size in bytes that the aggregate sizes of all
      of the blobs in the upload can be or None for no maximum size.
    **options: Options for create_rpc().

  Returns:
    The upload URL.

  Raises:
    TypeError: If max_bytes_per_blob or max_bytes_total are not integral types.
    ValueError: If max_bytes_per_blob or max_bytes_total are not
      positive values.
  """
  fut = create_upload_url_async(success_path,
                                max_bytes_per_blob=max_bytes_per_blob,
                                max_bytes_total=max_bytes_total,
                                **options)
  return fut.get_result()


@tasklets.tasklet
def create_upload_url_async(success_path,
                      max_bytes_per_blob=None,
                      max_bytes_total=None,
                      **options):
  """Async version of create_upload_url()."""
  rpc = blobstore.create_rpc(**options)
  rpc = blobstore.create_upload_url_async(success_path,
                                          max_bytes_per_blob=max_bytes_per_blob,
                                          max_bytes_total=max_bytes_total,
                                          rpc=rpc)
  result = yield rpc
  raise tasklets.Return(result)


def parse_blob_info(field_storage):
  """Parse a BlobInfo record from file upload field_storage.

  Args:
    field_storage: cgi.FieldStorage that represents uploaded blob.

  Returns:
    BlobInfo record as parsed from the field-storage instance.
    None if there was no field_storage.

  Raises:
    BlobInfoParseError when provided field_storage does not contain enough
    information to construct a BlobInfo object.
  """
  if field_storage is None:
    return None

  field_name = field_storage.name

  def get_value(dct, name):
    value = dct.get(name, None)
    if value is None:
      raise BlobInfoParseError(
          'Field %s has no %s.' % (field_name, name))
    return value

  filename = get_value(field_storage.disposition_options, 'filename')
  blob_key_str = get_value(field_storage.type_options, 'blob-key')
  blob_key = BlobKey(blob_key_str)

  upload_content = email.message_from_file(field_storage.file)
  content_type = get_value(upload_content, 'content-type')
  size = get_value(upload_content, 'content-length')
  creation_string = get_value(upload_content, UPLOAD_INFO_CREATION_HEADER)
  md5_hash_encoded = get_value(upload_content, 'content-md5')
  md5_hash = base64.urlsafe_b64decode(md5_hash_encoded)

  try:
    size = int(size)
  except (TypeError, ValueError):
    raise BlobInfoParseError(
        '%s is not a valid value for %s size.' % (size, field_name))

  try:
    creation = blobstore._parse_creation(creation_string, field_name)
  except blobstore._CreationFormatError, err:
    raise BlobInfoParseError(str(err))

  return BlobInfo(id=blob_key_str,
                  content_type=content_type,
                  creation=creation,
                  filename=filename,
                  size=size,
                  md5_hash=md5_hash,
                  )


def fetch_data(blob, start_index, end_index, **options):
  """Fetch data for blob.

  Fetches a fragment of a blob up to MAX_BLOB_FETCH_SIZE in length.  Attempting
  to fetch a fragment that extends beyond the boundaries of the blob will return
  the amount of data from start_index until the end of the blob, which will be
  a smaller size than requested.  Requesting a fragment which is entirely
  outside the boundaries of the blob will return empty string.  Attempting
  to fetch a negative index will raise an exception.

  Args:
    blob: BlobInfo, BlobKey, str or unicode representation of BlobKey of
      blob to fetch data from.
    start_index: Start index of blob data to fetch.  May not be negative.
    end_index: End index (inclusive) of blob data to fetch.  Must be
      >= start_index.
    **options: Options for create_rpc().

  Returns:
    str containing partial data of blob.  If the indexes are legal but outside
    the boundaries of the blob, will return empty string.

  Raises:
    TypeError if start_index or end_index are not indexes.  Also when blob
      is not a string, BlobKey or BlobInfo.
    DataIndexOutOfRangeError when start_index < 0 or end_index < start_index.
    BlobFetchSizeTooLargeError when request blob fragment is larger than
      MAX_BLOB_FETCH_SIZE.
    BlobNotFoundError when blob does not exist.
  """
  fut = fetch_data_async(blob, start_index, end_index, **options)
  return fut.get_result()


@tasklets.tasklet
def fetch_data_async(blob, start_index, end_index, **options):
  """Async version of fetch_data()."""
  if isinstance(blob, BlobInfo):
    blob = blob.key()
  rpc = blobstore.create_rpc(**options)
  rpc = blobstore.fetch_data_async(blob, start_index, end_index, rpc=rpc)
  result = yield rpc
  raise tasklets.Return(result)


class BlobReader(ext_blobstore.BlobReader):
  """Provides a read-only file-like interface to a blobstore blob."""

  # This just overrides two methods to use the proper versions.
  # Hack alert: this can access private attributes of the parent class
  # because it has the same class name.  (This is a Python feature.)

  def __fill_buffer(self, size=0):
    """Fills the internal buffer.

    Args:
      size: Number of bytes to read. Will be clamped to
        [self.__buffer_size, MAX_BLOB_FETCH_SIZE].
    """
    read_size = min(max(size, self.__buffer_size), MAX_BLOB_FETCH_SIZE)

    self.__buffer = fetch_data(self.__blob_key, self.__position,
                               self.__position + read_size - 1)
    self.__buffer_position = 0
    self.__eof = len(self.__buffer) < read_size

  @property
  def blob_info(self):
    """Returns the BlobInfo for this file."""
    if not self.__blob_info:
      self.__blob_info = BlobInfo.get(self.__blob_key)
    return self.__blob_info
