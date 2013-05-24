# -*- coding: utf-8 -*-
#
# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Provides the pure Python versions of L{BufferedByteStream}.

Do not reference directly, use L{pyamf.util.BufferedByteStream} instead.

@since: 0.6
"""

import struct

try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from pyamf import python

# worked out a little further down
SYSTEM_ENDIAN = None


class StringIOProxy(object):
    """
    I am a C{StringIO} type object containing byte data from the AMF stream.

    @see: U{ByteArray on OSFlash
        <http://osflash.org/documentation/amf3#x0c_-_bytearray>}
    @see: U{Parsing ByteArrays on OSFlash
        <http://osflash.org/documentation/amf3/parsing_byte_arrays>}
    """

    def __init__(self, buf=None):
        """
        @raise TypeError: Unable to coerce C{buf} to C{StringIO}.
        """
        self._buffer = StringIO()

        if isinstance(buf, python.str_types):
            self._buffer.write(buf)
        elif hasattr(buf, 'getvalue'):
            self._buffer.write(buf.getvalue())
        elif hasattr(buf, 'read') and hasattr(buf, 'seek') and hasattr(buf, 'tell'):
            old_pos = buf.tell()
            buf.seek(0)
            self._buffer.write(buf.read())
            buf.seek(old_pos)
        elif buf is not None:
            raise TypeError("Unable to coerce buf->StringIO got %r" % (buf,))

        self._get_len()
        self._len_changed = False
        self._buffer.seek(0, 0)

    def getvalue(self):
        """
        Get raw data from buffer.
        """
        return self._buffer.getvalue()

    def read(self, n=-1):
        """
        Reads C{n} bytes from the stream.
        """
        if n < -1:
            raise IOError('Cannot read backwards')

        bytes = self._buffer.read(n)

        return bytes

    def seek(self, pos, mode=0):
        """
        Sets the file-pointer offset, measured from the beginning of this stream,
        at which the next write operation will occur.

        @param pos:
        @type pos: C{int}
        @param mode:
        @type mode: C{int}
        """
        return self._buffer.seek(pos, mode)

    def tell(self):
        """
        Returns the position of the stream pointer.
        """
        return self._buffer.tell()

    def truncate(self, size=0):
        """
        Truncates the stream to the specified length.

        @param size: The length of the stream, in bytes.
        @type size: C{int}
        """
        if size == 0:
            self._buffer = StringIO()
            self._len_changed = True

            return

        cur_pos = self.tell()
        self.seek(0)
        buf = self.read(size)
        self._buffer = StringIO()

        self._buffer.write(buf)
        self.seek(cur_pos)
        self._len_changed = True

    def write(self, s, size=None):
        """
        Writes the content of the specified C{s} into this buffer.

        @param s: Raw bytes
        """
        self._buffer.write(s)
        self._len_changed = True

    def _get_len(self):
        """
        Return total number of bytes in buffer.
        """
        if hasattr(self._buffer, 'len'):
            self._len = self._buffer.len

            return

        old_pos = self._buffer.tell()
        self._buffer.seek(0, 2)

        self._len = self._buffer.tell()
        self._buffer.seek(old_pos)

    def __len__(self):
        if not self._len_changed:
            return self._len

        self._get_len()
        self._len_changed = False

        return self._len

    def consume(self):
        """
        Chops the tail off the stream starting at 0 and ending at C{tell()}.
        The stream pointer is set to 0 at the end of this function.

        @since: 0.4
        """
        try:
            bytes = self.read()
        except IOError:
            bytes = ''

        self.truncate()

        if len(bytes) > 0:
            self.write(bytes)
            self.seek(0)


class DataTypeMixIn(object):
    """
    Provides methods for reading and writing basic data types for file-like
    objects.

    @ivar endian: Byte ordering used to represent the data. Default byte order
        is L{ENDIAN_NETWORK}.
    @type endian: C{str}
    """

    #: Network byte order
    ENDIAN_NETWORK = "!"
    #: Native byte order
    ENDIAN_NATIVE = "@"
    #: Little endian
    ENDIAN_LITTLE = "<"
    #: Big endian
    ENDIAN_BIG = ">"

    endian = ENDIAN_NETWORK

    def _read(self, length):
        """
        Reads C{length} bytes from the stream. If an attempt to read past the
        end of the buffer is made, L{IOError} is raised.
        """
        bytes = self.read(length)

        if len(bytes) != length:
            self.seek(0 - len(bytes), 1)

            raise IOError("Tried to read %d byte(s) from the stream" % length)

        return bytes

    def _is_big_endian(self):
        """
        Whether the current endian is big endian.
        """
        if self.endian == DataTypeMixIn.ENDIAN_NATIVE:
            return SYSTEM_ENDIAN == DataTypeMixIn.ENDIAN_BIG

        return self.endian in (DataTypeMixIn.ENDIAN_BIG, DataTypeMixIn.ENDIAN_NETWORK)

    def read_uchar(self):
        """
        Reads an C{unsigned char} from the stream.
        """
        return ord(self._read(1))

    def write_uchar(self, c):
        """
        Writes an C{unsigned char} to the stream.

        @param c: Unsigned char
        @type c: C{int}
        @raise TypeError: Unexpected type for int C{c}.
        @raise OverflowError: Not in range.
        """
        if type(c) not in python.int_types:
            raise TypeError('expected an int (got:%r)' % type(c))

        if not 0 <= c <= 255:
            raise OverflowError("Not in range, %d" % c)

        self.write(struct.pack("B", c))

    def read_char(self):
        """
        Reads a C{char} from the stream.
        """
        return struct.unpack("b", self._read(1))[0]

    def write_char(self, c):
        """
        Write a C{char} to the stream.

        @param c: char
        @type c: C{int}
        @raise TypeError: Unexpected type for int C{c}.
        @raise OverflowError: Not in range.
        """
        if type(c) not in python.int_types:
            raise TypeError('expected an int (got:%r)' % type(c))

        if not -128 <= c <= 127:
            raise OverflowError("Not in range, %d" % c)

        self.write(struct.pack("b", c))

    def read_ushort(self):
        """
        Reads a 2 byte unsigned integer from the stream.
        """
        return struct.unpack("%sH" % self.endian, self._read(2))[0]

    def write_ushort(self, s):
        """
        Writes a 2 byte unsigned integer to the stream.

        @param s: 2 byte unsigned integer
        @type s: C{int}
        @raise TypeError: Unexpected type for int C{s}.
        @raise OverflowError: Not in range.
        """
        if type(s) not in python.int_types:
            raise TypeError('expected an int (got:%r)' % (type(s),))

        if not 0 <= s <= 65535:
            raise OverflowError("Not in range, %d" % s)

        self.write(struct.pack("%sH" % self.endian, s))

    def read_short(self):
        """
        Reads a 2 byte integer from the stream.
        """
        return struct.unpack("%sh" % self.endian, self._read(2))[0]

    def write_short(self, s):
        """
        Writes a 2 byte integer to the stream.

        @param s: 2 byte integer
        @type s: C{int}
        @raise TypeError: Unexpected type for int C{s}.
        @raise OverflowError: Not in range.
        """
        if type(s) not in python.int_types:
            raise TypeError('expected an int (got:%r)' % (type(s),))

        if not -32768 <= s <= 32767:
            raise OverflowError("Not in range, %d" % s)

        self.write(struct.pack("%sh" % self.endian, s))

    def read_ulong(self):
        """
        Reads a 4 byte unsigned integer from the stream.
        """
        return struct.unpack("%sL" % self.endian, self._read(4))[0]

    def write_ulong(self, l):
        """
        Writes a 4 byte unsigned integer to the stream.

        @param l: 4 byte unsigned integer
        @type l: C{int}
        @raise TypeError: Unexpected type for int C{l}.
        @raise OverflowError: Not in range.
        """
        if type(l) not in python.int_types:
            raise TypeError('expected an int (got:%r)' % (type(l),))

        if not 0 <= l <= 4294967295:
            raise OverflowError("Not in range, %d" % l)

        self.write(struct.pack("%sL" % self.endian, l))

    def read_long(self):
        """
        Reads a 4 byte integer from the stream.
        """
        return struct.unpack("%sl" % self.endian, self._read(4))[0]

    def write_long(self, l):
        """
        Writes a 4 byte integer to the stream.

        @param l: 4 byte integer
        @type l: C{int}
        @raise TypeError: Unexpected type for int C{l}.
        @raise OverflowError: Not in range.
        """
        if type(l) not in python.int_types:
            raise TypeError('expected an int (got:%r)' % (type(l),))

        if not -2147483648 <= l <= 2147483647:
            raise OverflowError("Not in range, %d" % l)

        self.write(struct.pack("%sl" % self.endian, l))

    def read_24bit_uint(self):
        """
        Reads a 24 bit unsigned integer from the stream.

        @since: 0.4
        """
        order = None

        if not self._is_big_endian():
            order = [0, 8, 16]
        else:
            order = [16, 8, 0]

        n = 0

        for x in order:
            n += (self.read_uchar() << x)

        return n

    def write_24bit_uint(self, n):
        """
        Writes a 24 bit unsigned integer to the stream.

        @since: 0.4
        @param n: 24 bit unsigned integer
        @type n: C{int}
        @raise TypeError: Unexpected type for int C{n}.
        @raise OverflowError: Not in range.
        """
        if type(n) not in python.int_types:
            raise TypeError('expected an int (got:%r)' % (type(n),))

        if not 0 <= n <= 0xffffff:
            raise OverflowError("n is out of range")

        order = None

        if not self._is_big_endian():
            order = [0, 8, 16]
        else:
            order = [16, 8, 0]

        for x in order:
            self.write_uchar((n >> x) & 0xff)

    def read_24bit_int(self):
        """
        Reads a 24 bit integer from the stream.

        @since: 0.4
        """
        n = self.read_24bit_uint()

        if n & 0x800000 != 0:
            # the int is signed
            n -= 0x1000000

        return n

    def write_24bit_int(self, n):
        """
        Writes a 24 bit integer to the stream.

        @since: 0.4
        @param n: 24 bit integer
        @type n: C{int}
        @raise TypeError: Unexpected type for int C{n}.
        @raise OverflowError: Not in range.
        """
        if type(n) not in python.int_types:
            raise TypeError('expected an int (got:%r)' % (type(n),))

        if not -8388608 <= n <= 8388607:
            raise OverflowError("n is out of range")

        order = None

        if not self._is_big_endian():
            order = [0, 8, 16]
        else:
            order = [16, 8, 0]

        if n < 0:
            n += 0x1000000

        for x in order:
            self.write_uchar((n >> x) & 0xff)

    def read_double(self):
        """
        Reads an 8 byte float from the stream.
        """
        return struct.unpack("%sd" % self.endian, self._read(8))[0]

    def write_double(self, d):
        """
        Writes an 8 byte float to the stream.

        @param d: 8 byte float
        @type d: C{float}
        @raise TypeError: Unexpected type for float C{d}.
        """
        if not type(d) is float:
            raise TypeError('expected a float (got:%r)' % (type(d),))

        self.write(struct.pack("%sd" % self.endian, d))

    def read_float(self):
        """
        Reads a 4 byte float from the stream.
        """
        return struct.unpack("%sf" % self.endian, self._read(4))[0]

    def write_float(self, f):
        """
        Writes a 4 byte float to the stream.

        @param f: 4 byte float
        @type f: C{float}
        @raise TypeError: Unexpected type for float C{f}.
        """
        if type(f) is not float:
            raise TypeError('expected a float (got:%r)' % (type(f),))

        self.write(struct.pack("%sf" % self.endian, f))

    def read_utf8_string(self, length):
        """
        Reads a UTF-8 string from the stream.

        @rtype: C{unicode}
        """
        s = struct.unpack("%s%ds" % (self.endian, length), self.read(length))[0]

        return s.decode('utf-8')

    def write_utf8_string(self, u):
        """
        Writes a unicode object to the stream in UTF-8.

        @param u: unicode object
        @raise TypeError: Unexpected type for str C{u}.
        """
        if not isinstance(u, python.str_types):
            raise TypeError('Expected %r, got %r' % (python.str_types, u))

        bytes = u

        if isinstance(bytes, unicode):
            bytes = u.encode("utf8")

        self.write(struct.pack("%s%ds" % (self.endian, len(bytes)), bytes))


class BufferedByteStream(StringIOProxy, DataTypeMixIn):
    """
    An extension of C{StringIO}.

    Features:
     - Raises L{IOError} if reading past end.
     - Allows you to C{peek()} into the stream.
    """

    def __init__(self, buf=None, min_buf_size=None):
        """
        @param buf: Initial byte stream.
        @type buf: C{str} or C{StringIO} instance
        @param min_buf_size: Ignored in the pure python version.
        """
        StringIOProxy.__init__(self, buf=buf)

    def read(self, length=-1):
        """
        Reads up to the specified number of bytes from the stream into
        the specified byte array of specified length.

        @raise IOError: Attempted to read past the end of the buffer.
        """
        if length == -1 and self.at_eof():
            raise IOError(
                'Attempted to read from the buffer but already at the end')
        elif length > 0 and self.tell() + length > len(self):
            raise IOError('Attempted to read %d bytes from the buffer but '
                'only %d remain' % (length, len(self) - self.tell()))

        return StringIOProxy.read(self, length)

    def peek(self, size=1):
        """
        Looks C{size} bytes ahead in the stream, returning what it finds,
        returning the stream pointer to its initial position.

        @param size: Default is 1.
        @type size: C{int}
        @raise ValueError: Trying to peek backwards.

        @return: Bytes.
        """
        if size == -1:
            return self.peek(len(self) - self.tell())

        if size < -1:
            raise ValueError("Cannot peek backwards")

        bytes = ''
        pos = self.tell()

        while not self.at_eof() and len(bytes) != size:
            bytes += self.read(1)

        self.seek(pos)

        return bytes

    def remaining(self):
        """
        Returns number of remaining bytes.

        @rtype: C{number}
        @return: Number of remaining bytes.
        """
        return len(self) - self.tell()

    def at_eof(self):
        """
        Returns C{True} if the internal pointer is at the end of the stream.

        @rtype: C{bool}
        """
        return self.tell() == len(self)

    def append(self, data):
        """
        Append data to the end of the stream. The pointer will not move if
        this operation is successful.

        @param data: The data to append to the stream.
        @type data: C{str} or C{unicode}
        @raise TypeError: data is not C{str} or C{unicode}
        """
        t = self.tell()

        # seek to the end of the stream
        self.seek(0, 2)

        if hasattr(data, 'getvalue'):
            self.write_utf8_string(data.getvalue())
        else:
            self.write_utf8_string(data)

        self.seek(t)

    def __add__(self, other):
        old_pos = self.tell()
        old_other_pos = other.tell()

        new = BufferedByteStream(self)

        other.seek(0)
        new.seek(0, 2)
        new.write(other.read())

        self.seek(old_pos)
        other.seek(old_other_pos)
        new.seek(0)

        return new


def is_float_broken():
    """
    Older versions of Python (<=2.5) and the Windows platform are renowned for
    mixing up 'special' floats. This function determines whether this is the
    case.

    @since: 0.4
    @rtype: C{bool}
    """
    return str(python.NaN) != str(
        struct.unpack("!d", '\xff\xf8\x00\x00\x00\x00\x00\x00')[0])


# init the module from here ..

if is_float_broken():
    def read_double_workaround(self):
        """
        Override the L{DataTypeMixIn.read_double} method to fix problems
        with doubles by using the third-party C{fpconst} library.
        """
        bytes = self.read(8)

        if self._is_big_endian():
            if bytes == '\xff\xf8\x00\x00\x00\x00\x00\x00':
                return python.NaN

            if bytes == '\xff\xf0\x00\x00\x00\x00\x00\x00':
                return python.NegInf

            if bytes == '\x7f\xf0\x00\x00\x00\x00\x00\x00':
                return python.PosInf
        else:
            if bytes == '\x00\x00\x00\x00\x00\x00\xf8\xff':
                return python.NaN

            if bytes == '\x00\x00\x00\x00\x00\x00\xf0\xff':
                return python.NegInf

            if bytes == '\x00\x00\x00\x00\x00\x00\xf0\x7f':
                return python.PosInf

        return struct.unpack("%sd" % self.endian, bytes)[0]

    DataTypeMixIn.read_double = read_double_workaround

    def write_double_workaround(self, d):
        """
        Override the L{DataTypeMixIn.write_double} method to fix problems
        with doubles by using the third-party C{fpconst} library.
        """
        if type(d) is not float:
            raise TypeError('expected a float (got:%r)' % (type(d),))

        if python.isNaN(d):
            if self._is_big_endian():
                self.write('\xff\xf8\x00\x00\x00\x00\x00\x00')
            else:
                self.write('\x00\x00\x00\x00\x00\x00\xf8\xff')
        elif python.isNegInf(d):
            if self._is_big_endian():
                self.write('\xff\xf0\x00\x00\x00\x00\x00\x00')
            else:
                self.write('\x00\x00\x00\x00\x00\x00\xf0\xff')
        elif python.isPosInf(d):
            if self._is_big_endian():
                self.write('\x7f\xf0\x00\x00\x00\x00\x00\x00')
            else:
                self.write('\x00\x00\x00\x00\x00\x00\xf0\x7f')
        else:
            write_double_workaround.old_func(self, d)

    x = DataTypeMixIn.write_double
    DataTypeMixIn.write_double = write_double_workaround
    write_double_workaround.old_func = x


if struct.pack('@H', 1)[0] == '\x01':
    SYSTEM_ENDIAN = DataTypeMixIn.ENDIAN_LITTLE
else:
    SYSTEM_ENDIAN = DataTypeMixIn.ENDIAN_BIG
