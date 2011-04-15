#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""Models to be used to access an app's datastore metadata.

These entities cannot be created by users, but are created as results of
__namespace__, __kind__ and __property__ metadata queries such as

  q = db.GqlQuery("SELECT * FROM __namespace__")
  for p in q.fetch(100):
    print "namespace: '%s'" % p.namespace_name

and

  q = db.GqlQuery("SELECT __key__ from __property__ " +
                  "WHERE __key__ >= :1 AND __key__ <= :2",
                  Property.key_for_property("A", "t"),
                  Property.key_for_property("C", "a"))
  for p in q.fetch(100):
    print "%s: %s" % (Property.key_to_kind(p), Property.key_to_property(p))
"""







from google.appengine.api import datastore_types
from google.appengine.ext import db


class BaseMetadata(db.Model):
  """Base class for all metadata models."""


  KIND_NAME = '__BaseMetadata__'

  @classmethod
  def kind(cls):
    """Kind name override."""
    return cls.KIND_NAME


class Namespace(BaseMetadata):
  """Model for __namespace__ metadata query results."""

  KIND_NAME = '__namespace__'
  EMPTY_NAMESPACE_ID = datastore_types._EMPTY_NAMESPACE_ID

  @property
  def namespace_name(self):
    """Return the namespace name specified by this entity's key."""
    return self.key_to_namespace(self.key())

  @classmethod
  def key_for_namespace(cls, namespace):
    """Return the __namespace__ key for namespace.

    Args:
      namespace: namespace whose key is requested.
    Returns:
      The key for namespace.
    """
    if namespace:
      return db.Key.from_path(cls.KIND_NAME, namespace)
    else:
      return db.Key.from_path(cls.KIND_NAME, cls.EMPTY_NAMESPACE_ID)

  @classmethod
  def key_to_namespace(cls, key):
    """Return the namespace specified by a given __namespace__ key.

    Args:
      key: key whose name is requested.
    Returns:
      The namespace specified by key.
    """
    return key.name() or ''


class Kind(BaseMetadata):
  """Model for __kind__ metadata query results."""

  KIND_NAME = '__kind__'

  @property
  def kind_name(self):
    """Return the kind name specified by this entity's key."""
    return self.key_to_kind(self.key())

  @classmethod
  def key_for_kind(cls, kind):
    """Return the __kind__ key for kind.

    Args:
      kind: kind whose key is requested.
    Returns:
      The key for kind.
    """
    return db.Key.from_path(cls.KIND_NAME, kind)

  @classmethod
  def key_to_kind(cls, key):
    """Return the kind specified by a given __kind__ key.

    Args:
      key: key whose name is requested.
    Returns:
      The kind specified by key.
    """
    return key.name()


class Property(BaseMetadata):
  """Model for __property__ metadata query results."""

  KIND_NAME = '__property__'

  @property
  def property_name(self):
    """Return the property name specified by this entity's key."""
    return self.key_to_property(self.key())

  @property
  def kind_name(self):
    """Return the kind name specified by this entity's key."""
    return self.key_to_kind(self.key())

  property_representation = db.StringListProperty()

  @classmethod
  def key_for_kind(cls, kind):
    """Return the __property__ key for kind.

    Args:
      kind: kind whose key is requested.
    Returns:
      The parent key for __property__ keys of kind.
    """
    return db.Key.from_path(Kind.KIND_NAME, kind)

  @classmethod
  def key_for_property(cls, kind, property):
    """Return the __property__ key for property of kind.

    Args:
      kind: kind whose key is requested.
      property: property whose key is requested.
    Returns:
      The key for property of kind.
    """
    return db.Key.from_path(Kind.KIND_NAME, kind, Property.KIND_NAME, property)

  @classmethod
  def key_to_kind(cls, key):
    """Return the kind specified by a given __property__ key.

    Args:
      key: key whose kind name is requested.
    Returns:
      The kind specified by key.
    """
    if key.kind() == Kind.KIND_NAME:
      return key.name()
    else:
      return key.parent().name()

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
      return key.name()
