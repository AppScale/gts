"""
This module contains shared encoding and decoding utilities for translating
datastore types to bytestrings and vice versa.
"""
import struct
import sys

import six

from appscale.common.unpackaged import APPSCALE_PYTHON_APPSERVER
from appscale.datastore.dbconstants import BadRequest, InternalError
from appscale.datastore.fdb.utils import fdb

sys.path.append(APPSCALE_PYTHON_APPSERVER)
from google.appengine.datastore import entity_pb

# The number of bytes used to encode a read versionstamp.
READ_VS_SIZE = 8


class V3Types(object):
  NULL = b'\x00'
  INT64 = b'\x01'
  BOOLEAN = b'\x02'
  STRING = b'\x03'
  DOUBLE = b'\x04'
  POINT = b'\x05'
  USER = b'\x06'
  REFERENCE = b'\x07'

  accessible = (
    ('int64', INT64), ('boolean', BOOLEAN), ('string', STRING),
    ('double', DOUBLE), ('point', POINT), ('user', USER),
    ('reference', REFERENCE))

  @classmethod
  def null(cls, encoded_type):
    return encoded_type == cls.NULL or cls.reverse(encoded_type) == cls.NULL

  @classmethod
  def scalar(cls, encoded_type):
    scalar_types = (cls.INT64, cls.BOOLEAN, cls.STRING, cls.DOUBLE)
    return (encoded_type in scalar_types or
            cls.reverse(encoded_type) in scalar_types)

  @classmethod
  def compound(cls, encoded_type):
    compound_types = (cls.POINT, cls.USER, cls.REFERENCE)
    return (encoded_type in compound_types or
            cls.reverse(encoded_type) in compound_types)

  @classmethod
  def name(cls, encoded_type):
    return next(key for key, val in V3Types.__dict__.items()
                if val == encoded_type or val == cls.reverse(encoded_type))

  @staticmethod
  def reverse(encoded_type):
    return bytes(bytearray([255 - ord(encoded_type)]))


def decode_str(string):
  """ Converts byte strings to unicode strings. """
  if isinstance(string, six.text_type):
    return string

  return string.decode('utf-8')


def encode_element(element):
  """ Converts a path element protobuf object to a tuple. """
  if element.has_id():
    id_or_name = element.id()
  elif element.has_name():
    id_or_name = decode_str(element.name())
  else:
    raise BadRequest('All path elements must either have a name or ID')

  return decode_str(element.type()), id_or_name


def decode_element(element_tuple):
  """ Converts a tuple to a path element protobuf object. """
  path_element = entity_pb.Path_Element()
  path_element.set_type(element_tuple[0])
  if isinstance(element_tuple[1], int):
    path_element.set_id(element_tuple[1])
  else:
    path_element.set_name(element_tuple[1])

  return path_element


def encode_ancestor_range(subspace, path):
  """ Determines the start and stop key selectors for an ancestor range. """
  embedded_value = fdb.tuple.pack(path)
  # In order to exclude the ancestor itself, the range is manually selected
  # using the potential values for the next element in the key path. It's
  # normally a unicode string specifying the kind of the next element, but it
  # can also be an integer if it's the last element and the index directory
  # includes the kind.
  embedded_start = embedded_value + six.int2byte(fdb.tuple.STRING_CODE)
  embedded_stop = embedded_value + six.int2byte(fdb.tuple.POS_INT_END + 1)
  prefix = subspace.rawPrefix + six.int2byte(fdb.tuple.NESTED_CODE)
  start = fdb.KeySelector.first_greater_than(prefix + embedded_start)
  stop = fdb.KeySelector.first_greater_or_equal(prefix + embedded_stop)
  return start, stop


def encode_path(path):
  """ Converts a key path protobuf object to a tuple. """
  if isinstance(path, entity_pb.PropertyValue):
    element_list = path.referencevalue().pathelement_list()
  elif isinstance(path, entity_pb.PropertyValue_ReferenceValue):
    element_list = path.pathelement_list()
  else:
    element_list = path.element_list()

  return tuple(item for element in element_list
               for item in encode_element(element))


def decode_path(encoded_path, reference_value=False):
  """ Converts a tuple to a key path protobuf object. """
  if reference_value:
    path = entity_pb.PropertyValue_ReferenceValue()
  else:
    path = entity_pb.Path()

  for index in range(0, len(encoded_path), 2):
    element = path.add_element()
    element.set_type(encoded_path[index])
    id_or_name = encoded_path[index + 1]
    if isinstance(id_or_name, int):
      element.set_id(id_or_name)
    else:
      element.set_name(id_or_name)

  return path


def reverse_encode_string(unicode_string):
  """ Encodes strings so that they will be sorted in reverse order. """
  byte_array = bytearray(unicode_string, encoding='utf-8')
  # In order to place smaller byte values before larger ones, each byte is
  # inverted. In order to ensure that the shorter of two strings with otherwise
  # identical prefixes will be placed after the longer string, the largest byte
  # value (255) is used to terminate the string.
  # Since b'\x00' would normally be encoded as the terminator with this
  # conversion, each value is first shifted up a value before being inverted.
  # For example, b'\x00' -> b'\x01' -> b'\xfe'. Luckily, b'\xff' is not used
  # by UTF-8, so every encoded UTF-8 byte can be incremented without exceeding
  # the largest byte value.
  for index, byte_value in enumerate(byte_array):
    byte_array[index] = 255 - (byte_value + 1)

  return bytes(byte_array) + b'\xff'


def reverse_decode_string(byte_string):
  """ Recovers the original unicode string from a reverse-encoded one. """
  byte_array = bytearray(byte_string[:-1])
  for index, byte_value in enumerate(byte_array):
    byte_array[index] = (255 - byte_value) - 1

  return byte_array.decode('utf-8')


def decode_point(val):
  """ Converts a tuple to a PointValue property value object. """
  point_val = entity_pb.PropertyValue_PointValue()
  point_val.set_x(val[0])
  point_val.set_y(val[1])
  return point_val


def decode_user(val):
  """ Converts a tuple to a UserValue property value object. """
  user_val = entity_pb.PropertyValue_UserValue()
  user_val.set_email(val[0])
  user_val.set_auth_domain(val[1])
  return user_val


def encode_reference(val):
  """ Converts an entity key protobuf object to a tuple. """
  project_id = decode_str(val.app())
  namespace = decode_str(val.name_space())
  return (project_id, namespace) + encode_path(val)


def decode_reference(val):
  """ Converts a tuple to an entity key protobuf object. """
  reference_val = entity_pb.PropertyValue_ReferenceValue()
  reference_val.set_app(val[0])
  reference_val.set_name_space(val[1])
  reference_val.MergeFrom(decode_path(val[2:], reference_value=True))
  return reference_val


ENCODERS = {
  V3Types.NULL: lambda val: tuple(),
  V3Types.INT64: lambda val: (val,),
  V3Types.BOOLEAN: lambda val: (val,),
  V3Types.STRING: lambda val: (decode_str(val),),
  V3Types.DOUBLE: lambda val: (val,),
  V3Types.POINT: lambda val: (val.x(), val.y()),
  V3Types.USER: lambda val: (decode_str(val.email()),
                             decode_str(val.auth_domain())),
  V3Types.REFERENCE: encode_reference,
  V3Types.reverse(V3Types.NULL): lambda val: tuple(),
  V3Types.reverse(V3Types.INT64): lambda val: (val * -1,),
  V3Types.reverse(V3Types.BOOLEAN): lambda val: (not val,),
  V3Types.reverse(V3Types.STRING):
    lambda val: (reverse_encode_string(decode_str(val)),),
  V3Types.reverse(V3Types.DOUBLE): lambda val: (val * -1,),
  V3Types.reverse(V3Types.POINT): lambda val: (val.x() * -1, val.y() * -1),
  V3Types.reverse(V3Types.USER):
    lambda val: (reverse_encode_string(decode_str(val.email())),
                 reverse_encode_string(decode_str(val.auth_domain()))),
  V3Types.reverse(V3Types.REFERENCE):
    lambda val: tuple(reverse_encode_string(item)
                      for item in encode_reference(val))
}


DECODERS = {
  V3Types.INT64: lambda val: val[0],
  V3Types.BOOLEAN: lambda val: val[0],
  V3Types.STRING: lambda val: val[0],
  V3Types.DOUBLE: lambda val: val[0],
  V3Types.POINT: decode_point,
  V3Types.USER: decode_user,
  V3Types.REFERENCE: decode_reference,
  V3Types.reverse(V3Types.INT64): lambda val: val[0] * -1,
  V3Types.reverse(V3Types.BOOLEAN): lambda val: not val[0],
  V3Types.reverse(V3Types.STRING): lambda val: reverse_decode_string(val[0]),
  V3Types.reverse(V3Types.DOUBLE): lambda val: val[0] * -1,
  V3Types.reverse(V3Types.POINT):
    lambda val: decode_point((val[0] * -1, val[1] * -1)),
  V3Types.reverse(V3Types.USER):
    lambda val: decode_user((reverse_decode_string(val[0]),
                             reverse_decode_string(val[1]))),
  V3Types.reverse(V3Types.REFERENCE):
    lambda val: decode_reference(tuple(reverse_decode_string(item)
                                       for item in val))
}


def unpack_value(value):
  """ Extracts the value from a V3 PropertyValue object.

  Args:
    value: A PropertyValue protobuf object.
  Returns:
    A tuple in the form of (<value-type>, <value>).
  """
  for type_name, encoded_type in V3Types.accessible:
    if getattr(value, 'has_{}value'.format(type_name))():
      return encoded_type, getattr(value, '{}value'.format(type_name))()

  return V3Types.NULL, None


def encode_value(value, reverse=False):
  """ Converts a PropertyValue to a tuple. """
  if isinstance(value, six.integer_types):
    encoded_type = V3Types.INT64
  else:
    encoded_type, value = unpack_value(value)

  if reverse:
    encoded_type = V3Types.reverse(encoded_type)

  return (encoded_type,) + ENCODERS[encoded_type](value)


def decode_value(encoded_value):
  """ Converts a tuple to a PropertyValue. """
  prop_value = entity_pb.PropertyValue()
  encoded_type = encoded_value[0]
  if V3Types.null(encoded_type):
    return prop_value

  decoded_value = DECODERS[encoded_type](encoded_value[1:])
  type_name = V3Types.name(encoded_type).lower()
  if V3Types.scalar(encoded_type):
    getattr(prop_value, 'set_{}value'.format(type_name))(decoded_value)
  elif V3Types.compound(encoded_type):
    compound_val = getattr(prop_value, 'mutable_{}value'.format(type_name))()
    compound_val.MergeFrom(decoded_value)

  return prop_value


def encode_sortable_int(value, byte_count):
  """ Encodes an integer using the specified number of bytes. """
  format_str = u'>Q' if byte_count > 4 else u'>I'
  encoded = struct.pack(format_str, value)
  if any(byte != b'\x00' for byte in encoded[:-1 * byte_count]):
    raise InternalError(u'Value exceeds maximum size')

  return encoded[-1 * byte_count:]


def decode_sortable_int(encoded_value):
  """ Converts a byte string to an integer. """
  format_str = u'>Q' if len(encoded_value) > 4 else u'>I'
  format_size = 8 if len(encoded_value) > 4 else 4
  encoded_value = b'\x00' * (format_size - len(encoded_value)) + encoded_value
  return struct.unpack(format_str, encoded_value)[0]


encode_read_vs = lambda read_version: encode_sortable_int(
  read_version, READ_VS_SIZE)


def encode_vs_index(vs_position):
  """ Encodes an FDB key index position. """
  return struct.pack(u'<L', vs_position)
