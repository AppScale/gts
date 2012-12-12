# -*- coding: utf-8 -*-
from webob import headers
from nose.tools import ok_, assert_raises, eq_

class TestError(Exception):
    pass

def test_ResponseHeaders_delitem_notpresent():
    """Deleting a missing key from ResponseHeaders should raise a KeyError"""
    d = headers.ResponseHeaders()
    assert_raises(KeyError, d.__delitem__, 'b')

def test_ResponseHeaders_delitem_present():
    """
    Deleting a present key should not raise an error at all
    """
    d = headers.ResponseHeaders(a=1)
    del d['a']
    ok_('a' not in d)

def test_ResponseHeaders_setdefault():
    """Testing set_default for ResponseHeaders"""
    d = headers.ResponseHeaders(a=1)
    res = d.setdefault('b', 1)
    assert res == d['b'] == 1
    res = d.setdefault('b', 10)
    assert res == d['b'] == 1
    res = d.setdefault('B', 10)
    assert res == d['b'] == d['B'] == 1

def test_ResponseHeader_pop():
    """Testing if pop return TypeError when more than len(*args)>1 plus other
    assorted tests"""
    d = headers.ResponseHeaders(a=1, b=2, c=3, d=4)
    assert_raises(TypeError, d.pop, 'a', 'z', 'y')
    eq_(d.pop('a'), 1)
    ok_('a' not in d)
    eq_(d.pop('B'), 2)
    ok_('b' not in d)
    eq_(d.pop('c', 'u'), 3)
    ok_('c' not in d)
    eq_(d.pop('e', 'u'), 'u')
    ok_('e' not in d)
    assert_raises(KeyError, d.pop, 'z')

def test_ResponseHeaders_getitem_miss():
    d = headers.ResponseHeaders()
    assert_raises(KeyError, d.__getitem__, 'a')

def test_ResponseHeaders_getall():
    d = headers.ResponseHeaders()
    d.add('a', 1)
    d.add('a', 2)
    result = d.getall('a')
    eq_(result, [1,2])

def test_ResponseHeaders_mixed():
    d = headers.ResponseHeaders()
    d.add('a', 1)
    d.add('a', 2)
    d['b'] = 1
    result = d.mixed()
    eq_(result, {'a':[1,2], 'b':1})

def test_ResponseHeaders_setitem_scalar_replaces_seq(): 
    d = headers.ResponseHeaders()
    d.add('a', 2)
    d['a'] = 1
    result = d.getall('a')
    eq_(result, [1])

def test_ResponseHeaders_contains():
    d = headers.ResponseHeaders()
    d['a'] = 1
    ok_('a' in d)
    ok_(not 'b' in d)

def test_EnvironHeaders_delitem():
    d = headers.EnvironHeaders({'CONTENT_LENGTH': '10'})
    del d['CONTENT-LENGTH']
    assert not d
    assert_raises(KeyError, d.__delitem__, 'CONTENT-LENGTH')

def test_EnvironHeaders_getitem():
    d = headers.EnvironHeaders({'CONTENT_LENGTH': '10'})
    eq_(d['CONTENT-LENGTH'], '10')

def test_EnvironHeaders_setitem():
    d = headers.EnvironHeaders({})
    d['abc'] = '10'
    eq_(d['abc'], '10')

def test_EnvironHeaders_contains():
    d = headers.EnvironHeaders({})
    d['a'] = '10'
    ok_('a' in d)
    ok_(not 'b' in d)

def test__trans_key_not_basestring():
    result = headers._trans_key(None)
    eq_(result, None)

def test__trans_key_not_a_header():
    result = headers._trans_key('')
    eq_(result, None)

def test__trans_key_key2header():
    result = headers._trans_key('CONTENT_TYPE')
    eq_(result, 'Content-Type')

def test__trans_key_httpheader():
    result = headers._trans_key('HTTP_FOO_BAR')
    eq_(result, 'Foo-Bar')
