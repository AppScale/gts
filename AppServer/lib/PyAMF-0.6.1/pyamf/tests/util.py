# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Test utilities.

@since: 0.1.0
"""

import unittest
import copy

import pyamf
from pyamf import python


class ClassicSpam:
    def __readamf__(self, input):
        pass

    def __writeamf__(self, output):
        pass


class Spam(object):
    """
    A generic object to use for object encoding.
    """

    def __init__(self, d={}):
        self.__dict__.update(d)

    def __readamf__(self, input):
        pass

    def __writeamf__(self, output):
        pass


class EncoderMixIn(object):
    """
    A mixin class that provides an AMF* encoder and some helpful methods to do
    testing.
    """

    amf_type = None

    def setUp(self):
        self.encoder = pyamf.get_encoder(encoding=self.amf_type)
        self.buf = self.encoder.stream
        self.context = self.encoder.context

    def tearDown(self):
        pass

    def encode(self, *args):
        self.buf.seek(0, 0)
        self.buf.truncate()

        for arg in args:
            self.encoder.writeElement(arg)

        return self.buf.getvalue()

    def assertEncoded(self, arg, *args, **kwargs):
        if kwargs.get('clear', True):
            self.context.clear()

        assert_buffer(self, self.encode(arg), args)


class DecoderMixIn(object):
    """
    A mixin class that provides an AMF* decoder and some helpful methods to do
    testing.
    """

    amf_type = None

    def setUp(self):
        self.decoder = pyamf.get_decoder(encoding=self.amf_type)
        self.buf = self.decoder.stream
        self.context = self.decoder.context

    def tearDown(self):
        pass

    def decode(self, bytes, raw=False):
        if not isinstance(bytes, basestring):
            bytes = _join(bytes)

        self.buf.seek(0, 0)
        self.buf.truncate()

        self.buf.write(bytes)
        self.buf.seek(0, 0)

        ret = []

        while not self.buf.at_eof():
            ret.append(self.decoder.readElement())

        if raw:
            return ret

        if len(ret) == 1:
            return ret[0]

        return ret

    def assertDecoded(self, decoded, bytes, raw=False, clear=True):
        if clear:
            self.context.clear()

        ret = self.decode(bytes, raw)

        self.assertEqual(ret, decoded)
        self.assertEqual(self.buf.remaining(), 0)


class ClassCacheClearingTestCase(unittest.TestCase):
    def setUp(self):
        unittest.TestCase.setUp(self)

        self._class_cache = pyamf.CLASS_CACHE.copy()
        self._class_loaders = copy.copy(pyamf.CLASS_LOADERS)

    def tearDown(self):
        unittest.TestCase.tearDown(self)

        pyamf.CLASS_CACHE = self._class_cache
        pyamf.CLASS_LOADERS = self._class_loaders

    def assertBuffer(self, first, second, msg=None):
        assert_buffer(self, first, second, msg)

    def assertEncodes(self, obj, buffer, encoding=pyamf.AMF3):
        bytes = pyamf.encode(obj, encoding=encoding).getvalue()

        if isinstance(buffer, basestring):
            self.assertEqual(bytes, buffer)

            return

        self.assertBuffer(bytes, buffer)

    def assertDecodes(self, bytes, cb, encoding=pyamf.AMF3, raw=False):
        if not isinstance(bytes, basestring):
            bytes = _join(bytes)

        ret = list(pyamf.decode(bytes, encoding=encoding))

        if not raw and len(ret) == 1:
            ret = ret[0]

        if python.callable(cb):
            cb(ret)
        else:
            self.assertEqual(ret, cb)


def assert_buffer(testcase, val, s, msg=None):
    if not check_buffer(val, s):
        testcase.fail(msg or ('%r != %r' % (val, s)))


def check_buffer(buf, parts, inner=False):
    assert isinstance(parts, (tuple, list))

    parts = [p for p in parts]

    for part in parts:
        if inner is False:
            if isinstance(part, (tuple, list)):
                buf = check_buffer(buf, part, inner=True)
            else:
                if not buf.startswith(part):
                    return False

                buf = buf[len(part):]
        else:
            for k in parts[:]:
                for p in parts[:]:
                    if isinstance(p, (tuple, list)):
                        buf = check_buffer(buf, p, inner=True)
                    else:
                        if buf.startswith(p):
                            parts.remove(p)
                            buf = buf[len(p):]

            return buf

    return len(buf) == 0


def replace_dict(src, dest):
    seen = []

    for name in dest.copy().keys():
        seen.append(name)

        if name not in src:
            del dest[name]

            continue

        if dest[name] is not src[name]:
            dest[name] = src[name]

    for name in src.keys():
        if name in seen:
            continue

        dest[name] = src[name]

    assert src == dest


class NullFileDescriptor(object):
    """
    A file like object that no-ops when writing.
    """

    def write(self, *args, **kwargs):
        pass


def get_fqcn(klass):
    return '%s.%s' % (klass.__module__, klass.__name__)


def expectedFailureIfAppengine(func):
    try:
        from google import appengine
    except ImportError:
        return func
    else:
        import os

        if os.environ.get('SERVER_SOFTWARE', None) is None:
            return func

        return unittest.expectedFailure(func)


def _join(parts):
    ret = ''

    for p in parts:
        if not isinstance(p, basestring):
            ret += _join(p)

            continue

        ret += p

    return ret
