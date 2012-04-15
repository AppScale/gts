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




"""Code for encoding protocol message primitives.

Contains the logic for encoding every logical protocol field type
into one of the 5 physical wire types.

This code is designed to push the Python interpreter's performance to the
limits.

The basic idea is that at startup time, for every field (i.e. every
FieldDescriptor) we construct two functions:  a "sizer" and an "encoder".  The
sizer takes a value of this field's type and computes its byte size.  The
encoder takes a writer function and a value.  It encodes the value into byte
strings and invokes the writer function to write those strings.  Typically the
writer function is the write() method of a cStringIO.

We try to do as much work as possible when constructing the writer and the
sizer rather than when calling them.  In particular:
* We copy any needed global functions to local variables, so that we do not need
  to do costly global table lookups at runtime.
* Similarly, we try to do any attribute lookups at startup time if possible.
* Every field's tag is encoded to bytes at startup, since it can't change at
  runtime.
* Whatever component of the field size we can compute at startup, we do.
* We *avoid* sharing code if doing so would make the code slower and not sharing
  does not burden us too much.  For example, encoders for repeated fields do
  not just call the encoders for singular fields in a loop because this would
  add an extra function call overhead for every loop iteration; instead, we
  manually inline the single-value encoder into the loop.
* If a Python function lacks a return statement, Python actually generates
  instructions to pop the result of the last statement off the stack, push
  None onto the stack, and then return that.  If we really don't care what
  value is returned, then we can save two instructions by returning the
  result of the last statement.  It looks funny but it helps.
* We assume that type and bounds checking has happened at a higher level.
"""


import struct
from google.net.proto2.python.internal import wire_format




_POS_INF = 1e10000
_NEG_INF = -_POS_INF


def _VarintSize(value):
  """Compute the size of a varint value."""
  if value <= 0x7f: return 1
  if value <= 0x3fff: return 2
  if value <= 0x1fffff: return 3
  if value <= 0xfffffff: return 4
  if value <= 0x7ffffffff: return 5
  if value <= 0x3ffffffffff: return 6
  if value <= 0x1ffffffffffff: return 7
  if value <= 0xffffffffffffff: return 8
  if value <= 0x7fffffffffffffff: return 9
  return 10


def _SignedVarintSize(value):
  """Compute the size of a signed varint value."""
  if value < 0: return 10
  if value <= 0x7f: return 1
  if value <= 0x3fff: return 2
  if value <= 0x1fffff: return 3
  if value <= 0xfffffff: return 4
  if value <= 0x7ffffffff: return 5
  if value <= 0x3ffffffffff: return 6
  if value <= 0x1ffffffffffff: return 7
  if value <= 0xffffffffffffff: return 8
  if value <= 0x7fffffffffffffff: return 9
  return 10


def _TagSize(field_number):
  """Returns the number of bytes required to serialize a tag with this field
  number."""

  return _VarintSize(wire_format.PackTag(field_number, 0))










def _SimpleSizer(compute_value_size):
  """A sizer which uses the function compute_value_size to compute the size of
  each value.  Typically compute_value_size is _VarintSize."""

  def SpecificSizer(field_number, is_repeated, is_packed):
    tag_size = _TagSize(field_number)
    if is_packed:
      local_VarintSize = _VarintSize
      def PackedFieldSize(value):
        result = 0
        for element in value:
          result += compute_value_size(element)
        return result + local_VarintSize(result) + tag_size
      return PackedFieldSize
    elif is_repeated:
      def RepeatedFieldSize(value):
        result = tag_size * len(value)
        for element in value:
          result += compute_value_size(element)
        return result
      return RepeatedFieldSize
    else:
      def FieldSize(value):
        return tag_size + compute_value_size(value)
      return FieldSize

  return SpecificSizer


def _ModifiedSizer(compute_value_size, modify_value):
  """Like SimpleSizer, but modify_value is invoked on each value before it is
  passed to compute_value_size.  modify_value is typically ZigZagEncode."""

  def SpecificSizer(field_number, is_repeated, is_packed):
    tag_size = _TagSize(field_number)
    if is_packed:
      local_VarintSize = _VarintSize
      def PackedFieldSize(value):
        result = 0
        for element in value:
          result += compute_value_size(modify_value(element))
        return result + local_VarintSize(result) + tag_size
      return PackedFieldSize
    elif is_repeated:
      def RepeatedFieldSize(value):
        result = tag_size * len(value)
        for element in value:
          result += compute_value_size(modify_value(element))
        return result
      return RepeatedFieldSize
    else:
      def FieldSize(value):
        return tag_size + compute_value_size(modify_value(value))
      return FieldSize

  return SpecificSizer


def _FixedSizer(value_size):
  """Like _SimpleSizer except for a fixed-size field.  The input is the size
  of one value."""

  def SpecificSizer(field_number, is_repeated, is_packed):
    tag_size = _TagSize(field_number)
    if is_packed:
      local_VarintSize = _VarintSize
      def PackedFieldSize(value):
        result = len(value) * value_size
        return result + local_VarintSize(result) + tag_size
      return PackedFieldSize
    elif is_repeated:
      element_size = value_size + tag_size
      def RepeatedFieldSize(value):
        return len(value) * element_size
      return RepeatedFieldSize
    else:
      field_size = value_size + tag_size
      def FieldSize(value):
        return field_size
      return FieldSize

  return SpecificSizer









Int32Sizer = Int64Sizer = EnumSizer = _SimpleSizer(_SignedVarintSize)

UInt32Sizer = UInt64Sizer = _SimpleSizer(_VarintSize)

SInt32Sizer = SInt64Sizer = _ModifiedSizer(
    _SignedVarintSize, wire_format.ZigZagEncode)

Fixed32Sizer = SFixed32Sizer = FloatSizer  = _FixedSizer(4)
Fixed64Sizer = SFixed64Sizer = DoubleSizer = _FixedSizer(8)

BoolSizer = _FixedSizer(1)


def StringSizer(field_number, is_repeated, is_packed):
  """Returns a sizer for a string field."""

  tag_size = _TagSize(field_number)
  local_VarintSize = _VarintSize
  local_len = len
  assert not is_packed
  if is_repeated:
    def RepeatedFieldSize(value):
      result = tag_size * len(value)
      for element in value:
        l = local_len(element.encode('utf-8'))
        result += local_VarintSize(l) + l
      return result
    return RepeatedFieldSize
  else:
    def FieldSize(value):
      l = local_len(value.encode('utf-8'))
      return tag_size + local_VarintSize(l) + l
    return FieldSize


def BytesSizer(field_number, is_repeated, is_packed):
  """Returns a sizer for a bytes field."""

  tag_size = _TagSize(field_number)
  local_VarintSize = _VarintSize
  local_len = len
  assert not is_packed
  if is_repeated:
    def RepeatedFieldSize(value):
      result = tag_size * len(value)
      for element in value:
        l = local_len(element)
        result += local_VarintSize(l) + l
      return result
    return RepeatedFieldSize
  else:
    def FieldSize(value):
      l = local_len(value)
      return tag_size + local_VarintSize(l) + l
    return FieldSize


def GroupSizer(field_number, is_repeated, is_packed):
  """Returns a sizer for a group field."""

  tag_size = _TagSize(field_number) * 2
  assert not is_packed
  if is_repeated:
    def RepeatedFieldSize(value):
      result = tag_size * len(value)
      for element in value:
        result += element.ByteSize()
      return result
    return RepeatedFieldSize
  else:
    def FieldSize(value):
      return tag_size + value.ByteSize()
    return FieldSize


def MessageSizer(field_number, is_repeated, is_packed):
  """Returns a sizer for a message field."""

  tag_size = _TagSize(field_number)
  local_VarintSize = _VarintSize
  assert not is_packed
  if is_repeated:
    def RepeatedFieldSize(value):
      result = tag_size * len(value)
      for element in value:
        l = element.ByteSize()
        result += local_VarintSize(l) + l
      return result
    return RepeatedFieldSize
  else:
    def FieldSize(value):
      l = value.ByteSize()
      return tag_size + local_VarintSize(l) + l
    return FieldSize






def MessageSetItemSizer(field_number):
  """Returns a sizer for extensions of MessageSet.

  The message set message looks like this:
    message MessageSet {
      repeated group Item = 1 {
        required int32 type_id = 2;
        required string message = 3;
      }
    }
  """
  static_size = (_TagSize(1) * 2 + _TagSize(2) + _VarintSize(field_number) +
                 _TagSize(3))
  local_VarintSize = _VarintSize

  def FieldSize(value):
    l = value.ByteSize()
    return static_size + local_VarintSize(l) + l

  return FieldSize






def _VarintEncoder():
  """Return an encoder for a basic varint value (does not include tag)."""

  local_chr = chr
  def EncodeVarint(write, value):
    bits = value & 0x7f
    value >>= 7
    while value:
      write(local_chr(0x80|bits))
      bits = value & 0x7f
      value >>= 7
    return write(local_chr(bits))

  return EncodeVarint


def _SignedVarintEncoder():
  """Return an encoder for a basic signed varint value (does not include
  tag)."""

  local_chr = chr
  def EncodeSignedVarint(write, value):
    if value < 0:
      value += (1 << 64)
    bits = value & 0x7f
    value >>= 7
    while value:
      write(local_chr(0x80|bits))
      bits = value & 0x7f
      value >>= 7
    return write(local_chr(bits))

  return EncodeSignedVarint


_EncodeVarint = _VarintEncoder()
_EncodeSignedVarint = _SignedVarintEncoder()


def _VarintBytes(value):
  """Encode the given integer as a varint and return the bytes.  This is only
  called at startup time so it doesn't need to be fast."""

  pieces = []
  _EncodeVarint(pieces.append, value)
  return "".join(pieces)


def TagBytes(field_number, wire_type):
  """Encode the given tag and return the bytes.  Only called at startup."""

  return _VarintBytes(wire_format.PackTag(field_number, wire_type))






def _SimpleEncoder(wire_type, encode_value, compute_value_size):
  """Return a constructor for an encoder for fields of a particular type.

  Args:
      wire_type:  The field's wire type, for encoding tags.
      encode_value:  A function which encodes an individual value, e.g.
        _EncodeVarint().
      compute_value_size:  A function which computes the size of an individual
        value, e.g. _VarintSize().
  """

  def SpecificEncoder(field_number, is_repeated, is_packed):
    if is_packed:
      tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
      local_EncodeVarint = _EncodeVarint
      def EncodePackedField(write, value):
        write(tag_bytes)
        size = 0
        for element in value:
          size += compute_value_size(element)
        local_EncodeVarint(write, size)
        for element in value:
          encode_value(write, element)
      return EncodePackedField
    elif is_repeated:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeRepeatedField(write, value):
        for element in value:
          write(tag_bytes)
          encode_value(write, element)
      return EncodeRepeatedField
    else:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeField(write, value):
        write(tag_bytes)
        return encode_value(write, value)
      return EncodeField

  return SpecificEncoder


def _ModifiedEncoder(wire_type, encode_value, compute_value_size, modify_value):
  """Like SimpleEncoder but additionally invokes modify_value on every value
  before passing it to encode_value.  Usually modify_value is ZigZagEncode."""

  def SpecificEncoder(field_number, is_repeated, is_packed):
    if is_packed:
      tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
      local_EncodeVarint = _EncodeVarint
      def EncodePackedField(write, value):
        write(tag_bytes)
        size = 0
        for element in value:
          size += compute_value_size(modify_value(element))
        local_EncodeVarint(write, size)
        for element in value:
          encode_value(write, modify_value(element))
      return EncodePackedField
    elif is_repeated:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeRepeatedField(write, value):
        for element in value:
          write(tag_bytes)
          encode_value(write, modify_value(element))
      return EncodeRepeatedField
    else:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeField(write, value):
        write(tag_bytes)
        return encode_value(write, modify_value(value))
      return EncodeField

  return SpecificEncoder


def _StructPackEncoder(wire_type, format):
  """Return a constructor for an encoder for a fixed-width field.

  Args:
      wire_type:  The field's wire type, for encoding tags.
      format:  The format string to pass to struct.pack().
  """

  value_size = struct.calcsize(format)

  def SpecificEncoder(field_number, is_repeated, is_packed):
    local_struct_pack = struct.pack
    if is_packed:
      tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
      local_EncodeVarint = _EncodeVarint
      def EncodePackedField(write, value):
        write(tag_bytes)
        local_EncodeVarint(write, len(value) * value_size)
        for element in value:
          write(local_struct_pack(format, element))
      return EncodePackedField
    elif is_repeated:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeRepeatedField(write, value):
        for element in value:
          write(tag_bytes)
          write(local_struct_pack(format, element))
      return EncodeRepeatedField
    else:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeField(write, value):
        write(tag_bytes)
        return write(local_struct_pack(format, value))
      return EncodeField

  return SpecificEncoder


def _FloatingPointEncoder(wire_type, format):
  """Return a constructor for an encoder for float fields.

  This is like StructPackEncoder, but catches errors that may be due to
  passing non-finite floating-point values to struct.pack, and makes a
  second attempt to encode those values.

  Args:
      wire_type:  The field's wire type, for encoding tags.
      format:  The format string to pass to struct.pack().
  """

  value_size = struct.calcsize(format)
  if value_size == 4:
    def EncodeNonFiniteOrRaise(write, value):

      if value == _POS_INF:
        write('\x00\x00\x80\x7F')
      elif value == _NEG_INF:
        write('\x00\x00\x80\xFF')
      elif value != value:
        write('\x00\x00\xC0\x7F')
      else:
        raise
  elif value_size == 8:
    def EncodeNonFiniteOrRaise(write, value):
      if value == _POS_INF:
        write('\x00\x00\x00\x00\x00\x00\xF0\x7F')
      elif value == _NEG_INF:
        write('\x00\x00\x00\x00\x00\x00\xF0\xFF')
      elif value != value:
        write('\x00\x00\x00\x00\x00\x00\xF8\x7F')
      else:
        raise
  else:
    raise ValueError('Can\'t encode floating-point values that are '
                     '%d bytes long (only 4 or 8)' % value_size)

  def SpecificEncoder(field_number, is_repeated, is_packed):
    local_struct_pack = struct.pack
    if is_packed:
      tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
      local_EncodeVarint = _EncodeVarint
      def EncodePackedField(write, value):
        write(tag_bytes)
        local_EncodeVarint(write, len(value) * value_size)
        for element in value:


          try:
            write(local_struct_pack(format, element))
          except SystemError:
            EncodeNonFiniteOrRaise(write, element)
      return EncodePackedField
    elif is_repeated:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeRepeatedField(write, value):
        for element in value:
          write(tag_bytes)
          try:
            write(local_struct_pack(format, element))
          except SystemError:
            EncodeNonFiniteOrRaise(write, element)
      return EncodeRepeatedField
    else:
      tag_bytes = TagBytes(field_number, wire_type)
      def EncodeField(write, value):
        write(tag_bytes)
        try:
          write(local_struct_pack(format, value))
        except SystemError:
          EncodeNonFiniteOrRaise(write, value)
      return EncodeField

  return SpecificEncoder







Int32Encoder = Int64Encoder = EnumEncoder = _SimpleEncoder(
    wire_format.WIRETYPE_VARINT, _EncodeSignedVarint, _SignedVarintSize)

UInt32Encoder = UInt64Encoder = _SimpleEncoder(
    wire_format.WIRETYPE_VARINT, _EncodeVarint, _VarintSize)

SInt32Encoder = SInt64Encoder = _ModifiedEncoder(
    wire_format.WIRETYPE_VARINT, _EncodeVarint, _VarintSize,
    wire_format.ZigZagEncode)





Fixed32Encoder  = _StructPackEncoder(wire_format.WIRETYPE_FIXED32, '<I')
Fixed64Encoder  = _StructPackEncoder(wire_format.WIRETYPE_FIXED64, '<Q')
SFixed32Encoder = _StructPackEncoder(wire_format.WIRETYPE_FIXED32, '<i')
SFixed64Encoder = _StructPackEncoder(wire_format.WIRETYPE_FIXED64, '<q')
FloatEncoder    = _FloatingPointEncoder(wire_format.WIRETYPE_FIXED32, '<f')
DoubleEncoder   = _FloatingPointEncoder(wire_format.WIRETYPE_FIXED64, '<d')


def BoolEncoder(field_number, is_repeated, is_packed):
  """Returns an encoder for a boolean field."""

  false_byte = chr(0)
  true_byte = chr(1)
  if is_packed:
    tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
    local_EncodeVarint = _EncodeVarint
    def EncodePackedField(write, value):
      write(tag_bytes)
      local_EncodeVarint(write, len(value))
      for element in value:
        if element:
          write(true_byte)
        else:
          write(false_byte)
    return EncodePackedField
  elif is_repeated:
    tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_VARINT)
    def EncodeRepeatedField(write, value):
      for element in value:
        write(tag_bytes)
        if element:
          write(true_byte)
        else:
          write(false_byte)
    return EncodeRepeatedField
  else:
    tag_bytes = TagBytes(field_number, wire_format.WIRETYPE_VARINT)
    def EncodeField(write, value):
      write(tag_bytes)
      if value:
        return write(true_byte)
      return write(false_byte)
    return EncodeField


def StringEncoder(field_number, is_repeated, is_packed):
  """Returns an encoder for a string field."""

  tag = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
  local_EncodeVarint = _EncodeVarint
  local_len = len
  assert not is_packed
  if is_repeated:
    def EncodeRepeatedField(write, value):
      for element in value:
        encoded = element.encode('utf-8')
        write(tag)
        local_EncodeVarint(write, local_len(encoded))
        write(encoded)
    return EncodeRepeatedField
  else:
    def EncodeField(write, value):
      encoded = value.encode('utf-8')
      write(tag)
      local_EncodeVarint(write, local_len(encoded))
      return write(encoded)
    return EncodeField


def BytesEncoder(field_number, is_repeated, is_packed):
  """Returns an encoder for a bytes field."""

  tag = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
  local_EncodeVarint = _EncodeVarint
  local_len = len
  assert not is_packed
  if is_repeated:
    def EncodeRepeatedField(write, value):
      for element in value:
        write(tag)
        local_EncodeVarint(write, local_len(element))
        write(element)
    return EncodeRepeatedField
  else:
    def EncodeField(write, value):
      write(tag)
      local_EncodeVarint(write, local_len(value))
      return write(value)
    return EncodeField


def GroupEncoder(field_number, is_repeated, is_packed):
  """Returns an encoder for a group field."""

  start_tag = TagBytes(field_number, wire_format.WIRETYPE_START_GROUP)
  end_tag = TagBytes(field_number, wire_format.WIRETYPE_END_GROUP)
  assert not is_packed
  if is_repeated:
    def EncodeRepeatedField(write, value):
      for element in value:
        write(start_tag)
        element._InternalSerialize(write)
        write(end_tag)
    return EncodeRepeatedField
  else:
    def EncodeField(write, value):
      write(start_tag)
      value._InternalSerialize(write)
      return write(end_tag)
    return EncodeField


def MessageEncoder(field_number, is_repeated, is_packed):
  """Returns an encoder for a message field."""

  tag = TagBytes(field_number, wire_format.WIRETYPE_LENGTH_DELIMITED)
  local_EncodeVarint = _EncodeVarint
  assert not is_packed
  if is_repeated:
    def EncodeRepeatedField(write, value):
      for element in value:
        write(tag)
        local_EncodeVarint(write, element.ByteSize())
        element._InternalSerialize(write)
    return EncodeRepeatedField
  else:
    def EncodeField(write, value):
      write(tag)
      local_EncodeVarint(write, value.ByteSize())
      return value._InternalSerialize(write)
    return EncodeField






def MessageSetItemEncoder(field_number):
  """Encoder for extensions of MessageSet.

  The message set message looks like this:
    message MessageSet {
      repeated group Item = 1 {
        required int32 type_id = 2;
        required string message = 3;
      }
    }
  """
  start_bytes = "".join([
      TagBytes(1, wire_format.WIRETYPE_START_GROUP),
      TagBytes(2, wire_format.WIRETYPE_VARINT),
      _VarintBytes(field_number),
      TagBytes(3, wire_format.WIRETYPE_LENGTH_DELIMITED)])
  end_bytes = TagBytes(1, wire_format.WIRETYPE_END_GROUP)
  local_EncodeVarint = _EncodeVarint

  def EncodeField(write, value):
    write(start_bytes)
    local_EncodeVarint(write, value.ByteSize())
    value._InternalSerialize(write)
    return write(end_bytes)

  return EncodeField
