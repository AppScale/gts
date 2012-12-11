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


"""Contains routines for printing protocol messages in text format."""


import cStringIO
import re

from collections import deque
from google.net.proto2.python.internal import type_checkers
from google.net.proto2.python.public import descriptor

__all__ = [ 'MessageToString', 'PrintMessage', 'PrintField',
            'PrintFieldValue', 'Merge' ]


_INTEGER_CHECKERS = (type_checkers.Uint32ValueChecker(),
                     type_checkers.Int32ValueChecker(),
                     type_checkers.Uint64ValueChecker(),
                     type_checkers.Int64ValueChecker())
_FLOAT_INFINITY = re.compile('-?inf(?:inity)?f?', re.IGNORECASE)
_FLOAT_NAN = re.compile('nanf?', re.IGNORECASE)


class ParseError(Exception):
  """Thrown in case of ASCII parsing error."""


def MessageToString(message, as_utf8=False, as_one_line=False):
  out = cStringIO.StringIO()
  PrintMessage(message, out, as_utf8=as_utf8, as_one_line=as_one_line)
  result = out.getvalue()
  out.close()
  if as_one_line:
    return result.rstrip()
  return result


def PrintMessage(message, out, indent=0, as_utf8=False, as_one_line=False):
  for field, value in message.ListFields():
    if field.label == descriptor.FieldDescriptor.LABEL_REPEATED:
      for element in value:
        PrintField(field, element, out, indent, as_utf8, as_one_line)
    else:
      PrintField(field, value, out, indent, as_utf8, as_one_line)


def PrintField(field, value, out, indent=0, as_utf8=False, as_one_line=False):
  """Print a single field name/value pair.  For repeated fields, the value
  should be a single element."""

  out.write(' ' * indent);
  if field.is_extension:
    out.write('[')
    if (field.containing_type.GetOptions().message_set_wire_format and
        field.type == descriptor.FieldDescriptor.TYPE_MESSAGE and
        field.message_type == field.extension_scope and
        field.label == descriptor.FieldDescriptor.LABEL_OPTIONAL):
      out.write(field.message_type.full_name)
    else:
      out.write(field.full_name)
    out.write(']')
  elif field.type == descriptor.FieldDescriptor.TYPE_GROUP:

    out.write(field.message_type.name)
  else:
    out.write(field.name)

  if field.cpp_type != descriptor.FieldDescriptor.CPPTYPE_MESSAGE:


    out.write(': ')

  PrintFieldValue(field, value, out, indent, as_utf8, as_one_line)
  if as_one_line:
    out.write(' ')
  else:
    out.write('\n')


def PrintFieldValue(field, value, out, indent=0,
                    as_utf8=False, as_one_line=False):
  """Print a single field value (not including name).  For repeated fields,
  the value should be a single element."""

  if field.cpp_type == descriptor.FieldDescriptor.CPPTYPE_MESSAGE:
    if as_one_line:
      out.write(' { ')
      PrintMessage(value, out, indent, as_utf8, as_one_line)
      out.write('}')
    else:
      out.write(' {\n')
      PrintMessage(value, out, indent + 2, as_utf8, as_one_line)
      out.write(' ' * indent + '}')
  elif field.cpp_type == descriptor.FieldDescriptor.CPPTYPE_ENUM:
    enum_value = field.enum_type.values_by_number.get(value, None)
    if enum_value is not None:
      out.write(enum_value.name)
    else:
      out.write(str(value))
  elif field.cpp_type == descriptor.FieldDescriptor.CPPTYPE_STRING:
    out.write('\"')
    if type(value) is unicode:
      out.write(_CEscape(value.encode('utf-8'), as_utf8))
    else:
      out.write(_CEscape(value, as_utf8))
    out.write('\"')
  elif field.cpp_type == descriptor.FieldDescriptor.CPPTYPE_BOOL:
    if value:
      out.write("true")
    else:
      out.write("false")
  else:
    out.write(str(value))


def Merge(text, message):
  """Merges an ASCII representation of a protocol message into a message.

  Args:
    text: Message ASCII representation.
    message: A protocol buffer message to merge into.

  Raises:
    ParseError: On ASCII parsing problems.
  """
  tokenizer = _Tokenizer(text)
  while not tokenizer.AtEnd():
    _MergeField(tokenizer, message)


def _MergeField(tokenizer, message):
  """Merges a single protocol message field into a message.

  Args:
    tokenizer: A tokenizer to parse the field name and values.
    message: A protocol message to record the data.

  Raises:
    ParseError: In case of ASCII parsing problems.
  """
  message_descriptor = message.DESCRIPTOR
  if tokenizer.TryConsume('['):
    name = [tokenizer.ConsumeIdentifier()]
    while tokenizer.TryConsume('.'):
      name.append(tokenizer.ConsumeIdentifier())
    name = '.'.join(name)

    if not message_descriptor.is_extendable:
      raise tokenizer.ParseErrorPreviousToken(
          'Message type "%s" does not have extensions.' %
          message_descriptor.full_name)
    field = message.Extensions._FindExtensionByName(name)
    if not field:
      raise tokenizer.ParseErrorPreviousToken(
          'Extension "%s" not registered.' % name)
    elif message_descriptor != field.containing_type:
      raise tokenizer.ParseErrorPreviousToken(
          'Extension "%s" does not extend message type "%s".' % (
              name, message_descriptor.full_name))
    tokenizer.Consume(']')
  else:
    name = tokenizer.ConsumeIdentifier()
    field = message_descriptor.fields_by_name.get(name, None)




    if not field:
      field = message_descriptor.fields_by_name.get(name.lower(), None)
      if field and field.type != descriptor.FieldDescriptor.TYPE_GROUP:
        field = None

    if (field and field.type == descriptor.FieldDescriptor.TYPE_GROUP and
        field.message_type.name != name):
      field = None

    if not field:
      raise tokenizer.ParseErrorPreviousToken(
          'Message type "%s" has no field named "%s".' % (
              message_descriptor.full_name, name))

  if field.cpp_type == descriptor.FieldDescriptor.CPPTYPE_MESSAGE:
    tokenizer.TryConsume(':')

    if tokenizer.TryConsume('<'):
      end_token = '>'
    else:
      tokenizer.Consume('{')
      end_token = '}'

    if field.label == descriptor.FieldDescriptor.LABEL_REPEATED:
      if field.is_extension:
        sub_message = message.Extensions[field].add()
      else:
        sub_message = getattr(message, field.name).add()
    else:
      if field.is_extension:
        sub_message = message.Extensions[field]
      else:
        sub_message = getattr(message, field.name)
      sub_message.SetInParent()

    while not tokenizer.TryConsume(end_token):
      if tokenizer.AtEnd():
        raise tokenizer.ParseErrorPreviousToken('Expected "%s".' % (end_token))
      _MergeField(tokenizer, sub_message)
  else:
    _MergeScalarField(tokenizer, message, field)


def _MergeScalarField(tokenizer, message, field):
  """Merges a single protocol message scalar field into a message.

  Args:
    tokenizer: A tokenizer to parse the field value.
    message: A protocol message to record the data.
    field: The descriptor of the field to be merged.

  Raises:
    ParseError: In case of ASCII parsing problems.
    RuntimeError: On runtime errors.
  """
  tokenizer.Consume(':')
  value = None

  if field.type in (descriptor.FieldDescriptor.TYPE_INT32,
                    descriptor.FieldDescriptor.TYPE_SINT32,
                    descriptor.FieldDescriptor.TYPE_SFIXED32):
    value = tokenizer.ConsumeInt32()
  elif field.type in (descriptor.FieldDescriptor.TYPE_INT64,
                      descriptor.FieldDescriptor.TYPE_SINT64,
                      descriptor.FieldDescriptor.TYPE_SFIXED64):
    value = tokenizer.ConsumeInt64()
  elif field.type in (descriptor.FieldDescriptor.TYPE_UINT32,
                      descriptor.FieldDescriptor.TYPE_FIXED32):
    value = tokenizer.ConsumeUint32()
  elif field.type in (descriptor.FieldDescriptor.TYPE_UINT64,
                      descriptor.FieldDescriptor.TYPE_FIXED64):
    value = tokenizer.ConsumeUint64()
  elif field.type in (descriptor.FieldDescriptor.TYPE_FLOAT,
                      descriptor.FieldDescriptor.TYPE_DOUBLE):
    value = tokenizer.ConsumeFloat()
  elif field.type == descriptor.FieldDescriptor.TYPE_BOOL:
    value = tokenizer.ConsumeBool()
  elif field.type == descriptor.FieldDescriptor.TYPE_STRING:
    value = tokenizer.ConsumeString()
  elif field.type == descriptor.FieldDescriptor.TYPE_BYTES:
    value = tokenizer.ConsumeByteString()
  elif field.type == descriptor.FieldDescriptor.TYPE_ENUM:
    value = tokenizer.ConsumeEnum(field)
  else:
    raise RuntimeError('Unknown field type %d' % field.type)

  if field.label == descriptor.FieldDescriptor.LABEL_REPEATED:
    if field.is_extension:
      message.Extensions[field].append(value)
    else:
      getattr(message, field.name).append(value)
  else:
    if field.is_extension:
      message.Extensions[field] = value
    else:
      setattr(message, field.name, value)


class _Tokenizer(object):
  """Protocol buffer ASCII representation tokenizer.

  This class handles the lower level string parsing by splitting it into
  meaningful tokens.

  It was directly ported from the Java protocol buffer API.
  """

  _WHITESPACE = re.compile('(\\s|(#.*$))+', re.MULTILINE)
  _TOKEN = re.compile(
      '[a-zA-Z_][0-9a-zA-Z_+-]*|'
      '[0-9+-][0-9a-zA-Z_.+-]*|'
      '\"([^\"\n\\\\]|\\\\.)*(\"|\\\\?$)|'
      '\'([^\'\n\\\\]|\\\\.)*(\'|\\\\?$)')
  _IDENTIFIER = re.compile('\w+')

  def __init__(self, text_message):
    self._text_message = text_message

    self._position = 0
    self._line = -1
    self._column = 0
    self._token_start = None
    self.token = ''
    self._lines = deque(text_message.split('\n'))
    self._current_line = ''
    self._previous_line = 0
    self._previous_column = 0
    self._SkipWhitespace()
    self.NextToken()

  def AtEnd(self):
    """Checks the end of the text was reached.

    Returns:
      True iff the end was reached.
    """
    return self.token == ''

  def _PopLine(self):
    while len(self._current_line) <= self._column:
      if not self._lines:
        self._current_line = ''
        return
      self._line += 1
      self._column = 0
      self._current_line = self._lines.popleft()

  def _SkipWhitespace(self):
    while True:
      self._PopLine()
      match = self._WHITESPACE.match(self._current_line, self._column)
      if not match:
        break
      length = len(match.group(0))
      self._column += length

  def TryConsume(self, token):
    """Tries to consume a given piece of text.

    Args:
      token: Text to consume.

    Returns:
      True iff the text was consumed.
    """
    if self.token == token:
      self.NextToken()
      return True
    return False

  def Consume(self, token):
    """Consumes a piece of text.

    Args:
      token: Text to consume.

    Raises:
      ParseError: If the text couldn't be consumed.
    """
    if not self.TryConsume(token):
      raise self._ParseError('Expected "%s".' % token)

  def ConsumeIdentifier(self):
    """Consumes protocol message field identifier.

    Returns:
      Identifier string.

    Raises:
      ParseError: If an identifier couldn't be consumed.
    """
    result = self.token
    if not self._IDENTIFIER.match(result):
      raise self._ParseError('Expected identifier.')
    self.NextToken()
    return result

  def ConsumeInt32(self):
    """Consumes a signed 32bit integer number.

    Returns:
      The integer parsed.

    Raises:
      ParseError: If a signed 32bit integer couldn't be consumed.
    """
    try:
      result = ParseInteger(self.token, is_signed=True, is_long=False)
    except ValueError, e:
      raise self._ParseError(str(e))
    self.NextToken()
    return result

  def ConsumeUint32(self):
    """Consumes an unsigned 32bit integer number.

    Returns:
      The integer parsed.

    Raises:
      ParseError: If an unsigned 32bit integer couldn't be consumed.
    """
    try:
      result = ParseInteger(self.token, is_signed=False, is_long=False)
    except ValueError, e:
      raise self._ParseError(str(e))
    self.NextToken()
    return result

  def ConsumeInt64(self):
    """Consumes a signed 64bit integer number.

    Returns:
      The integer parsed.

    Raises:
      ParseError: If a signed 64bit integer couldn't be consumed.
    """
    try:
      result = ParseInteger(self.token, is_signed=True, is_long=True)
    except ValueError, e:
      raise self._ParseError(str(e))
    self.NextToken()
    return result

  def ConsumeUint64(self):
    """Consumes an unsigned 64bit integer number.

    Returns:
      The integer parsed.

    Raises:
      ParseError: If an unsigned 64bit integer couldn't be consumed.
    """
    try:
      result = ParseInteger(self.token, is_signed=False, is_long=True)
    except ValueError, e:
      raise self._ParseError(str(e))
    self.NextToken()
    return result

  def ConsumeFloat(self):
    """Consumes an floating point number.

    Returns:
      The number parsed.

    Raises:
      ParseError: If a floating point number couldn't be consumed.
    """
    try:
      result = ParseFloat(self.token)
    except ValueError, e:
      raise self._ParseError(str(e))
    self.NextToken()
    return result

  def ConsumeBool(self):
    """Consumes a boolean value.

    Returns:
      The bool parsed.

    Raises:
      ParseError: If a boolean value couldn't be consumed.
    """
    try:
      result = ParseBool(self.token)
    except ValueError, e:
      raise self._ParseError(str(e))
    self.NextToken()
    return result

  def ConsumeString(self):
    """Consumes a string value.

    Returns:
      The string parsed.

    Raises:
      ParseError: If a string value couldn't be consumed.
    """
    bytes = self.ConsumeByteString()
    try:
      return unicode(bytes, 'utf-8')
    except UnicodeDecodeError, e:
      raise self._StringParseError(e)

  def ConsumeByteString(self):
    """Consumes a byte array value.

    Returns:
      The array parsed (as a string).

    Raises:
      ParseError: If a byte array value couldn't be consumed.
    """
    list = [self._ConsumeSingleByteString()]
    while len(self.token) > 0 and self.token[0] in ('\'', '"'):
      list.append(self._ConsumeSingleByteString())
    return "".join(list)

  def _ConsumeSingleByteString(self):
    """Consume one token of a string literal.

    String literals (whether bytes or text) can come in multiple adjacent
    tokens which are automatically concatenated, like in C or Python.  This
    method only consumes one token.
    """
    text = self.token
    if len(text) < 1 or text[0] not in ('\'', '"'):
      raise self._ParseError('Expected string.')

    if len(text) < 2 or text[-1] != text[0]:
      raise self._ParseError('String missing ending quote.')

    try:
      result = _CUnescape(text[1:-1])
    except ValueError, e:
      raise self._ParseError(str(e))
    self.NextToken()
    return result

  def ConsumeEnum(self, field):
    try:
      result = ParseEnum(field, self.token)
    except ValueError, e:
      raise self._ParseError(str(e))
    self.NextToken()
    return result

  def ParseErrorPreviousToken(self, message):
    """Creates and *returns* a ParseError for the previously read token.

    Args:
      message: A message to set for the exception.

    Returns:
      A ParseError instance.
    """
    return ParseError('%d:%d : %s' % (
        self._previous_line + 1, self._previous_column + 1, message))

  def _ParseError(self, message):
    """Creates and *returns* a ParseError for the current token."""
    return ParseError('%d:%d : %s' % (
        self._line + 1, self._column + 1, message))

  def _StringParseError(self, e):
    return self._ParseError('Couldn\'t parse string: ' + str(e))

  def NextToken(self):
    """Reads the next meaningful token."""
    self._previous_line = self._line
    self._previous_column = self._column

    self._column += len(self.token)
    self._SkipWhitespace()

    if not self._lines and len(self._current_line) <= self._column:
      self.token = ''
      return

    match = self._TOKEN.match(self._current_line, self._column)
    if match:
      token = match.group(0)
      self.token = token
    else:
      self.token = self._current_line[self._column]







def _CEscape(text, as_utf8):
  def escape(c):
    o = ord(c)
    if o == 10: return r"\n"
    if o == 13: return r"\r"
    if o ==  9: return r"\t"
    if o == 39: return r"\'"

    if o == 34: return r'\"'
    if o == 92: return r"\\"


    if not as_utf8 and (o >= 127 or o < 32): return "\\%03o" % o
    return c
  return "".join([escape(c) for c in text])


_CUNESCAPE_HEX = re.compile('\\\\x([0-9a-fA-F]{2}|[0-9a-fA-F])')


def _CUnescape(text):
  def ReplaceHex(m):
    return chr(int(m.group(0)[2:], 16))


  result = _CUNESCAPE_HEX.sub(ReplaceHex, text)
  return result.decode('string_escape')


def ParseInteger(text, is_signed=False, is_long=False):
  """Parses an integer.

  Args:
    text: The text to parse.
    is_signed: True if a signed integer must be parsed.
    is_long: True if a long integer must be parsed.

  Returns:
    The integer value.

  Raises:
    ValueError: Thrown Iff the text is not a valid integer.
  """

  try:
    result = int(text, 0)
  except ValueError:
    raise ValueError('Couldn\'t parse integer: %s' % text)


  checker = _INTEGER_CHECKERS[2 * int(is_long) + int(is_signed)]
  checker.CheckValue(result)
  return result


def ParseFloat(text):
  """Parse a floating point number.

  Args:
    text: Text to parse.

  Returns:
    The number parsed.

  Raises:
    ValueError: If a floating point number couldn't be parsed.
  """
  try:

    return float(text)
  except ValueError:

    if _FLOAT_INFINITY.match(text):
      if text[0] == '-':
        return float('-inf')
      else:
        return float('inf')
    elif _FLOAT_NAN.match(text):
      return float('nan')
    else:

      try:
        return float(text.rstrip('f'))
      except ValueError:
        raise ValueError('Couldn\'t parse float: %s' % text)


def ParseBool(text):
  """Parse a boolean value.

  Args:
    text: Text to parse.

  Returns:
    Boolean values parsed

  Raises:
    ValueError: If text is not a valid boolean.
  """
  if text in ('true', 't', '1'):
    return True
  elif text in ('false', 'f', '0'):
    return False
  else:
    raise ValueError('Expected "true" or "false".')


def ParseEnum(field, value):
  """Parse an enum value.

  The value can be specified by a number (the enum value), or by
  a string literal (the enum name).

  Args:
    field: Enum field descriptor.
    value: String value.

  Returns:
    Enum value number.

  Raises:
    ValueError: If the enum value could not be parsed.
  """
  enum_descriptor = field.enum_type
  try:
    number = int(value, 0)
  except ValueError:

    enum_value = enum_descriptor.values_by_name.get(value, None)
    if enum_value is None:
      raise ValueError(
          'Enum type "%s" has no value named %s.' % (
              enum_descriptor.full_name, value))
  else:

    enum_value = enum_descriptor.values_by_number.get(number, None)
    if enum_value is None:
      raise ValueError(
          'Enum type "%s" has no value with number %d.' % (
              enum_descriptor.full_name, number))
  return enum_value.number
