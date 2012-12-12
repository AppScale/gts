import json
import os
from threading import Lock

__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

class PersistentDictionary:
  """
  A dictionary implementation that optionally writes through to a
  persistent data store.
  """

  def __init__(self, store=None):
    self.store = store
    if store is not None:
      self.dict = store.get_all_entries()
    else:
      self.dict = {}

  def put(self, key, value):
    self.dict[key] = value
    if self.store is not None:
      self.store.save_all_entries(self.dict)

  def get(self, key):
    return self.dict[key]

  def has_key(self, key):
    return self.dict.has_key(key)


class PersistentStore:
  """
  Defines the interface of the persistent data store used
  by the PersistentDictionary.
  """

  def get_all_entries(self):
    """
    Read all the dictionary entries from the persistent store
    and return as a dictionary. If there are no entries in the
    underlying store, returns an empty dictionary.

    Returns:
      A dictionary of key-value pairs (possibly empty)
    """
    raise NotImplementedError

  def save_all_entries(self, dict):
    """
    Save the contents of the given dictionary to the data store,
    thereby overwriting any previous content.

    Args:
      dict    A dictionary of key-value pairs
    """
    raise NotImplementedError


class PersistentStoreFactory:
  """
  A factory class that can be used to instantiate PersistentStore
  instances.
  """

  PARAM_STORE_TYPE = 'store_type'

  def create_store(self, parameters):
    """
    Instantiate a new PersistentStore instance using the provided
    arguments.

    Arguments:
      parameters  Any additional parameters required to create the
                  PersistentStore instance. This map must at least
                  contain PARAM_STORE_TYPE.

    Returns:
      A PersistentStore instance

    Raises:
      NameError   If the type name provided is invalid
    """
    type = parameters[self.PARAM_STORE_TYPE]
    if type == 'file':
      return FileSystemBasedPersistentStore(parameters)
    else:
      raise NameError('Unrecognized persistent store type')

class FileSystemBasedPersistentStore(PersistentStore):

  PARAM_FILE_PATH = 'file_path'

  def __init__(self, parameters):
    self.file_path = parameters[self.PARAM_FILE_PATH]
    self.lock = Lock()

  def get_all_entries(self):
    self.lock.acquire()
    if os.path.exists(self.file_path):
      file_handle = open(self.file_path, 'r')
      dict = json.load(file_handle)
      file_handle.close()
      self.lock.release()
      return dict
    else:
      self.lock.release()
      return {}

  def save_all_entries(self, dict):
    self.lock.acquire()
    file_handle = open(self.file_path, 'w')
    json.dump(dict, file_handle)
    file_handle.close()
    self.lock.release()
