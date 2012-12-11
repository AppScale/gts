from webob import Request
from webob.acceptparse import Accept, MIMEAccept, NilAccept, NoAccept, accept_property, AcceptLanguage, AcceptCharset
from nose.tools import eq_, assert_raises

def test_parse_accept_badq():
    assert list(Accept.parse("value1; q=0.1.2")) == [('value1', 1)]

def test_init_accept_content_type():
    accept = Accept('text/html')
    assert accept._parsed == [('text/html', 1)]

def test_init_accept_accept_charset():
    accept = AcceptCharset('iso-8859-5, unicode-1-1;q=0.8')
    assert accept._parsed == [('iso-8859-5', 1),
                              ('unicode-1-1', 0.80000000000000004),
                              ('iso-8859-1', 1)]

def test_init_accept_accept_charset_with_iso_8859_1():
    accept = Accept('iso-8859-1')
    assert accept._parsed == [('iso-8859-1', 1)]

def test_init_accept_accept_charset_wildcard():
    accept = Accept('*')
    assert accept._parsed == [('*', 1)]

def test_init_accept_accept_language():
    accept = AcceptLanguage('da, en-gb;q=0.8, en;q=0.7')
    assert accept._parsed == [('da', 1),
                              ('en-gb', 0.80000000000000004),
                              ('en', 0.69999999999999996)]

def test_init_accept_invalid_value():
    accept = AcceptLanguage('da, q, en-gb;q=0.8')
    # The "q" value should not be there.
    assert accept._parsed == [('da', 1),
                              ('en-gb', 0.80000000000000004)]

def test_init_accept_invalid_q_value():
    accept = AcceptLanguage('da, en-gb;q=foo')
    # I can't get to cover line 40-41 (webob.acceptparse) as the regex
    # will prevent from hitting these lines (aconrad)
    assert accept._parsed == [('da', 1), ('en-gb', 1)]

def test_accept_repr():
    accept = Accept('text/html')
    assert repr(accept) == "<Accept('text/html')>"

def test_accept_str():
    accept = Accept('text/html')
    assert str(accept) == 'text/html'

def test_zero_quality():
    assert Accept('bar, *;q=0').best_match(['foo']) is None
    assert 'foo' not in Accept('*;q=0')
    assert Accept('foo, *;q=0').first_match(['bar', 'foo']) == 'foo'


def test_accept_str_with_q_not_1():
    value = 'text/html;q=0.5'
    accept = Accept(value)
    assert str(accept) == value

def test_accept_str_with_q_not_1_multiple():
    value = 'text/html;q=0.5, foo/bar'
    accept = Accept(value)
    assert str(accept) == value

def test_accept_add_other_accept():
    accept = Accept('text/html') + Accept('foo/bar')
    assert str(accept) == 'text/html, foo/bar'
    accept += Accept('bar/baz;q=0.5')
    assert str(accept) == 'text/html, foo/bar, bar/baz;q=0.5'

def test_accept_add_other_list_of_tuples():
    accept = Accept('text/html')
    accept += [('foo/bar', 1)]
    assert str(accept) == 'text/html, foo/bar'
    accept += [('bar/baz', 0.5)]
    assert str(accept) == 'text/html, foo/bar, bar/baz;q=0.5'
    accept += ['she/bangs', 'the/house']
    assert str(accept) == ('text/html, foo/bar, bar/baz;q=0.5, '
                           'she/bangs, the/house')

def test_accept_add_other_dict():
    accept = Accept('text/html')
    accept += {'foo/bar': 1}
    assert str(accept) == 'text/html, foo/bar'
    accept += {'bar/baz': 0.5}
    assert str(accept) == 'text/html, foo/bar, bar/baz;q=0.5'

def test_accept_add_other_empty_str():
    accept = Accept('text/html')
    accept += ''
    assert str(accept) == 'text/html'

def test_accept_with_no_value_add_other_str():
    accept = Accept('')
    accept += 'text/html'
    assert str(accept) == 'text/html'

def test_contains():
    accept = Accept('text/html')
    assert 'text/html' in accept

def test_contains_not():
    accept = Accept('text/html')
    assert not 'foo/bar' in accept

def test_quality():
    accept = Accept('text/html')
    assert accept.quality('text/html') == 1
    accept = Accept('text/html;q=0.5')
    assert accept.quality('text/html') == 0.5

def test_quality_not_found():
    accept = Accept('text/html')
    assert accept.quality('foo/bar') is None

def test_first_match():
    accept = Accept('text/html, foo/bar')
    assert accept.first_match(['text/html', 'foo/bar']) == 'text/html'
    assert accept.first_match(['foo/bar', 'text/html']) == 'foo/bar'
    assert accept.first_match(['xxx/xxx', 'text/html']) == 'text/html'
    assert accept.first_match(['xxx/xxx']) == 'xxx/xxx'
    assert accept.first_match([None, 'text/html']) is None
    assert accept.first_match(['text/html', None]) == 'text/html'
    assert accept.first_match(['foo/bar', None]) == 'foo/bar'
    assert_raises(ValueError, accept.first_match, [])

def test_best_match():
    accept = Accept('text/html, foo/bar')
    assert accept.best_match(['text/html', 'foo/bar']) == 'text/html'
    assert accept.best_match(['foo/bar', 'text/html']) == 'foo/bar'
    assert accept.best_match([('foo/bar', 0.5),
                              'text/html']) == 'text/html'
    assert accept.best_match([('foo/bar', 0.5),
                              ('text/html', 0.4)]) == 'foo/bar'
    assert_raises(ValueError, accept.best_match, ['text/*'])

def test_best_match_with_one_lower_q():
    accept = Accept('text/html, foo/bar;q=0.5')
    assert accept.best_match(['text/html', 'foo/bar']) == 'text/html'
    accept = Accept('text/html;q=0.5, foo/bar')
    assert accept.best_match(['text/html', 'foo/bar']) == 'foo/bar'

def test_best_matches():
    accept = Accept('text/html, foo/bar')
    assert accept.best_matches() == ['text/html', 'foo/bar']
    accept = Accept('text/html, foo/bar;q=0.5')
    assert accept.best_matches() == ['text/html', 'foo/bar']
    accept = Accept('text/html;q=0.5, foo/bar')
    assert accept.best_matches() == ['foo/bar', 'text/html']

def test_best_matches_with_fallback():
    accept = Accept('text/html, foo/bar')
    assert accept.best_matches('xxx/yyy') == ['text/html',
                                              'foo/bar',
                                              'xxx/yyy']
    accept = Accept('text/html;q=0.5, foo/bar')
    assert accept.best_matches('xxx/yyy') == ['foo/bar',
                                              'text/html',
                                              'xxx/yyy']
    assert accept.best_matches('foo/bar') == ['foo/bar']
    assert accept.best_matches('text/html') == ['foo/bar', 'text/html']

def test_accept_match():
    for mask in ['*', 'text/html', 'TEXT/HTML']:
        assert 'text/html' in Accept(mask)
    assert 'text/html' not in Accept('foo/bar')

def test_accept_match_lang():
    for mask, lang in [
        ('*', 'da'),
        ('da', 'DA'),
        ('en', 'en-gb'),
        ('en-gb', 'en-gb'),
        ('en-gb', 'en'),
        ('en-gb', 'en_GB'),
    ]:
        assert lang in AcceptLanguage(mask)
    for mask, lang in [
        ('en-gb', 'en-us'),
        ('en-gb', 'fr-fr'),
        ('en-gb', 'fr'),
        ('en', 'fr-fr'),
    ]:
        assert lang not in AcceptLanguage(mask)

# NilAccept tests

def test_nil():
    nilaccept = NilAccept()
    eq_(repr(nilaccept),
        "<NilAccept: <class 'webob.acceptparse.Accept'>>"
    )
    assert not nilaccept
    assert str(nilaccept) == ''
    assert nilaccept.quality('dummy') == 0
    assert nilaccept.best_matches() == []
    assert nilaccept.best_matches('foo') == ['foo']


def test_nil_add():
    nilaccept = NilAccept()
    accept = Accept('text/html')
    assert nilaccept + accept is accept
    new_accept = nilaccept + nilaccept
    assert isinstance(new_accept, accept.__class__)
    assert new_accept.header_value == ''
    new_accept = nilaccept + 'foo'
    assert isinstance(new_accept, accept.__class__)
    assert new_accept.header_value == 'foo'

def test_nil_radd():
    nilaccept = NilAccept()
    accept = Accept('text/html')
    assert isinstance('foo' + nilaccept, accept.__class__)
    assert ('foo' + nilaccept).header_value == 'foo'
    # How to test ``if isinstance(item, self.MasterClass): return item``
    # under NilAccept.__radd__ ??

def test_nil_radd_masterclass():
    # Is this "reaching into" __radd__ legit?
    nilaccept = NilAccept()
    accept = Accept('text/html')
    assert nilaccept.__radd__(accept) is accept

def test_nil_contains():
    nilaccept = NilAccept()
    assert 'anything' in nilaccept

def test_nil_first_match():
    nilaccept = NilAccept()
    # NilAccept.first_match always returns element 0 of the list
    assert nilaccept.first_match(['dummy', '']) == 'dummy'
    assert nilaccept.first_match(['', 'dummy']) == ''

def test_nil_best_match():
    nilaccept = NilAccept()
    assert nilaccept.best_match(['foo', 'bar']) == 'foo'
    assert nilaccept.best_match([('foo', 1), ('bar', 0.5)]) == 'foo'
    assert nilaccept.best_match([('foo', 0.5), ('bar', 1)]) == 'bar'
    assert nilaccept.best_match([('foo', 0.5), 'bar']) == 'bar'
    # default_match has no effect on NilAccept class
    assert nilaccept.best_match([('foo', 0.5), 'bar'],
                                default_match=True) == 'bar'
    assert nilaccept.best_match([('foo', 0.5), 'bar'],
                                default_match=False) == 'bar'


# NoAccept tests
def test_noaccept_contains():
    assert 'text/plain' not in NoAccept()


# MIMEAccept tests

def test_mime_init():
    mimeaccept = MIMEAccept('image/jpg')
    assert mimeaccept._parsed == [('image/jpg', 1)]
    mimeaccept = MIMEAccept('image/png, image/jpg;q=0.5')
    assert mimeaccept._parsed == [('image/png', 1), ('image/jpg', 0.5)]
    mimeaccept = MIMEAccept('image, image/jpg;q=0.5')
    assert mimeaccept._parsed == [('image/jpg', 0.5)]
    mimeaccept = MIMEAccept('*/*')
    assert mimeaccept._parsed == [('*/*', 1)]
    mimeaccept = MIMEAccept('*/png')
    assert mimeaccept._parsed == []
    mimeaccept = MIMEAccept('image/*')
    assert mimeaccept._parsed == [('image/*', 1)]

def test_accept_html():
    mimeaccept = MIMEAccept('image/jpg')
    assert not mimeaccept.accept_html()
    mimeaccept = MIMEAccept('image/jpg, text/html')
    assert mimeaccept.accept_html()

def test_match():
    mimeaccept = MIMEAccept('image/jpg')
    assert mimeaccept._match('image/jpg', 'image/jpg')
    assert mimeaccept._match('image/*', 'image/jpg')
    assert mimeaccept._match('*/*', 'image/jpg')
    assert not mimeaccept._match('text/html', 'image/jpg')
    assert_raises(ValueError, mimeaccept._match, 'image/jpg', '*/*')

def test_accept_json():
    mimeaccept = MIMEAccept('text/html, *; q=.2, */*; q=.2')
    assert mimeaccept.best_match(['application/json']) == 'application/json'

# property tests

def test_accept_property_fget():
    desc = accept_property('Accept-Charset', '14.2')
    req = Request.blank('/', environ={'envkey': 'envval'})
    desc.fset(req, 'val')
    eq_(desc.fget(req).header_value, 'val')

def test_accept_property_fget_nil():
    desc = accept_property('Accept-Charset', '14.2')
    req = Request.blank('/')
    eq_(type(desc.fget(req)), NilAccept)

def test_accept_property_fset():
    desc = accept_property('Accept-Charset', '14.2')
    req = Request.blank('/', environ={'envkey': 'envval'})
    desc.fset(req, 'baz')
    eq_(desc.fget(req).header_value, 'baz')

def test_accept_property_fset_acceptclass():
    req = Request.blank('/', environ={'envkey': 'envval'})
    req.accept_charset = ['utf-8', 'latin-11']
    eq_(req.accept_charset.header_value, 'utf-8, latin-11, iso-8859-1')

def test_accept_property_fdel():
    desc = accept_property('Accept-Charset', '14.2')
    req = Request.blank('/', environ={'envkey': 'envval'})
    desc.fset(req, 'val')
    assert desc.fget(req).header_value == 'val'
    desc.fdel(req)
    eq_(type(desc.fget(req)), NilAccept)
