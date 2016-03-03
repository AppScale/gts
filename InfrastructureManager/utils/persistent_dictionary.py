import json
import os
from threading import Lock

class PersistentDictionary:
  """
  A dictionary implementation that optionally writes through to a
  persistent data store.
  """

  def __init__(self, store=None):
    """
    Create a new instance with an optional persistent backing store. If no
    backing store is provided, this instance will behave as a regular in-memory
    dictionary. If however a PersistentStore is provided as an argument, the
    created dictionary will write through all its updates to the specified
    store.

    Args:
      store   An instance of PersistentStore class (Optional)
    """
    self.store = store
    if store is not None:
      self.dictionary = store.get_all_entries()
    else:
      self.dictionary = {}

  def put(self, key, value):
    """
    Insert the specified key-value pair to the dictionary. If this instance
    of PersistentDictionary is backed by an instance of PersistentStore, the
    inserted entry will also be written to that store.

    Args:
      key   Key of the entry
      value Value of the entry
    """
    self.dictionary[key] = value
    if self.store is not None:
      self.store.save_all_entries(self.dictionary)

  def get(self, key):
    """
    Retrieve the value of the specified key from the dictionary.

    Args:
      key Key of the entry

    Returns:
      Value of the entry if the key exists in the map

    Raises:
      KeyError  If the specified key does not exist in the dictionary
    """
    return self.dictionary[key]

  def has_key(self, key):
    """
    Checks whether the specified key exists in the dictionary.

    Args:
      key Key of the entry

    Returns:
      True if the key exists and False otherwise.
    """
    return self.dictionary.has_key(key)


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

  def save_all_entries(self, dictionary):
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
    store_type = parameters[self.PARAM_STORE_TYPE]
    if store_type == 'file':
      return FileSystemBasedPersistentStore(parameters)
    else:
      raise NameError('Unrecognized persistent store type')

class FileSystemBasedPersistentStore(PersistentStore):
  """
  A simple PersistentStore implementation that writes through to
  the local file system. The location of the target file can be
  specified using PARAM_FILE_PATH option in the dictionary
  passed into the constructor. This implementation uses locking
  to prevent concurrent reads and writes. Therefore it should not
  be used in a highly concurrent environment. Also it writes the
  entire dictionary to the file system every time something is
  changed in the dictionary. Therefore it should not be used with
  large amounts of data either.
  """

  PARAM_FILE_PATH = 'file_path'

  def __init__(self, parameters):
    """
    Create a new instance of the persistent store.

    Args:
      parameters  A dictionary containing the PARAM_FILE_PATH entry
    """
    self.file_path = parameters[self.PARAM_FILE_PATH]
    self.lock = Lock()

  def get_all_entries(self):
    """
    See parent class documentation
    """
    self.lock.acquire()
    if os.path.exists(self.file_path):
      file_handle = open(self.file_path, 'r')
      dictionary = json.load(file_handle)
      file_handle.close()
      self.lock.release()
      return dictionary
    else:
      self.lock.release()
      return {}

  def save_all_entries(self, dictionary):
    """
    See parent class documentation
    """
    self.lock.acquire()
    file_handle = open(self.file_path, 'w')
    json.dump(dictionary, file_handle)
    file_handle.close()
    self.lock.release()
