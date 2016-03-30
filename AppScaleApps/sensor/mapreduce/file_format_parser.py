#!/usr/bin/env python
# Copyright 2012 Google Inc. All Rights Reserved.
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

"""Defines the parser for MapReduce FileInputReader's file format string."""

# pylint: disable=g-bad-name



__all__ = ['parse']

import re
import tokenize

from mapreduce import file_formats


def parse(format_string):
  """Parses format string.

  Args:
    format_string: format_string from MapReduce FileInputReader.

  Returns:
    a list of file_formats._FileFormat objects.

  Raises:
    ValueError: when format_string parsing fails because of invalid syntax
      or semantics.
  """
  tokenizer = _Tokenizer(format_string)
  return _Parser(tokenizer).formats


class _Parser(object):
  """Parses a format string according to the following grammar.

  In Python's modified BNF notation.
  format_string ::= parameterized_format ( "[" parameterized_format "]" )*
  parameterized_format ::= format [ format_parameters ]
  format_parameters ::= "(" format_paramter ("," format_parameter )* ")"
  format_parameter ::= format_specific_parameter "=" parameter_value
  format ::= (<letter>|<number>)+
  parameter_value ::= (<letter>|<number>|<punctuation>)+
  format_specific_parameter ::= (<letter>|<number>)+
  """

  def __init__(self, tokenizer):
    """Initialize.

    Args:
      tokenizer: an instance of _Tokenizer.

    Raises:
      ValueError: when parser couldn't consume all format_string.
    """
    self.formats = []
    self._tokenizer = tokenizer
    self._parse_format_string()
    if tokenizer.remainder():
      raise ValueError('Extra chars after index -%d' % tokenizer.remainder())

  def _add_format(self, format_name, kwargs):
    """Add a format to result list.

    The format name will be resolved to its corresponding _FileFormat class.
    kwargs will be passed to the class's __init___.

    Args:
      format_name: name of the parsed format in str.
      kwargs: a dict containing key word arguments for the format.

    Raises:
      ValueError: when format_name is not supported or the kwargs are not
        supported by the format.
    """
    if format_name not in file_formats.FORMATS:
      raise ValueError('Invalid format %s.' % format_name)
    format_cls = file_formats.FORMATS[format_name]
    for k in kwargs:
      if k not in format_cls.ARGUMENTS:
        raise ValueError('Invalid argument %s for format %s' %
                         (k, format_name))
    self.formats.append(format_cls.default_instance(**kwargs))

  def _parse_format_string(self):
    """Parses format_string."""
    self._parse_parameterized_format()
    if self._tokenizer.consume_if('['):
      self._parse_format_string()
      self._tokenizer.consume(']')

  def _validate_string(self, text):
    """Validates a string is composed of valid characters.

    Args:
      text: any str to validate.

    Raises:
      ValueError: when text contains illegal characters.
    """
    if not re.match(tokenize.Name, text):
      raise ValueError('%s should only contain ascii letters or digits.' %
                       text)

  def _parse_parameterized_format(self):
    """Parses parameterized_format."""
    format_name = self._tokenizer.next()
    self._validate_string(format_name)

    arguments = {}

    if self._tokenizer.consume_if('('):
      arguments = self._parse_format_parameters()
      self._tokenizer.consume(')')

    self._add_format(format_name, arguments)

  def _parse_format_parameters(self):
    """Parses format_parameters.

    Returns:
      a dict of parameter names to their values for this format.

    Raises:
      ValueError: when the format_parameters have illegal syntax or semantics.
    """
    arguments = {}
    comma_exist = True
    while self._tokenizer.peek() not in ')]':
      if not comma_exist:
        raise ValueError('Arguments should be separated by comma at index %d.'
                         % self._tokenizer.index)
      key = self._tokenizer.next()
      self._validate_string(key)
      self._tokenizer.consume('=')
      value = self._tokenizer.next()
      comma_exist = self._tokenizer.consume_if(',')
      if key in arguments:
        raise ValueError('Argument %s defined more than once.' % key)
      arguments[key] = value
    return arguments


class _Tokenizer(object):
  """Tokenizes a user supplied format string.

  A token is either a special character or a group of characters between
  two special characters or the beginning or the end of format string.
  Escape character can be used to escape special characters and itself.
  """

  SPECIAL_CHARS = '[]()=,'
  ESCAPE_CHAR = '\\'

  def __init__(self, format_string):
    """Initialize.

    Args:
      format_string: user supplied format string for MapReduce InputReader.
    """
    self.index = 0
    self._format_string = format_string

  def peek(self):
    """Returns the next token with surrounding white spaces stripped.

    This method does not advance underlying buffer.

    Returns:
      the next token with surrounding whitespaces stripped.
    """
    return self.next(advance=False)

  def next(self, advance=True):
    """Returns the next token with surrounding white spaces stripped.

    Args:
      advance: boolean. True if underlying buffer should be advanced.

    Returns:
      the next token with surrounding whitespaces stripped.
    """
    escaped = False
    token = ''
    previous_index = self.index
    while self.remainder():
      char = self._format_string[self.index]
      if char == self.ESCAPE_CHAR:
        if escaped:
          token += char
          self.index += 1
          escaped = False
        else:
          self.index += 1
          escaped = True
      elif char in self.SPECIAL_CHARS and not escaped:
        if not token.strip():
          self.index += 1
          token += char
        break
      else:
        escaped = False
        self.index += 1
        token += char

    if not advance:
      self.index = previous_index

    return token.strip()

  def consume(self, expected_token):
    """Consumes the next token which must match expectation.

    Args:
      expected_token: the expected value of the next token.

    Raises:
      ValueError: raised when the next token doesn't match expected_token.
    """
    token = self.next()
    if token != expected_token:
      raise ValueError('Expect "%s" but got "%s" at offset %d' %
                       (expected_token, token, self.index))

  def consume_if(self, token):
    """Consumes the next token when it matches expectation.

    Args:
      token: the expected next token.

    Returns:
      True when next token matches the argument and is consumed.
      False otherwise.
    """
    if self.peek() == token:
      self.consume(token)
      return True
    return False

  def remainder(self):
    """Returns the number of bytes left to be processed."""
    return len(self._format_string) - self.index

