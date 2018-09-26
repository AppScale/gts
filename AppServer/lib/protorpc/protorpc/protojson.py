#!/usr/bin/env python
#
# Copyright 2010 Google Inc.
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

"""JSON support for message types.

Public classes:
  MessageJSONEncoder: JSON encoder for message objects.

Public functions:
  encode_message: Encodes a message in to a JSON string.
  decode_message: Merge from a JSON string in to a message.
"""

__author__ = 'rafek@google.com (Rafe Kaplan)'

import cStringIO
import base64
import logging

from . import message_types
from . import messages
from . import util

__all__ = [
    'ALTERNATIVE_CONTENT_TYPES',
    'CONTENT_TYPE',
    'MessageJSONEncoder',
    'encode_message',
    'decode_message',
]

CONTENT_TYPE = 'application/json'

ALTERNATIVE_CONTENT_TYPES = [
  'application/x-javascript',
  'text/javascript',
  'text/x-javascript',
  'text/x-json',
  'text/json',
]


def _load_json_module():
  """Try to load a valid json module.

  There are more than one json modules that might be installed.  They are
  mostly compatible with one another but some versions may be different.
  This function attempts to load various json modules in a preferred order.
  It does a basic check to guess if a loaded version of json is compatible.

  Returns:
    Compatible json module.

  Raises:
    ImportError if there are no json modules or the loaded json module is
      not compatible with ProtoRPC.
  """
  first_import_error = None
  for module_name in ['json',
                      'simplejson']:
    try:
      module = __import__(module_name, {}, {}, 'json')
      if not hasattr(module, 'JSONEncoder'):
        message = ('json library "%s" is not compatible with ProtoRPC' %
                   module_name)
        logging.warning(message)
        raise ImportError(message)
      else:
        return module
    except ImportError, err:
      if not first_import_error:
        first_import_error = err

  logging.error('Must use valid json library (Python 2.6 json or simplejson)')
  raise first_import_error
json = _load_json_module()


class MessageJSONEncoder(json.JSONEncoder):
  """Message JSON encoder class.

  Extension of JSONEncoder that can build JSON from a message object.
  """

  def default(self, value):
    """Return dictionary instance from a message object.

    Args:
    value: Value to get dictionary for.  If not encodable, will
      call superclasses default method.
    """
    if isinstance(value, messages.Enum):
      return str(value)

    if isinstance(value, messages.Message):
      result = {}
      for field in value.all_fields():
        item = value.get_assigned_value(field.name)
        if item not in (None, [], ()):
          if isinstance(field, messages.BytesField):
            if field.repeated:
              item = [base64.b64encode(i) for i in item]
            else:
              item = base64.b64encode(item)
          elif isinstance(field, message_types.DateTimeField):
            # DateTimeField stores its data as a RFC 3339 compliant string.
            if field.repeated:
              item = [i.isoformat() for i in item]
            else:
              item = item.isoformat()
          result[field.name] = item
      # Handle unrecognized fields, so they're included when a message is
      # decoded then encoded.
      for unknown_key in value.all_unrecognized_fields():
        unrecognized_field, _ = value.get_unrecognized_field_info(unknown_key)
        result[unknown_key] = unrecognized_field
      return result
    else:
      return super(MessageJSONEncoder, self).default(value)


class _MessageJSONEncoder(MessageJSONEncoder):

  def __init__(self, *args, **kwds):
    """DEPRECATED: please use MessageJSONEncoder instead."""
    logging.warning(
        '_MessageJSONEncoder has been renamed to MessageJSONEncoder, '
        'please update any references')
    super(_MessageJSONEncoder, self).__init__(*args, **kwds)


def encode_message(message):
  """Encode Message instance to JSON string.

  Args:
    Message instance to encode in to JSON string.

  Returns:
    String encoding of Message instance in protocol JSON format.

  Raises:
    messages.ValidationError if message is not initialized.
  """
  message.check_initialized()

  return json.dumps(message, cls=MessageJSONEncoder)


def decode_message(message_type, encoded_message):
  """Merge JSON structure to Message instance.

  Args:
    message_type: Message to decode data to.
    encoded_message: JSON encoded version of message.

  Returns:
    Decoded instance of message_type.

  Raises:
    ValueError: If encoded_message is not valid JSON.
    messages.ValidationError if merged message is not initialized.
  """
  if not encoded_message.strip():
    return message_type()

  dictionary = json.loads(encoded_message)

  def find_variant(value):
    """Find the messages.Variant type that describes this value.

    Args:
      value: The value whose variant type is being determined.

    Returns:
      The messages.Variant value that best describes value's type, or None if
      it's a type we don't know how to handle.
    """
    if isinstance(value, bool):
      return messages.Variant.BOOL
    elif isinstance(value, (int, long)):
      return messages.Variant.INT64
    elif isinstance(value, float):
      return messages.Variant.DOUBLE
    elif isinstance(value, basestring):
      return messages.Variant.STRING
    elif isinstance(value, (list, tuple)):
      # Find the most specific variant that covers all elements.
      variant_priority = [None, messages.Variant.INT64, messages.Variant.DOUBLE,
                          messages.Variant.STRING]
      chosen_priority = 0
      for v in value:
        variant = find_variant(v)
        try:
          priority = variant_priority.index(variant)
        except IndexError:
          priority = -1
        if priority > chosen_priority:
          chosen_priority = priority
      return variant_priority[chosen_priority]
    # Unrecognized type.
    return None

  def decode_dictionary(message_type, dictionary):
    """Merge dictionary in to message.

    Args:
      message: Message to merge dictionary in to.
      dictionary: Dictionary to extract information from.  Dictionary
        is as parsed from JSON.  Nested objects will also be dictionaries.
    """
    message = message_type()
    for key, value in dictionary.iteritems():
      if value is None:
        message.reset(key)
        continue

      try:
        field = message.field_by_name(key)
      except KeyError:
        # Save unknown values.
        variant = find_variant(value)
        if variant:
          if key.isdigit():
            key = int(key)
          message.set_unrecognized_field(key, value, variant)
        else:
          logging.warning('No variant found for unrecognized field: %s', key)
        continue

      # Normalize values in to a list.
      if isinstance(value, list):
        if not value:
          continue
      else:
        value = [value]

      valid_value = []
      for item in value:
        if isinstance(field, messages.EnumField):
          try:
            item = field.type(item)
          except TypeError:
            raise messages.DecodeError('Invalid enum value "%s"' % value[0])
        elif isinstance(field, messages.BytesField):
          try:
            item = base64.b64decode(item)
          except TypeError, err:
            raise messages.DecodeError('Base64 decoding error: %s' % err)
        elif isinstance(field, message_types.DateTimeField):
          try:
            item = util.decode_datetime(item)
          except ValueError, err:
            raise messages.DecodeError(err)
        elif isinstance(field, messages.MessageField):
          item = decode_dictionary(field.message_type, item)
        elif (isinstance(field, messages.FloatField) and
              isinstance(item, (int, long, basestring))):
          try:
            item = float(item)
          except:
            pass
        elif (isinstance(field, messages.IntegerField) and
              isinstance(item, basestring)):
          try:
            item = int(item)
          except:
            pass
        valid_value.append(item)

      if field.repeated:
        existing_value = getattr(message, field.name)
        setattr(message, field.name, valid_value)
      else:
        setattr(message, field.name, valid_value[-1])
    return message

  message = decode_dictionary(message_type, dictionary)
  message.check_initialized()
  return message
