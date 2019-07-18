"""
This module allows FDB clients to cache directory mappings and invalidate
them when the schema changes.
"""
import logging
from collections import deque

from tornado import gen

from appscale.datastore.dbconstants import InternalError
from appscale.datastore.fdb.utils import fdb

logger = logging.getLogger(__name__)


class DirectoryCache(object):
  """ A simple cache that keeps track of directory prefixes. """

  # The location of the metadata version key. The value of this key is passed
  # to FDB clients at the start of every transaction.
  METADATA_KEY = b'\xff/metadataVersion'

  # The number of items to keep in the cache.
  SIZE = 2048

  def __init__(self, db, tornado_fdb, root_dir):
    self.root_dir = root_dir
    self._db = db
    self._tornado_fdb = tornado_fdb

    self._directory_dict = {}
    self._directory_keys = deque()
    self._metadata_version = None

  def __setitem__(self, key, value):
    if key not in self._directory_dict:
      self._directory_keys.append(key)
      if len(self._directory_keys) > self.SIZE:
        oldest_key = self._directory_keys.popleft()
        del self._directory_dict[oldest_key]

    self._directory_dict[key] = value

  def __getitem__(self, key):
    return self._directory_dict[key]

  def __contains__(self, item):
    return item in self._directory_dict

  def initialize(self):
    self._ensure_metadata_key(self._db)

  @gen.coroutine
  def get(self, tr, key):
    current_version = yield self._tornado_fdb.get(tr, self.METADATA_KEY)
    if not current_version.present():
      raise InternalError(u'The FDB cluster metadata key is missing')

    if current_version.value != self._metadata_version:
      self._metadata_version = current_version.value
      self._directory_dict.clear()
      self._directory_keys.clear()

    full_key = self.root_dir.get_path() + key
    if full_key not in self:
      # TODO: This can be made async.
      # This is performed in a separate transaction so that it can be retried
      # automatically and so that it's only added to the cache when the
      # directory has been successfully created.
      self[full_key] = fdb.directory.create_or_open(self._db, full_key)

    raise gen.Return(self[full_key])

  @fdb.transactional
  def _ensure_metadata_key(self, tr):
    current_version = tr[self.METADATA_KEY]
    if not current_version.present():
      logger.info(u'Setting metadata key for the first time')
      tr.set_versionstamped_value(self.METADATA_KEY, b'\x00' * 14)
