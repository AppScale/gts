# $Id: 0d2e5b9d01530c575fc4f6834113699dda23cc4a $

"""
Input/Output utility methods and classes.
"""

from __future__ import absolute_import

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import os
import zipfile

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['AutoFlush', 'MultiWriter', 'PushbackFile', 'Zip']

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class AutoFlush(object):
    """
    An ``AutoFlush`` wraps a file-like object and flushes the output
    (via a call to ``flush()`` after every write operation. Here's how
    to use an ``AutoFlush`` object to force standard output to flush after
    every write:

    .. python::

        import sys
        from grizzled.io import AutoFlush

        sys.stdout = AutoFlush(sys.stdout)
    """
    def __init__(self, f):
        """
        Create a new ``AutoFlush`` object to wrap a file-like object.

        :Parameters:
            f : file
                A file-like object that contains both a ``write()`` method
                and a ``flush()`` method.
        """
        self.__file = f

    def write(self, buf):
        """
        Write the specified buffer to the file.

        :Parameters:
            buf : str or bytes
                buffer to write
        """
        self.__file.write(buf)
        self.__file.flush()

    def flush(self):
        """
        Force a flush.
        """
        self.__file.flush()

    def truncate(self, size=-1):
        """
        Truncate the underlying file. Might fail.

        :Parameters:
            size : int
                Where to truncate. If less than 0, then file's current position
                is used.
        """
        if size < 0:
            size = self.__file.tell()
        self.__file.truncate(size)

    def tell(self):
        """
        Return the file's current position, if applicable.

        :rtype:  int
        :return: Current file position
        """
        return self.__file.tell()

    def seek(self, offset, whence=os.SEEK_SET):
        """
        Set the file's current position. The ``whence`` argument is optional;
        legal values are:

         - ``os.SEEK_SET`` or 0: absolute file positioning (default)
         - ``os.SEEK_CUR`` or 1: seek relative to the current position
         - ``os.SEEK_END`` or 2: seek relative to the file's end

        There is no return value. Note that if the file is opened for
        appending (mode 'a' or 'a+'), any ``seek()`` operations will be undone
        at the next write. If the file is only opened for writing in append
        mode (mode 'a'), this method is essentially a no-op, but it remains
        useful for files opened in append mode with reading enabled (mode
        'a+'). If the file is opened in text mode (without 'b'), only offsets
        returned by ``tell()`` are legal. Use of other offsets causes
        undefined behavior.

        Note that not all file objects are seekable.

        :Parameters:
            offset : int
                where to seek
            whence : int
                see above
        """
        self.__file.seek(offset, whence)

    def fileno(self):
        """
        Return the integer file descriptor used by the underlying file.

        :rtype:  int
        :return: the file descriptor
        """
        return self.__file.fileno()

class MultiWriter(object):
    """
    Wraps multiple file-like objects so that they all may be written at once.
    For example, the following code arranges to have anything written to
    ``sys.stdout`` go to ``sys.stdout`` and to a temporary file:

    .. python::

        import sys
        from grizzled.io import MultiWriter

        sys.stdout = MultiWriter(sys.__stdout__, open('/tmp/log', 'w'))
    """
    def __init__(self, *args):
        """
        Create a new ``MultiWriter`` object to wrap one or more file-like
        objects.

        :Parameters:
            args : iterable
                One or more file-like objects to wrap
        """
        self.__files = args

    def write(self, buf):
        """
        Write the specified buffer to the wrapped files.

        :Parameters:
            buf : str or bytes
                buffer to write
        """
        for f in self.__files:
            f.write(buf)

    def flush(self):
        """
        Force a flush.
        """
        for f in self.__files:
            f.flush()

    def close(self):
        """
        Close all contained files.
        """
        for f in self.__files:
            f.close()

class PushbackFile(object):
    """
    A file-like wrapper object that permits pushback.
    """
    def __init__(self, f):
        """
        Create a new ``PushbackFile`` object to wrap a file-like object.

        :Parameters:
            f : file
                A file-like object that contains both a ``write()`` method
                and a ``flush()`` method.
        """
        self.__buf = [c for c in ''.join(f.readlines())]

    def write(self, buf):
        """
        Write the specified buffer to the file. This method throws an
        unconditional exception, since ``PushbackFile`` objects are read-only.

        :Parameters:
            buf : str or bytes
                buffer to write

        :raise NotImplementedError: unconditionally
        """
        raise NotImplementedError, 'PushbackFile is read-only'

    def pushback(self, s):
        """
        Push a character or string back onto the input stream.

        :Parameters:
            s : str
                the string to push back onto the input stream
        """
        self.__buf = [c for c in s] + self.__buf

    unread=pushback

    def read(self, n=-1):
        """
        Read *n* bytes from the open file.

        :Parameters:
            n : int
                Number of bytes to read. A negative number instructs
                ``read()`` to read all remaining bytes.

        :return: the bytes read
        """
        resultBuf = None
        if n > len(self.__buf):
            n = len(self.__buf)

        if (n < 0) or (n >= len(self.__buf)):
            resultBuf = self.__buf
            self.__buf = []

        else:
            resultBuf = self.__buf[0:n]
            self.__buf = self.__buf[n:]

        return ''.join(resultBuf)

    def readline(self, length=-1):
        """
        Read the next line from the file.

        :Parameters:
            length : int
                a length hint, or negative if you don't care

        :rtype:  str
        :return: the line
        """
        i = 0
        while i < len(self.__buf) and (self.__buf[i] != '\n'):
            i += 1

        result = self.__buf[0:i+1]
        self.__buf = self.__buf[i+1:]
        return ''.join(result)

    def readlines(self, sizehint=0):
        """
        Read all remaining lines in the file.

        :rtype:  list
        :return: list of lines
        """
        return self.read(-1)

    def __iter__(self):
        return self

    def next(self):
        """A file object is its own iterator.

        :rtype: str
        :return: the next line from the file

        :raise StopIteration: end of file
        :raise IncludeError: on error
        """
        line = self.readline()
        if (line == None) or (len(line) == 0):
            raise StopIteration
        return line

    def close(self):
        """Close the file. A no-op in this class."""
        pass

    def flush(self):
        """
        Force a flush. This method throws an unconditional exception, since
        ``PushbackFile`` objects are read-only.

        :raise NotImplementedError: unconditionally
        """
        raise NotImplementedError, 'PushbackFile is read-only'

    def truncate(self, size=-1):
        """
        Truncate the underlying file.  This method throws an unconditional exception, since
        ``PushbackFile`` objects are read-only.

        :Parameters:
            size : int
                Where to truncate. If less than 0, then file's current
                position is used

        :raise NotImplementedError: unconditionally
        """
        raise NotImplementedError, 'PushbackFile is read-only'

    def tell(self):
        """
        Return the file's current position, if applicable. This method throws
        an unconditional exception, since ``PushbackFile`` objects are
        read-only.

        :rtype:  int
        :return: Current file position

        :raise NotImplementedError: unconditionally
        """
        raise NotImplementedError, 'PushbackFile is not seekable'

    def seek(self, offset, whence=os.SEEK_SET):
        """
        Set the file's current position. This method throws an unconditional
        exception, since ``PushbackFile`` objects are not seekable.

        :Parameters:
            offset : int
                where to seek
            whence : int
                see above

        :raise NotImplementedError: unconditionally
        """
        raise NotImplementedError, 'PushbackFile is not seekable'

    def fileno(self):
        """
        Return the integer file descriptor used by the underlying file.

        :rtype:  int
        :return: the file descriptor
        """
        return -1

class Zip(zipfile.ZipFile):
    """
    ``Zip`` extends the standard ``zipfile.ZipFile`` class and provides a
    method to extract the contents of a zip file into a directory. Adapted
    from http://aspn.activestate.com/ASPN/Cookbook/Python/Recipe/252508.
    """
    def __init__(self, file, mode="r",
                 compression=zipfile.ZIP_STORED,
                 allow_zip64=False):
        """
        Constructor. Initialize a new zip file.

        :Parameters:
            file : str
                path to zip file
            mode : str
                open mode. Valid values are 'r' (read), 'w' (write), and
                'a' (append)
            compression : int
                Compression type. Valid values: ``zipfile.ZIP_STORED`,
                ``zipfile.ZIP_DEFLATED``
            allow_zip64 : bool
                Whether or not Zip64 extensions are to be used
        """
        zipfile.ZipFile.__init__(self, file, mode, compression, allow_zip64)
        self.zipFile = file

    def extract(self, output_dir):
        """
        Unpack the zip file into the specified output directory.

        :Parameters:
            output_dir : str
                path to output directory. The directory is
                created if it doesn't already exist.
        """
        if not output_dir.endswith(':') and not os.path.exists(output_dir):
            os.mkdir(output_dir)

        num_files = len(self.namelist())

        # extract files to directory structure
        for i, name in enumerate(self.namelist()):
            if not name.endswith('/'):
                directory = os.path.dirname(name)
                if directory == '':
                    directory = None
                if directory:
                    directory = os.path.join(output_dir, directory)
                    if not os.path.exists(directory):
                        os.makedirs(directory)

                outfile = open(os.path.join(output_dir, name), 'wb')
                outfile.write(self.read(name))
                outfile.flush()
                outfile.close()
