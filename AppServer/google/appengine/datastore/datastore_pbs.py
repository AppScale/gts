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




"""Utilities for converting between v3 and v4 datastore protocol buffers.

This module is internal and should not be used by client applications.
"""
















from google.appengine.datastore import entity_pb

from google.appengine.datastore import entity_v4_pb



MEANING_ATOM_CATEGORY = 1
MEANING_URL = 2
MEANING_ATOM_TITLE = 3
MEANING_ATOM_CONTENT = 4
MEANING_ATOM_SUMMARY = 5
MEANING_ATOM_AUTHOR = 6
MEANING_GD_EMAIL = 8
MEANING_GEORSS_POINT = 9
MEANING_GD_IM = 10
MEANING_GD_PHONENUMBER = 11
MEANING_GD_POSTALADDRESS = 12
MEANING_PERCENT = 13
MEANING_TEXT = 15
MEANING_BYTESTRING = 16
MEANING_INDEX_ONLY = 18
MEANING_PREDEFINED_ENTITY_USER = 20
MEANING_PREDEFINED_ENTITY_POINT = 21
MEANING_ZLIB = 22


URI_MEANING_ZLIB = 'ZLIB'


MAX_INDEXED_BLOB_BYTES = 500


PROPERTY_NAME_X = 'x'
PROPERTY_NAME_Y = 'y'


PROPERTY_NAME_EMAIL = 'email'
PROPERTY_NAME_AUTH_DOMAIN = 'auth_domain'
PROPERTY_NAME_USER_ID = 'user_id'
PROPERTY_NAME_INTERNAL_ID = 'internal_id'
PROPERTY_NAME_FEDERATED_IDENTITY = 'federated_identity'
PROPERTY_NAME_FEDERATED_PROVIDER = 'federated_provider'


PROPERTY_NAME_KEY = '__key__'

DEFAULT_GAIA_ID = 0


def v4_key_to_string(v4_key):
  """Generates a string representing a key's path.

  The output makes no effort to qualify special characters in strings.

  The key need not be valid, but if any of the key path elements have
  both a name and an ID the name is ignored.

  Args:
    v4_key: a datastore_v4_pb.Key

  Returns:
    a string representing the key's path
  """
  path_element_strings = []
  for path_element in v4_key.path_element_list():
    if path_element.has_id():
      id_or_name = str(path_element.id())
    elif path_element.has_name():
      id_or_name = path_element.name()
    else:
      id_or_name = ''
    path_element_strings.append('%s: %s' % (path_element.kind(), id_or_name))
  return '[%s]' % ', '.join(path_element_strings)


def is_valid_utf8(s):
  try:
    s.decode('utf-8')
    return True
  except UnicodeDecodeError:
    return False


def check_conversion(condition, message):
  """Asserts a conversion condition and raises an error if it's not met.

  Args:
    condition: (boolean) condition to enforce
    message: error message

  Raises:
    InvalidConversionError: if condition is not met
  """
  if not condition:
    raise InvalidConversionError(message)



class InvalidConversionError(Exception):
  """Raised when conversion fails."""
  pass


class _EntityConverter(object):
  """Converter for entities and keys."""

  def v4_to_v3_reference(self, v4_key, v3_ref):
    """Converts a v4 Key to a v3 Reference.

    Args:
      v4_key: an entity_v4_pb.Key
      v3_ref: an entity_pb.Reference to populate
    """
    v3_ref.Clear()
    if v4_key.has_partition_id():
      if v4_key.partition_id().has_dataset_id():
        v3_ref.set_app(v4_key.partition_id().dataset_id())
      if v4_key.partition_id().has_namespace():
        v3_ref.set_name_space(v4_key.partition_id().namespace())
    for v4_element in v4_key.path_element_list():
      v3_element = v3_ref.mutable_path().add_element()
      v3_element.set_type(v4_element.kind())
      if v4_element.has_id():
        v3_element.set_id(v4_element.id())
      if v4_element.has_name():
        v3_element.set_name(v4_element.name())

  def v4_to_v3_references(self, v4_keys):
    """Converts a list of v4 Keys to a list of v3 References.

    Args:
      v4_keys: a list of entity_v4_pb.Key objects

    Returns:
      a list of entity_pb.Reference objects
    """
    v3_refs = []
    for v4_key in v4_keys:
      v3_ref = entity_pb.Reference()
      self.v4_to_v3_reference(v4_key, v3_ref)
      v3_refs.append(v3_ref)
    return v3_refs

  def v3_to_v4_key(self, v3_ref, v4_key):
    """Converts a v3 Reference to a v4 Key.

    Args:
      v3_ref: an entity_pb.Reference
      v4_key: an entity_v4_pb.Key to populate
    """
    v4_key.Clear()
    if not v3_ref.app():
      return
    v4_key.mutable_partition_id().set_dataset_id(v3_ref.app())
    if v3_ref.name_space():
      v4_key.mutable_partition_id().set_namespace(v3_ref.name_space())
    for v3_element in v3_ref.path().element_list():
      v4_element = v4_key.add_path_element()
      v4_element.set_kind(v3_element.type())
      if v3_element.has_id():
        v4_element.set_id(v3_element.id())
      if v3_element.has_name():
        v4_element.set_name(v3_element.name())

  def v3_to_v4_keys(self, v3_refs):
    """Converts a list of v3 References to a list of v4 Keys.

    Args:
      v3_refs: a list of entity_pb.Reference objects

    Returns:
      a list of entity_v4_pb.Key objects
    """
    v4_keys = []
    for v3_ref in v3_refs:
      v4_key = entity_v4_pb.Key()
      self.v3_to_v4_key(v3_ref, v4_key)
      v4_keys.append(v4_key)
    return v4_keys

  def v4_to_v3_entity(self, v4_entity, v3_entity):
    """Converts a v4 Entity to a v3 EntityProto.

    Args:
      v4_entity: an entity_v4_pb.Entity
      v3_entity: an entity_pb.EntityProto to populate
    """
    v3_entity.Clear()
    for v4_property in v4_entity.property_list():
      property_name = v4_property.name()
      if v4_property.has_value():
        v4_value = v4_property.value()
        if v4_value.list_value_list():
          for v4_sub_value in v4_value.list_value_list():
            self.__add_v3_property(property_name, True, v4_sub_value, v3_entity)
        else:
          self.__add_v3_property(property_name, False, v4_value, v3_entity)
      else:
        is_multi = v4_property.deprecated_multi()
        for v4_value in v4_property.deprecated_value_list():
          self.__add_v3_property(property_name, is_multi, v4_value, v3_entity)
    if v4_entity.has_key():
      v4_key = v4_entity.key()
      self.v4_to_v3_reference(v4_key, v3_entity.mutable_key())
      v3_ref = v3_entity.key()
      if (self.__v3_reference_has_id_or_name(v3_ref)
          or v3_ref.path().element_size() > 1):
        self.v3_reference_to_group(v3_ref, v3_entity.mutable_entity_group())
    else:


      pass

  def v3_to_v4_entity(self, v3_entity, v4_entity):
    """Converts a v3 EntityProto to a v4 Entity.

    Args:
      v3_entity: an entity_pb.EntityProto
      v4_entity: an entity_v4_pb.Proto to populate
    """
    v4_entity.Clear()
    self.v3_to_v4_key(v3_entity.key(), v4_entity.mutable_key())
    if not v3_entity.key().has_app():

      v4_entity.clear_key()




    v4_properties = {}
    for v3_property in v3_entity.property_list():
      self.__add_v4_property_to_entity(v4_entity, v4_properties, v3_property,
                                       True)
    for v3_property in v3_entity.raw_property_list():
      self.__add_v4_property_to_entity(v4_entity, v4_properties, v3_property,
                                       False)

  def v4_value_to_v3_property_value(self, v4_value, v3_value):
    """Converts a v4 Value to a v3 PropertyValue.

    Args:
      v4_value: an entity_v4_pb.Value
      v3_value: an entity_pb.PropertyValue to populate
    """
    v3_value.Clear()
    if v4_value.has_boolean_value():
      v3_value.set_booleanvalue(v4_value.boolean_value())
    elif v4_value.has_integer_value():
      v3_value.set_int64value(v4_value.integer_value())
    elif v4_value.has_double_value():
      v3_value.set_doublevalue(v4_value.double_value())
    elif v4_value.has_timestamp_microseconds_value():
      v3_value.set_int64value(v4_value.timestamp_microseconds_value())
    elif v4_value.has_key_value():
      v3_ref = entity_pb.Reference()
      self.v4_to_v3_reference(v4_value.key_value(), v3_ref)
      self.v3_reference_to_v3_property_value(v3_ref, v3_value)
    elif v4_value.has_blob_key_value():
      v3_value.set_stringvalue(v4_value.blob_key_value())
    elif v4_value.has_string_value():
      v3_value.set_stringvalue(v4_value.string_value())
    elif v4_value.has_blob_value():
      v3_value.set_stringvalue(v4_value.blob_value())
    elif v4_value.has_entity_value():
      v4_entity_value = v4_value.entity_value()
      v4_meaning = v4_value.meaning()
      if (v4_meaning == MEANING_GEORSS_POINT
          or v4_meaning == MEANING_PREDEFINED_ENTITY_POINT):
        self.__v4_to_v3_point_value(v4_entity_value,
                                    v3_value.mutable_pointvalue())
      elif v4_meaning == MEANING_PREDEFINED_ENTITY_USER:
        self.__v4_to_v3_user_value(v4_entity_value,
                                   v3_value.mutable_uservalue())
      else:
        v3_entity_value = entity_pb.EntityProto()
        self.v4_to_v3_entity(v4_entity_value, v3_entity_value)
        v3_value.set_stringvalue(v3_entity_value.SerializePartialToString())
    else:

      pass

  def v3_property_to_v4_value(self, v3_property, indexed, v4_value):
    """Converts a v3 Property to a v4 Value.

    Args:
      v3_property: an entity_pb.Property
      indexed: whether the v3 property is indexed
      v4_value: an entity_v4_pb.Value to populate
    """
    v4_value.Clear()
    v3_property_value = v3_property.value()
    v3_meaning = v3_property.meaning()
    v3_uri_meaning = None
    if v3_property.meaning_uri():
      v3_uri_meaning = v3_property.meaning_uri()

    if not self.__is_v3_property_value_union_valid(v3_property_value):


      v3_meaning = None
      v3_uri_meaning = None
    elif v3_meaning == entity_pb.Property.NO_MEANING:
      v3_meaning = None
    elif not self.__is_v3_property_value_meaning_valid(v3_property_value,
                                                       v3_meaning):

      v3_meaning = None

    is_zlib_value = False
    if v3_uri_meaning:
      if v3_uri_meaning == URI_MEANING_ZLIB:
        if v3_property_value.has_stringvalue():
          is_zlib_value = True
          if v3_meaning != entity_pb.Property.BLOB:

            v3_meaning = entity_pb.Property.BLOB
        else:
          pass
      else:
        pass


    if v3_property_value.has_booleanvalue():
      v4_value.set_boolean_value(v3_property_value.booleanvalue())
    elif v3_property_value.has_int64value():
      if v3_meaning == entity_pb.Property.GD_WHEN:
        v4_value.set_timestamp_microseconds_value(
            v3_property_value.int64value())
        v3_meaning = None
      else:
        v4_value.set_integer_value(v3_property_value.int64value())
    elif v3_property_value.has_doublevalue():
      v4_value.set_double_value(v3_property_value.doublevalue())
    elif v3_property_value.has_referencevalue():
      v3_ref = entity_pb.Reference()
      self.__v3_reference_value_to_v3_reference(
          v3_property_value.referencevalue(), v3_ref)
      self.v3_to_v4_key(v3_ref, v4_value.mutable_key_value())
    elif v3_property_value.has_stringvalue():
      if v3_meaning == entity_pb.Property.ENTITY_PROTO:
        serialized_entity_v3 = v3_property_value.stringvalue()
        v3_entity = entity_pb.EntityProto()


        v3_entity.ParsePartialFromString(serialized_entity_v3)
        self.v3_to_v4_entity(v3_entity, v4_value.mutable_entity_value())
        v3_meaning = None
      elif (v3_meaning == entity_pb.Property.BLOB
            or v3_meaning == entity_pb.Property.BYTESTRING):
        v4_value.set_blob_value(v3_property_value.stringvalue())

        if indexed or v3_meaning == entity_pb.Property.BLOB:
          v3_meaning = None
      else:
        string_value = v3_property_value.stringvalue()
        if is_valid_utf8(string_value):
          if v3_meaning == entity_pb.Property.BLOBKEY:
            v4_value.set_blob_key_value(string_value)
            v3_meaning = None
          else:
            v4_value.set_string_value(string_value)
        else:

          v4_value.set_blob_value(string_value)

          if v3_meaning != entity_pb.Property.INDEX_VALUE:
            v3_meaning = None


    elif v3_property_value.has_pointvalue():
      self.__v3_to_v4_point_entity(v3_property_value.pointvalue(),
                                   v4_value.mutable_entity_value())
      if v3_meaning != entity_pb.Property.GEORSS_POINT:
        v4_value.set_meaning(MEANING_PREDEFINED_ENTITY_POINT)
        v3_meaning = None
    elif v3_property_value.has_uservalue():
      self.__v3_to_v4_user_entity(v3_property_value.uservalue(),
                                  v4_value.mutable_entity_value())
      v4_value.set_meaning(MEANING_PREDEFINED_ENTITY_USER)
    else:
      pass

    if is_zlib_value:
      v4_value.set_meaning(MEANING_ZLIB)
    elif v3_meaning:
      v4_value.set_meaning(v3_meaning)


    if indexed != v4_value.indexed():
      v4_value.set_indexed(indexed)

  def __v4_to_v3_property(self, property_name, is_multi, v4_value, v3_property):
    """Converts info from a v4 Property to a v3 Property.

    v4_value must not have a list_value.

    Args:
      property_name: the name of the property
      is_multi: whether the property contains multiple values
      v4_value: an entity_v4_pb.Value
      v3_property: an entity_pb.Property to populate
    """
    assert not v4_value.list_value_list(), 'v4 list_value not convertable to v3'
    v3_property.Clear()
    v3_property.set_name(property_name)
    v3_property.set_multiple(is_multi)
    self.v4_value_to_v3_property_value(v4_value, v3_property.mutable_value())

    v4_meaning = None
    if v4_value.has_meaning():
      v4_meaning = v4_value.meaning()

    if v4_value.has_timestamp_microseconds_value():
      v3_property.set_meaning(entity_pb.Property.GD_WHEN)
    elif v4_value.has_blob_key_value():
      v3_property.set_meaning(entity_pb.Property.BLOBKEY)
    elif v4_value.has_blob_value():
      if v4_meaning == MEANING_ZLIB:
        v3_property.set_meaning_uri(URI_MEANING_ZLIB)
      if v4_meaning == entity_pb.Property.BYTESTRING:
        if v4_value.indexed():
          pass


      else:
        if v4_value.indexed():
          v3_property.set_meaning(entity_pb.Property.BYTESTRING)
        else:
          v3_property.set_meaning(entity_pb.Property.BLOB)
        v4_meaning = None
    elif v4_value.has_entity_value():
      if v4_meaning != MEANING_GEORSS_POINT:
        if (v4_meaning != MEANING_PREDEFINED_ENTITY_POINT
            and v4_meaning != MEANING_PREDEFINED_ENTITY_USER):
          v3_property.set_meaning(entity_pb.Property.ENTITY_PROTO)
        v4_meaning = None
    else:

      pass
    if v4_meaning is not None:
      v3_property.set_meaning(v4_meaning)

  def __add_v3_property(self, property_name, is_multi, v4_value, v3_entity):
    """Adds a v3 Property to an Entity based on information from a v4 Property.

    Args:
      property_name: the name of the property
      is_multi: whether the property contains multiple values
      v4_value: an entity_v4_pb.Value
      v3_entity: an entity_pb.EntityProto
    """
    if v4_value.indexed():
      self.__v4_to_v3_property(property_name, is_multi, v4_value,
                               v3_entity.add_property())
    else:
      self.__v4_to_v3_property(property_name, is_multi, v4_value,
                               v3_entity.add_raw_property())

  def __build_name_to_v4_property_map(self, v4_entity):
    property_map = {}
    for prop in v4_entity.property_list():
      property_map[prop.name()] = prop
    return property_map

  def __add_v4_property_to_entity(self, v4_entity, property_map, v3_property,
                                  indexed):
    """Adds a v4 Property to an entity or modifies an existing one.

    property_map is used to track of properties that have already been added.
    The same dict should be used for all of an entity's properties.

    Args:
      v4_entity: an entity_v4_pb.Entity
      property_map: a dict of name -> v4_property
      v3_property: an entity_pb.Property to convert to v4 and add to the dict
      indexed: whether the property is indexed
    """
    property_name = v3_property.name()
    if property_name in property_map:
      v4_property = property_map[property_name]
    else:
      v4_property = v4_entity.add_property()
      v4_property.set_name(property_name)
      property_map[property_name] = v4_property
    if v3_property.multiple():
      self.v3_property_to_v4_value(v3_property, indexed,
                                   v4_property.mutable_value().add_list_value())
    else:
      self.v3_property_to_v4_value(v3_property, indexed,
                                   v4_property.mutable_value())

  def __get_single_v4_integer_value(self, v4_property):
    """Returns an integer value from a v4 Property.

    Args:
      v4_property: an entity_v4_pb.Property

    Returns:
      an integer

    Throws:
      AssertionError if v4_property doesn't contain exactly one value
    """
    if v4_property.has_value():
      return v4_property.value().integer_value()
    else:
      v4_values = v4_property.deprecated_value_list()
      assert len(v4_values) == 1, 'property had %d values' % len(v4_values)
      return v4_values[0].integer_value()

  def __get_single_v4_double_value(self, v4_property):
    """Returns a double value from a v4 Property.

    Args:
      v4_property: an entity_v4_pb.Property

    Returns:
      a double

    Throws:
      AssertionError if v4_property doesn't contain exactly one value
    """
    if v4_property.has_value():
      return v4_property.value().double_value()
    else:
      v4_values = v4_property.deprecated_value_list()
      assert len(v4_values) == 1, 'property had %d values' % len(v4_values)
      return v4_values[0].double_value()

  def __get_single_v4_string_value(self, v4_property):
    """Returns an string value from a v4 Property.

    Args:
      v4_property: an entity_v4_pb.Property

    Returns:
      a string

    Throws:
      AssertionError if v4_property doesn't contain exactly one value
    """
    if v4_property.has_value():
      return v4_property.value().string_value()
    else:
      v4_values = v4_property.deprecated_value_list()
      assert len(v4_values) == 1, 'property had %d values' % len(v4_values)
      return v4_values[0].string_value()

  def __v4_integer_property(self, name, value, indexed):
    """Creates a single-integer-valued v4 Property.

    Args:
      name: the property name
      value: the integer value of the property
      indexed: whether the value should be indexed

    Returns:
      an entity_v4_pb.Property
    """
    v4_property = entity_v4_pb.Property()
    v4_property.set_name(name)
    v4_value = v4_property.mutable_value()
    v4_value.set_indexed(indexed)
    v4_value.set_integer_value(value)
    return v4_property

  def __v4_double_property(self, name, value, indexed):
    """Creates a single-double-valued v4 Property.

    Args:
      name: the property name
      value: the double value of the property
      indexed: whether the value should be indexed

    Returns:
      an entity_v4_pb.Property
    """
    v4_property = entity_v4_pb.Property()
    v4_property.set_name(name)
    v4_value = v4_property.mutable_value()
    v4_value.set_indexed(indexed)
    v4_value.set_double_value(value)
    return v4_property

  def __v4_string_property(self, name, value, indexed):
    """Creates a single-string-valued v4 Property.

    Args:
      name: the property name
      value: the string value of the property
      indexed: whether the value should be indexed

    Returns:
      an entity_v4_pb.Property
    """
    v4_property = entity_v4_pb.Property()
    v4_property.set_name(name)
    v4_value = v4_property.mutable_value()
    v4_value.set_indexed(indexed)
    v4_value.set_string_value(value)
    return v4_property

  def __v4_to_v3_point_value(self, v4_point_entity, v3_point_value):
    """Converts a v4 point Entity to a v3 PointValue.

    Args:
      v4_point_entity: an entity_v4_pb.Entity representing a point
      v3_point_value: an entity_pb.Property_PointValue to populate
    """
    v3_point_value.Clear()
    name_to_v4_property = self.__build_name_to_v4_property_map(v4_point_entity)
    v3_point_value.set_x(
        self.__get_single_v4_double_value(name_to_v4_property['x']))
    v3_point_value.set_y(
        self.__get_single_v4_double_value(name_to_v4_property['y']))

  def __v3_to_v4_point_entity(self, v3_point_value, v4_entity):
    """Converts a v3 UserValue to a v4 user Entity.

    Args:
      v3_point_value: an entity_pb.Property_PointValue
      v4_entity: an entity_v4_pb.Entity to populate
    """
    v4_entity.Clear()
    v4_entity.property_list().append(
        self.__v4_double_property(PROPERTY_NAME_X, v3_point_value.x(), False))
    v4_entity.property_list().append(
        self.__v4_double_property(PROPERTY_NAME_Y, v3_point_value.y(), False))

  def __v4_to_v3_user_value(self, v4_user_entity, v3_user_value):
    """Converts a v4 user Entity to a v3 UserValue.

    Args:
      v4_user_entity: an entity_v4_pb.Entity representing a user
      v3_user_value: an entity_pb.Property_UserValue to populate
    """
    v3_user_value.Clear()
    name_to_v4_property = self.__build_name_to_v4_property_map(v4_user_entity)

    v3_user_value.set_email(self.__get_single_v4_string_value(
        name_to_v4_property[PROPERTY_NAME_EMAIL]))
    v3_user_value.set_auth_domain(self.__get_single_v4_string_value(
        name_to_v4_property[PROPERTY_NAME_AUTH_DOMAIN]))
    if PROPERTY_NAME_USER_ID in name_to_v4_property:
      v3_user_value.set_obfuscated_gaiaid(
          self.__get_single_v4_string_value(
              name_to_v4_property[PROPERTY_NAME_USER_ID]))
    if PROPERTY_NAME_INTERNAL_ID in name_to_v4_property:
      v3_user_value.set_gaiaid(self.__get_single_v4_integer_value(
          name_to_v4_property[PROPERTY_NAME_INTERNAL_ID]))
    else:

      v3_user_value.set_gaiaid(0)
    if PROPERTY_NAME_FEDERATED_IDENTITY in name_to_v4_property:
      v3_user_value.set_federated_identity(
          self.__get_single_v4_string_value(name_to_v4_property[
              PROPERTY_NAME_FEDERATED_IDENTITY]))
    if PROPERTY_NAME_FEDERATED_PROVIDER in name_to_v4_property:
      v3_user_value.set_federated_provider(
          self.__get_single_v4_string_value(name_to_v4_property[
              PROPERTY_NAME_FEDERATED_PROVIDER]))

  def __v3_to_v4_user_entity(self, v3_user_value, v4_entity):
    """Converts a v3 UserValue to a v4 user Entity.

    Args:
      v3_user_value: an entity_pb.Property_UserValue
      v4_entity: an entity_v4_pb.Entity to populate
    """
    v4_entity.Clear()
    v4_entity.property_list().append(
        self.__v4_string_property(PROPERTY_NAME_EMAIL, v3_user_value.email(),
                                  False))
    v4_entity.property_list().append(self.__v4_string_property(
        PROPERTY_NAME_AUTH_DOMAIN,
        v3_user_value.auth_domain(), False))

    if v3_user_value.gaiaid() != 0:
      v4_entity.property_list().append(self.__v4_integer_property(
          PROPERTY_NAME_INTERNAL_ID,
          v3_user_value.gaiaid(),
          False))
    if v3_user_value.has_obfuscated_gaiaid():
      v4_entity.property_list().append(self.__v4_string_property(
          PROPERTY_NAME_USER_ID,
          v3_user_value.obfuscated_gaiaid(),
          False))
    if v3_user_value.has_federated_identity():
      v4_entity.property_list().append(self.__v4_string_property(
          PROPERTY_NAME_FEDERATED_IDENTITY,
          v3_user_value.federated_identity(),
          False))
    if v3_user_value.has_federated_provider():
      v4_entity.property_list().append(self.__v4_string_property(
          PROPERTY_NAME_FEDERATED_PROVIDER,
          v3_user_value.federated_provider(),
          False))

  def __is_v3_property_value_union_valid(self, v3_property_value):
    """Returns True if the v3 PropertyValue's union is valid."""
    num_sub_values = 0
    if v3_property_value.has_booleanvalue():
      num_sub_values += 1
    if v3_property_value.has_int64value():
      num_sub_values += 1
    if v3_property_value.has_doublevalue():
      num_sub_values += 1
    if v3_property_value.has_referencevalue():
      num_sub_values += 1
    if v3_property_value.has_stringvalue():
      num_sub_values += 1
    if v3_property_value.has_pointvalue():
      num_sub_values += 1
    if v3_property_value.has_uservalue():
      num_sub_values += 1
    return num_sub_values <= 1

  def __is_v3_property_value_meaning_valid(self, v3_property_value, v3_meaning):
    """Returns True if the v3 PropertyValue's type value matches its meaning."""
    def ReturnTrue():
      return True
    def HasStringValue():
      return v3_property_value.has_stringvalue()
    def HasInt64Value():
      return v3_property_value.has_int64value()
    def HasPointValue():
      return v3_property_value.has_pointvalue()
    def ReturnFalse():
      return False
    value_checkers = {
        entity_pb.Property.NO_MEANING: ReturnTrue,
        entity_pb.Property.INDEX_VALUE: ReturnTrue,
        entity_pb.Property.BLOB: HasStringValue,
        entity_pb.Property.TEXT: HasStringValue,
        entity_pb.Property.BYTESTRING: HasStringValue,
        entity_pb.Property.ATOM_CATEGORY: HasStringValue,
        entity_pb.Property.ATOM_LINK: HasStringValue,
        entity_pb.Property.ATOM_TITLE: HasStringValue,
        entity_pb.Property.ATOM_CONTENT: HasStringValue,
        entity_pb.Property.ATOM_SUMMARY: HasStringValue,
        entity_pb.Property.ATOM_AUTHOR: HasStringValue,
        entity_pb.Property.GD_EMAIL: HasStringValue,
        entity_pb.Property.GD_IM: HasStringValue,
        entity_pb.Property.GD_PHONENUMBER: HasStringValue,
        entity_pb.Property.GD_POSTALADDRESS: HasStringValue,
        entity_pb.Property.BLOBKEY: HasStringValue,
        entity_pb.Property.ENTITY_PROTO: HasStringValue,
        entity_pb.Property.GD_WHEN: HasInt64Value,
        entity_pb.Property.GD_RATING: HasInt64Value,
        entity_pb.Property.GEORSS_POINT: HasPointValue,
        }
    default = ReturnFalse
    return value_checkers.get(v3_meaning, default)()

  def __v3_reference_has_id_or_name(self, v3_ref):
    """Determines if a v3 Reference specifies an ID or name.

    Args:
      v3_ref: an entity_pb.Reference

    Returns:
      boolean: True if the last path element specifies an ID or name.
    """
    path = v3_ref.path()
    assert path.element_size() >= 1
    last_element = path.element(path.element_size() - 1)
    return last_element.has_id() or last_element.has_name()

  def v3_reference_to_group(self, v3_ref, group):
    """Converts a v3 Reference to a v3 Path representing the entity group.

    The entity group is represented as an entity_pb.Path containing only the
    first element in the provided Reference.

    Args:
      v3_ref: an entity_pb.Reference
      group: an entity_pb.Path to populate
    """
    group.Clear()
    path = v3_ref.path()
    assert path.element_size() >= 1
    group.add_element().CopyFrom(path.element(0))

  def v3_reference_to_v3_property_value(self, v3_ref, v3_property_value):
    """Converts a v3 Reference to a v3 PropertyValue.

    Args:
      v3_ref: an entity_pb.Reference
      v3_property_value: an entity_pb.PropertyValue to populate
    """
    v3_property_value.Clear()
    reference_value = v3_property_value.mutable_referencevalue()
    if v3_ref.has_app():
      reference_value.set_app(v3_ref.app())
    if v3_ref.has_name_space():
      reference_value.set_name_space(v3_ref.name_space())
    for v3_path_element in v3_ref.path().element_list():
      v3_ref_value_path_element = reference_value.add_pathelement()
      if v3_path_element.has_type():
        v3_ref_value_path_element.set_type(v3_path_element.type())
      if v3_path_element.has_id():
        v3_ref_value_path_element.set_id(v3_path_element.id())
      if v3_path_element.has_name():
        v3_ref_value_path_element.set_name(v3_path_element.name())

  def __v3_reference_value_to_v3_reference(self, v3_ref_value, v3_ref):
    """Converts a v3 ReferenceValue to a v3 Reference.

    Args:
      v3_ref_value: an entity_pb.PropertyValue_ReferenceValue
      v3_ref: an entity_pb.Reference to populate
    """
    v3_ref.Clear()
    if v3_ref_value.has_app():
      v3_ref.set_app(v3_ref_value.app())
    if v3_ref_value.has_name_space():
      v3_ref.set_name_space(v3_ref_value.name_space())
    for v3_ref_value_path_element in v3_ref_value.pathelement_list():
      v3_path_element = v3_ref.mutable_path().add_element()
      if v3_ref_value_path_element.has_type():
        v3_path_element.set_type(v3_ref_value_path_element.type())
      if v3_ref_value_path_element.has_id():
        v3_path_element.set_id(v3_ref_value_path_element.id())
      if v3_ref_value_path_element.has_name():
        v3_path_element.set_name(v3_ref_value_path_element.name())



__entity_converter = _EntityConverter()


def get_entity_converter():
  """Returns a converter for v3 and v4 entities and keys."""
  return __entity_converter
