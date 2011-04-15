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




"""Stub replacement for Python's imp module."""


import os
import sys


PY_SOURCE, PY_COMPILED, C_EXTENSION = 1, 2, 3
PKG_DIRECTORY, C_BUILTIN, PY_FROZEN = 5, 6, 7


def get_magic():
  """Return the magic string used to recognize byte-compiled code files."""


  return '\xb3\xf2\r\n'


_PY_SOURCE_SUFFIX = ('.py', 'U', PY_SOURCE)
_PKG_DIRECTORY_SUFFIX = ('', '', PKG_DIRECTORY)


def get_suffixes():
  """Return a list that describes the files that find_module() looks for."""

  return [_PY_SOURCE_SUFFIX]


def find_module(name, path=None):
  """Try to find the named module on the given search path or sys.path."""

  if path == None:
    path = sys.path

  for directory in path:
    filename = os.path.join(directory, '%s.py' % name)
    if os.path.exists(filename):
      return open(filename, 'U'), filename, _PY_SOURCE_SUFFIX

    dirname = os.path.join(directory, name)
    filename = os.path.join(dirname, '__init__.py')
    if os.path.exists(filename):
      return None, dirname, _PKG_DIRECTORY_SUFFIX

  raise ImportError('No module named %s' % name)


def load_module(name, file_, pathname, description):
  """Load or reload the specified module.

  Please note that this function has only rudimentary supported on App Engine:
  Only loading packages is supported.
  """
  suffix, mode, type_ = description
  if type_ == PKG_DIRECTORY:
    if name in sys.modules:
      mod = sys.modules[name]
    else:
      mod = new_module(name)
      sys.modules[name] = mod
    filename = os.path.join(pathname, '__init__.py')
    mod.__file__ = filename
    execfile(filename, mod.__dict__, mod.__dict__)
    return mod
  else:
    raise NotImplementedError('Only importing packages is supported on '
                              'App Engine')


def new_module(name):
  """Return a new empty module object."""
  return type(sys)(name)


def lock_held():
  """Return False since threading is not supported."""
  return False


def acquire_lock():
  """Acquiring the lock is a no-op since no threading is supported."""
  pass


def release_lock():
  """There is no lock to release since acquiring is a no-op when there is no
  threading."""
  pass


def init_builtin(name):
  raise NotImplementedError('This function is not supported on App Engine.')


def init_frozen(name):
  raise NotImplementedError('This function is not supported on App Engine.')


def is_builtin(name):
  return name in sys.builtin_module_names


def is_frozen(name):
  return False


def load_compiled(name, pathname, file_=None):
  raise NotImplementedError('This function is not supported on App Engine.')


def load_dynamic(name, pathname, file_=None):
  raise NotImplementedError('This function is not supported on App Engine.')


def load_source(name, pathname, file_=None):
  raise NotImplementedError('This function is not supported on App Engine.')


class NullImporter(object):
  """Null importer object"""

  def __init__(self, path_string):
    if not path_string:
      raise ImportError("empty pathname")
    elif os.path.isdir(path_string):
      raise ImportError("existing directory")

  def find_module(self, fullname):
    return None
