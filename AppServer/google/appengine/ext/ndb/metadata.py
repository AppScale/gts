"""Models and helper functions for access to app's datastore metadata.

These entities cannot be created by users, but are created as results of
__namespace__, __kind__, __property__ and __entity_group__ metadata queries
or gets.

A simplified API is also offered:

  ndb.metadata.get_namespaces(): A list of namespace names.
  ndb.metadata.get_kinds(): A list of kind names.
  ndb.metadata.get_properties_of_kind(kind):
    A list of property names for the given kind name.
  ndb.metadata.get_representations_of_kind(kind):
    A dict mapping property names to lists of representation ids.
  ndb.metadata.get_entity_group_version(key):
    The version of the entity group containing key (HRD only).

get_kinds(), get_properties_of_kind(), get_representations_of_kind()
implicitly apply to the current namespace.

get_namespaces(), get_kinds(), get_properties_of_kind(),
get_representations_of_kind() have optional start and end arguments to limit the
query to a range of names, such that start <= name < end.
"""

from . import model

__all__ = ['Namespace', 'Kind', 'Property', 'EntityGroup',
           'get_namespaces', 'get_kinds',
           'get_properties_of_kind', 'get_representations_of_kind',
           'get_entity_group_version',
           ]


class _BaseMetadata(model.Model):
  """Base class for all metadata models."""

  _use_cache = False
  _use_memcache = False

  KIND_NAME = ''  # Don't instantiate this class; always use a subclass.

  @classmethod
  def _get_kind(cls):
    """Kind name override."""
    return cls.KIND_NAME


class Namespace(_BaseMetadata):
  """Model for __namespace__ metadata query results."""

  KIND_NAME = '__namespace__'
  EMPTY_NAMESPACE_ID = 1  # == datastore_types._EMPTY_NAMESPACE_ID

  @property
  def namespace_name(self):
    """Return the namespace name specified by this entity's key."""
    return self.key_to_namespace(self.key)

  @classmethod
  def key_for_namespace(cls, namespace):
    """Return the Key for a namespace.

    Args:
      namespace: A string giving the namespace whose key is requested.

    Returns:
      The Key for the namespace.
    """
    if namespace:
      return model.Key(cls.KIND_NAME, namespace)
    else:
      return model.Key(cls.KIND_NAME, cls.EMPTY_NAMESPACE_ID)

  @classmethod
  def key_to_namespace(cls, key):
    """Return the namespace specified by a given __namespace__ key.

    Args:
      key: key whose name is requested.

    Returns:
      The namespace specified by key.
    """
    return key.string_id() or ''


class Kind(_BaseMetadata):
  """Model for __kind__ metadata query results."""

  KIND_NAME = '__kind__'

  @property
  def kind_name(self):
    """Return the kind name specified by this entity's key."""
    return self.key_to_kind(self.key)

  @classmethod
  def key_for_kind(cls, kind):
    """Return the __kind__ key for kind.

    Args:
      kind: kind whose key is requested.

    Returns:
      The key for kind.
    """
    return model.Key(cls.KIND_NAME, kind)

  @classmethod
  def key_to_kind(cls, key):
    """Return the kind specified by a given __kind__ key.

    Args:
      key: key whose name is requested.

    Returns:
      The kind specified by key.
    """
    return key.id()


class Property(_BaseMetadata):
  """Model for __property__ metadata query results."""

  KIND_NAME = '__property__'

  @property
  def property_name(self):
    """Return the property name specified by this entity's key."""
    return self.key_to_property(self.key)

  @property
  def kind_name(self):
    """Return the kind name specified by this entity's key."""
    return self.key_to_kind(self.key)

  property_representation = model.StringProperty(repeated=True)

  @classmethod
  def key_for_kind(cls, kind):
    """Return the __property__ key for kind.

    Args:
      kind: kind whose key is requested.

    Returns:
      The parent key for __property__ keys of kind.
    """
    return model.Key(Kind.KIND_NAME, kind)

  @classmethod
  def key_for_property(cls, kind, property):
    """Return the __property__ key for property of kind.

    Args:
      kind: kind whose key is requested.
      property: property whose key is requested.

    Returns:
      The key for property of kind.
    """
    return model.Key(Kind.KIND_NAME, kind, Property.KIND_NAME, property)

  @classmethod
  def key_to_kind(cls, key):
    """Return the kind specified by a given __property__ key.

    Args:
      key: key whose kind name is requested.

    Returns:
      The kind specified by key.
    """
    if key.kind() == Kind.KIND_NAME:
      return key.id()
    else:
      return key.parent().id()

  @classmethod
  def key_to_property(cls, key):
    """Return the property specified by a given __property__ key.

    Args:
      key: key whose property name is requested.

    Returns:
      property specified by key, or None if the key specified only a kind.
    """
    if key.kind() == Kind.KIND_NAME:
      return None
    else:
      return key.id()


class EntityGroup(_BaseMetadata):
  """Model for __entity_group__ metadata (available in HR datastore only).

  This metadata contains a numeric __version__ property that is guaranteed
  to increase on every change to the entity group. The version may increase
  even in the absence of user-visible changes to the entity group. The
  __entity_group__ entity may not exist if the entity group was never
  written to.
  """

  KIND_NAME = '__entity_group__'
  ID = 1

  version = model.IntegerProperty(name='__version__')

  @classmethod
  def key_for_entity_group(cls, key):
    """Return the key for the entity group containing key.

    Args:
      key: a key for an entity group whose __entity_group__ key you want.

    Returns:
      The __entity_group__ key for the entity group containing key.
    """
    return model.Key(cls.KIND_NAME, cls.ID, parent=key.root())


def get_namespaces(start=None, end=None):
  """Return all namespaces in the specified range.

  Args:
    start: only return namespaces >= start if start is not None.
    end: only return namespaces < end if end is not None.

  Returns:
    A list of namespace names between the (optional) start and end values.
  """
  q = Namespace.query()
  if start is not None:
    q = q.filter(Namespace.key >= Namespace.key_for_namespace(start))
  if end is not None:
    q = q.filter(Namespace.key < Namespace.key_for_namespace(end))
  return [x.namespace_name for x in q]


def get_kinds(start=None, end=None):
  """Return all kinds in the specified range, for the current namespace.

  Args:
    start: only return kinds >= start if start is not None.
    end: only return kinds < end if end is not None.

  Returns:
    A list of kind names between the (optional) start and end values.
  """
  q = Kind.query()
  if start is not None and start != '':
    q = q.filter(Kind.key >= Kind.key_for_kind(start))
  if end is not None:
    if end == '':
      return []
    q = q.filter(Kind.key < Kind.key_for_kind(end))

  return [x.kind_name for x in q]


def get_properties_of_kind(kind, start=None, end=None):
  """Return all properties of kind in the specified range.

  NOTE: This function does not return unindexed properties.

  Args:
    kind: name of kind whose properties you want.
    start: only return properties >= start if start is not None.
    end: only return properties < end if end is not None.

  Returns:
    A list of property names of kind between the (optional) start and end
    values.
  """
  q = Property.query(ancestor=Property.key_for_kind(kind))
  if start is not None and start != '':
    q = q.filter(Property.key >= Property.key_for_property(kind, start))
  if end is not None:
    if end == '':
      return []
    q = q.filter(Property.key < Property.key_for_property(kind, end))

  return [Property.key_to_property(k) for k in q.iter(keys_only=True)]


def get_representations_of_kind(kind, start=None, end=None):
  """Return all representations of properties of kind in the specified range.

  NOTE: This function does not return unindexed properties.

  Args:
    kind: name of kind whose properties you want.
    start: only return properties >= start if start is not None.
    end: only return properties < end if end is not None.

  Returns:
    A dictionary mapping property names to its list of representations.
  """
  q = Property.query(ancestor=Property.key_for_kind(kind))
  if start is not None and start != '':
    q = q.filter(Property.key >= Property.key_for_property(kind, start))
  if end is not None:
    if end == '':
      return {}
    q = q.filter(Property.key < Property.key_for_property(kind, end))

  result = {}
  for property in q:
    result[property.property_name] = property.property_representation

  return result


def get_entity_group_version(key):
  """Return the version of the entity group containing key.

  Args:
    key: a key for an entity group whose __entity_group__ key you want.

  Returns:
    The version of the entity group containing key. This version is
    guaranteed to increase on every change to the entity group. The version
    may increase even in the absence of user-visible changes to the entity
    group. May return None if the entity group was never written to.

    On non-HR datatores, this function returns None.
  """

  eg = EntityGroup.key_for_entity_group(key).get()
  if eg:
    return eg.version
  else:
    return None
