from cpyamf cimport codec, util


cdef class ClassDefinition(object):
    """
    Holds transient class trait info for an individual encode/decode.
    """

    cdef readonly object alias
    cdef Py_ssize_t ref
    cdef readonly Py_ssize_t attr_len
    cdef readonly int encoding

    cdef char *encoded_ref
    cdef Py_ssize_t encoded_ref_size

    cdef readonly list static_properties

    cdef int writeReference(self, util.cBufferedByteStream stream)


cdef class Context(codec.Context):
    cdef codec.IndexedCollection strings
    cdef dict classes
    cdef dict class_ref
    cdef dict proxied_objects
    cdef Py_ssize_t class_idx

    cpdef object getString(self, Py_ssize_t ref)
    cpdef Py_ssize_t getStringReference(self, object s) except -2
    cpdef Py_ssize_t addString(self, object s) except -1

    cpdef int addProxyObject(self, object obj, object proxied) except? -1
    cpdef object getProxyForObject(self, object obj)
    cpdef object getObjectForProxy(self, object proxy)

    cpdef object getClassByReference(self, Py_ssize_t ref)
    cpdef ClassDefinition getClass(self, object klass)
    cpdef Py_ssize_t addClass(self, ClassDefinition alias, klass) except? -1


cdef class Decoder(codec.Decoder):
    cdef public bint use_proxies
    cdef readonly Context context

    cdef ClassDefinition _getClassDefinition(self, long ref)
    cdef int _readStatic(self, ClassDefinition class_def, dict obj) except -1
    cdef int _readDynamic(self, ClassDefinition class_def, dict obj) except -1

    cdef object readBytes(self)
    cdef object readInteger(self, int signed=?)
    cdef object readByteArray(self)
    cdef object readProxy(self, obj)


cdef class Encoder(codec.Encoder):
    cdef public bint use_proxies
    cdef readonly Context context

    cdef int writeByteArray(self, object obj) except -1
    cdef int writeProxy(self, obj) except -1
