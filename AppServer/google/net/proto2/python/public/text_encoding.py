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
"""Encoding related utilities."""

import re


def CEscape(text, as_utf8):
  """Escape a string for use in an ascii protocol buffer.

  text.encode('string_escape') does not seem to satisfy our needs as it
  encodes unprintable characters using two-digit hex escapes whereas our
  C++ unescaping function allows hex escapes to be any length.  So,
  "\0011".encode('string_escape') ends up being "\\x011", which will be
  decoded in C++ as a single-character string with char code 0x11.

  Args:
    text: A string to be escaped
    as_utf8: Specifies if result should be returned in UTF-8 encoding
  Returns:
    Escaped string
  """

  def EscapeChar(c):
    """Escape one character."""
    o = ord(c)
    if o == 10: return r'\n'
    if o == 13: return r'\r'
    if o == 9: return r'\t'
    if o == 39: return r"\'"

    if o == 34: return r'\"'
    if o == 92: return r'\\'


    if not as_utf8 and (o >= 127 or o < 32):
      return r'\%03o' % o
    return c
  return ''.join([EscapeChar(c) for c in text])


_CUNESCAPE_HEX = re.compile(r'(\\+)x([0-9a-fA-F])(?![0-9a-fA-F])')


def CUnescape(text):
  """Unescape a text string with C-style escape sequences."""

  def ReplaceHex(m):


    if len(m.group(1)) & 1:
      return m.group(1) + 'x0' + m.group(2)
    return m.group(0)



  result = _CUNESCAPE_HEX.sub(ReplaceHex, text)
  return result.decode('string_escape')
