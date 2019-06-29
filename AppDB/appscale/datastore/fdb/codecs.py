"""
This module contains shared encoding and decoding utilities for translating
datastore types to bytestrings and vice versa.
"""
import bisect
import logging
import struct
import sys

import six

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.dbconstants import BadRequest, InternalError

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb

# The number of bytes used to encode a read versionstamp.
READ_VS_SIZE = 8

# Byte values that signify a data type. A couple values are left between each
# one just in case they need adjustment.
NULL_CODE = 0x01
# 17 values are reserved for integers in order to allow variable size in both a
# negative and positive direction.
INT64_ZERO_CODE = 0x0C
FALSE_CODE = 0x17
TRUE_CODE = 0x18
BYTES_CODE = 0x1B
DOUBLE_CODE = 0x1E
POINT_CODE = 0x21
USER_CODE = 0x24
REFERENCE_CODE = 0x27

# Ensures the shorter of two variable-length values (with identical prefixes)
# is placed before the longer one.
TERMINATOR = 0x00

logger = logging.getLogger(__name__)


def reverse_bits(blob):
  return b''.join(map(lambda x: six.int2byte(x ^ 0xFF), six.iterbytes(blob)))


def encode_marker(marker, reverse):
  return six.int2byte(marker ^ 0xFF) if reverse else six.int2byte(marker)


def decode_str(string):
  """ Converts byte strings to unicode strings. """
  if isinstance(string, six.text_type):
    return string

  return string.decode('utf-8')


class Int64(object):
  LIMITS = tuple((1 << (i * 8)) - 1 for i in range(9))

  @classmethod
  def encode(cls, value, reverse=False):
    if value == 0:
      code = INT64_ZERO_CODE
      packed = b''
    elif value > 0:
      encoded_size = bisect.bisect_left(cls.LIMITS, value)
      adjusted_value = cls.LIMITS[encoded_size] - value if reverse else value
      code = INT64_ZERO_CODE + encoded_size
      packed = struct.pack('>Q', adjusted_value)[-encoded_size:]
    else:
      encoded_size = bisect.bisect_left(cls.LIMITS, -value)
      # Shift negative values to an unsigned space.
      adjusted_value = -value if reverse else cls.LIMITS[encoded_size] + value
      code = INT64_ZERO_CODE - encoded_size
      packed = struct.pack('>Q', adjusted_value)[-encoded_size:]

    return encode_marker(code, reverse) + packed

  @classmethod
  def decode(cls, marker, blob, pos, reverse=False):
    code = ord(marker) ^ 0xFF if reverse else ord(marker)
    if code == INT64_ZERO_CODE:
      return 0, pos

    encoded_size = abs(code - INT64_ZERO_CODE)
    packed = b'\x00' * (8 - encoded_size) + blob[pos:pos + encoded_size]
    pos += encoded_size
    value = struct.unpack('>Q', packed)[0]
    if code > INT64_ZERO_CODE:
      value = cls.LIMITS[encoded_size] - value if reverse else value
    else:
      # Shift values back to their original, negative state.
      value = -value if reverse else value - cls.LIMITS[encoded_size]

    return value, pos

  @classmethod
  def encode_bare(cls, value, byte_count):
    """
    Encodes an integer without a prefix using the specified number of bytes.
    """
    encoded = struct.pack('>Q', value)
    if any(byte != b'\x00' for byte in encoded[:-byte_count]):
      raise InternalError(u'Value exceeds maximum size')

    return encoded[-byte_count:]

  @classmethod
  def decode_bare(cls, encoded_value):
    """ Decodes a byte string back to an integer. """
    encoded_value = b'\x00' * (8 - len(encoded_value)) + encoded_value
    return struct.unpack('>Q', encoded_value)[0]


class Bytes(object):
  @classmethod
  def encode(cls, value, prefix=six.int2byte(BYTES_CODE), reverse=False):
    packed = reverse_bits(value) if reverse else value
    terminator = encode_marker(TERMINATOR, reverse)
    # Escape each occurrence of the terminator. The first byte of whatever
    # follows must not contain the escape character.
    packed = packed.replace(terminator, terminator + reverse_bits(terminator))
    return prefix + packed + terminator

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    end = cls._find_terminator(blob, pos, reverse)
    terminator = encode_marker(TERMINATOR, reverse)
    packed = blob[pos:end].replace(terminator + reverse_bits(terminator),
                                   terminator)
    value = reverse_bits(packed) if reverse else packed
    return value, end + 1

  @staticmethod
  def _find_terminator(blob, pos, reverse=False):
    """ Finds the position of the terminator. """
    terminator = encode_marker(TERMINATOR, reverse)
    escape_byte = reverse_bits(terminator)
    while True:
      pos = blob.find(terminator, pos)
      if pos < 0:
        raise InternalError(u'Byte string is missing terminator')

      if blob[pos + 1:pos + 2] != escape_byte:
        return pos

      pos += 2


class Double(object):
  @classmethod
  def encode(cls, value, prefix=six.int2byte(DOUBLE_CODE), reverse=False):
    adjusted_value = -value if reverse else value
    packed = struct.pack('>d', adjusted_value)
    # Flip all of the bits for negative values.
    if six.indexbytes(packed, 0) & 0x80 != 0x00:
      # If it's negative and reversed, there is no transformation.
      packed = packed if reverse else reverse_bits(packed)
    else:
      # Flip the sign bit for positive values.
      packed = six.int2byte(six.indexbytes(packed, 0) ^ 0x80) + packed[1:]
      if reverse:
        packed = reverse_bits(packed)

    return prefix + packed

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    packed = blob[pos:pos + 8]
    pos += 8
    # Restore all the original bits for reverse values.
    if six.indexbytes(packed, 0) & 0x80 != 0x80:
      # If it's negative and reversed, there is no transformation.
      packed = packed if reverse else reverse_bits(packed)
    else:
      # Restore the sign bit for positive values.
      packed = six.int2byte(six.indexbytes(packed, 0) ^ 0x80) + packed[1:]
      if reverse:
        packed = reverse_bits(packed)

    adjusted_value = struct.unpack('>d', packed)[0]
    value = -adjusted_value if reverse else adjusted_value
    return value, pos


class Point(object):
  @classmethod
  def encode(cls, value, prefix=six.int2byte(POINT_CODE), reverse=False):
    x_packed = Double.encode(value.x(), prefix=b'', reverse=reverse)
    y_packed = Double.encode(value.y(), prefix=b'', reverse=reverse)
    return prefix + x_packed + y_packed

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    x, pos = Double.decode(blob, pos, reverse)
    y, pos = Double.decode(blob, pos, reverse)
    point_val = entity_pb.PropertyValue_PointValue()
    point_val.set_x(x)
    point_val.set_y(y)
    return point_val


class Text(object):
  @classmethod
  def encode(cls, unicode_string, prefix=b'', reverse=False):
    byte_array = bytearray(unicode_string, encoding='utf-8')
    # Ensure the encoded value does not contain the terminator. UTF-8 does not
    # use 0xFF, so this can be done without exceeding the largest byte value.
    for index, byte_value in enumerate(byte_array):
      byte_array[index] = byte_value + 1
      if reverse:
        byte_array[index] = byte_value ^ 0xFF

    terminator = encode_marker(TERMINATOR, reverse)
    return prefix + bytes(byte_array) + terminator

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    terminator = TERMINATOR ^ 0xFF if reverse else TERMINATOR
    byte_array = bytearray()
    while pos < len(blob):
      byte_value = six.indexbytes(blob, pos)
      pos += 1
      if byte_value == terminator:
        break

      if reverse:
        byte_value ^= 0xFF

      # Shift the byte back to its original value.
      byte_array.append(byte_value - 1)

    return byte_array.decode('utf-8'), pos


class User(object):
  @classmethod
  def encode(cls, value, prefix=six.int2byte(POINT_CODE), reverse=False):
    packed = (Text.encode(decode_str(value.email()), reverse=reverse) +
              Text.encode(decode_str(value.auth_domain()), reverse=reverse))
    return prefix + packed

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    email, pos = Text.decode(blob, pos, reverse)
    auth_domain, pos = Double.decode(blob, pos, reverse)
    user_val = entity_pb.PropertyValue_UserValue()
    user_val.set_email(email)
    user_val.set_auth_domain(auth_domain)
    return user_val


class Path(object):
  KIND_MARKER = 0x1C

  MIN_ID_MARKER = INT64_ZERO_CODE - 8

  # Marks an item as a name rather than an ID. These should be be placed after
  # entries with IDs.
  NAME_MARKER = 0x1D

  @classmethod
  def pack(cls, path, omit_kind=None, prefix=b'', omit_terminator=False,
           reverse=False):
    if not isinstance(path, tuple):
      path = cls.flatten(path)

    encoded_items = []
    kind_marker = encode_marker(cls.KIND_MARKER, reverse)
    for index in range(0, len(path), 2):
      kind = path[index]
      if omit_kind is None or kind != omit_kind:
        encoded_items.append(Text.encode(kind, kind_marker, reverse))

      encoded_items.append(cls.encode_id_or_name(path[index + 1], reverse))

    terminator = b'' if omit_terminator else encode_marker(TERMINATOR, reverse)
    return b''.join([prefix] + encoded_items + [terminator])

  @classmethod
  def encode_id_or_name(cls, id_or_name, reverse=False):
    if isinstance(id_or_name, six.text_type):
      name_marker = encode_marker(cls.NAME_MARKER, reverse)
      return Text.encode(id_or_name, name_marker, reverse)
    elif isinstance(id_or_name, int):
      return Int64.encode(id_or_name, reverse)
    else:
      raise BadRequest(u'Invalid path element type')

  @classmethod
  def unpack(cls, blob, pos, kind=None, reverse=False):
    items = []
    terminator = encode_marker(TERMINATOR, reverse)
    kind_marker = encode_marker(cls.KIND_MARKER, reverse)
    name_marker = encode_marker(cls.NAME_MARKER, reverse)
    while pos < len(blob):
      marker = blob[pos]
      pos += 1
      if marker == terminator:
        break

      if marker != kind_marker:
        if not kind:
          raise InternalError(u'Encoded path is missing kind')

        items.append(kind)
        pos -= 1
      else:
        elem_kind, pos = Text.decode(blob, pos, reverse)
        items.append(elem_kind)

      marker = blob[pos]
      pos += 1
      if marker == name_marker:
        elem_name, pos = Text.decode(blob, pos, reverse)
        items.append(elem_name)
      else:
        elem_id, pos = Int64.decode(marker, blob, pos, reverse)
        items.append(elem_id)

    return tuple(items), pos

  @staticmethod
  def flatten(path):
    """ Converts a key path protobuf object to a tuple. """
    if isinstance(path, entity_pb.PropertyValue):
      element_list = path.referencevalue().pathelement_list()
    elif isinstance(path, entity_pb.PropertyValue_ReferenceValue):
      element_list = path.pathelement_list()
    else:
      element_list = path.element_list()

    return tuple(item for element in element_list
                 for item in Path.encode_element(element))

  @staticmethod
  def decode(flat_path, reference_value=False):
    """ Converts a tuple to a key path protobuf object. """
    if reference_value:
      path = entity_pb.PropertyValue_ReferenceValue()
    else:
      path = entity_pb.Path()

    for index in range(0, len(flat_path), 2):
      if reference_value:
        element = path.add_pathelement()
      else:
        element = path.add_element()

      element.set_type(flat_path[index])
      id_or_name = flat_path[index + 1]
      if isinstance(id_or_name, int):
        element.set_id(id_or_name)
      else:
        element.set_name(id_or_name.encode('utf-8'))

    return path

  @staticmethod
  def encode_element(element):
    """ Converts a path element protobuf object to a tuple. """
    if element.has_id():
      id_or_name = int(element.id())
    elif element.has_name():
      id_or_name = decode_str(element.name())
    else:
      raise BadRequest(u'All path elements must either have a name or ID')

    return decode_str(element.type()), id_or_name

  @staticmethod
  def decode_element(element_tuple):
    """ Converts a tuple to a path element protobuf object. """
    path_element = entity_pb.Path_Element()
    path_element.set_type(element_tuple[0])
    if isinstance(element_tuple[1], int):
      path_element.set_id(element_tuple[1])
    else:
      path_element.set_name(element_tuple[1])

    return path_element


class Reference(object):
  @classmethod
  def encode(cls, value, prefix=six.int2byte(REFERENCE_CODE), reverse=False):
    return b''.join([
      prefix,
      Text.encode(decode_str(value.app()), reverse=reverse),
      Text.encode(decode_str(value.name_space()), reverse=reverse),
      Path.pack(Path.flatten(value), reverse=reverse)
    ])

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    project_id, pos = Text.decode(blob, pos, reverse)
    namespace, pos = Text.decode(blob, pos, reverse)
    flat_path, pos = Path.unpack(blob, pos, reverse=reverse)
    reference_val = entity_pb.PropertyValue_ReferenceValue()
    reference_val.set_app(project_id)
    reference_val.set_name_space(namespace)
    reference_val.MergeFrom(Path.decode(flat_path, reference_value=True))
    return reference_val, pos


def encode_value(value, reverse=False):
  if isinstance(value, six.integer_types):
    return Int64.encode(value, reverse)

  if value.has_int64value():
    return Int64.encode(value.int64value(), reverse)

  if value.has_booleanvalue():
    to_encode = TRUE_CODE if value.booleanvalue() else FALSE_CODE
    return encode_marker(to_encode, reverse)

  if value.has_stringvalue():
    prefix = encode_marker(BYTES_CODE, reverse)
    return Bytes.encode(value.stringvalue(), prefix, reverse)

  if value.has_doublevalue():
    prefix = encode_marker(DOUBLE_CODE, reverse)
    return Double.encode(value.doublevalue(), prefix, reverse)

  if value.has_pointvalue():
    prefix = encode_marker(POINT_CODE, reverse)
    return Point.encode(value.pointvalue(), prefix, reverse)

  if value.has_uservalue():
    prefix = encode_marker(USER_CODE, reverse)
    return User.encode(value.uservalue(), prefix, reverse)

  if value.has_referencevalue():
    prefix = encode_marker(REFERENCE_CODE, reverse)
    return Reference.encode(value.referencevalue(), prefix, reverse)

  return encode_marker(NULL_CODE, reverse)


def decode_value(blob, pos, reverse=False):
  prop_value = entity_pb.PropertyValue()
  marker = blob[pos]
  pos += 1
  code = ord(marker) ^ 0xFF if reverse else ord(marker)
  if code == NULL_CODE:
    pass
  elif INT64_ZERO_CODE - 8 <= code <= INT64_ZERO_CODE + 8:
    int_val, pos = Int64.decode(marker, blob, pos, reverse)
    prop_value.set_int64value(int_val)
  elif code in (TRUE_CODE, FALSE_CODE):
    prop_value.set_booleanvalue(code == TRUE_CODE)
  elif code == BYTES_CODE:
    bytes_val, pos = Bytes.decode(blob, pos, reverse)
    prop_value.set_stringvalue(bytes_val)
  elif code == DOUBLE_CODE:
    double_val, pos = Double.decode(blob, pos, reverse)
    prop_value.set_doublevalue(double_val)
  elif code == POINT_CODE:
    point_val, pos = Point.decode(blob, pos, reverse)
    prop_value.mutable_pointvalue().MergeFrom(point_val)
  elif code == USER_CODE:
    user_val, pos = User.decode(blob, pos, reverse)
    prop_value.mutable_uservalue().MergeFrom(user_val)
  elif code == REFERENCE_CODE:
    ref_val, pos = Reference.decode(blob, pos, reverse)
    prop_value.mutable_referencevalue().MergeFrom(ref_val)

  return prop_value, pos


class TransactionID(object):
  COMMIT_VERSION_BITS = 8 * 7 - 4

  BATCH_ORDER_BITS = 8

  @classmethod
  def encode(cls, scatter_val, commit_vs):
    commit_version = struct.unpack('>Q', commit_vs[:8])[0]
    batch_order = struct.unpack('>H', commit_vs[8:])[0]
    if not 0 <= scatter_val <= 15:
      raise InternalError(u'Invalid scatter value')

    if commit_version >= 2 ** cls.COMMIT_VERSION_BITS:
      raise InternalError(u'Commit version too high')

    if batch_order >= 2 ** cls.BATCH_ORDER_BITS:
      raise InternalError(u'Batch order too high')

    return (commit_version << 12) + (batch_order << 4) + scatter_val

  @classmethod
  def decode(cls, txid):
    commit_version_bytes = struct.pack('>Q', txid >> 12)
    batch_order_bytes = struct.pack('>H', (txid & 0x0FF0) >> 4)
    scatter_val = txid & 0x0F
    return scatter_val, commit_version_bytes + batch_order_bytes


encode_read_vs = lambda read_version: Int64.encode_bare(
  read_version, READ_VS_SIZE)


def encode_vs_index(vs_position):
  """ Encodes an FDB key index position. """
  return struct.pack(u'<L', vs_position)
