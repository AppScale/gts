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


"""A simple wrapper around enum types to expose utility functions.

Instances are created as properties with the same name as the enum they wrap
on proto classes.  For usage, see:
  reflection_test.py
"""



class EnumTypeWrapper(object):
  """A utility for finding the names of enum values."""

  DESCRIPTOR = None

  def __init__(self, enum_type):
    """Inits EnumTypeWrapper with an EnumDescriptor."""
    self._enum_type = enum_type
    self.DESCRIPTOR = enum_type;

  def Name(self, number):
    """Returns a string containing the name of an enum value."""
    if number in self._enum_type.values_by_number:
      return self._enum_type.values_by_number[number].name
    raise ValueError('Enum %s has no name defined for value %d' % (
        self._enum_type.name, number))

  def Value(self, name):
    """Returns the value coresponding to the given enum name."""
    if name in self._enum_type.values_by_name:
      return self._enum_type.values_by_name[name].number
    raise ValueError('Enum %s has no value defined for name %s' % (
        self._enum_type.name, name))

  def keys(self):
    """Return a list of the string names in the enum.

    These are returned in the order they were defined in the .proto file.
    """

    return [value_descriptor.name
            for value_descriptor in self._enum_type.values]

  def values(self):
    """Return a list of the integer values in the enum.

    These are returned in the order they were defined in the .proto file.
    """

    return [value_descriptor.number
            for value_descriptor in self._enum_type.values]

  def items(self):
    """Return a list of the (name, value) pairs of the enum.

    These are returned in the order they were defined in the .proto file.
    """
    return [(value_descriptor.name, value_descriptor.number)
            for value_descriptor in self._enum_type.values]
