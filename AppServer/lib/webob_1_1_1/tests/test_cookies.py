# -*- coding: utf-8 -*-
from datetime import timedelta
from webob import cookies
from nose.tools import eq_

def test_cookie_empty():
    c = cookies.Cookie() # empty cookie
    eq_(repr(c), '<Cookie: []>')

def test_cookie_one_value():
    c = cookies.Cookie('dismiss-top=6')
    eq_(repr(c), "<Cookie: [<Morsel: dismiss-top='6'>]>")

def test_cookie_one_value_with_trailing_semi():
    c = cookies.Cookie('dismiss-top=6;')
    eq_(repr(c), "<Cookie: [<Morsel: dismiss-top='6'>]>")

def test_cookie_complex():
    c = cookies.Cookie('dismiss-top=6; CP=null*, '\
                       'PHPSESSID=0a539d42abc001cdc762809248d4beed, a="42,"')
    c_dict = dict((k,v.value) for k,v in c.items())
    eq_(c_dict, {'a': '42,',
        'CP': 'null*',
        'PHPSESSID': '0a539d42abc001cdc762809248d4beed',
        'dismiss-top': '6'
    })

def test_cookie_complex_serialize():
    c = cookies.Cookie('dismiss-top=6; CP=null*, '\
                       'PHPSESSID=0a539d42abc001cdc762809248d4beed, a="42,"')
    eq_(c.serialize(),
        'CP=null*; PHPSESSID=0a539d42abc001cdc762809248d4beed; a="42\\054"; '
        'dismiss-top=6')

def test_cookie_load_multiple():
    c = cookies.Cookie('a=1; Secure=true')
    eq_(repr(c), "<Cookie: [<Morsel: a='1'>]>")
    eq_(c['a']['secure'], 'true')

def test_cookie_secure():
    c = cookies.Cookie()
    c['foo'] = 'bar'
    c['foo'].secure = True
    eq_(c.serialize(), 'foo=bar; secure')

def test_cookie_httponly():
    c = cookies.Cookie()
    c['foo'] = 'bar'
    c['foo'].httponly = True
    eq_(c.serialize(), 'foo=bar; HttpOnly')

def test_cookie_reserved_keys():
    c = cookies.Cookie('dismiss-top=6; CP=null*; $version=42; a=42')
    assert '$version' not in c
    c = cookies.Cookie('$reserved=42; a=$42')
    eq_(c.keys(), ['a'])

def test_serialize_cookie_date():
    """
        Testing webob.cookies.serialize_cookie_date.
        Missing scenarios:
            * input value is an str, should be returned verbatim
            * input value is an int, should be converted to timedelta and we
              should continue the rest of the process
    """
    eq_(cookies.serialize_cookie_date('Tue, 04-Jan-2011 13:43:50 GMT'),
        'Tue, 04-Jan-2011 13:43:50 GMT')
    eq_(cookies.serialize_cookie_date(None), None)
    cdate_delta = cookies.serialize_cookie_date(timedelta(seconds=10))
    cdate_int = cookies.serialize_cookie_date(10)
    eq_(cdate_delta, cdate_int)

def test_ch_unquote():
    eq_(cookies._unquote(u'"hello world'), u'"hello world')
    eq_(cookies._unquote(u'hello world'), u'hello world')
    for unq, q in [
        ('hello world', '"hello world"'),
        # quotation mark is escaped w/ backslash
        ('"', r'"\""'),
        # misc byte escaped as octal
        ('\xff', r'"\377"'),
        # combination
        ('a"\xff', r'"a\"\377"'),
    ]:
        eq_(cookies._unquote(q), unq)
        eq_(cookies._quote(unq), q)

def test_cookie_setitem_needs_quoting():
    c = cookies.Cookie()
    c['La Pe\xc3\xb1a'] = '1'
    eq_(len(c), 0)

def test_morsel_serialize_with_expires():
    morsel = cookies.Morsel('bleh', 'blah')
    morsel.expires = 'Tue, 04-Jan-2011 13:43:50 GMT'
    result = morsel.serialize()
    eq_(result, 'bleh=blah; expires=Tue, 04-Jan-2011 13:43:50 GMT')

def test_serialize_max_age_timedelta():
    import datetime
    val = datetime.timedelta(86400)
    result = cookies.serialize_max_age(val)
    eq_(result, '7464960000')

def test_serialize_max_age_int():
    val = 86400
    result = cookies.serialize_max_age(val)
    eq_(result, '86400')

def test_serialize_max_age_str():
    val = '86400'
    result = cookies.serialize_max_age(val)
    eq_(result, '86400')

def test_escape_comma():
    c = cookies.Cookie()
    c['x'] = '";,"'
    eq_(c.serialize(True), r'x="\"\073\054\""')

def test_parse_qmark_in_val():
    v = r'x="\"\073\054\""; expires=Sun, 12-Jun-2011 23:16:01 GMT'
    c = cookies.Cookie(v)
    eq_(c['x'].value, r'";,"')

def test_parse_expires_no_quoting():
    v = r'x="\"\073\054\""; expires=Sun, 12-Jun-2011 23:16:01 GMT'
    c = cookies.Cookie(v)
    eq_(c['x'].expires, 'Sun, 12-Jun-2011 23:16:01 GMT')
