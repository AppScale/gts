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





"""Temporary files.

This module is a replacement for the stock tempfile module in Python,
and provides only in-memory temporary files as implemented by
cStringIO. The only functionality provided is the TemporaryFile
function.
"""

try:
  from cStringIO import StringIO
except ImportError:
  from StringIO import StringIO

__all__ = [
  "TemporaryFile",

  "NamedTemporaryFile", "mkstemp", "mkdtemp", "mktemp",
  "TMP_MAX", "gettempprefix", "tempdir", "gettempdir",
]

TMP_MAX = 10000

template = "tmp"

tempdir = None

def TemporaryFile(mode='w+b', bufsize=-1, suffix="",
                  prefix=template, dir=None):
  """Create and return a temporary file.
  Arguments:
  'prefix', 'suffix', 'dir', 'mode', 'bufsize' are all ignored.

  Returns an object with a file-like interface.  The file is in memory
  only, and does not exist on disk.
  """

  return StringIO()

def PlaceHolder(*args, **kwargs):
  raise NotImplementedError("Only tempfile.TemporaryFile is available for use")

NamedTemporaryFile = PlaceHolder
mkstemp = PlaceHolder
mkdtemp = PlaceHolder
mktemp = PlaceHolder
gettempprefix = PlaceHolder
tempdir = PlaceHolder
gettempdir = PlaceHolder
