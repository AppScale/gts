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














"""Pure Python zipfile importer.

This approximates the standard zipimport module, which isn't supported
by Google App Engine.  See PEP 302 for more information about the API
for import hooks.

Usage:
  import py_zipimport

As a side effect of importing, the module overrides sys.path_hooks,
and also creates an alias 'zipimport' for itself.  When your app is
running in Google App Engine production, you don't even need to import
it, since this is already done for you.  In the Google App Engine SDK
this module is not used; instead, the standard zipimport module is
used.
"""


__all__ = ['ZipImportError', 'zipimporter']











import os
import sys
import types
import UserDict
import zipfile




_SEARCH_ORDER = [

    ('.py', False),
    ('/__init__.py', True),
]




_zipfile_cache = {}


class ZipImportError(ImportError):
  """Exception raised by zipimporter objects."""



class zipimporter:
  """A PEP-302-style importer that can import from a zipfile.

  Just insert or append this class (not an instance) to sys.path_hooks
  and you're in business.  Instances satisfy both the 'importer' and
  'loader' APIs specified in PEP 302.
  """

  def __init__(self, path_entry):
    """Constructor.

    Args:
      path_entry: The entry in sys.path.  This should be the name of an
        existing zipfile possibly with a path separator and a prefix
        path within the archive appended, e.g. /x/django.zip or
        /x/django.zip/foo/bar.

    Raises:
      ZipImportError if the path_entry does not represent a valid
      zipfile with optional prefix.
    """

    archive = path_entry
    prefix = ''

    while not os.path.lexists(archive):
      head, tail = os.path.split(archive)
      if head == archive:
        msg = 'Nothing found for %r' % path_entry

        raise ZipImportError(msg)
      archive = head
      prefix = os.path.join(tail, prefix)
    if not os.path.isfile(archive):
      msg = 'Non-file %r found for %r' % (archive, path_entry)

      raise ZipImportError(msg)

    self.archive = archive
    self.prefix = os.path.join(prefix, '')

    self.zipfile = _zipfile_cache.get(archive)
    if self.zipfile is None:

      try:
        self.zipfile = zipfile.ZipFile(self.archive)
      except (EnvironmentError, zipfile.BadZipfile), err:


        msg = 'Can\'t open zipfile %s: %s: %s' % (self.archive,
                                                  err.__class__.__name__, err)
        import logging
        logging.warn(msg)
        raise ZipImportError(msg)
      else:

        _zipfile_cache[archive] = self.zipfile



        import logging
        logging.info('zipimporter(%r, %r)', archive, prefix)

  def __repr__(self):
    """Return a string representation matching zipimport.c."""
    name = self.archive
    if self.prefix:
      name = os.path.join(name, self.prefix)
    return '<zipimporter object "%s">' % name

  def _get_info(self, fullmodname):
    """Internal helper for find_module() and load_module().

    Args:
      fullmodname: The dot-separated full module name, e.g. 'django.core.mail'.

    Returns:
      A tuple (submodname, is_package, relpath) where:
        submodname: The final component of the module name, e.g. 'mail'.
        is_package: A bool indicating whether this is a package.
        relpath: The path to the module's source code within to the zipfile.

    Raises:
      ImportError if the module is not found in the archive.
    """
    parts = fullmodname.split('.')
    submodname = parts[-1]
    for suffix, is_package in _SEARCH_ORDER:
      relpath = os.path.join(self.prefix,
                             submodname + suffix.replace('/', os.sep))
      try:
        self.zipfile.getinfo(relpath.replace(os.sep, '/'))
      except KeyError:
        pass
      else:
        return submodname, is_package, relpath
    msg = ('Can\'t find module %s in zipfile %s with prefix %r' %
           (fullmodname, self.archive, self.prefix))

    raise ZipImportError(msg)

  def _get_source(self, fullmodname):
    """Internal helper for load_module().

    Args:
      fullmodname: The dot-separated full module name, e.g. 'django.core.mail'.

    Returns:
      A tuple (submodname, is_package, fullpath, source) where:
        submodname: The final component of the module name, e.g. 'mail'.
        is_package: A bool indicating whether this is a package.
        fullpath: The path to the module's source code including the
          zipfile's filename.
        source: The module's source code.

    Raises:
      ImportError if the module is not found in the archive.
    """
    submodname, is_package, relpath = self._get_info(fullmodname)
    fullpath = '%s%s%s' % (self.archive, os.sep, relpath)
    source = self.zipfile.read(relpath.replace(os.sep, '/'))
    source = source.replace('\r\n', '\n')
    source = source.replace('\r', '\n')
    return submodname, is_package, fullpath, source

  def find_module(self, fullmodname, path=None):
    """PEP-302-compliant find_module() method.

    Args:
      fullmodname: The dot-separated full module name, e.g. 'django.core.mail'.
      path: Optional and ignored; present for API compatibility only.

    Returns:
      None if the module isn't found in the archive; self if it is found.
    """
    try:
      submodname, is_package, relpath = self._get_info(fullmodname)
    except ImportError:

      return None
    else:

      return self

  def load_module(self, fullmodname):
    """PEP-302-compliant load_module() method.

    Args:
      fullmodname: The dot-separated full module name, e.g. 'django.core.mail'.

    Returns:
      The module object constructed from the source code.

    Raises:
      SyntaxError if the module's source code is syntactically incorrect.
      ImportError if there was a problem accessing the source code.
      Whatever else can be raised by executing the module's source code.
    """

    submodname, is_package, fullpath, source = self._get_source(fullmodname)
    code = compile(source, fullpath, 'exec')
    mod = sys.modules.get(fullmodname)
    try:
      if mod is None:
        mod = sys.modules[fullmodname] = types.ModuleType(fullmodname)
      mod.__loader__ = self
      mod.__file__ = fullpath
      mod.__name__ = fullmodname
      if is_package:
        mod.__path__ = [os.path.dirname(mod.__file__)]
      exec code in mod.__dict__
    except:
      if fullmodname in sys.modules:
        del sys.modules[fullmodname]
      raise
    return mod



  def get_data(self, fullpath):
    """Return (binary) content of a data file in the zipfile."""
    prefix = os.path.join(self.archive, '')
    if fullpath.startswith(prefix):

      relpath = fullpath[len(prefix):]
    elif os.path.isabs(fullpath):
      raise IOError('Absolute path %r doesn\'t start with zipfile name %r' %
                    (fullpath, prefix))
    else:

      relpath = fullpath
    try:
      return self.zipfile.read(relpath.replace(os.sep, '/'))
    except KeyError:
      raise IOError('Path %r not found in zipfile %r' %
                    (relpath, self.archive))

  def is_package(self, fullmodname):
    """Return whether a module is a package."""
    submodname, is_package, relpath = self._get_info(fullmodname)
    return is_package

  def get_code(self, fullmodname):
    """Return bytecode for a module."""
    submodname, is_package, fullpath, source = self._get_source(fullmodname)
    return compile(source, fullpath, 'exec')

  def get_source(self, fullmodname):
    """Return source code for a module."""
    submodname, is_package, fullpath, source = self._get_source(fullmodname)
    return source


class ZipFileCache(UserDict.DictMixin):
  """Helper class to export archive data in _zip_directory_cache.

  Just take the info from _zipfile_cache and convert it as required.
  """

  def __init__(self, archive):

    _zipfile_cache[archive]

    self._archive = archive

  def keys(self):
    return _zipfile_cache[self._archive].namelist()

  def __getitem__(self, filename):
    info = _zipfile_cache[self._archive].getinfo(filename.replace(os.sep, '/'))
    dt = info.date_time
    dostime = dt[3] << 11 | dt[4] << 5 | (dt[5] // 2)
    dosdate = (dt[0] - 1980) << 9 | dt[1] << 5 | dt[2]
    return (os.path.join(self._archive, info.filename), info.compress_type,
            info.compress_size, info.file_size, info.header_offset, dostime,
            dosdate, info.CRC)


class ZipDirectoryCache(UserDict.DictMixin):
  """Helper class to export _zip_directory_cache."""

  def keys(self):
    return _zipfile_cache.keys()

  def __getitem__(self, archive):
    return ZipFileCache(archive)





_zip_directory_cache = ZipDirectoryCache()




sys.modules['zipimport'] = sys.modules[__name__]
sys.path_hooks[:] = [zipimporter]
