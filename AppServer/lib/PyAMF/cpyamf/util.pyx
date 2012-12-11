# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
C-extension for L{pyamf.util} Python module in L{PyAMF<pyamf>}.

@since: 0.4
"""

from cpython cimport *
from libc.stdlib cimport *
from libc.string cimport *

cimport cython

cdef extern from "stdio.h":
    int SIZEOF_LONG

cdef extern from "Python.h":
    int _PyFloat_Pack4(float, unsigned char *, int) except? -1
    int _PyFloat_Pack8(double, unsigned char *, int) except? -1
    double _PyFloat_Unpack4(unsigned char *, int) except? -1.0
    double _PyFloat_Unpack8(unsigned char *, int) except? -1.0


from pyamf import python

# module constant declarations
DEF ENDIAN_NETWORK = "!"
DEF ENDIAN_NATIVE = "@"
DEF ENDIAN_LITTLE = "<"
DEF ENDIAN_BIG = ">"

DEF MAX_BUFFER_EXTENSION = 1 << 14

cdef char SYSTEM_ENDIAN

cdef int float_broken = -1

cdef unsigned char *NaN = <unsigned char *>'\xff\xf8\x00\x00\x00\x00\x00\x00'
cdef unsigned char *NegInf = <unsigned char *>'\xff\xf0\x00\x00\x00\x00\x00\x00'
cdef unsigned char *PosInf = <unsigned char *>'\x7f\xf0\x00\x00\x00\x00\x00\x00'

cdef double platform_nan
cdef double platform_posinf
cdef double platform_neginf

cdef double system_nan
cdef double system_posinf
cdef double system_neginf

cdef object pyamf_NaN = python.NaN
cdef object pyamf_NegInf = python.NegInf
cdef object pyamf_PosInf = python.PosInf
cdef object empty_unicode = unicode('')


@cython.profile(False)
cdef int _memcpy_ensure_endian(void *src, void *dest, unsigned int size) nogil:
    """
    """
    cdef unsigned char *buf = <unsigned char *>malloc(size)

    if buf == NULL:
        return -1

    memcpy(buf, src, size)

    if not is_big_endian(SYSTEM_ENDIAN):
        if swap_bytes(buf, size) == -1:
            free(buf)

            return -1

    memcpy(dest, buf, size)
    free(buf)

    return 0


cdef int build_platform_exceptional_floats() except -1:
    global platform_nan, platform_posinf, platform_neginf
    global system_nan, system_posinf, system_neginf

    if _memcpy_ensure_endian(NaN, &system_nan, 8) == -1:
        PyErr_NoMemory()

    if _memcpy_ensure_endian(NegInf, &system_neginf, 8) == -1:
        PyErr_NoMemory()

    if _memcpy_ensure_endian(PosInf, &system_posinf, 8) == -1:
        PyErr_NoMemory()

    if float_broken == 1:
        try:
            _PyFloat_Unpack8(<unsigned char *>&NaN, not is_big_endian(SYSTEM_ENDIAN))
        except:
            raise
        else:
            memcpy(&platform_nan, &system_nan, 8)

        try:
            _PyFloat_Unpack8(<unsigned char *>&PosInf, not is_big_endian(SYSTEM_ENDIAN))
        except:
            raise
        else:
            memcpy(&platform_posinf, &system_posinf, 8)

        try:
            _PyFloat_Unpack8(<unsigned char *>&NegInf, not is_big_endian(SYSTEM_ENDIAN))
        except:
            raise
        else:
            memcpy(&platform_neginf, &system_neginf, 8)

    return 0


@cython.profile(False)
cdef char get_native_endian() nogil:
    """
    A quick hack to determine the system's endian-ness ...

    @return: Either L{ENDIAN_LITTLE} or L{ENDIAN_BIG}
    """
    cdef unsigned int one = 1
    cdef int big_endian = (<char*>&one)[0] != 1

    if big_endian == 1:
        return ENDIAN_BIG
    else:
        return ENDIAN_LITTLE


@cython.profile(False)
cdef inline bint is_big_endian(char endian) nogil:
    """
    Returns a boolean value whether the supplied C{endian} is big.
    """
    if endian == ENDIAN_NATIVE:
        return SYSTEM_ENDIAN == ENDIAN_BIG

    return endian == ENDIAN_NETWORK or endian == ENDIAN_BIG


@cython.profile(False)
cdef inline int is_native_endian(char endian) nogil:
    if endian == ENDIAN_NATIVE:
        return 1

    if endian == ENDIAN_NETWORK:
        endian = ENDIAN_BIG

    return endian == SYSTEM_ENDIAN


@cython.profile(False)
cdef inline int swap_bytes(unsigned char *buffer, Py_ssize_t size) nogil:
    cdef unsigned char *buf = <unsigned char *>malloc(size)

    if buf == NULL:
        return -1

    cdef Py_ssize_t i

    for i from 0 <= i < size:
        buf[i] = buffer[size - i - 1]

    memcpy(buffer, buf, size)
    free(buf)

    return 0


cdef bint is_broken_float() except -1:
    cdef double test = _PyFloat_Unpack8(NaN, 0)

    cdef int result
    cdef unsigned char *buf = <unsigned char *>&test

    if not is_big_endian(SYSTEM_ENDIAN):
        if swap_bytes(buf, 8) == -1:
            PyErr_NoMemory()

    result = memcmp(NaN, buf, 8)

    return result != 0


cdef class cBufferedByteStream(object):
    """
    A file like object that can be read/written to. Supports data type
    specific reads/writes (e.g. ints, longs, floats etc.)

    Endian aware.
    """

    def __cinit__(self):
        self.endian = ENDIAN_NETWORK
        self.buffer = NULL
        self.min_buf_size = 512
        self.size = 0

    def __dealloc__(self):
        if self.buffer != NULL:
            free(self.buffer)

        self.buffer = NULL

    cdef inline int _init_buffer(self) except -1:
        if self.buffer != NULL:
            free(self.buffer)

            self.buffer = NULL

        self.pos = 0
        self.length = 0
        self.size = self.min_buf_size

        self.buffer = <char *>malloc(self.size)

        if self.buffer == NULL:
            PyErr_NoMemory()

        return 0

    cpdef inline Py_ssize_t tell(self):
        """
        Returns the position of the stream pointer.
        """
        return self.pos

    cdef int _actually_increase_buffer(self, Py_ssize_t new_size) except -1:
        if self.size == 0:
            self._init_buffer()

        cdef Py_ssize_t requested_size = self.size
        cdef char *buf

        while new_size > requested_size:
            requested_size *= 2

        if requested_size > new_size + MAX_BUFFER_EXTENSION:
            requested_size = new_size + MAX_BUFFER_EXTENSION

        buf = <char *>realloc(self.buffer, sizeof(char *) * requested_size)

        if buf == NULL:
            PyErr_NoMemory()

        self.buffer = buf
        self.size = requested_size

        return 0

    cdef inline int _increase_buffer(self, Py_ssize_t size) except -1:
        """
        Request to increase the buffer by C{size}
        """
        cdef Py_ssize_t new_len = self.length + size

        if new_len <= self.size:
            return 0

        return self._actually_increase_buffer(new_len)

    cdef int write(self, char *buf, Py_ssize_t size) except -1:
        """
        Writes the content of the specified C{buf} into this buffer.
        """
        assert buf != NULL, 'buf cannot be NULL'

        if size == 0:
            return 0

        self._increase_buffer(size)

        memcpy(self.buffer + self.pos, buf, size)

        self.pos += size

        if self.pos > self.length:
            self.length = self.pos

        return 0

    cdef inline bint has_available(self, Py_ssize_t size):
        if size == 0:
            return 1
        elif size < 0:
            return 0

        if self.length == self.pos:
            return 0

        if self.pos + size > self.length:
            return 0

        return 1

    cdef int read(self, char **buf, Py_ssize_t size) except -1:
        """
        Reads up to the specified number of bytes from the stream into
        the specified byte array of specified length.

        Do not free the results or bad things will happen
        """
        if size == -1:
            size = self.remaining()

            if size == 0:
                size = 1

        if not self.has_available(size):
            raise IOError

        buf[0] = self.buffer + self.pos

        self.pos += size

        return 0

    cpdef inline bint at_eof(self) except -1:
        """
        Returns C{True} if the internal pointer is at the end of the stream.

        @rtype: C{bool}
        """
        return self.length == self.pos

    cpdef inline Py_ssize_t remaining(self) except -1:
        """
        Returns number of remaining bytes.
        """
        return self.length - self.pos

    cpdef int seek(self, Py_ssize_t pos, int mode=0) except -1:
        """
        Sets the file-pointer offset, measured from the beginning of this stream,
        at which the next write operation will occur.

        @param mode: mode 0: absolute; 1: relative; 2: relative to EOF
        """
        if mode == 0:
            if pos < 0 or pos > self.length:
                raise IOError

            self.pos = pos
        elif mode == 1:
            if pos + self.pos < 0 or pos + self.pos > self.length:
                raise IOError

            self.pos += pos
        elif mode == 2:
            if pos + self.length < 0 or pos + self.length > self.length:
                raise IOError

            self.pos = self.length + pos
        else:
            raise ValueError('Bad value for mode')

        return 0

    cpdef object getvalue(self):
        """
        Get raw data from buffer.
        """
        return PyString_FromStringAndSize(self.buffer, self.length)

    cdef Py_ssize_t peek(self, char **buf, Py_ssize_t size) except -1:
        """
        Makes a pointer reference to the underlying buffer. Do NOT modify the
        returned value or free its contents. That would be seriously bad.
        """
        if not self.has_available(size):
            size = self.length - self.pos

        buf[0] = self.buffer + self.pos

        return size

    cpdef int truncate(self, Py_ssize_t size=0) except -1:
        """
        Truncates the stream to the specified length.

        @param size: The length of the stream, in bytes.
        @type size: C{int}
        """
        if size > self.length:
            raise IOError

        if size == 0:
            return self._init_buffer()

        cdef char *buf = NULL
        cdef Py_ssize_t cur_pos = self.pos

        buf = <char *>malloc(self.length)

        if buf == NULL:
            PyErr_NoMemory()

        memcpy(buf, self.buffer, self.length)

        try:
            self._init_buffer()

            self.write(buf, size)
        finally:
            free(buf)

        if self.length > cur_pos:
            self.pos = self.length
        else:
            self.seek(cur_pos, 0)

        return 0

    cpdef int consume(self) except -1:
        """
        Chops the tail off the stream starting at 0 and ending at C{tell()}.
        The stream pointer is set to 0 at the end of this function.
        """
        cdef char *buf = NULL
        cdef char *peek_buf
        cdef Py_ssize_t size = self.remaining()

        if size > 0:
            size = self.peek(&peek_buf, size)
            buf = <char *>malloc(size)

            if buf == NULL:
                PyErr_NoMemory()

            memcpy(buf, peek_buf, size)

        try:
            self._init_buffer()

            if size > 0:
                self.write(buf, size)
        finally:
            free(buf)

        self.pos = 0

        return 0

    cdef int unpack_int(self, unsigned int num_bytes, void *ret) except -1:
        """
        Unpacks a long from C{buf}.
        """
        cdef Py_ssize_t nb

        if num_bytes > 4:
            raise ValueError('Max 4 bytes to unpack')

        if not self.has_available(num_bytes):
            raise IOError

        cdef unsigned long x = 0
        cdef unsigned char *bytes = <unsigned char *>(self.buffer + self.pos)

        if is_big_endian(self.endian):
            for 0 <= nb < num_bytes:
                x = (x << 8) | bytes[nb]
        else:
            for 0 <= nb < num_bytes:
                x = (x << 8) | bytes[num_bytes - nb - 1]

        self.pos += num_bytes
        memcpy(ret, &x, num_bytes)

        return 0

    cdef int pack_int(self, int num_bytes, long x) except -1:
        """
        Packs a long.

        @raise OverflowError: integer out of range
        """
        cdef long maxint = 1
        cdef long minint = -1

        if num_bytes != SIZEOF_LONG:
            maxint = (maxint << (num_bytes * 8 - 1)) - 1
            minint = (-maxint) - 1

            if x > maxint or x < minint:
                raise OverflowError('integer out of range')

        cdef char *buf = <char *>malloc(num_bytes)

        if buf == NULL:
            PyErr_NoMemory()

        cdef long i = num_bytes

        if is_big_endian(self.endian):
            while i > 0:
                i -= 1
                buf[i] = <char>x
                x >>= 8
        else:
            while i > 0:
                buf[num_bytes - i] = <char>x
                i -= 1
                x >>= 8

        try:
            self.write(buf, num_bytes)
        finally:
            free(buf)

        return 0

    cdef int pack_uint(self, int num_bytes, unsigned long x) except -1:
        """
        Packs an unsigned long into a buffer.

        @raise OverflowError: integer out of range
        """
        cdef unsigned long maxint = 1

        if num_bytes != SIZEOF_LONG:
            maxint <<= <unsigned long>(num_bytes * 8)

            if x >= maxint:
                raise OverflowError('integer out of range')

        cdef char *buf = <char *>malloc(num_bytes)

        if buf == NULL:
            PyErr_NoMemory()

        cdef long i = num_bytes

        if is_big_endian(self.endian):
            while i > 0:
                i -= 1
                buf[i] = <char>x
                x >>= 8
        else:
            while i > 0:
                buf[num_bytes - i] = <char>x
                i -= 1
                x >>= 8

        try:
            self.write(buf, num_bytes)
        finally:
            free(buf)

        return 0

    cpdef unsigned char read_uchar(self) except? 0:
        """
        Reads an C{unsigned char} from the stream.
        """
        cdef unsigned char ch = 0

        self.unpack_int(1, &ch)

        return ch

    cpdef char read_char(self) except? 0:
        """
        Reads a C{char} from the stream.
        """
        cdef char ch = 0

        self.unpack_int(1, &ch)

        return ch

    cpdef unsigned short read_ushort(self) except? 0:
        """
        Reads a 2 byte unsigned integer from the stream.
        """
        cdef unsigned short x = 0

        self.unpack_int(2, &x)

        return x

    cpdef short read_short(self) except? 0:
        """
        Reads a 2 byte integer from the stream.
        """
        cdef short x = 0

        self.unpack_int(2, &x)

        return x

    cpdef unsigned long read_24bit_uint(self) except? 0:
        """
        Reads a 24 bit unsigned integer from the stream.
        """
        cdef unsigned long x = 0

        self.unpack_int(3, &x)

        return x

    cpdef long read_24bit_int(self) except? 0:
        """
        Reads a 24 bit integer from the stream.
        """
        cdef long x = 0

        self.unpack_int(3, &x)

        if x & 0x800000:
            x |= ~0xffffff

        return x

    cpdef unsigned long read_ulong(self) except? 0:
        """
        Reads a 4 byte unsigned integer from the stream.
        """
        cdef unsigned long x = 0

        self.unpack_int(4, &x)

        return x

    cpdef long read_long(self) except? 0:
        """
        Reads a 4 byte integer from the stream.
        """
        cdef long x = 0

        self.unpack_int(4, &x)

        if x & 0x80000000:
            x |= ~0x7fffffff

        return x

    cpdef int write_uchar(self, unsigned char ret) except -1:
        """
        Writes an C{unsigned char} to the stream.

        @param ret: Unsigned char
        @type ret: C{int}
        """
        return self.pack_uint(1, <unsigned long>ret)

    cpdef int write_char(self, char ret) except -1:
        """
        Write a C{char} to the stream.

        @param ret: char
        @type ret: C{int}
        """
        return self.pack_int(1, <long>ret)

    cpdef int write_ushort(self, unsigned short ret) except -1:
        """
        Writes a 2 byte unsigned integer to the stream.

        @param ret: 2 byte unsigned integer
        @type ret: C{int}
        """
        return self.pack_uint(2, <unsigned long>ret)

    cpdef int write_short(self, short ret) except -1:
        """
        Writes a 2 byte integer to the stream.

        @param ret: 2 byte integer
        @type ret: C{int}
        """
        return self.pack_int(2, <long>ret)

    cpdef int write_ulong(self, unsigned long ret) except -1:
        """
        Writes a 4 byte unsigned integer to the stream.

        @param ret: 4 byte unsigned integer
        @type ret: C{int}
        """
        return self.pack_uint(4, ret)

    cpdef int write_long(self, long ret) except -1:
        """
        Writes a 4 byte integer to the stream.

        @param ret: 4 byte integer
        @type ret: C{int}
        """
        return self.pack_int(4, ret)

    cpdef int write_24bit_uint(self, unsigned long ret) except -1:
        """
        Writes a 24 bit unsigned integer to the stream.

        @param ret: 24 bit unsigned integer
        @type ret: C{int}
        """
        return self.pack_uint(3, ret)

    cpdef int write_24bit_int(self, long ret) except -1:
        """
        Writes a 24 bit integer to the stream.

        @param ret: 24 bit integer
        @type ret: C{int}
        """
        return self.pack_int(3, ret)

    cpdef object read_utf8_string(self, Py_ssize_t l):
        """
        Reads a UTF-8 string from the stream.

        @rtype: C{unicode}
        """
        cdef char* buf = NULL
        cdef object ret

        if l == 0:
            return empty_unicode

        self.read(&buf, l)
        ret = PyUnicode_DecodeUTF8(buf, l, 'strict')

        return ret

    cpdef int write_utf8_string(self, object obj) except -1:
        """
        Writes a unicode object to the stream in UTF-8.

        @param obj: unicode object
        @raise TypeError: Unexpected type for str C{u}.
        """
        cdef object encoded_string
        cdef char *buf = NULL
        cdef Py_ssize_t l = -1

        if PyUnicode_Check(obj) == 1:
            encoded_string = PyUnicode_AsUTF8String(obj)
        elif PyString_Check(obj) == 1:
            encoded_string = obj
        else:
            raise TypeError('value must be Unicode or str')

        PyString_AsStringAndSize(encoded_string, &buf, &l)
        self.write(buf, l)

        return 0

    cdef int read_double(self, double *obj) except -1:
        """
        Reads an 8 byte float from the stream.
        """
        cdef unsigned char *buf = NULL
        cdef int done = 0

        self.read(<char **>&buf, 8)

        if float_broken == 1:
            if is_big_endian(SYSTEM_ENDIAN):
                if not is_big_endian(self.endian):
                    if swap_bytes(buf, 8) == -1:
                        PyErr_NoMemory()
            else:
                if is_big_endian(self.endian):
                    if swap_bytes(buf, 8) == -1:
                        PyErr_NoMemory()

            if memcmp(buf, &system_nan, 8) == 0:
                memcpy(obj, &system_nan, 8)

                done = 1
            elif memcmp(buf, &system_posinf, 8) == 0:
                memcpy(obj, &system_posinf, 8)

                done = 1
            elif memcmp(buf, &system_neginf, 8) == 0:
                memcpy(obj, &system_neginf, 8)

                done = 1

            if done == 1:
                return 0

            if is_big_endian(SYSTEM_ENDIAN):
                if not is_big_endian(self.endian):
                    if swap_bytes(buf, 8) == -1:
                        PyErr_NoMemory()
            else:
                if is_big_endian(self.endian):
                    if swap_bytes(buf, 8) == -1:
                        PyErr_NoMemory()

        obj[0] = _PyFloat_Unpack8(buf, not is_big_endian(self.endian))

        return 0

    cpdef int write_double(self, double val) except -1:
        """
        Writes an 8 byte float to the stream.

        @param val: 8 byte float
        @type val: C{float}
        """
        cdef unsigned char *buf
        cdef unsigned char *foo
        cdef int done = 0

        buf = <unsigned char *>malloc(sizeof(double))

        if buf == NULL:
            PyErr_NoMemory()

        try:
            if float_broken == 1:
                if memcmp(&val, &system_nan, 8) == 0:
                    memcpy(buf, &val, 8)

                    done = 1
                elif memcmp(&val, &system_posinf, 8) == 0:
                    memcpy(buf, &val, 8)

                    done = 1
                elif memcmp(&val, &system_neginf, 8) == 0:
                    memcpy(buf, &val, 8)

                    done = 1

                if done == 1:
                    if is_big_endian(SYSTEM_ENDIAN):
                        if not is_big_endian(self.endian):
                            if swap_bytes(buf, 8) == -1:
                                PyErr_NoMemory()
                    else:
                        if is_big_endian(self.endian):
                            if swap_bytes(buf, 8) == -1:
                                PyErr_NoMemory()

            if done == 0:
                _PyFloat_Pack8(val, <unsigned char *>buf, not is_big_endian(self.endian))

            self.write(<char *>buf, 8)
        finally:
            free(buf)

        return 0

    cdef int read_float(self, float *x) except -1:
        """
        Reads a 4 byte float from the stream.
        """
        cdef char *buf = NULL
        cdef unsigned char le = not is_big_endian(self.endian)

        self.read(&buf, 4)

        x[0] = _PyFloat_Unpack4(<unsigned char *>buf, le)

        return 0

    cpdef int write_float(self, float c) except -1:
        """
        Writes a 4 byte float to the stream.

        @param c: 4 byte float
        @type c: C{float}
        """
        cdef unsigned char *buf
        cdef unsigned char le = not is_big_endian(self.endian)

        buf = <unsigned char *>malloc(4)

        if buf == NULL:
            PyErr_NoMemory()

        try:
            _PyFloat_Pack4(c, <unsigned char *>buf, le)

            self.write(<char *>buf, 4)
        finally:
            free(buf)

        return 0

    cpdef int append(self, object obj) except -1:
        cdef int i = self.pos

        self.pos = self.length

        if hasattr(obj, 'getvalue'):
            self.write_utf8_string(obj.getvalue())
        else:
            self.write_utf8_string(obj)

        self.pos = i

        return 0

    def __nonzero__(self):
        return self.length > 0


cdef class BufferedByteStream(cBufferedByteStream):
    """
    A Python exposed version of cBufferedByteStream. This exists because of
    various intricacies of Cythons cpdef (probably just user stupidity tho)
    """

    def __init__(self, buf=None, min_buf_size=512):
        cdef Py_ssize_t i
        cdef cBufferedByteStream x

        self.min_buf_size = min_buf_size

        if buf is None:
            pass
        elif isinstance(buf, cBufferedByteStream):
            x = <cBufferedByteStream>buf
            self.write(x.getvalue())
        elif isinstance(buf, (str, unicode)):
            self.write(buf)
        elif hasattr(buf, 'getvalue'):
            self.write(buf.getvalue())
        elif hasattr(buf, 'read') and hasattr(buf, 'seek') and hasattr(buf, 'tell'):
            old_pos = buf.tell()
            buf.seek(0)
            self.write(buf.read())
            buf.seek(old_pos)
        else:
            raise TypeError("Unable to coerce buf->StringIO")

        self.seek(0)

    property endian:
        def __set__(self, value):
            if PyString_Check(value) == 0:
                raise TypeError('String value expected')

            if value not in [ENDIAN_NETWORK, ENDIAN_NATIVE, ENDIAN_LITTLE, ENDIAN_BIG]:
                raise ValueError('Not a valid endian type')

            self.endian = PyString_AsString(value)[0]

        def __get__(self):
            return PyString_FromStringAndSize(&self.endian, 1)

    def read(self, size=-1):
        """
        Reads C{size} bytes from the stream.
        """
        cdef Py_ssize_t s
        cdef object cls

        if size != -1:
            s = <Py_ssize_t>size
        else:
            s = self.remaining()

            if s == 0:
                s = 1

        cdef char *buf = NULL

        cBufferedByteStream.read(self, &buf, s)

        return PyString_FromStringAndSize(buf, s)

    def write(self, x, size=-1):
        """
        Writes the content of the specified C{x} into this buffer.

        @param x:
        @type x:
        """
        if size == -1:
            cBufferedByteStream.write_utf8_string(self, x)
        else:
            cBufferedByteStream.write(self, x, size)

    def flush(self):
        # no-op
        pass

    def __len__(self):
        return self.length

    def peek(self, Py_ssize_t size=1):
        """
        Looks C{size} bytes ahead in the stream, returning what it finds,
        returning the stream pointer to its initial position.

        @param size: Default is 1.
        @type size: C{int}

        @rtype:
        @return: Bytes.
        """
        cdef char *buf = NULL

        if size == -1:
            size = cBufferedByteStream.remaining(self)

        size = cBufferedByteStream.peek(self, &buf, size)

        return PyString_FromStringAndSize(buf, size)

    def write_char(self, x):
        """
        Write a C{char} to the stream.

        @param x: char
        @type x: C{int}
        @raise TypeError: Unexpected type for int C{x}.
        """
        if PyInt_Check(x) == 0 and PyLong_Check(x) == 0:
            raise TypeError('expected int for x')

        cBufferedByteStream.write_char(self, <char>x)

    def write_ushort(self, x):
        """
        Writes a 2 byte unsigned integer to the stream.

        @param x: 2 byte unsigned integer
        @type x: C{int}
        @raise TypeError: Unexpected type for int C{x}.
        """
        if PyInt_Check(x) == 0 and PyLong_Check(x) == 0:
            raise TypeError('expected int for x')

        cBufferedByteStream.write_ushort(self, <unsigned short>x)

    def write_short(self, x):
        """
        Writes a 2 byte integer to the stream.

        @param x: 2 byte integer
        @type x: C{int}
        @raise TypeError: Unexpected type for int C{x}.
        """
        if PyInt_Check(x) == 0 and PyLong_Check(x) == 0:
            raise TypeError('expected int for x')

        cBufferedByteStream.write_short(self, <short>x)

    def write_ulong(self, x):
        """
        Writes a 4 byte unsigned integer to the stream.

        @param x: 4 byte unsigned integer
        @type x: C{int}
        @raise TypeError: Unexpected type for int C{x}.
        """
        if PyInt_Check(x) == 0 and PyLong_Check(x) == 0:
            raise TypeError('expected int for x')

        if x > 4294967295L or x < 0:
            raise OverflowError

        cBufferedByteStream.write_ulong(self, <unsigned long>x)

    def read_double(self):
        """
        Reads an 8 byte float from the stream.
        """
        cdef double x

        cBufferedByteStream.read_double(self, &x)

        if float_broken == 1:
            if memcmp(&x, &system_nan, 8) == 0:
                return pyamf_NaN
            elif memcmp(&x, &system_neginf, 8) == 0:
                return pyamf_NegInf
            elif memcmp(&x, &system_posinf, 8) == 0:
                return pyamf_PosInf

        return PyFloat_FromDouble(x)

    def write_double(self, val):
        """
        Writes an 8 byte float to the stream.

        @param val: 8 byte float
        @type val: C{float}
        @raise TypeError: Unexpected type for float C{val}.
        """
        if PyFloat_Check(val) == 0:
            raise TypeError('Expecting float for val')

        cdef double d = val

        if float_broken == 1:
            if memcmp(&d, &platform_nan, 8) == 0:
                done = 1
            elif memcmp(&d, &platform_neginf, 8) == 0:
                done = 1
            elif memcmp(&d, &platform_posinf, 8) == 0:
                done = 1

            if done == 1:
                if is_big_endian(SYSTEM_ENDIAN):
                    if not is_big_endian(self.endian):
                        if swap_bytes(<unsigned char *>&d, 8) == -1:
                            PyErr_NoMemory()
                else:
                    if is_big_endian(self.endian):
                        if swap_bytes(<unsigned char *>&d, 8) == -1:
                            PyErr_NoMemory()

                cBufferedByteStream.write(self, <char *>&d, 8)

                return

        cBufferedByteStream.write_double(self, d)

    def read_float(self):
        """
        Reads a 4 byte float from the stream.
        """
        cdef float x

        cBufferedByteStream.read_float(self, &x)

        return PyFloat_FromDouble(x)

    def __add__(self, other):
        cdef Py_ssize_t old_pos = self.tell()
        cdef Py_ssize_t old_other_pos = other.tell()

        new = BufferedByteStream(self)

        other.seek(0)
        new.seek(0, 2)
        new.write(other.read())

        self.seek(old_pos)
        other.seek(old_other_pos)
        new.seek(0)

        return new

    def __str__(self):
        return self.getvalue()


# init the module from here

SYSTEM_ENDIAN = get_native_endian()

if is_broken_float():
    float_broken = 1

if build_platform_exceptional_floats() == -1:
    raise SystemError('Unable to initialise cpyamf.util')
