"""
This module allows FDB clients to cache directory mappings and invalidate
them when the schema changes.
"""
import logging
from collections import deque

from fdb.directory_impl import DirectorySubspace
from tornado import gen

from appscale.datastore.dbconstants import InternalError
from appscale.datastore.fdb.codecs import decode_str
from appscale.datastore.fdb.utils import KVIterator

logger = logging.getLogger(__name__)


class DirectoryCache(object):
  """ A simple directory cache that more specialized caches can extend. """

  # The location of the metadata version key. The value of this key is passed
  # to FDB clients at the start of every transaction.
  METADATA_KEY = b'\xff/metadataVersion'

  def __init__(self, tornado_fdb, root_dir, cache_size):
    self.root_dir = root_dir
    self._cache_size = cache_size
    self._directory_dict = {}
    self._directory_keys = deque()
    self._metadata_version = None
    self._tornado_fdb = tornado_fdb

  def __setitem__(self, key, value):
    if key not in self._directory_dict:
      self._directory_keys.append(key)
      if len(self._directory_keys) > self._cache_size:
        oldest_key = self._directory_keys.popleft()
        del self._directory_dict[oldest_key]

    self._directory_dict[key] = value

  def __getitem__(self, key):
    return self._directory_dict[key]

  def __contains__(self, item):
    return item in self._directory_dict

  @gen.coroutine
  def validate_cache(self, tr):
    """ Clears the cache if the metadata key has been updated. """
    current_version = yield self._tornado_fdb.get(tr, self.METADATA_KEY)
    if not current_version.present():
      raise InternalError(u'The FDB cluster metadata key is missing')

    if current_version.value != self._metadata_version:
      self._metadata_version = current_version.value
      self._directory_dict.clear()
      self._directory_keys.clear()

  @staticmethod
  def subdirs_subspace(directory):
    """
    Returns the subspace used by the directory layer to keep track of
    subdirectories.
    """
    dir_layer = directory._directory_layer
    parent_subspace = dir_layer._node_with_prefix(directory.rawPrefix)
    return parent_subspace.subspace((dir_layer.SUBDIRS,))

  def ensure_metadata_key(self, tr):
    current_version = tr[self.METADATA_KEY]
    if not current_version.present():
      logger.info(u'Setting metadata key for the first time')
      tr.set_versionstamped_value(self.METADATA_KEY, b'\x00' * 14)


class ProjectCache(DirectoryCache):
  """ A directory cache that keeps track of projects. """

  # The number of items the cache can hold.
  SIZE = 256

  def __init__(self, tornado_fdb, root_dir):
    super(ProjectCache, self).__init__(tornado_fdb, root_dir, self.SIZE)

  @gen.coroutine
  def get(self, tr, project_id):
    """ Gets a project's directory.

    Args:
      tr: An FDB transaction.
      project_id: A string specifying a project ID.
    Returns:
      A DirectorySubspace object.
    """
    yield self.validate_cache(tr)
    if project_id not in self:
      # TODO: Check new projects instead of assuming they are valid.
      # This can also be made async.
      self[project_id] = self.root_dir.create_or_open(tr, (project_id,))

    raise gen.Return(self[project_id])

  @gen.coroutine
  def list(self, tr):
    """ Gets a project's subdirectories.

    Args:
      tr: An FDB transaction.
    Returns:
      A list of DirectorySubspace objects.
    """
    yield self.validate_cache(tr)
    subdirs_subspace = self.subdirs_subspace(self.root_dir)
    kvs = yield KVIterator(tr, self._tornado_fdb,
                           subdirs_subspace.range()).list()
    directories = []
    for kv in kvs:
      project_id = subdirs_subspace.unpack(kv.key)[0]
      directory = DirectorySubspace(
        self.root_dir.get_path() + (project_id,), kv.value)
      if project_id not in self:
        self[project_id] = directory

      directories.append(self[project_id])

    raise gen.Return(directories)


class SectionCache(DirectoryCache):
  """ Caches non-namespaced section directories within a project. """

  # The number of items the cache can hold.
  SIZE = 256

  def __init__(self, tornado_fdb, project_cache, dir_type):
    super(SectionCache, self).__init__(
      tornado_fdb, project_cache.root_dir, self.SIZE)
    self._project_cache = project_cache
    self._dir_type = dir_type

  @gen.coroutine
  def get(self, tr, project_id):
    """ Gets a section directory for the given project.

    Args:
      tr: An FDB transaction.
      project_id: A string specifying the project ID.
    Returns:
      A namespace directory object of the directory type.
    """
    yield self.validate_cache(tr)
    if project_id not in self:
      project_dir = yield self._project_cache.get(tr, project_id)
      # TODO: Make async.
      section_dir = project_dir.create_or_open(tr, (self._dir_type.DIR_NAME,))
      self[project_id] = self._dir_type(section_dir)

    raise gen.Return(self[project_id])


class NSCache(DirectoryCache):
  """ Caches namespaced sections to keep track of directory prefixes. """

  # The number of items the cache can hold.
  SIZE = 512

  def __init__(self, tornado_fdb, project_cache, dir_type):
    super(NSCache, self).__init__(
      tornado_fdb, project_cache.root_dir, self.SIZE)
    self._project_cache = project_cache
    self._dir_type = dir_type

  # TODO: This interface is really clumsy. Rethink arguments.
  @gen.coroutine
  def get(self, tr, project_id, namespace, *args, **kwargs):
    """ Gets a namespace directory for the given project and namespace.

    Args:
      tr: An FDB transaction.
      project_id: A string specifying the project ID.
      namespace: A string specifying the namespace.
    Returns:
      A namespace directory object of the directory type.
    """
    yield self.validate_cache(tr)
    key = (project_id, namespace)
    if key not in self:
      project_dir = yield self._project_cache.get(tr, project_id)
      section_dir = yield self.get_section(tr, project_dir)
      # TODO: Make async.
      ns_dir = section_dir.create_or_open(tr, (namespace,) + tuple(args))
      self[key] = self._dir_type(ns_dir, **kwargs)

    raise gen.Return(self[key])

  @gen.coroutine
  def get_from_key(self, tr, key):
    """ Gets a namespace directory for a protobuf reference object.

    Args:
      tr: An FDB transaction.
      key: A protobuf reference object.
    Returns:
      A namespace directory object of the directory type.
    """
    project_id = decode_str(key.app())
    namespace = decode_str(key.name_space())
    ns_dir = yield self.get(tr, project_id, namespace)
    raise gen.Return(ns_dir)

  @gen.coroutine
  def get_section(self, tr, project_dir):
    """ Gets a project's directory type section.

    Args:
      tr: An FDB transaction.
      project_dir: The project's DirectorySubspace.
    Returns:
      A DirectorySubpace object with the path of
      (<ds-root>, <project-id>, <section>).
    """
    project_id = project_dir.get_path()[-1]
    if project_id not in self:
      # TODO: Make async.
      section_dir = project_dir.create_or_open(tr, (self._dir_type.DIR_NAME,))
      self[project_id] = section_dir

    raise gen.Return(self[project_id])

  @gen.coroutine
  def list(self, tr, project_dir):
    """ Gets the namepsace directories from the project's relevant section.

    Args:
      tr: An FDB transaction.
      project_dir: The project's DirectorySubspace.
    Returns:
      A list of DirectorySubspace objects with the path of
      (<ds-root>, <project-id>, <section>, <namespace>).
    """
    project_id = project_dir.get_path()[-1]
    section_dir = yield self.get_section(tr, project_dir)
    subdirs_subspace = self.subdirs_subspace(section_dir)
    kvs = yield KVIterator(tr, self._tornado_fdb,
                           subdirs_subspace.range()).list()
    ns_directories = []
    for kv in kvs:
      namespace = subdirs_subspace.unpack(kv.key)[0]
      ns_directory = DirectorySubspace(
        section_dir.get_path() + (namespace,), kv.value)
      key = (project_id, namespace)
      if key not in self:
        self[key] = self._dir_type(ns_directory)

      ns_directories.append(self[key])

    raise gen.Return(ns_directories)
