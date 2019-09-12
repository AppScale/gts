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

# The number of bytes used to encode a read version in a way that is comparable
# to commit versionstamps.
READ_VERSION_SIZE = 8

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
# is placed before the longer one. Otherwise, the following byte(s) could
# determine the sort order. It also allows a decoder to find the end of the
# value.
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
  """
  Handles encoding and decoding operations for 64-bit integers. The encoded
  value is variable-length. The value of the marker indicates how many bytes
  were used to encode the value.
  """
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
  """
  Handles encoding and decoding operations for arbitrary blobs. Since the
  length of the value is variable and there is usually data that follows the
  encoded value, a terminator byte is used to indicate the end of the value.
  Any occurrence of the terminator byte within the value is escaped in order to
  preserve the ordering and allow the parser to find the real terminator.
  """
  @classmethod
  def encode(cls, value, prefix=six.int2byte(BYTES_CODE), reverse=False):
    packed = reverse_bits(value) if reverse else value
    terminator = encode_marker(TERMINATOR, reverse)
    # Replace each occurrence of the terminator with a sequence that maintains
    # the sort order. In order for the parser to be able to find the end of the
    # value, directories that use this codec must ensure that the first byte
    # that follows the encoded Bytes object must not be 0x00 or 0xFF.
    if reverse:
      # The preceding 0xFE ensures a terminator character within the value
      # compares as less than the real terminator. For example,
      # 0x0200 -> 0xFDFF -> 0xFDFEFF00FF should come before
      # 0x02   -> 0xFD   -> 0xFDFF
      # The trailing 0x00 ensures that the parser is able to differentiate
      # between a replaced value and the real terminator.
      packed = packed.replace(terminator, b'\xFE\xFF\x00')
    else:
      # A trailing 0xFF is enough for the parser to find the terminator and
      # to maintain sort order despite the values that follow. For example
      # (assuming 0x10 is the value that follows),
      # 0x00, 0x10   -> 0x00FF0010     (not 0x000010) should come before
      # 0x0000, 0x10 -> 0x00FF00FF0010 (not 0x00000010)
      packed = packed.replace(terminator, b'\x00\xFF')

    return prefix + packed + terminator

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    end = cls._find_terminator(blob, pos, reverse)
    packed = blob[pos:end]
    terminator = encode_marker(TERMINATOR, reverse)
    if reverse:
      packed = packed.replace(b'\xFE\xFF\x00', terminator)
    else:
      packed = packed.replace(b'\x00\xFF', terminator)

    value = reverse_bits(packed) if reverse else packed
    return value, end + 1

  @staticmethod
  def _find_terminator(blob, pos, reverse=False):
    """ Finds the position of the terminator. """
    terminator = encode_marker(TERMINATOR, reverse)
    escape_byte = b'\x00' if reverse else b'\xFF'
    while True:
      pos = blob.find(terminator, pos)
      if pos < 0:
        raise InternalError(u'Byte string is missing terminator')

      if blob[pos + 1:pos + 2] != escape_byte:
        return pos

      pos += 2


class Double(object):
  """
  Handles encoding and decoding operations for floating point values. 8 bytes
  (plus the marker byte) are always used.
  """
  @classmethod
  def encode(cls, value, prefix=six.int2byte(DOUBLE_CODE), reverse=False):
    packed = struct.pack('>d', value)
    # The first bit of the packed value indicates whether it's negative or not.
    positive = six.indexbytes(packed, 0) & 0x80 == 0x00
    if positive:
      # Flip the sign bit.
      packed = six.int2byte(six.indexbytes(packed, 0) ^ 0x80) + packed[1:]
      if reverse:
        packed = reverse_bits(packed)
    else:
      # Flip all the bits unless the sort order is reversed.
      packed = packed if reverse else reverse_bits(packed)

    return prefix + packed

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    packed = blob[pos:pos + 8]
    pos += 8
    first_bit = six.indexbytes(packed, 0) & 0x80 == 0x80
    positive = first_bit if not reverse else not first_bit
    if positive:
      if reverse:
        packed = reverse_bits(packed)

      # Restore the sign bit.
      packed = six.int2byte(six.indexbytes(packed, 0) ^ 0x80) + packed[1:]
    else:
      # Restore all the original bits for ascending values.
      packed = packed if reverse else reverse_bits(packed)

    value = struct.unpack('>d', packed)[0]
    return value, pos


class Point(object):
  """
  Handles encoding and decoding operations for point values. The Double codec
  is used for each coordinate (x and y).
  """
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
    return point_val, pos


class Text(object):
  """
  Handles encoding and decoding operations for unicode strings. Since the
  length of the value is variable and there is usually data that follows the
  encoded value, a terminator byte is used to indicate the end of the value.
  """
  @classmethod
  def encode(cls, unicode_string, prefix=b'', reverse=False):
    # Ensure the encoded value does not contain the terminator. UTF-8 does not
    # use 0xFF, so this can be done without exceeding the largest byte value.
    if reverse:
      encode_byte = lambda x: six.int2byte(x + 1 ^ 0xFF)
    else:
      encode_byte = lambda x: six.int2byte(x + 1)

    encoded = b''.join(
      map(encode_byte, six.iterbytes(unicode_string.encode('utf-8'))))
    terminator = encode_marker(TERMINATOR, reverse)
    return prefix + encoded + terminator

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
  """
  Handles encoding and decoding operations for User values. The Double codec
  is used for each of the required fields (email and auth_domain).
  """
  @classmethod
  def encode(cls, value, prefix=six.int2byte(POINT_CODE), reverse=False):
    packed = (Text.encode(decode_str(value.email()), reverse=reverse) +
              Text.encode(decode_str(value.auth_domain()), reverse=reverse))
    return prefix + packed

  @classmethod
  def decode(cls, blob, pos, reverse=False):
    email, pos = Text.decode(blob, pos, reverse)
    auth_domain, pos = Text.decode(blob, pos, reverse)
    user_val = entity_pb.PropertyValue_UserValue()
    user_val.set_email(email)
    user_val.set_auth_domain(auth_domain)
    return user_val, pos


class Path(object):
  """
  Handles encoding and decoding operations for entity paths. The Text codec
  is used for kinds and names. The Int64 codec is used for IDs.
  """
  KIND_MARKER = 0x1C

  MIN_ID_MARKER = INT64_ZERO_CODE - 8

  # Marks an item as a name rather than an ID. These should be be placed after
  # entries with IDs.
  NAME_MARKER = 0x1D

  @classmethod
  def pack(cls, path, prefix=b'', omit_terminator=False, reverse=False):
    if not isinstance(path, tuple):
      path = cls.flatten(path)

    encoded_items = []
    kind_marker = encode_marker(cls.KIND_MARKER, reverse)
    for index in range(0, len(path), 2):
      kind = path[index]
      id_or_name = path[index + 1]
      encoded_items.append(Text.encode(kind, kind_marker, reverse))
      encoded_items.append(cls.encode_id_or_name(id_or_name, reverse))

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
  def unpack(cls, blob, pos, reverse=False):
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
        raise InternalError(u'Encoded path is missing kind')

      kind, pos = Text.decode(blob, pos, reverse)
      items.append(kind)

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
  """
  Handles encoding and decoding operations for entity keys. The Text codec is
  used for the project ID and namespace. The Path codec is used for the key's
  path.
  """
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
    flat_path, pos = Path.unpack(blob, pos, reverse)
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
  """
  Handles encoding and decoding operations for transaction IDs. Since this
  cannot handle every commit versionstamp value, it will be removed as soon as
  the interface can handle larger values for transaction handles.
  """
  COMMIT_VERSION_BITS = 8 * 7 - 4

  BATCH_ORDER_BITS = 8

  @classmethod
  def encode(cls, scatter_val, commit_versionstamp):
    commit_version = struct.unpack('>Q', commit_versionstamp[:8])[0]
    batch_order = struct.unpack('>H', commit_versionstamp[8:])[0]
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


encode_read_version = lambda read_version: Int64.encode_bare(
  read_version, READ_VERSION_SIZE)


def encode_versionstamp_index(versionstamp_position):
  """ Encodes an FDB key index position. """
  return struct.pack(u'<L', versionstamp_position)
