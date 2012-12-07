# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
C-extension for L{pyamf.amf3} Python module in L{PyAMF<pyamf>}.

:since: 0.6
"""

from cpython cimport *
from libc.stdlib cimport *
from libc.string cimport *

cdef extern from "math.h":
    float floor(float)

from cpyamf cimport codec, amf3

import pyamf
from pyamf import xml, util


cdef char TYPE_NUMBER      = '\x00'
cdef char TYPE_BOOL        = '\x01'
cdef char TYPE_STRING      = '\x02'
cdef char TYPE_OBJECT      = '\x03'
cdef char TYPE_MOVIECLIP   = '\x04'
cdef char TYPE_NULL        = '\x05'
cdef char TYPE_UNDEFINED   = '\x06'
cdef char TYPE_REFERENCE   = '\x07'
cdef char TYPE_MIXEDARRAY  = '\x08'
cdef char TYPE_OBJECTTERM  = '\x09'
cdef char TYPE_ARRAY       = '\x0A'
cdef char TYPE_DATE        = '\x0B'
cdef char TYPE_LONGSTRING  = '\x0C'
cdef char TYPE_UNSUPPORTED = '\x0D'
cdef char TYPE_RECORDSET   = '\x0E'
cdef char TYPE_XML         = '\x0F'
cdef char TYPE_TYPEDOBJECT = '\x10'
cdef char TYPE_AMF3        = '\x11'


cdef object ASObject = pyamf.ASObject
cdef object UnknownClassAlias = pyamf.UnknownClassAlias


cdef class Context(codec.Context):
    cdef amf3.Context amf3_context

    cpdef int clear(self) except -1:
        codec.Context.clear(self)

        if self.amf3_context:
            self.amf3_context.clear()

        return 0


cdef class Decoder(codec.Decoder):
    """
    """

    cdef public bint use_amf3
    cdef readonly Context context
    cdef amf3.Decoder amf3_decoder

    def __cinit__(self):
        self.use_amf3 = 0

    def __init__(self, *args, **kwargs):
        self.use_amf3 = kwargs.pop('use_amf3', 0)
        self.context = kwargs.pop('context', None)

        if self.context is None:
            self.context = Context()

        codec.Codec.__init__(self, *args, **kwargs)

    cdef object readNumber(self):
        cdef double i

        self.stream.read_double(&i)

        if floor(i) == i:
            try:
                return int(i)
            except OverflowError:
                return i

        return i

    cdef object readBoolean(self):
        cdef unsigned char b = self.stream.read_uchar()

        if b == 1:
            return True
        elif b == 0:
            return False

        raise pyamf.DecodeError('Bad boolean read from stream')

    cdef object readBytes(self):
        cdef object u

        u = self.readString()

        return self.context.getBytesForString(u)

    cpdef object readString(self):
        cdef unsigned short l
        cdef char *b = NULL

        l = self.stream.read_ushort()

        self.stream.read(&b, l)

        return PyUnicode_DecodeUTF8(b, <Py_ssize_t>l, 'strict')

    cdef dict readObjectAttributes(self, object obj_attrs):
        cdef object key
        cdef char *peek = NULL

        while True:
            self.stream.peek(&peek, 3)

            if memcmp(peek, b'\x00\x00\x09', 3) == 0:
                self.stream.seek(3, 1)

                break

            key = self.readBytes()

            PyDict_SetItem(obj_attrs, key, self.readElement())

        # discard the end marker (TYPE_OBJECTTERM)

    cdef object readObject(self):
        cdef object obj = ASObject()

        self.context.addObject(obj)

        self.readObjectAttributes(obj)

        return obj

    cdef object readTypedObject(self):
        cdef object class_alias = self.readString()

        try:
            alias = self.context.getClassAlias(class_alias)
        except UnknownClassAlias:
            if self.strict:
                raise

            alias = pyamf.TypedObjectClassAlias(class_alias)

        obj = alias.createInstance(codec=self)
        self.context.addObject(obj)

        cdef dict attrs = {}

        self.readObjectAttributes(attrs)

        alias.applyAttributes(obj, attrs, codec=self)

        return obj

    cdef object readReference(self):
        cdef unsigned short idx

        idx = self.stream.read_ushort()
        o = self.context.getObject(idx)

        if o is None:
            raise pyamf.ReferenceError('Unknown reference %d' % (idx,))

        return o

    cdef object readMixedArray(self):
        cdef unsigned long l
        cdef dict attrs

        obj = pyamf.MixedArray()
        self.context.addObject(obj)

        l = self.stream.read_ulong()

        attrs = self.readObjectAttributes(obj)

        for key, value in attrs.iteritems():
            try:
                key = int(key)
            except ValueError:
                pass

            obj[key] = value

        return obj

    cdef object readList(self):
        cdef list obj = []
        cdef unsigned long l
        cdef unsigned long i

        self.context.addObject(obj)
        l = self.stream.read_ulong()

        for i from 0 <= i < l:
            PyList_Append(obj, self.readElement())

        return obj

    cdef object readDate(self):
        cdef double ms
        cdef short tz

        self.stream.read_double(&ms)
        tz = self.stream.read_short()

        # Timezones are ignored
        d = util.get_datetime(ms / 1000.0)

        if self.timezone_offset:
            d = d + self.timezone_offset

        self.context.addObject(d)

        return d

    cdef object readLongString(self, bint bytes=0):
        cdef unsigned long l
        cdef char *b = NULL
        cdef object s

        l = self.stream.read_ulong()

        self.stream.read(&b, l)
        s = PyString_FromStringAndSize(b, <Py_ssize_t>l)

        if bytes:
            return s

        return self.context.getStringForBytes(s)

    cdef object readXML(self):
        cdef object data = self.readLongString()
        cdef object root = xml.fromstring(data)

        self.context.addObject(root)

        return root

    cdef object readAMF3(self):
        if self.amf3_decoder is None:
            self.context.amf3_context = amf3.Context()

            self.amf3_decoder = amf3.Decoder(
                stream=self.stream,
                context=self.context.amf3_context,
                timezone_offset=self.timezone_offset)

        return self.amf3_decoder.readElement()

    cdef object readConcreteElement(self, char type):
        if type == TYPE_NUMBER:
            return self.readNumber()
        elif type == TYPE_BOOL:
            return self.readBoolean()
        elif type == TYPE_STRING:
            return self.readString()
        elif type == TYPE_OBJECT:
            return self.readObject()
        elif type == TYPE_NULL:
            return self.readNull()
        elif type == TYPE_UNDEFINED:
            return self.readUndefined()
        elif type == TYPE_REFERENCE:
            return self.readReference()
        elif type == TYPE_MIXEDARRAY:
            return self.readMixedArray()
        elif type == TYPE_ARRAY:
            return self.readList()
        elif type == TYPE_DATE:
            return self.readDate()
        elif type == TYPE_LONGSTRING:
            return self.readLongString()
        elif type == TYPE_UNSUPPORTED:
            return self.readNull()
        elif type == TYPE_XML:
            return self.readXML()
        elif type == TYPE_TYPEDOBJECT:
            return self.readTypedObject()
        elif type == TYPE_AMF3:
            return self.readAMF3()

        raise pyamf.DecodeError("Unsupported ActionScript type")


cdef class Encoder(codec.Encoder):
    """
    The AMF0 Encoder.
    """

    cdef public bint use_amf3
    cdef readonly Context context
    cdef amf3.Encoder amf3_encoder

    def __cinit__(self):
        self.use_amf3 = 0

    def __init__(self, *args, **kwargs):
        self.use_amf3 = kwargs.pop('use_amf3', 0)

        self.context = kwargs.pop('context', None)

        if self.context is None:
            self.context = Context()

        codec.Codec.__init__(self, *args, **kwargs)

    cdef inline int writeReference(self, o) except -2:
        """
        Write reference to the data stream.
        """
        cdef Py_ssize_t idx = self.context.getObjectReference(o)

        if idx == -1 or idx > 65535:
            return -1

        self.writeType(TYPE_REFERENCE)

        return self.stream.write_ushort(idx)

    cdef int writeBoolean(self, b) except -1:
        self.writeType(TYPE_BOOL)

        if b is True:
            return self.writeType('\x01')
        else:
            return self.writeType('\x00')

    cdef int writeUndefined(self, data) except -1:
        return self.writeType(TYPE_UNDEFINED)

    cdef int writeNull(self, n) except -1:
        """
        Write null type to data stream.
        """
        return self.writeType(TYPE_NULL)

    cpdef int writeList(self, object a, bint is_proxy=0) except -1:
        """
        Write array to the stream.
        """
        cdef Py_ssize_t size, i
        cdef PyObject *x

        if self.writeReference(a) != -1:
            return 0

        self.context.addObject(a)

        self.writeType(TYPE_ARRAY)
        size = PyList_GET_SIZE(a)

        self.stream.write_ulong(size)

        for i from 0 <= i < size:
            x = PyList_GET_ITEM(a, i)

            self.writeElement(<object>x)

        return 0

    cdef int writeTuple(self, object a) except -1:
        cdef Py_ssize_t size, i
        cdef PyObject *x

        if self.writeReference(a) != -1:
            return 0

        self.context.addObject(a)

        self.writeType(TYPE_ARRAY)
        size = PyTuple_GET_SIZE(a)

        self.stream.write_ulong(size)

        for i from 0 <= i < size:
            x = PyTuple_GET_ITEM(a, i)

            self.writeElement(<object>x)

        return 0

    cdef int writeInt(self, object a) except -1:
        self.writeType(TYPE_NUMBER)

        return self.stream.write_double(a)

    cdef int writeNumber(self, n) except -1:
        self.writeType(TYPE_NUMBER)

        return self.stream.write_double(n)

    cdef int writeLong(self, object a):
        self.writeType(TYPE_NUMBER)

        return self.stream.write_double(a)

    cdef int writeBytes(self, s) except -1:
        """
        Write a string of bytes to the data stream.
        """
        cdef Py_ssize_t l = PyString_GET_SIZE(s)

        if l > 0xffff:
            self.writeType(TYPE_LONGSTRING)
        else:
            self.writeType(TYPE_STRING)

        if l > 0xffff:
            self.stream.write_ulong(l)
        else:
            self.stream.write_ushort(l)

        return self.stream.write(PyString_AS_STRING(s), l)

    cdef int writeString(self, u) except -1:
        """
        Write a unicode to the data stream.
        """
        cdef object s = self.context.getBytesForString(u)

        return self.writeBytes(s)

    cpdef int serialiseString(self, u) except -1:
        """
        Similar to L{writeString} but does not encode a type byte.
        """
        if PyUnicode_CheckExact(u):
            u = self.context.getBytesForString(u)

        cdef Py_ssize_t l = PyString_GET_SIZE(u)

        if l > 0xffff:
            self.stream.write_ulong(l)
        else:
            self.stream.write_ushort(l)

        return self.stream.write(PyString_AS_STRING(u), l)

    cdef int writeXML(self, e) except -1:
        """
        Writes an XML instance.
        """
        self.writeType(TYPE_XML)

        data = xml.tostring(e)

        if isinstance(data, unicode):
            data = data.encode('utf-8')

        if not PyString_CheckExact(data):
            raise TypeError('expected str from xml.tostring')

        cdef Py_ssize_t l = PyString_GET_SIZE(data)

        self.stream.write_ulong(l)

        return self.stream.write(PyString_AS_STRING(data), l)

    cdef int writeDateTime(self, d) except -1:
        if self.timezone_offset is not None:
            d -= self.timezone_offset

        secs = util.get_timestamp(d)

        self.writeType(TYPE_DATE)
        self.stream.write_double(secs * 1000.0)

        return self.stream.write('\x00\x00', 2)

    cdef int writeDict(self, dict o) except -1:
        if self.writeReference(o) != -1:
            return 0

        self.context.addObject(o)
        self.writeType(TYPE_OBJECT)
        self._writeDict(o)

        return self._writeEndObject()

    cdef int _writeDict(self, dict attrs) except -1:
        """
        Write C{dict} to the data stream.

        @param o: The C{dict} data to be encoded to the AMF0 data stream.
        """
        for key, value in attrs.iteritems():
            if PyInt_Check(key) or PyLong_Check(key):
                key = str(key)

            self.serialiseString(key)
            self.writeElement(value)

        return 0

    cdef inline int _writeEndObject(self) except -1:
        return self.stream.write('\x00\x00\x09', 3)

    cpdef int writeObject(self, o, bint is_proxy=0) except -1:
        """
        Write a Python object to the stream.

        @param o: The object data to be encoded to the AMF0 data stream.
        """
        if self.writeReference(o) != -1:
            return 0

        self.context.addObject(o)
        alias = self.context.getClassAlias(o.__class__)

        alias.compile()

        if alias.amf3:
            return self.writeAMF3(o)

        if alias.anonymous:
            self.writeType(TYPE_OBJECT)
        else:
            self.writeType(TYPE_TYPEDOBJECT)
            self.serialiseString(alias.alias)

        cdef dict attrs = alias.getEncodableAttributes(o, codec=self)

        if len(attrs) and alias.static_attrs:
            for key in alias.static_attrs:
                value = attrs.pop(key)

                self.serialiseString(key)
                self.writeElement(value)

        if attrs:
            self._writeDict(attrs)

        return self._writeEndObject()

    cdef int writeMixedArray(self, o) except -1:
        if self.writeReference(o) != -1:
            return 0

        self.context.addObject(o)
        self.writeType(TYPE_MIXEDARRAY)

        # TODO: optimise this
        # work out the highest integer index
        try:
            # list comprehensions to save the day
            max_index = max([y[0] for y in o.items()
                if isinstance(y[0], (int, long))])

            if max_index < 0:
                max_index = 0
        except ValueError:
            max_index = 0

        self.stream.write_ulong(max_index)

        self._writeDict(dict(o))
        self._writeEndObject()

    cdef int writeAMF3(self, o) except -1:
        if self.amf3_encoder is None:
            self.context.amf3_context = amf3.Context()

            self.amf3_encoder = amf3.Encoder(
                stream=self.stream,
                context=self.context.amf3_context,
                timezone_offset=self.timezone_offset)

        self.writeType(TYPE_AMF3)
        self.amf3_encoder.writeElement(o)

    cdef inline int handleBasicTypes(self, object element, object py_type) except -1:
        if self.use_amf3:
            return self.writeAMF3(element)

        return codec.Encoder.handleBasicTypes(self, element, py_type)
