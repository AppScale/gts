""" Utilities for parsing datastore entities. """

from datastore_server import TOMBSTONE

from dbconstants import JOURNAL_SCHEMA
from dbconstants import JOURNAL_TABLE
from dbconstants import KEY_DELIMITER
from dbconstants import KIND_SEPARATOR

from google.appengine.datastore import entity_pb

def get_root_key_from_entity_key(key):
  """ Extract the root key from an entity key. We
      remove any excess children from a string to get to
      the root key.

  Args:
    entity_key: A string representing a row key.
  Returns:
    The root key extracted from the row key.
  """
  tokens = key.split(KIND_SEPARATOR)
  return tokens[0] + KIND_SEPARATOR

def get_prefix_from_entity_key(entity_key):
  """ Extracts the prefix from a key to the entity table.

  Args:
    entity_key: A str representing a row key to the entity table.
  Returns:
    A str representing the app prefix (app_id and namespace).
  """
  tokens = entity_key.split(KEY_DELIMITER)
  return tokens[0] + KEY_DELIMITER + tokens[1]

def fetch_journal_entry(self, key):
  """ Fetches the given key from the journal.

  Args:
    keys: A str, the key to fetch.
  Returns:
    The entity fetched from the datastore, or None if it was deleted.
  """
  result = self.db_access.batch_get_entity(JOURNAL_TABLE, [key],
    JOURNAL_SCHEMA)
  if len(result.keys()) == 0:
    return None

  if JOURNAL_SCHEMA[0] in result[0]:
    ent_string = result[0][JOURNAL_SCHEMA[0]]
    if ent_string == TOMBSTONE:
      return None
    return entity_pb.EntityProto().ParseFromString(ent_string)
  else:
    return None