# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.


cdef class cBufferedByteStream:
    """
    The c version of BufferedByteStream.

    :todo: Need to spend some time marrying these two up.
    """
    cdef char endian
    cdef char *buffer
    cdef int closed
    cdef Py_ssize_t pos
    cdef Py_ssize_t size # total size of the alloc'd buffer
    cdef Py_ssize_t length
    cdef Py_ssize_t min_buf_size

    cpdef inline Py_ssize_t tell(self) except -1
    cdef int write(self, char *buf, Py_ssize_t size) except -1
    cdef inline int _init_buffer(self)
    cdef int _actually_increase_buffer(self, Py_ssize_t size) except -1
    cdef int _increase_buffer(self, Py_ssize_t size) except -1
    cdef inline bint has_available(self, Py_ssize_t size) except -1
    cdef int read(self, char **buf, Py_ssize_t size) except -1
    cpdef bint at_eof(self) except -1
    cpdef inline Py_ssize_t remaining(self) except -1
    cpdef int seek(self, Py_ssize_t pos, int mode=*) except -1
    cpdef object getvalue(self)
    cdef Py_ssize_t peek(self, char **buf, Py_ssize_t size) except -1
    cpdef int truncate(self, Py_ssize_t size=?) except -1
    cpdef int consume(self) except -1
    cdef int unpack_int(self, unsigned int num_bytes, void *ret) except -1
    cdef int pack_int(self, int num_bytes, long x) except -1
    cdef int pack_uint(self, int num_bytes, unsigned long x) except -1
    cpdef unsigned char read_uchar(self) except? 0
    cpdef char read_char(self) except? 0
    cpdef unsigned short read_ushort(self) except? 0
    cpdef short read_short(self) except? 0
    cpdef unsigned long read_24bit_uint(self) except? 0
    cpdef long read_24bit_int(self) except? 0
    cpdef unsigned long read_ulong(self) except? 0
    cpdef long read_long(self) except? 0
    cpdef int write_uchar(self, unsigned char ret) except -1
    cpdef int write_char(self, char ret) except -1
    cpdef int write_ushort(self, unsigned short ret) except -1
    cpdef int write_short(self, short ret) except -1
    cpdef int write_24bit_uint(self, unsigned long ret) except -1
    cpdef int write_24bit_int(self, long ret) except -1
    cpdef int write_ulong(self, unsigned long ret) except -1
    cpdef int write_long(self, long ret) except -1
    cpdef object read_utf8_string(self, Py_ssize_t)
    cpdef int write_utf8_string(self, object obj) except -1
    cdef int read_double(self, double *obj) except -1
    cpdef int write_double(self, double val) except -1
    cdef int read_float(self, float *x) except -1
    cpdef int write_float(self, float c) except -1
    cpdef int append(self, object obj) except -1


cdef class BufferedByteStream(cBufferedByteStream):
    """
    A file like object that mimics StringIO with some extra helper methods.

    Provides the ability to read arbitrary data types from the underlying
    stream.
    """
