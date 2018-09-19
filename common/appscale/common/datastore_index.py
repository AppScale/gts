""" Represents a datastore index. """
from appscale.common.constants import InvalidConfiguration


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
      raise InvalidConfiguration('Index property missing "name"')

    if direction not in ('asc', 'desc'):
      raise InvalidConfiguration(
        'Invalid "direction" value: {}'.format(direction))

    self.name = name
    self.direction = direction

  @property
  def id(self):
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
    return cls(prop_pb.name(), prop_pb.direction())


class DatastoreIndex(object):
  """ Represents a datastore index. """

  __slots__ = ['kind', 'ancestor', 'properties']

  # Separates fields of an encoded index.
  ENCODING_DELIMITER = '|'

  def __init__(self, kind, ancestor, properties):
    """ Creates a new DatastoreIndex object.

    Args:
      kind: A string specifying the datastore kind.
      ancestor: A boolean indicating whether or not the index is for
        satisfying ancestor queries.
      properties: A list of IndexProperty objects.
    """
    self.kind = kind
    self.ancestor = ancestor
    self.properties = properties

  @property
  def id(self):
    encoded_ancestor = '1' if self.ancestor else '0'
    encoded_properties = self.ENCODING_DELIMITER.join(
      [prop.id for prop in self.properties])
    return self.ENCODING_DELIMITER.join(
      [self.kind, encoded_ancestor, encoded_properties])

  @classmethod
  def from_yaml(cls, entry):
    """ Constructs a DatastoreIndex from a parsed index.yaml entry.

    Args:
      entry: A dictionary generated from a index.yaml file.
    Returns:
      A DatastoreIndex object.
    Raises:
      InvalidConfiguration exception if entry is invalid.
    """
    kind = entry.get('kind')
    if not kind:
      raise InvalidConfiguration('Index entry is missing "kind" field')

    ancestor = entry.get('ancestor', False)
    if not isinstance(ancestor, bool):
      if ancestor.lower() not in ('yes', 'no', 'true', 'false'):
        raise InvalidConfiguration(
          'Invalid "ancestor" value: {}'.format(ancestor))

      ancestor = ancestor.lower() in ('yes', 'true')

    configured_props = entry.get('properties', [])
    if not configured_props:
      raise InvalidConfiguration('Index missing properties')

    properties = [IndexProperty(prop.get('name'), prop.get('direction', 'asc'))
                  for prop in configured_props]
    return cls(kind, ancestor, properties)

  def to_dict(self):
    """ Generates a JSON-safe dictionary representation of the index.

    Returns:
      A dictionary containing the index details.
    """
    return {
      'kind': self.kind,
      'ancestor': self.ancestor,
      'properties': [prop.to_dict() for prop in self.properties]
    }

  @classmethod
  def from_dict(cls, entry):
    """ Constructs a DatastoreIndex from a JSON-derived dictionary.

    Args:
      entry: A dictionary containing the kind, ancestor, and properties fields.
    Returns:
      A DatastoreIndex object.
    """
    properties = [IndexProperty.from_dict(prop)
                  for prop in entry['properties']]
    return cls(entry['kind'], entry['ancestor'], properties)

  @classmethod
  def from_pb(cls, index_pb):
    """ Constructs a DatastoreIndex from an entity_pb.CompositeIndex.

    Args:
      index_pb: An entity_pb.CompositeIndex.
    Returns:
      A DatastoreIndex object.
    """
    kind = index_pb.definition().entity_type()
    ancestor = index_pb.definition().ancestor()
    properties = [IndexProperty.from_pb(prop)
                  for prop in index_pb.definition().property_list()]
    return cls(kind, ancestor, properties)
