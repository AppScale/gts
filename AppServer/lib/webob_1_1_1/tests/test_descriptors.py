# -*- coding: utf-8 -*-

from datetime import tzinfo
from datetime import timedelta

from nose.tools import eq_
from nose.tools import ok_
from nose.tools import assert_raises

from webob import Request


class GMT(tzinfo):
    """UTC"""
    ZERO = timedelta(0)
    def utcoffset(self, dt):
        return self.ZERO

    def tzname(self, dt):
        return "UTC"

    def dst(self, dt):
        return self.ZERO


class MockDescriptor:
    _val = 'avalue'
    def __get__(self, obj, type=None):
        return self._val
    def __set__(self, obj, val):
        self._val = val
    def __delete__(self, obj):
        self._val = None


def test_environ_getter_docstring():
    from webob.descriptors import environ_getter
    desc = environ_getter('akey')
    eq_(desc.__doc__, "Gets and sets the ``akey`` key in the environment.")

def test_environ_getter_nodefault_keyerror():
    from webob.descriptors import environ_getter
    req = Request.blank('/')
    desc = environ_getter('akey')
    assert_raises(KeyError, desc.fget, req)

def test_environ_getter_nodefault_fget():
    from webob.descriptors import environ_getter
    req = Request.blank('/')
    desc = environ_getter('akey')
    desc.fset(req, 'bar')
    eq_(req.environ['akey'], 'bar')

def test_environ_getter_nodefault_fdel():
    from webob.descriptors import environ_getter
    desc = environ_getter('akey')
    eq_(desc.fdel, None)

def test_environ_getter_default_fget():
    from webob.descriptors import environ_getter
    req = Request.blank('/')
    desc = environ_getter('akey', default='the_default')
    eq_(desc.fget(req), 'the_default')

def test_environ_getter_default_fset():
    from webob.descriptors import environ_getter
    req = Request.blank('/')
    desc = environ_getter('akey', default='the_default')
    desc.fset(req, 'bar')
    eq_(req.environ['akey'], 'bar')

def test_environ_getter_default_fset_none():
    from webob.descriptors import environ_getter
    req = Request.blank('/')
    desc = environ_getter('akey', default='the_default')
    desc.fset(req, 'baz')
    desc.fset(req, None)
    ok_('akey' not in req.environ)

def test_environ_getter_default_fdel():
    from webob.descriptors import environ_getter
    req = Request.blank('/')
    desc = environ_getter('akey', default='the_default')
    desc.fset(req, 'baz')
    assert 'akey' in req.environ
    desc.fdel(req)
    ok_('akey' not in req.environ)

def test_environ_getter_rfc_section():
    from webob.descriptors import environ_getter
    desc = environ_getter('HTTP_X_AKEY', rfc_section='14.3')
    eq_(desc.__doc__, "Gets and sets the ``X-Akey`` header "
        "(`HTTP spec section 14.3 "
        "<http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.3>`_)."
    )


def test_upath_property_fget():
    from webob.descriptors import upath_property
    req = Request.blank('/')
    desc = upath_property('akey')
    eq_(desc.fget(req), '')

def test_upath_property_fset():
    from webob.descriptors import upath_property
    req = Request.blank('/')
    desc = upath_property('akey')
    desc.fset(req, 'avalue')
    eq_(desc.fget(req), 'avalue')

def test_header_getter_doc():
    from webob.descriptors import header_getter
    desc = header_getter('X-Header', '14.3')
    assert 'http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.3' in desc.__doc__
    assert '``X-Header`` header' in desc.__doc__

def test_header_getter_fget():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    eq_(desc.fget(resp), None)

def test_header_getter_fset():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    desc.fset(resp, 'avalue')
    eq_(desc.fget(resp), 'avalue')

def test_header_getter_fset_none():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    desc.fset(resp, 'avalue')
    desc.fset(resp, None)
    eq_(desc.fget(resp), None)

def test_header_getter_fdel():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    desc.fset(resp, 'avalue2')
    desc.fdel(resp)
    eq_(desc.fget(resp), None)

def test_header_getter_unicode_fget_none():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    eq_(desc.fget(resp), None)

def test_header_getter_unicode_fget():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    desc.fset(resp, u'avalue')
    eq_(desc.fget(resp), u'avalue')

def test_header_getter_unicode_fset_none():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    desc.fset(resp, None)
    eq_(desc.fget(resp), None)

def test_header_getter_unicode_fset():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    desc.fset(resp, u'avalue2')
    eq_(desc.fget(resp), u'avalue2')

def test_header_getter_unicode_fdel():
    from webob.descriptors import header_getter
    from webob import Response
    resp = Response('aresp')
    desc = header_getter('AHEADER', '14.3')
    desc.fset(resp, u'avalue3')
    desc.fdel(resp)
    eq_(desc.fget(resp), None)

def test_converter_not_prop():
    from webob.descriptors import converter
    from webob.descriptors import parse_int_safe
    from webob.descriptors import serialize_int
    assert_raises(AssertionError,converter,
        ('CONTENT_LENGTH', None, '14.13'),
        parse_int_safe, serialize_int, 'int')

def test_converter_with_name_docstring():
    from webob.descriptors import converter
    from webob.descriptors import environ_getter
    from webob.descriptors import parse_int_safe
    from webob.descriptors import serialize_int
    desc = converter(
        environ_getter('CONTENT_LENGTH', '666', '14.13'),
        parse_int_safe, serialize_int, 'int')

    assert 'http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.13' in desc.__doc__
    assert '``Content-Length`` header' in desc.__doc__

def test_converter_with_name_fget():
    from webob.descriptors import converter
    from webob.descriptors import environ_getter
    from webob.descriptors import parse_int_safe
    from webob.descriptors import serialize_int
    req = Request.blank('/')
    desc = converter(
        environ_getter('CONTENT_LENGTH', '666', '14.13'),
        parse_int_safe, serialize_int, 'int')
    eq_(desc.fget(req), 666)

def test_converter_with_name_fset():
    from webob.descriptors import converter
    from webob.descriptors import environ_getter
    from webob.descriptors import parse_int_safe
    from webob.descriptors import serialize_int
    req = Request.blank('/')
    desc = converter(
        environ_getter('CONTENT_LENGTH', '666', '14.13'),
        parse_int_safe, serialize_int, 'int')
    desc.fset(req, '999')
    eq_(desc.fget(req), 999)

def test_converter_without_name_fget():
    from webob.descriptors import converter
    from webob.descriptors import environ_getter
    from webob.descriptors import parse_int_safe
    from webob.descriptors import serialize_int
    req = Request.blank('/')
    desc = converter(
        environ_getter('CONTENT_LENGTH', '666', '14.13'),
        parse_int_safe, serialize_int)
    eq_(desc.fget(req), 666)

def test_converter_without_name_fset():
    from webob.descriptors import converter
    from webob.descriptors import environ_getter
    from webob.descriptors import parse_int_safe
    from webob.descriptors import serialize_int
    req = Request.blank('/')
    desc = converter(
        environ_getter('CONTENT_LENGTH', '666', '14.13'),
        parse_int_safe, serialize_int)
    desc.fset(req, '999')
    eq_(desc.fget(req), 999)

def test_converter_none_for_wrong_type():
    from webob.descriptors import converter
    from webob.descriptors import environ_getter
    from webob.descriptors import parse_int_safe
    from webob.descriptors import serialize_int
    req = Request.blank('/')
    desc = converter(
        ## XXX: Should this fail  if the type is wrong?
        environ_getter('CONTENT_LENGTH', 'sixsixsix', '14.13'),
        parse_int_safe, serialize_int, 'int')
    eq_(desc.fget(req), None)

def test_converter_delete():
    from webob.descriptors import converter
    from webob.descriptors import environ_getter
    from webob.descriptors import parse_int_safe
    from webob.descriptors import serialize_int
    req = Request.blank('/')
    desc = converter(
        ## XXX: Should this fail  if the type is wrong?
        environ_getter('CONTENT_LENGTH', '666', '14.13'),
        parse_int_safe, serialize_int, 'int')
    assert_raises(KeyError, desc.fdel, req)

def test_list_header():
    from webob.descriptors import list_header
    desc = list_header('CONTENT_LENGTH', '14.13')
    eq_(type(desc), property)

def test_parse_list_single():
    from webob.descriptors import parse_list
    result = parse_list('avalue')
    eq_(result, ('avalue',))

def test_parse_list_multiple():
    from webob.descriptors import parse_list
    result = parse_list('avalue,avalue2')
    eq_(result, ('avalue', 'avalue2'))

def test_parse_list_none():
    from webob.descriptors import parse_list
    result = parse_list(None)
    eq_(result, None)

def test_parse_list_unicode_single():
    from webob.descriptors import parse_list
    result = parse_list(u'avalue')
    eq_(result, ('avalue',))

def test_parse_list_unicode_multiple():
    from webob.descriptors import parse_list
    result = parse_list(u'avalue,avalue2')
    eq_(result, ('avalue', 'avalue2'))

def test_serialize_list():
    from webob.descriptors import serialize_list
    result = serialize_list(('avalue', 'avalue2'))
    eq_(result, 'avalue, avalue2')

def test_serialize_list_string():
    from webob.descriptors import serialize_list
    result = serialize_list('avalue')
    eq_(result, 'avalue')

def test_serialize_list_unicode():
    from webob.descriptors import serialize_list
    result = serialize_list(u'avalue')
    eq_(result, u'avalue')

def test_converter_date():
    import datetime
    from webob.descriptors import converter_date
    from webob.descriptors import environ_getter
    req = Request.blank('/')
    UTC = GMT()
    desc = converter_date(environ_getter(
        "HTTP_DATE", "Tue, 15 Nov 1994 08:12:31 GMT", "14.8"))
    eq_(desc.fget(req),
        datetime.datetime(1994, 11, 15, 8, 12, 31, tzinfo=UTC))

def test_converter_date_docstring():
    from webob.descriptors import converter_date
    from webob.descriptors import environ_getter
    desc = converter_date(environ_getter(
        "HTTP_DATE", "Tue, 15 Nov 1994 08:12:31 GMT", "14.8"))
    assert 'http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.8' in desc.__doc__
    assert '``Date`` header' in desc.__doc__


def test_date_header_fget_none():
    from webob import Response
    from webob.descriptors import date_header
    resp = Response('aresponse')
    desc = date_header('HTTP_DATE', "14.8")
    eq_(desc.fget(resp), None)

def test_date_header_fset_fget():
    import datetime
    from webob import Response
    from webob.descriptors import date_header
    resp = Response('aresponse')
    UTC = GMT()
    desc = date_header('HTTP_DATE', "14.8")
    desc.fset(resp, "Tue, 15 Nov 1994 08:12:31 GMT")
    eq_(desc.fget(resp), datetime.datetime(1994, 11, 15, 8, 12, 31, tzinfo=UTC))

def test_date_header_fdel():
    from webob import Response
    from webob.descriptors import date_header
    resp = Response('aresponse')
    desc = date_header('HTTP_DATE', "14.8")
    desc.fset(resp, "Tue, 15 Nov 1994 08:12:31 GMT")
    desc.fdel(resp)
    eq_(desc.fget(resp), None)

def test_deprecated_property():
    req = Request.blank('/')
    assert_raises(DeprecationWarning, getattr, req, 'postvars')
    assert_raises(DeprecationWarning, setattr, req, 'postvars', {})
    assert_raises(DeprecationWarning, delattr, req, 'postvars')
    eq_(Request.postvars.__repr__(), "<Deprecated attribute postvars>")

def test_parse_etag_response():
    from webob.descriptors import parse_etag_response
    etresp = parse_etag_response("etag")
    eq_(etresp, "etag")

def test_parse_etag_response_quoted():
    from webob.descriptors import parse_etag_response
    etresp = parse_etag_response('"etag"')
    eq_(etresp, "etag")

def test_parse_etag_response_is_none():
    from webob.descriptors import parse_etag_response
    etresp = parse_etag_response(None)
    eq_(etresp, None)

def test_serialize_etag_response():
    from webob.descriptors import serialize_etag_response
    etresp = serialize_etag_response("etag")
    eq_(etresp, '"etag"')

def test_parse_if_range_is_None():
    from webob.descriptors import parse_if_range
    from webob.descriptors import NoIfRange
    eq_(NoIfRange, parse_if_range(None))

def test_parse_if_range_date_ifr():
    from webob.descriptors import parse_if_range
    from webob.descriptors import IfRange
    ifr = parse_if_range("2011-03-15 01:24:43.272409")
    eq_(type(ifr), IfRange)

def test_parse_if_range_date_etagmatcher():
    from webob.descriptors import parse_if_range
    from webob.etag import ETagMatcher
    ifr = parse_if_range("2011-03-15 01:24:43.272409")
    eq_(type(ifr.etag), ETagMatcher)

def test_serialize_if_range_string():
    from webob.descriptors import serialize_if_range
    val = serialize_if_range("avalue")
    eq_(val, "avalue")

def test_serialize_if_range_unicode():
    from webob.descriptors import serialize_if_range
    val = serialize_if_range(u"avalue")
    eq_(val, u"avalue")

def test_serialize_if_range_datetime():
    import datetime
    from webob.descriptors import serialize_if_range
    UTC = GMT()
    val = serialize_if_range(datetime.datetime(1994, 11, 15, 8, 12, 31, tzinfo=UTC))
    eq_(val, "Tue, 15 Nov 1994 08:12:31 GMT")

def test_serialize_if_range_other():
    from webob.descriptors import serialize_if_range
    val = serialize_if_range(123456)
    eq_(val, '123456')

def test_parse_range_none():
    from webob.descriptors import parse_range
    val = parse_range(None)
    eq_(val, None)

def test_parse_range_type():
    from webob.byterange import Range
    from webob.descriptors import parse_range
    val = parse_range("bytes=1-500")
    eq_(type(val), type(Range.parse("bytes=1-500")))

def test_parse_range_values():
    from webob.byterange import Range
    from webob.descriptors import parse_range
    val = parse_range("bytes=1-500")
    eq_(val.ranges, Range.parse("bytes=1-500").ranges)

def test_serialize_range_none():
    from webob.descriptors import serialize_range
    val = serialize_range(None)
    eq_(val, None)

def test_serialize_range():
    from webob.descriptors import serialize_range
    val = serialize_range((1,500))
    eq_(val, 'bytes=1-499')

def test_serialize_invalid_len():
    from webob.descriptors import serialize_range
    assert_raises(ValueError, serialize_range, (1,))

def test_parse_int_none():
    from webob.descriptors import parse_int
    val = parse_int(None)
    eq_(val, None)

def test_parse_int_emptystr():
    from webob.descriptors import parse_int
    val = parse_int('')
    eq_(val, None)

def test_parse_int():
    from webob.descriptors import parse_int
    val = parse_int('123')
    eq_(val, 123)

def test_parse_int_invalid():
    from webob.descriptors import parse_int
    assert_raises(ValueError, parse_int, 'abc')

def test_parse_int_safe_none():
    from webob.descriptors import parse_int_safe
    eq_(parse_int_safe(None), None)

def test_parse_int_safe_emptystr():
    from webob.descriptors import parse_int_safe
    eq_(parse_int_safe(''), None)

def test_parse_int_safe():
    from webob.descriptors import parse_int_safe
    eq_(parse_int_safe('123'), 123)

def test_parse_int_safe_invalid():
    from webob.descriptors import parse_int_safe
    eq_(parse_int_safe('abc'), None)

def test_serialize_int():
    from webob.descriptors import serialize_int
    assert serialize_int is str

def test_parse_content_range_none():
    from webob.descriptors import parse_content_range
    eq_(parse_content_range(None), None)

def test_parse_content_range_emptystr():
    from webob.descriptors import parse_content_range
    eq_(parse_content_range(' '), None)

def test_parse_content_range_length():
    from webob.byterange import ContentRange
    from webob.descriptors import parse_content_range
    val = parse_content_range("bytes 0-499/1234")
    eq_(val.length, ContentRange.parse("bytes 0-499/1234").length)

def test_parse_content_range_start():
    from webob.byterange import ContentRange
    from webob.descriptors import parse_content_range
    val = parse_content_range("bytes 0-499/1234")
    eq_(val.start, ContentRange.parse("bytes 0-499/1234").start)

def test_parse_content_range_stop():
    from webob.byterange import ContentRange
    from webob.descriptors import parse_content_range
    val = parse_content_range("bytes 0-499/1234")
    eq_(val.stop, ContentRange.parse("bytes 0-499/1234").stop)

def test_serialize_content_range_none():
    from webob.descriptors import serialize_content_range
    eq_(serialize_content_range(None), 'None') ### XXX: Seems wrong

def test_serialize_content_range_emptystr():
    from webob.descriptors import serialize_content_range
    eq_(serialize_content_range(''), None)

def test_serialize_content_range_invalid():
    from webob.descriptors import serialize_content_range
    assert_raises(ValueError, serialize_content_range, (1,))

def test_serialize_content_range_asterisk():
    from webob.descriptors import serialize_content_range
    eq_(serialize_content_range((0, 500)), 'bytes 0-499/*')

def test_serialize_content_range_defined():
    from webob.descriptors import serialize_content_range
    eq_(serialize_content_range((0, 500, 1234)), 'bytes 0-499/1234')

def test_parse_auth_params_leading_capital_letter():
    from webob.descriptors import parse_auth_params
    val = parse_auth_params('Basic Realm=WebOb')
    eq_(val, {'ealm': 'WebOb'})

def test_parse_auth_params_trailing_capital_letter():
    from webob.descriptors import parse_auth_params
    val = parse_auth_params('Basic realM=WebOb')
    eq_(val, {})

def test_parse_auth_params_doublequotes():
    from webob.descriptors import parse_auth_params
    val = parse_auth_params('Basic realm="Web Object"')
    eq_(val, {'realm': 'Web Object'})

def test_parse_auth_params_multiple_values():
    from webob.descriptors import parse_auth_params
    val = parse_auth_params("foo='blah &&234', qop=foo, nonce='qwerty1234'")
    eq_(val, {'nonce': "'qwerty1234'", 'foo': "'blah &&234'", 'qop': 'foo'})

def test_parse_auth_params_truncate_on_comma():
    from webob.descriptors import parse_auth_params
    val = parse_auth_params("Basic realm=WebOb,this_will_truncate")
    eq_(val, {'realm': 'WebOb'})

def test_parse_auth_params_emptystr():
    from webob.descriptors import parse_auth_params
    eq_(parse_auth_params(''), {})

def test_parse_auth_none():
    from webob.descriptors import parse_auth
    eq_(parse_auth(None), None)

def test_parse_auth_emptystr():
    from webob.descriptors import parse_auth
    assert_raises(ValueError, parse_auth, '')

def test_parse_auth_basic():
    from webob.descriptors import parse_auth
    eq_(parse_auth("Basic realm=WebOb"), ('Basic', 'realm=WebOb'))

def test_parse_auth_basic_quoted():
    from webob.descriptors import parse_auth
    eq_(parse_auth('Basic realm="Web Ob"'), ('Basic', {'realm': 'Web Ob'}))

def test_parse_auth_basic_quoted_multiple_unknown():
    from webob.descriptors import parse_auth
    eq_(parse_auth("foo='blah &&234', qop=foo, nonce='qwerty1234'"),
        ("foo='blah", "&&234', qop=foo, nonce='qwerty1234'"))

def test_parse_auth_basic_quoted_known_multiple():
    from webob.descriptors import parse_auth
    eq_(parse_auth("Basic realm='blah &&234', qop=foo, nonce='qwerty1234'"),
        ('Basic', "realm='blah &&234', qop=foo, nonce='qwerty1234'"))

def test_serialize_auth_none():
    from webob.descriptors import serialize_auth
    eq_(serialize_auth(None), None)

def test_serialize_auth_emptystr():
    from webob.descriptors import serialize_auth
    eq_(serialize_auth(''), '')

def test_serialize_auth_basic_quoted():
    from webob.descriptors import serialize_auth
    val = serialize_auth(('Basic', 'realm="WebOb"'))
    eq_(val, 'Basic realm="WebOb"')

def test_serialize_auth_digest_multiple():
    from webob.descriptors import serialize_auth
    val = serialize_auth(('Digest', 'realm="WebOb", nonce=abcde12345, qop=foo'))
    flags = val[len('Digest'):]
    result = sorted([ x.strip() for x in flags.split(',') ])
    eq_(result, ['nonce=abcde12345', 'qop=foo', 'realm="WebOb"'])

def test_serialize_auth_digest_tuple():
    from webob.descriptors import serialize_auth
    val = serialize_auth(('Digest', {'realm':'"WebOb"', 'nonce':'abcde12345', 'qop':'foo'}))
    flags = val[len('Digest'):]
    result = sorted([ x.strip() for x in flags.split(',') ])
    eq_(result, ['nonce="abcde12345"', 'qop="foo"', 'realm=""WebOb""'])
