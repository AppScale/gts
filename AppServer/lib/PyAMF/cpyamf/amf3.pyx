# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
C-extension for L{pyamf.amf3} Python module in L{PyAMF<pyamf>}.

@since: 0.6
"""

from cpython cimport *
from libc.stdlib cimport malloc, free

cimport cython

from cpyamf.util cimport cBufferedByteStream, BufferedByteStream
from cpyamf cimport codec
import pyamf
from pyamf import util, amf3, xml
import types


try:
    import zlib
except ImportError:
    zlib = None


cdef char TYPE_UNDEFINED = '\x00'
cdef char TYPE_NULL = '\x01'
cdef char TYPE_BOOL_FALSE = '\x02'
cdef char TYPE_BOOL_TRUE = '\x03'
cdef char TYPE_INTEGER = '\x04'
cdef char TYPE_NUMBER = '\x05'
cdef char TYPE_STRING = '\x06'
cdef char TYPE_XML = '\x07'
cdef char TYPE_DATE = '\x08'
cdef char TYPE_ARRAY = '\x09'
cdef char TYPE_OBJECT = '\x0A'
cdef char TYPE_XMLSTRING = '\x0B'
cdef char TYPE_BYTEARRAY = '\x0C'

cdef unsigned int REFERENCE_BIT = 0x01
cdef char REF_CHAR = '\x01'

#: The maximum that can be represented by an signed 29 bit integer.
cdef long MAX_29B_INT = 0x0FFFFFFF

#: The minimum that can be represented by an signed 29 bit integer.
cdef long MIN_29B_INT = -0x10000000

cdef int OBJECT_ENCODING_STATIC = 0x00
cdef int OBJECT_ENCODING_EXTERNAL = 0x01
cdef int OBJECT_ENCODING_DYNAMIC = 0x02
cdef int OBJECT_ENCODING_PROXY = 0x03

cdef object ByteArrayType = amf3.ByteArray
cdef object DataInput = amf3.DataInput
cdef object DataOutput = amf3.DataOutput
cdef str empty_string = str('')
cdef unicode empty_unicode = empty_string.decode('utf-8')
cdef object undefined = pyamf.Undefined


cdef class ClassDefinition(object):
    """
    Holds transient class trait info for an individual encode/decode.
    """

    def __cinit__(self):
        self.alias = None
        self.ref = -1
        self.attr_len = -1
        self.encoding = -1
        self.encoded_ref = NULL
        self.encoded_ref_size = -1

    def __init__(self, alias):
        self.alias = alias

        alias.compile()

        self.attr_len = 0
        self.static_properties = []

        if alias.static_attrs:
            self.attr_len = len(alias.static_attrs)
            self.static_properties = alias.static_attrs

        self.encoding = OBJECT_ENCODING_DYNAMIC

        if alias.external:
            self.encoding = OBJECT_ENCODING_EXTERNAL
        elif not alias.dynamic:
            if alias.encodable_properties is not None:
                if len(alias.static_attrs) == len(alias.encodable_properties):
                    self.encoding = OBJECT_ENCODING_STATIC
            else:
                self.encoding = OBJECT_ENCODING_STATIC

    def __dealloc__(self):
        if self.encoded_ref != NULL:
            free(self.encoded_ref)
            self.encoded_ref = NULL

    cdef int writeReference(self, cBufferedByteStream stream):
        if self.encoded_ref != NULL:
            return stream.write(self.encoded_ref, self.encoded_ref_size)

        cdef Py_ssize_t ref = 0
        cdef char *buf
        cdef int ret = 0

        if self.encoding != OBJECT_ENCODING_EXTERNAL:
            ref += self.attr_len << 4

        ref |= self.encoding << 2 | REFERENCE_BIT << 1 | REFERENCE_BIT

        try:
            ret = encode_int(ref, &buf)

            stream.write(buf, ret)
        finally:
            if buf != NULL:
                free(buf)

        try:
            self.encoded_ref_size = encode_int(self.ref << 2 | REFERENCE_BIT, &self.encoded_ref)
        except:
            if self.encoded_ref != NULL:
                free(self.encoded_ref)
                self.encoded_ref = NULL

            raise

        return 0


cdef class Context(codec.Context):
    """
    I hold the AMF3 context for en/decoding streams.
    """

    def __cinit__(self):
        self.strings = codec.IndexedCollection(use_hash=1)
        self.classes = {}
        self.class_ref = {}
        self.proxied_objects = {}

        self.class_idx = 0

    cpdef int clear(self) except -1:
        """
        Clears the context.
        """
        codec.Context.clear(self)

        self.strings.clear()
        self.proxied_objects = {}

        self.classes = {}
        self.class_ref = {}
        self.class_idx = 0

        return 0

    cpdef object getString(self, Py_ssize_t ref):
        return self.strings.getByReference(ref)

    cpdef Py_ssize_t getStringReference(self, object s) except -2:
        return self.strings.getReferenceTo(s)

    cpdef Py_ssize_t addString(self, object s) except -1:
        """
        Returns -2 which signifies that s was empty
        """
        return self.strings.append(s)

    cpdef object getClassByReference(self, Py_ssize_t ref):
        return self.class_ref.get(ref, None)

    cpdef ClassDefinition getClass(self, object klass):
        return self.classes.get(klass, None)

    cpdef Py_ssize_t addClass(self, ClassDefinition alias, klass) except? -1:
        cdef object ref = self.class_idx

        self.class_ref[ref] = alias
        self.classes[klass] = alias

        alias.ref = ref
        self.class_idx += 1

        return ref

    cpdef object getProxyForObject(self, object obj):
        """
        Returns the proxied version of C{obj} as stored in the context, or
        creates a new proxied object and returns that.

        @see: L{pyamf.flex.proxy_object}
        @since: 0.6
        """
        cdef PyObject *ret = PyDict_GetItem(self.proxied_objects, PyLong_FromVoidPtr(<void *>obj))

        if ret != NULL:
            return <object>ret

        from pyamf import flex

        proxied = flex.proxy_object(obj)

        self.addProxyObject(obj, proxied)

        return proxied

    cpdef object getObjectForProxy(self, object proxy):
        """
        Returns the unproxied version of C{proxy} as stored in the context, or
        unproxies the proxy and returns that 'raw' object.

        @see: L{pyamf.flex.unproxy_object}
        @since: 0.6
        """
        cdef PyObject *ret = PyDict_GetItem(self.proxied_objects, PyLong_FromVoidPtr(<void *>proxy))

        if ret != NULL:
            return <object>ret

        from pyamf import flex

        obj = flex.unproxy_object(proxy)

        self.addProxyObject(obj, proxy)

        return obj

    cpdef int addProxyObject(self, object obj, object proxied) except? -1:
        """
        Stores a reference to the unproxied and proxied versions of C{obj} for
        later retrieval.

        @since: 0.6
        """
        self.proxied_objects[PyLong_FromVoidPtr(<void *>obj)] = proxied
        self.proxied_objects[PyLong_FromVoidPtr(<void *>proxied)] = obj

        return 0


cdef class Decoder(codec.Decoder):
    """
    Decodes an AMF3 data stream.
    """

    def __init__(self, *args, **kwargs):
        context = kwargs.pop('context', None)

        if context is None:
            context = Context()

        self.context = context

        codec.Decoder.__init__(self, *args, **kwargs)

    cdef object readInteger(self, int signed=1):
        """
        Reads and returns an integer from the stream.

        @type signed: C{bool}
        @see: U{Parsing integers on OSFlash
        <http://osflash.org/amf3/parsing_integers>} for the AMF3 integer data
        format.
        """
        cdef int r = decode_int(self.stream, signed)

        return <object>r

    cdef object readNumber(self):
        cdef double d

        self.stream.read_double(&d)

        return d

    cdef object readBytes(self):
        cdef object s = self.readString()

        return self.context.getBytesForString(s)

    cpdef object readString(self):
        """
        Reads and returns a string from the stream.
        """
        cdef Py_ssize_t r = _read_ref(self.stream)
        cdef object s

        if r & REFERENCE_BIT == 0:
            # read a string reference
            return self.context.getString(r >> 1)

        r >>= 1

        if r == 0:
            return empty_unicode

        cdef char *buf = NULL

        self.stream.read(&buf, r)
        s = PyUnicode_DecodeUTF8(buf, r, 'strict')

        self.context.addString(s)

        return s

    cdef object readDate(self):
        """
        Read date from the stream.

        The timezone is ignored as the date is always in UTC.
        """
        cdef Py_ssize_t ref = _read_ref(self.stream)

        if ref & REFERENCE_BIT == 0:
            return self.context.getObject(ref >> 1)

        cdef double ms

        self.stream.read_double(&ms)

        cdef object result = util.get_datetime(ms / 1000.0)

        if self.timezone_offset is not None:
            result += self.timezone_offset

        self.context.addObject(result)

        return result

    cdef object readList(self):
        """
        Reads an array from the stream.
        """
        cdef int size = _read_ref(self.stream)
        cdef int i
        cdef list result
        cdef object tmp
        cdef unicode key

        if size & REFERENCE_BIT == 0:
            return self.context.getObject(size >> 1)

        size >>= 1
        key = self.readString()

        if PyUnicode_GetSize(key) == 0:
            # integer indexes only -> python list
            result = []
            self.context.addObject(result)

            for i from 0 <= i < size:
                result.append(self.readElement())

            return result

        tmp = pyamf.MixedArray()
        self.context.addObject(result)

        while PyUnicode_GetSize(key):
            tmp[key] = self.readElement()
            key = self.readString()

        for i from 0 <= i < size:
            el = self.readElement()
            tmp[i] = el

        return tmp

    cdef ClassDefinition _getClassDefinition(self, long ref):
        """
        Reads class definition from the stream.
        """
        if ref & REFERENCE_BIT == 0:
            return self.context.getClassByReference(ref >> 1)

        ref >>= 1

        cdef object name = self.readString()
        cdef object alias = None
        cdef Py_ssize_t i

        if PyUnicode_GET_SIZE(name) == 0:
            name = pyamf.ASObject

        try:
            alias = self.context.getClassAlias(name)
        except pyamf.UnknownClassAlias:
            if self.strict:
                raise

            alias = pyamf.TypedObjectClassAlias(name)

        cdef ClassDefinition class_def = ClassDefinition(alias)

        class_def.encoding = ref & 0x03
        class_def.attr_len = ref >> 2
        class_def.static_properties = []

        if class_def.attr_len > 0:
            for i from 0 <= i < class_def.attr_len:
                class_def.static_properties.append(self.readString())

        self.context.addClass(class_def, alias.klass)

        return class_def

    @cython.boundscheck(False)
    cdef int _readStatic(self, ClassDefinition class_def, dict obj) except -1:
        cdef Py_ssize_t i

        for 0 <= i < class_def.attr_len:
            obj[class_def.static_properties[i]] = self.readElement()

        return 0

    cdef int _readDynamic(self, ClassDefinition class_def, dict obj) except -1:
        cdef object attr
        cdef char *peek


        while True:
            self.stream.peek(&peek, 1)

            if peek[0] == REF_CHAR:
                self.stream.seek(1, 1)

                break

            attr = self.readBytes()

            PyDict_SetItem(obj, attr, self.readElement())

        return 0

    cdef object readObject(self):
        """
        Reads an object from the stream.

        @raise pyamf.EncodeError: Decoding an object in amf3 tagged as amf0
            only is not allowed.
        @raise pyamf.DecodeError: Unknown object encoding.
        """
        cdef int ref = _read_ref(self.stream)
        cdef object obj

        if ref & REFERENCE_BIT == 0:
            obj = self.context.getObject(ref >> 1)

            if obj is None:
                raise pyamf.ReferenceError('Unknown reference')

            if self.use_proxies == 1:
                return self.readProxy(obj)

            return obj

        cdef ClassDefinition class_def = self._getClassDefinition(ref >> 1)
        cdef object alias = class_def.alias

        obj = alias.createInstance(codec=self)
        cdef dict obj_attrs = {}

        self.context.addObject(obj)

        if class_def.encoding == OBJECT_ENCODING_DYNAMIC:
            self._readStatic(class_def, obj_attrs)
            self._readDynamic(class_def, obj_attrs)
        elif class_def.encoding == OBJECT_ENCODING_STATIC:
            self._readStatic(class_def, obj_attrs)
        elif class_def.encoding == OBJECT_ENCODING_EXTERNAL or class_def.encoding == OBJECT_ENCODING_PROXY:
            obj.__readamf__(DataInput(self))

            if self.use_proxies == 1:
                return self.readProxy(obj)

            return obj
        else:
            raise pyamf.DecodeError("Unknown object encoding")

        alias.applyAttributes(obj, obj_attrs, codec=self)

        if self.use_proxies:
            return self.readProxy(obj)

        return obj

    cdef object readXML(self):
        """
        Reads an XML object from the stream.
        """
        cdef int ref = _read_ref(self.stream)

        if ref & REFERENCE_BIT == 0:
            return self.context.getObject(ref >> 1)

        ref >>= 1

        cdef char *buf = NULL
        cdef object s

        self.stream.read(&buf, ref)
        s = PyString_FromStringAndSize(buf, ref)

        x = xml.fromstring(s)
        self.context.addObject(x)

        return x

    cdef object readByteArray(self):
        """
        Reads a string of data from the stream.

        Detects if the L{ByteArray} was compressed using C{zlib}.

        @see: L{ByteArray}
        @note: This is not supported in ActionScript 1.0 and 2.0.
        """
        cdef int ref = _read_ref(self.stream)

        if ref & REFERENCE_BIT == 0:
            return self.context.getObject(ref >> 1)

        cdef char *buf = NULL
        cdef object s
        cdef object compressed = None

        ref >>= 1

        self.stream.read(&buf, ref)
        s = PyString_FromStringAndSize(buf, ref)

        if zlib:
            try:
                s = zlib.decompress(s)
                compressed = True
            except zlib.error:
                compressed = False

            s = (<object>ByteArrayType)(s)

        s.compressed = compressed

        self.context.addObject(s)

        return s

    cdef object readProxy(self, obj):
        """
        Decodes a proxied object from the stream.

        @since: 0.6
        """
        return self.context.getObjectForProxy(obj)

    cdef object readConcreteElement(self, char t):
        if t == TYPE_STRING:
            return self.readString()
        elif t == TYPE_OBJECT:
            return self.readObject()
        elif t == TYPE_UNDEFINED:
            return undefined
        elif t == TYPE_NULL:
            return None
        elif t == TYPE_BOOL_FALSE:
            return False
        elif t == TYPE_BOOL_TRUE:
            return True
        elif t == TYPE_INTEGER:
            return self.readInteger(1)
        elif t == TYPE_NUMBER:
            return self.readNumber()
        elif t == TYPE_ARRAY:
            return self.readList()
        elif t == TYPE_DATE:
            return self.readDate()
        elif t == TYPE_BYTEARRAY:
            return self.readByteArray()
        elif t == TYPE_XML:
            return self.readXML()
        elif t == TYPE_XMLSTRING:
            return self.readXML()

        raise pyamf.DecodeError("Unsupported ActionScript type")


cdef class Encoder(codec.Encoder):
    """
    The AMF3 Encoder.
    """

    def __init__(self, *args, **kwargs):
        self.use_proxies = kwargs.pop('use_proxies', amf3.use_proxies_default)
        context = kwargs.pop('context', None)

        if context is None:
            context = Context()

        self.context = context

        codec.Encoder.__init__(self, *args, **kwargs)

    cdef inline int writeNull(self, n) except -1:
        """
        Writes a C{null} value to the stream.
        """
        return self.writeType(TYPE_NULL)

    cdef inline int writeUndefined(self, n) except -1:
        return self.writeType(TYPE_UNDEFINED)

    cdef inline int writeBoolean(self, n) except -1:
        if n is True:
            return self.writeType(TYPE_BOOL_TRUE)

        return self.writeType(TYPE_BOOL_FALSE)

    cpdef int serialiseString(self, u) except -1:
        """
        Serialises a unicode object.
        """
        cdef Py_ssize_t l
        cdef bint is_unicode = 0

        if PyUnicode_Check(u):
            l = PyUnicode_GET_SIZE(u)
            is_unicode = 1
        elif PyString_Check(u):
            l = PyString_GET_SIZE(u)
        else:
            raise TypeError('Expected str or unicode')

        if l == 0:
            # '' is a special case
            return self.stream.write(&REF_CHAR, 1)

        r = self.context.getStringReference(u)

        if r != -1:
            # we have a reference
            return _encode_integer(self.stream, r << 1)

        self.context.addString(u)

        if is_unicode:
            u = self.context.getBytesForString(u)
            l = PyString_GET_SIZE(u)

        _encode_integer(self.stream, (l << 1) | REFERENCE_BIT)

        return self.stream.write(PyString_AS_STRING(u), l)

    cdef int writeString(self, object s) except -1:
        self.writeType(TYPE_STRING)
        self.serialiseString(s)

    cdef int writeBytes(self, object s) except -1:
        self.writeType(TYPE_STRING)
        self.serialiseString(s)

    cdef int writeInt(self, object n) except -1:
        cdef long x = PyInt_AS_LONG(n)

        if x < MIN_29B_INT or x > MAX_29B_INT:
            return self.writeNumber(float(n))

        self.writeType(TYPE_INTEGER)
        _encode_integer(self.stream, x)

    cdef int writeLong(self, object n) except -1:
        cdef long x

        try:
            x = PyLong_AsLong(n)
        except:
            return self.writeNumber(float(n))

        if x < MIN_29B_INT or x > MAX_29B_INT:
            return self.writeNumber(float(n))

        self.writeType(TYPE_INTEGER)
        _encode_integer(self.stream, x)

    cdef int writeNumber(self, object n) except -1:
        cdef double x = PyFloat_AS_DOUBLE(n)

        self.writeType(TYPE_NUMBER)
        self.stream.write_double(x)

        return 0

    cpdef int writeList(self, object n, bint is_proxy=0) except -1:
        cdef Py_ssize_t ref = self.context.getObjectReference(n)
        cdef Py_ssize_t i
        cdef PyObject *x

        if self.use_proxies == 1 and not is_proxy:
            # Encode lists as ArrayCollections
            return self.writeProxy(n)

        self.writeType(TYPE_ARRAY)

        if ref != -1:
            return _encode_integer(self.stream, ref << 1)

        self.context.addObject(n)
        ref = PyList_GET_SIZE(n)

        _encode_integer(self.stream, (ref << 1) | REFERENCE_BIT)

        self.writeType('\x01')

        for i from 0 <= i < ref:
            x = PyList_GET_ITEM(n, i)

            self.writeElement(<object>x)

        return 0

    cdef int writeTuple(self, object n) except -1:
        cdef Py_ssize_t ref = self.context.getObjectReference(n)
        cdef Py_ssize_t i
        cdef PyObject *x

        self.writeType(TYPE_ARRAY)

        if ref != -1:
            return _encode_integer(self.stream, ref << 1)

        self.context.addObject(n)

        ref = PyTuple_GET_SIZE(n)

        _encode_integer(self.stream, (ref << 1) | REFERENCE_BIT)
        self.writeType('\x01')

        for i from 0 <= i < ref:
            x = PyTuple_GET_ITEM(n, i)

            self.writeElement(<object>x)

        return 0

    cdef int writeDict(self, dict obj) except -1:
        cdef Py_ssize_t idx = 0

        if self.use_proxies:
            return self.writeProxy(obj)

        self.writeType(TYPE_OBJECT)

        ref = self.context.getObjectReference(obj)

        if ref != -1:
            _encode_integer(self.stream, ref << 1)

            return 0

        self.context.addObject(obj)

        cdef bint class_ref = 0
        cdef ClassDefinition definition = self.context.getClass(dict)

        if not definition:
            definition = ClassDefinition(self.context.getClassAlias(dict))
            self.context.addClass(definition, dict)
        else:
            class_ref = 1

        definition.writeReference(self.stream)

        if class_ref == 0:
            self.stream.write(&REF_CHAR, 1)

        for key, value in obj.iteritems():
            if PyInt_Check(key) or PyLong_Check(key):
                key = str(key)

            self.serialiseString(key)
            self.writeElement(value)

        return self.stream.write(&REF_CHAR, 1)

    cdef int writeMixedArray(self, object n) except -1:
        # Design bug in AMF3 that cannot read/write empty key strings
        # http://www.docuverse.com/blog/donpark/2007/05/14/flash-9-amf3-bug
        # for more info
        if '' in n:
            raise pyamf.EncodeError("dicts cannot contain empty string keys")

        if self.use_proxies:
            return self.writeProxy(n)

        self.writeType(TYPE_ARRAY)

        ref = self.context.getObjectReference(n)

        if ref != -1:
            return _encode_integer(self.stream, ref << 1)

        self.context.addObject(n)

        # The AMF3 spec demands that all str based indicies be listed first
        keys = n.keys()
        int_keys = []
        str_keys = []

        for x in keys:
            if isinstance(x, (int, long)):
                int_keys.append(x)
            elif isinstance(x, (str, unicode)):
                str_keys.append(x)
            else:
                raise ValueError("Non int/str key value found in dict")

        # Make sure the integer keys are within range
        l = len(int_keys)

        for x in int_keys:
            if l < x <= 0:
                # treat as a string key
                str_keys.append(x)
                del int_keys[int_keys.index(x)]

        int_keys.sort()

        # If integer keys don't start at 0, they will be treated as strings
        if len(int_keys) > 0 and int_keys[0] != 0:
            for x in int_keys:
                str_keys.append(str(x))
                del int_keys[int_keys.index(x)]

        _encode_integer(self.stream, len(int_keys) << 1 | REFERENCE_BIT)

        for x in str_keys:
            self.serialiseString(x)
            self.writeElement(n[x])

        self.stream.write_uchar(0x01)

        for k in int_keys:
            self.writeElement(n[k])

    cpdef int writeObject(self, object obj, bint is_proxy=0) except -1:
        cdef Py_ssize_t ref
        cdef object kls
        cdef ClassDefinition definition
        cdef object alias = None
        cdef int class_ref = 0
        cdef int ret = 0
        cdef char *buf = NULL
        cdef PyObject *key
        cdef PyObject *value
        cdef object attrs

        if self.use_proxies and not is_proxy:
            return self.writeProxy(obj)

        self.writeType(TYPE_OBJECT)

        ref = self.context.getObjectReference(obj)

        if ref != -1:
            _encode_integer(self.stream, ref << 1)

            return 0

        self.context.addObject(obj)

        # object is not referenced, serialise it
        kls = obj.__class__
        definition = self.context.getClass(kls)

        if definition:
            class_ref = 1
            alias = definition.alias
        else:
            alias = self.context.getClassAlias(kls)
            definition = ClassDefinition(alias)

            self.context.addClass(definition, alias.klass)

        definition.writeReference(self.stream)

        if class_ref == 0:
            if alias.anonymous:
                self.stream.write(&REF_CHAR, 1)
            else:
                self.serialiseString(alias.alias)

            # work out what the final reference for the class will be.
            # this is okay because the next time an object of the same
            # class is encoded, class_ref will be True and never get here
            # again.

        if alias.external:
            obj.__writeamf__(DataOutput(self))

            return 0

        attrs = alias.getEncodableAttributes(obj, codec=self)

        if PyDict_CheckExact(attrs) != 1:
            raise TypeError('Expected dict for encodable attributes')

        if definition.attr_len > 0:
            if class_ref == 0:
                for attr in definition.static_properties:
                    self.serialiseString(attr)

            for attr in definition.static_properties:
                value = PyDict_GetItem(attrs, attr)

                if value == NULL:
                    raise KeyError

                if PyDict_DelItem(attrs, attr) == -1:
                    return -1

                self.writeElement(<object>value)

            if definition.encoding == OBJECT_ENCODING_STATIC:
                return 0

        if definition.encoding == OBJECT_ENCODING_DYNAMIC:
            ref = 0
            key = NULL
            value = NULL

            while PyDict_Next(attrs, &ref, &key, &value):
                self.serialiseString(<object>key)
                self.writeElement(<object>value)

            self.stream.write(&REF_CHAR, 1)

        return 0

    cdef int writeByteArray(self, object obj) except -1:
        """
        Writes a L{ByteArray} to the data stream.

        @param n: The L{ByteArray} data to be encoded to the AMF3 data stream.
        @type n: L{ByteArray}
        """
        cdef Py_ssize_t ref
        cdef object buf

        self.writeType(TYPE_BYTEARRAY)

        ref = self.context.getObjectReference(obj)

        if ref != -1:
            _encode_integer(self.stream, ref << 1)

            return 0

        self.context.addObject(obj)

        buf = str(obj)
        l = PyString_GET_SIZE(buf)

        _encode_integer(self.stream, (l << 1) | REFERENCE_BIT)
        self.stream.write(PyString_AS_STRING(buf), l)

        return 0

    cdef int writeXML(self, obj) except -1:
        self.writeType(TYPE_XMLSTRING)

        i = self.context.getObjectReference(obj)

        if i != -1:
            _encode_integer(self.stream, i << 1)

            return 0

        self.context.addObject(obj)

        s = xml.tostring(obj).encode('utf-8')

        if not PyString_CheckExact(s):
            raise TypeError('Expected string from xml serialization')

        i = PyString_GET_SIZE(s)

        _encode_integer(self.stream, (i << 1) | REFERENCE_BIT)
        self.stream.write(PyString_AS_STRING(s), i)

        return 0

    cdef int writeDateTime(self, obj) except -1:
        """
        Writes an L{datetime.datetime} object to the stream
        """
        cdef Py_ssize_t ref = self.context.getObjectReference(obj)

        self.writeType(TYPE_DATE)

        if ref != -1:
            _encode_integer(self.stream, ref << 1)

            return 0

        self.context.addObject(obj)
        self.stream.write(&REF_CHAR, 1)

        if self.timezone_offset is not None:
            obj -= self.timezone_offset

        ms = <double>util.get_timestamp(obj)
        self.stream.write_double(ms * 1000.0)

    cdef int writeProxy(self, obj) except -1:
        """
        Encodes a proxied object to the stream.

        @since: 0.6
        """
        cdef object proxy = self.context.getProxyForObject(obj)

        return self.writeObject(proxy, 1)

    cdef inline int handleBasicTypes(self, object element, object py_type) except -1:
        cdef int ret = codec.Encoder.handleBasicTypes(self, element, py_type)

        if ret == 1: # not handled
            if py_type is ByteArrayType:
                return self.writeByteArray(element)

        return ret


cdef int encode_int(long i, char **buf) except -1:
    # Use typecasting to get the twos complement representation of i
    cdef unsigned long n = (<unsigned long*>(<void *>(&i)))[0]

    cdef unsigned long real_value = n
    cdef unsigned char count = 0
    cdef char *bytes = NULL

    if n > 0x1fffff:
        bytes = <char *>malloc(4)

        if bytes == NULL:
            PyErr_NoMemory()

        n = n >> 1
        bytes[count] = 0x80 | ((n >> 21) & 0xff)
        count += 1

    if n > 0x3fff:
        if bytes == NULL:
            bytes = <char *>malloc(3)

            if bytes == NULL:
                PyErr_NoMemory()

        bytes[count] = 0x80 | ((n >> 14) & 0xff)
        count += 1

    if n > 0x7f:
        if bytes == NULL:
            bytes = <char *>malloc(2)

            if bytes == NULL:
                PyErr_NoMemory()

        bytes[count] = 0x80 | ((n >> 7) & 0xff)
        count += 1

    if bytes == NULL:
        bytes = <char *>malloc(1)

        if bytes == NULL:
            PyErr_NoMemory()

    if real_value > 0x1fffff:
        bytes[count] = real_value & 0xff
    else:
        bytes[count] = real_value & 0x7f

    buf[0] = bytes

    return count + 1


cdef int decode_int(cBufferedByteStream stream, int sign=0) except? -1:
    cdef int n = 0
    cdef int result = 0
    cdef unsigned char b = stream.read_uchar()

    while b & 0x80 != 0 and n < 3:
        result <<= 7
        result |= b & 0x7f

        b = stream.read_uchar()

        n += 1

    if n < 3:
        result <<= 7
        result |= b
    else:
        result <<= 8
        result |= b

        if result & 0x10000000 != 0:
            if sign == 1:
                result -= 0x20000000
            else:
                result <<= 1
                result += 1

    return result


cdef inline int _encode_integer(cBufferedByteStream stream, int i) except -1:
    cdef char *buf = NULL
    cdef int size = 0

    try:
        size = encode_int(i, &buf)

        return stream.write(buf, size)
    finally:
        free(buf)


cdef inline Py_ssize_t _read_ref(cBufferedByteStream stream) except -1:
    return <Py_ssize_t>decode_int(stream, 0)
