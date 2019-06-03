""" Represents a datastore index. """
import json
import sys
import uuid

from appscale.common.constants import InvalidIndexConfiguration
from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.api.datastore import entity_pb


def merge_indexes(zk_client, project_id, new_indexes):
  """ Adds new indexes to a project.

  Args:
    zk_client: A kazoo.client.KazooClient object.
    project_id: A string specifying a project ID.
    new_indexes: An iterable containing DatastoreIndex objects. Indexes that
      are not already present in the configuration will be added.
  """
  indexes_node = '/appscale/projects/{}/indexes'.format(project_id)
  zk_client.ensure_path(indexes_node)
  encoded_indexes, znode_stat = zk_client.get(indexes_node)
  node_version = znode_stat.version

  if encoded_indexes:
    existing_indexes = [DatastoreIndex.from_dict(project_id, index)
                        for index in json.loads(encoded_indexes)]
  else:
    existing_indexes = []

  # Disregard index entries that already exist.
  existing_index_defs = {index.encoded_def for index in existing_indexes}
  new_indexes = [index for index in new_indexes
                 if index.encoded_def not in existing_index_defs]

  # Assign each new index an ID.
  for new_index in new_indexes:
    if new_index.id is not None:
      continue

    # The ID must be a positive number that fits in a signed 64-bit int.
    new_index.id = uuid.uuid1().int >> 65

  combined_indexes = existing_indexes + new_indexes

  encoded_indexes = json.dumps(
    [index.to_dict() for index in combined_indexes])
  zk_client.set(indexes_node, encoded_indexes, version=node_version)


class IndexProperty(object):
  """ Represents a datastore index property. """

  __slots__ = ['name', 'direction']

  def __init__(self, name, direction):
    """ Creates a new IndexProperty object.

    Args:
      name: A string specifying the property name.
      direction: A string specifying the index direction (asc or desc).
    """
    if not name:
      raise InvalidIndexConfiguration('Index property missing "name"')

    if direction not in ('asc', 'desc'):
      raise InvalidIndexConfiguration(
        'Invalid "direction" value: {}'.format(direction))

    self.name = name
    self.direction = direction

  @property
  def encoded_def(self):
    """ Returns a string representation of the index property. """
    if self.direction == 'asc':
      return self.name
    else:
      return ','.join([self.name, 'desc'])

  def to_dict(self):
    """ Generates a JSON-safe dictionary representation of the property.

    Returns:
      A dictionary containing the property details.
    """
    return {'name': self.name, 'direction': self.direction}

  def to_pb(self):
    """ Generates an protobuffer representation of the object.

    Returns:
      An entity_pb.Index_Property object.
    """
    prop_pb = entity_pb.Index_Property()
    prop_pb.set_name(self.name)
    if self.direction == 'asc':
      prop_pb.set_direction(entity_pb.Index_Property.ASCENDING)
    else:
      prop_pb.set_direction(entity_pb.Index_Property.DESCENDING)

    return prop_pb

  @classmethod
  def from_dict(cls, prop):
    """ Constructs an IndexProperty from a JSON-derived dictionary.

    Args:
      prop: A dictionary containing the name and direction fields.
    Returns:
      An IndexProperty object.
    """
    return cls(prop['name'], prop['direction'])

  @classmethod
  def from_pb(cls, prop_pb):
    """ Constructs an IndexProperty from an entity_pb.Index_Property.

    Args:
      prop_pb: An entity_pb.Index_Property object.
    Returns:
      An IndexProperty object.
    """
    if prop_pb.direction() == entity_pb.Index_Property.ASCENDING:
      direction = 'asc'
    else:
      direction = 'desc'
    return cls(prop_pb.name(), direction)


class DatastoreIndex(object):
  """ Represents a datastore index. """

  __slots__ = ['project_id', 'kind', 'ancestor', 'properties', 'ready', 'id']

  # Separates fields of an encoded index.
  ENCODING_DELIMITER = '|'

  def __init__(self, project_id, kind, ancestor, properties):
    """ Creates a new DatastoreIndex object.

    Args:
      project_id: A string specifying a project ID.
      kind: A string specifying the datastore kind.
      ancestor: A boolean indicating whether or not the index is for
        satisfying ancestor queries.
      properties: A list of IndexProperty objects.
    """
    self.project_id = project_id
    self.kind = kind
    self.ancestor = ancestor
    self.properties = properties

    # When creating a new index, assume that it's not ready to be queried yet.
    self.ready = False

    # The index ID is assigned by UpdateIndexes.
    self.id = None

  @property
  def encoded_def(self):
    """ Returns a string representation of the datastore index definition.

    This is useful for determining index identity without an ID assigned.
    """
    encoded_ancestor = '1' if self.ancestor else '0'
    encoded_properties = self.ENCODING_DELIMITER.join(
      [prop.encoded_def for prop in self.properties])
    return self.ENCODING_DELIMITER.join(
      [self.kind, encoded_ancestor, encoded_properties])

  @classmethod
  def from_yaml(cls, project_id, entry):
    """ Constructs a DatastoreIndex from a parsed index.yaml entry.

    Args:
      project_id: A string specifying the project ID.
      entry: A dictionary generated from a index.yaml file.
    Returns:
      A DatastoreIndex object.
    Raises:
      InvalidIndexConfiguration exception if entry is invalid.
    """
    kind = entry.get('kind')
    if not kind:
      raise InvalidIndexConfiguration('Index entry is missing "kind" field')

    ancestor = entry.get('ancestor', False)
    if not isinstance(ancestor, bool):
      if ancestor.lower() not in ('yes', 'no', 'true', 'false'):
        raise InvalidIndexConfiguration(
          'Invalid "ancestor" value: {}'.format(ancestor))

      ancestor = ancestor.lower() in ('yes', 'true')

    configured_props = entry.get('properties', [])
    if not configured_props:
      raise InvalidIndexConfiguration('Index missing properties')

    properties = [IndexProperty(prop.get('name'), prop.get('direction', 'asc'))
                  for prop in configured_props]
    return cls(project_id, kind, ancestor, properties)

  @classmethod
  def from_dict(cls, project_id, entry):
    """ Constructs a DatastoreIndex from a JSON-derived dictionary.

    Args:
      project_id: A string specifying the project ID.
      entry: A dictionary containing the index details.
    Returns:
      A DatastoreIndex object.
    """
    properties = [IndexProperty.from_dict(prop)
                  for prop in entry['properties']]
    datastore_index = cls(project_id, entry['kind'], entry['ancestor'],
                          properties)
    datastore_index.ready = entry['ready']
    datastore_index.id = entry.get('id')
    return datastore_index

  @classmethod
  def from_pb(cls, index_pb):
    """ Constructs a DatastoreIndex from an entity_pb.CompositeIndex.

    Args:
      index_pb: An entity_pb.CompositeIndex.
    Returns:
      A DatastoreIndex object.
    """
    project_id = index_pb.app_id()
    kind = index_pb.definition().entity_type()
    ancestor = index_pb.definition().ancestor()
    properties = [IndexProperty.from_pb(prop)
                  for prop in index_pb.definition().property_list()]
    datastore_index = cls(project_id, kind, ancestor, properties)
    datastore_index.id = index_pb.id()
    return datastore_index

  def to_dict(self):
    """ Generates a JSON-safe dictionary representation of the index.

    Returns:
      A dictionary containing the index details.
    """
    output = {
      'kind': self.kind,
      'ancestor': self.ancestor,
      'properties': [prop.to_dict() for prop in self.properties],
      'ready': self.ready
    }
    if self.id is not None:
      output['id'] = self.id

    return output

  def to_pb(self):
    """ Generates an entity_pb.CompositeIndex representation of the index.

    Returns:
      An entity_pb.CompositeIndex object.
    """
    index_pb = entity_pb.CompositeIndex()
    index_pb.set_app_id(self.project_id)
    index_pb.set_id(self.id)
    if self.ready:
      index_pb.set_state(entity_pb.CompositeIndex.READ_WRITE)
    else:
      index_pb.set_state(entity_pb.CompositeIndex.WRITE_ONLY)

    index_def = index_pb.mutable_definition()
    index_def.set_ancestor(self.ancestor)
    index_def.set_entity_type(self.kind)
    for prop in self.properties:
      prop_pb = index_def.add_property()
      prop_pb.MergeFrom(prop.to_pb())

    return index_pb
