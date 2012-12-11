# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Provides basic functionality for all pyamf.amf?.[De|E]ncoder classes.
"""

import types
import datetime

import pyamf
from pyamf import util, python, xml

__all__ = [
    'IndexedCollection',
    'Context',
    'Decoder',
    'Encoder'
]

try:
    unicode
except NameError:
    # py3k support
    unicode = str
    str = bytes


class IndexedCollection(object):
    """
    Store references to objects and provides an api to query references.

    All reference checks are done using the builtin C{id} function unless
    C{use_hash} is specified as C{True} where the slower but more flexible
    C{hash} builtin is used.

    @note: All attributes on the instance are private, use the apis only.
    """

    def __init__(self, use_hash=False):
        if use_hash is True:
            self.func = hash
        else:
            self.func = id

        self.clear()

    def clear(self):
        """
        Clears the collection.
        """
        self.list = []
        self.dict = {}

    def getByReference(self, ref):
        """
        Returns an object based on the supplied reference. The C{ref} should
        be an C{int}.

        If the reference is not found, C{None} will be returned.
        """
        try:
            return self.list[ref]
        except IndexError:
            return None

    def getReferenceTo(self, obj):
        """
        Returns a reference to C{obj} if it is contained within this index.

        If the object is not contained within the collection, C{-1} will be
        returned.

        @param obj: The object to find the reference to.
        @return: An C{int} representing the reference or C{-1} is the object
            is not contained within the collection.
        """
        return self.dict.get(self.func(obj), -1)

    def append(self, obj):
        """
        Appends C{obj} to this index.

        @note: Uniqueness is not checked
        @return: The reference to C{obj} in this index.
        """
        h = self.func(obj)

        self.list.append(obj)
        idx = len(self.list) - 1
        self.dict[h] = idx

        return idx

    def __eq__(self, other):
        if isinstance(other, list):
            return self.list == other

        raise NotImplementedError("cannot compare %s to %r" % (
            type(other), self))

    def __len__(self):
        return len(self.list)

    def __getitem__(self, idx):
        return self.getByReference(idx)

    def __contains__(self, obj):
        r = self.getReferenceTo(obj)

        return r != -1

    def __repr__(self):
        t = self.__class__

        return '<%s.%s size=%d 0x%x>' % (
            t.__module__,
            t.__name__,
            len(self.list),
            id(self))


class Context(object):
    """
    The base context for all AMF [de|en]coding.

    @ivar extra: The only public attribute. This is a placeholder for any extra
        contextual data that required for different adapters.
    @type extra: C{dict}
    @ivar _objects: A collection of stored references to objects that have
        already been visited by this context.
    @type _objects: L{IndexedCollection}
    @ivar _class_aliases: Lookup of C{class} -> L{pyamf.ClassAlias} as
        determined by L{pyamf.get_class_alias}
    @ivar _unicodes: Lookup of utf-8 encoded byte strings -> string objects
        (aka strings/unicodes).
    """

    def __init__(self):
        self._objects = IndexedCollection()

        self.clear()

    def clear(self):
        """
        Clears the context.
        """
        self._objects.clear()
        self._class_aliases = {}
        self._unicodes = {}
        self.extra = {}

    def getObject(self, ref):
        """
        Gets an object based on a reference.

        @type ref: C{int}
        @return: The referenced object or C{None} if not found.
        """
        return self._objects.getByReference(ref)

    def getObjectReference(self, obj):
        """
        Gets a reference for an already referenced object.

        @return: The reference to the object or C{-1} if the object is not in
            the context.
        """
        return self._objects.getReferenceTo(obj)

    def addObject(self, obj):
        """
        Adds a reference to C{obj}.

        @return: Reference to C{obj}.
        @rtype: C{int}
        """
        return self._objects.append(obj)

    def getClassAlias(self, klass):
        """
        Gets a class alias based on the supplied C{klass}. If one is not found
        in the global context, one is created locally.

        If you supply a string alias and the class is not registered,
        L{pyamf.UnknownClassAlias} will be raised.

        @param klass: A class object or string alias.
        @return: The L{pyamf.ClassAlias} instance that describes C{klass}
        """
        try:
            return self._class_aliases[klass]
        except KeyError:
            pass

        try:
            alias = self._class_aliases[klass] = pyamf.get_class_alias(klass)
        except pyamf.UnknownClassAlias:
            if isinstance(klass, python.str_types):
                raise

            # no alias has been found yet .. check subclasses
            alias = util.get_class_alias(klass) or pyamf.ClassAlias
            meta = util.get_class_meta(klass)
            alias = alias(klass, defer=True, **meta)

            self._class_aliases[klass] = alias

        return alias

    def getStringForBytes(self, s):
        """
        Returns the corresponding string for the supplied utf-8 encoded bytes.
        If there is no string object, one is created.

        @since: 0.6
        """
        h = hash(s)
        u = self._unicodes.get(h, None)

        if u is not None:
            return u

        u = self._unicodes[h] = s.decode('utf-8')

        return u

    def getBytesForString(self, u):
        """
        Returns the corresponding utf-8 encoded string for a given unicode
        object. If there is no string, one is encoded.

        @since: 0.6
        """
        h = hash(u)
        s = self._unicodes.get(h, None)

        if s is not None:
            return s

        s = self._unicodes[h] = u.encode('utf-8')

        return s


class _Codec(object):
    """
    Base codec.

    @ivar stream: The underlying data stream.
    @type stream: L{util.BufferedByteStream}
    @ivar context: The context for the encoding.
    @ivar strict: Whether the codec should operate in I{strict} mode.
    @type strict: C{bool}, default is C{False}.
    @ivar timezone_offset: The offset from I{UTC} for any C{datetime} objects
        being encoded. Default to C{None} means no offset.
    @type timezone_offset: C{datetime.timedelta} or C{int} or C{None}
    """

    def __init__(self, stream=None, context=None, strict=False,
                 timezone_offset=None):
        if not isinstance(stream, util.BufferedByteStream):
            stream = util.BufferedByteStream(stream)

        self.stream = stream
        self.context = context or self.buildContext()
        self.strict = strict
        self.timezone_offset = timezone_offset

        self._func_cache = {}

    def buildContext(self):
        """
        A context factory.
        """
        raise NotImplementedError

    def getTypeFunc(self, data):
        """
        Returns a callable based on C{data}. If no such callable can be found,
        the default must be to return C{None}.
        """
        raise NotImplementedError


class Decoder(_Codec):
    """
    Base AMF decoder.

    @ivar strict: Defines how strict the decoding should be. For the time
        being this relates to typed objects in the stream that do not have a
        registered alias. Introduced in 0.4.
    @type strict: C{bool}
    """

    def send(self, data):
        """
        Add data for the decoder to work on.
        """
        self.stream.append(data)

    def next(self):
        """
        Part of the iterator protocol.
        """
        try:
            return self.readElement()
        except pyamf.EOStream:
            # all data was successfully decoded from the stream
            raise StopIteration

    def readElement(self):
        """
        Reads an AMF3 element from the data stream.

        @raise DecodeError: The ActionScript type is unsupported.
        @raise EOStream: No more data left to decode.
        """
        pos = self.stream.tell()

        try:
            t = self.stream.read(1)
        except IOError:
            raise pyamf.EOStream

        try:
            func = self._func_cache[t]
        except KeyError:
            func = self.getTypeFunc(t)

            if not func:
                raise pyamf.DecodeError("Unsupported ActionScript type %s" % (
                    hex(ord(t)),))

            self._func_cache[t] = func

        try:
            return func()
        except IOError:
            self.stream.seek(pos)

            raise

    def __iter__(self):
        return self


class _CustomTypeFunc(object):
    """
    Support for custom type mappings when encoding.
    """

    def __init__(self, encoder, func):
        self.encoder = encoder
        self.func = func

    def __call__(self, data, **kwargs):
        ret = self.func(data, encoder=self.encoder)

        if ret is not None:
            self.encoder.writeElement(ret)


class Encoder(_Codec):
    """
    Base AMF encoder.
    """

    def __init__(self, *args, **kwargs):
        _Codec.__init__(self, *args, **kwargs)

        self.bucket = []

    def _write_type(self, obj, **kwargs):
        """
        Subclasses should override this and all write[type] functions
        """
        raise NotImplementedError

    writeNull = _write_type
    writeBytes = _write_type
    writeString = _write_type
    writeBoolean = _write_type
    writeNumber = _write_type
    writeList = _write_type
    writeUndefined = _write_type
    writeDate = _write_type
    writeXML = _write_type
    writeObject = _write_type

    def writeSequence(self, iterable):
        """
        Encodes an iterable. The default is to write If the iterable has an al
        """
        try:
            alias = self.context.getClassAlias(iterable.__class__)
        except (AttributeError, pyamf.UnknownClassAlias):
            self.writeList(iterable)

            return

        if alias.external:
            # a is a subclassed list with a registered alias - push to the
            # correct method
            self.writeObject(iterable)

            return

        self.writeList(iterable)

    def writeGenerator(self, gen):
        """
        Iterates over a generator object and encodes all that is returned.
        """
        n = getattr(gen, 'next')

        while True:
            try:
                self.writeElement(n())
            except StopIteration:
                break

    def getTypeFunc(self, data):
        """
        Returns a callable that will encode C{data} to C{self.stream}. If
        C{data} is unencodable, then C{None} is returned.
        """
        if data is None:
            return self.writeNull

        t = type(data)

        # try types that we know will work
        if t is str or issubclass(t, str):
            return self.writeBytes
        if t is unicode or issubclass(t, unicode):
            return self.writeString
        elif t is bool:
            return self.writeBoolean
        elif t is float:
            return self.writeNumber
        elif t in python.int_types:
            return self.writeNumber
        elif t in (list, tuple):
            return self.writeList
        elif isinstance(data, (list, tuple)):
            return self.writeSequence
        elif t is types.GeneratorType:
            return self.writeGenerator
        elif t is pyamf.UndefinedType:
            return self.writeUndefined
        elif t in (datetime.date, datetime.datetime, datetime.time):
            return self.writeDate
        elif xml.is_xml(data):
            return self.writeXML

        # check for any overridden types
        for type_, func in pyamf.TYPE_MAP.iteritems():
            try:
                if isinstance(data, type_):
                    return _CustomTypeFunc(self, func)
            except TypeError:
                if python.callable(type_) and type_(data):
                    return _CustomTypeFunc(self, func)

        # now try some types that won't encode
        if t in python.class_types:
            # can't encode classes
            return None
        elif isinstance(data, python.func_types):
            # can't encode code objects
            return None
        elif isinstance(t, types.ModuleType):
            # cannot encode module objects
            return None

        # well, we tried ..
        return self.writeObject

    def writeElement(self, data):
        """
        Encodes C{data} to AMF. If the data is not able to be matched to an AMF
        type, then L{pyamf.EncodeError} will be raised.
        """
        key = type(data)
        func = None

        try:
            func = self._func_cache[key]
        except KeyError:
            func = self.getTypeFunc(data)

            if func is None:
                raise pyamf.EncodeError('Unable to encode %r (type %r)' % (
                    data, key))

            self._func_cache[key] = func

        func(data)

    def send(self, element):
        self.bucket.append(element)

    def next(self):
        try:
            element = self.bucket.pop(0)
        except IndexError:
            raise StopIteration

        start_pos = self.stream.tell()

        self.writeElement(element)

        end_pos = self.stream.tell()

        self.stream.seek(start_pos)

        return self.stream.read(end_pos - start_pos)

    def __iter__(self):
        return self
