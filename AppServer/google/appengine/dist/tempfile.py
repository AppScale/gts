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

import imp
from random import Random as _Random
import errno as _errno


  
__all__ = [
  "TemporaryFile",

  "NamedTemporaryFile", "mkstemp", "mkdtemp", "mktemp",
  "TMP_MAX", "gettempprefix", "tempdir", "gettempdir",
]

TMP_MAX = 10000

template = "tmp"

tempdir = template

def TemporaryFile(mode='w+b', bufsize=-1, suffix="",
                  prefix=template, dir=None):
  """Create and return a temporary file.
  Arguments:
  'prefix', 'suffix', 'dir', 'mode', 'bufsize' are all ignored.

  Returns an object with a file-like interface.  The file is in memory
  only, and does not exist on disk.
  """

  return StringIO()

def NamedTemporaryFile(mode='w+b', bufsize=-1, suffix="",
                       prefix=template, dir=None, delete=True):
    """Create and return a temporary file.
    Arguments:
    'prefix', 'suffix', 'dir', 'mode', 'bufsize', 'delete' are all
    ignored.

    Returns an object with a file-like interface; the name of the file
    is accessible as file.name.  The file will be not be automatically
    deleted when it is closed.
    """
    _os = imp.load_source('os','/usr/local/Python-2.7.3/Lib/os.py') 
    names = _RandomNameSequence()
    flags = _os.O_RDWR|_os.O_CREAT|_os.O_EXCL

    for seq in xrange(TMP_MAX):
        name = names.next()
        #fname = _os.path.join(tempdir, name)
        fname = _os.path.abspath('/' + str(template) + '/' + str(name))
        try:
            fd = _os.open(fname,flags, 0600)
            fobj = _os.fdopen(fd,'w+b',-1)
            return _TemporaryFileWrapper(fobj, fname, False)
        except OSError, e:
            if e.errno == _errno.EEXIST:
                continue # try again
            raise
    raise IOError, (_errno.EEXIST, "No usable temporary file name found")



def PlaceHolder(*args, **kwargs):
  raise NotImplementedError("Only tempfile.TemporaryFile is available for use")

#print 'real_tempfile: '+str(dir(real_tempfile))
#print '_os: '+str(dir(_os))
#NamedTemporaryFile = real_tempfile.NamedTemporaryFile
#NamedTemporaryFile = PlaceHolder
mkstemp = PlaceHolder
mkdtemp = PlaceHolder
#mktemp = real_tempfile.mktemp
mktemp = PlaceHolder
gettempprefix = PlaceHolder
tempdir = PlaceHolder
gettempdir = PlaceHolder


class _RandomNameSequence:
    """An instance of _RandomNameSequence generates an endless
    sequence of unpredictable strings which can safely be incorporated
    into file names.  Each string is six characters long.  Multiple
    threads can safely use the same instance at the same time.

    _RandomNameSequence is an iterator."""

    characters = ("abcdefghijklmnopqrstuvwxyz" +
                  "ABCDEFGHIJKLMNOPQRSTUVWXYZ" +
                  "0123456789_")

    def __init__(self):
        self._os = imp.load_source('os','/usr/local/Python-2.7.3/Lib/os.py')
        #self._Random = imp.load_source('os','/usr/local/Python-2.7.3/Lib/random.py')
        self.normcase = self._os.path.normcase

    @property
    def rng(self):
        cur_pid = self._os.getpid()
        if cur_pid != getattr(self, '_rng_pid', None):
            self._rng = _Random()
            self._rng_pid = cur_pid
        return self._rng

    def __iter__(self):
        return self

    def next(self):
        c = self.characters
        choose = self.rng.choice
        letters = [choose(c) for dummy in "123456"]
        return self.normcase(''.join(letters))


class _TemporaryFileWrapper:
    """Temporary file wrapper

    This class provides a wrapper around files opened for
    temporary use.  In particular, it seeks to automatically
    remove the file when it is no longer needed.
    """

    def __init__(self, file, name, delete=False):
        self.file = file
        self.name = name
        self.close_called = False
        self.delete = delete

    def __getattr__(self, name):
        # Attribute lookups are delegated to the underlying file
        # and cached for non-numeric results
        # (i.e. methods are cached, closed and friends are not)
        file = self.__dict__['file']
        a = getattr(file, name)
        if not issubclass(type(a), type(0)):
            setattr(self, name, a)
        return a

    # The underlying __enter__ method returns the wrong object
    # (self.file) so override it to return the wrapper
    def __enter__(self):
        self.file.__enter__()
        return self

    def __exit__(self, exc, value, tb):
        self.file.__exit__(exc, value, tb)





if __name__ == "__main__":
    t_file = NamedTemporaryFile()
    print "t_file = "+t_file.name
    t_file.write("Hello")
    t_file.seek(0)
    print "t_file.read() = "+t_file.read()

