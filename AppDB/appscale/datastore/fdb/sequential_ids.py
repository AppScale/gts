""" Handles storage details for sequential ID allocation. """
from tornado import gen

from appscale.datastore.fdb.codecs import Int64, Path
from appscale.datastore.fdb.utils import hash_tuple


class SequentialIDsNamespace(object):
  """
  A SequentialIDsNamespace handles the encoding and decoding details for
  allocate operations requested by the client. These can be explicit calls to
  reserve a range of IDs or part of a "put" operation that specifies the
  sequential allocator.

  The directory path looks like (<project-dir>, 'sequential-ids', <namespace>).

  Within this directory, keys are encoded as
  <scatter-byte> + <encoded-path-prefix> (missing the ID from the final
  element).

  The value is the largest ID that has been allocated.
  """
  DIR_NAME = u'sequential-ids'

  def __init__(self, directory):
    self.directory = directory

  @classmethod
  def directory_path(cls, project_id, namespace):
    return project_id, cls.DIR_NAME, namespace

  def encode_key(self, path_prefix):
    scatter_byte = hash_tuple(path_prefix)
    encoded_path = Path.pack(path_prefix, omit_terminator=True,
                             allow_partial=True)
    return self.directory.rawPrefix + scatter_byte + encoded_path

  @staticmethod
  def encode_value(largest_allocated):
    return Int64.encode(largest_allocated)

  @staticmethod
  def decode_value(value):
    marker = value[0]
    pos = 1
    return Int64.decode(marker, value, pos)[0]


@gen.coroutine
def sequential_id_key(tr, project_id, namespace, path_prefix, directory_cache):
  """ Looks up the FDB key for the max sequential ID. """
  dir_path = SequentialIDsNamespace.directory_path(project_id, namespace)
  directory = yield directory_cache.get(tr, dir_path)
  sequential_ids_ns = SequentialIDsNamespace(directory)
  raise gen.Return(sequential_ids_ns.encode_key(path_prefix))


@gen.coroutine
def old_max_id(tr, key, tornado_fdb):
  """ Retrieves the max allocated sequential ID for a path. """
  old_max = yield tornado_fdb.get(tr, key)
  if not old_max.present():
    raise gen.Return(0)
  else:
    raise gen.Return(SequentialIDsNamespace.decode_value(old_max))
