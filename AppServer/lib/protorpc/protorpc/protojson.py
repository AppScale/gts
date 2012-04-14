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

from . import messages

__all__ = [
    'ALTERNATIVE_CONTENT_TYPES',
    'CONTENT_TYPE',
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
    Comptable json module.

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


class _MessageJSONEncoder(json.JSONEncoder):
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
          result[field.name] = item
      return result
    else:
      return super(_MessageJSONEncoder, self).default(value)


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

  return json.dumps(message, cls=_MessageJSONEncoder)


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
        # TODO(rafek): Support saving unknown values.
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
          item = field.type(item)
        elif isinstance(field, messages.BytesField):
          item = base64.b64decode(item)
        elif isinstance(field, messages.MessageField):
          item = decode_dictionary(field.type, item)
        elif (isinstance(field, messages.FloatField) and
              isinstance(item, (int, long))):
          item = float(item)
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
