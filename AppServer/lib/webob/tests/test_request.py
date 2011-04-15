from paste.fixture import *
from webob import Request
from py.test import raises

def simpleapp(environ, start_response):
    status = '200 OK'
    response_headers = [('Content-type','text/plain')]
    start_response(status, response_headers)
    request = Request(environ)
    request.remote_user = 'bob'
    return [
        'Hello world!\n',
        'The get is %r' % request.GET,
        ' and Val is %s\n' % request.GET.get('name'),
        'The languages are: %s\n' % request.accept_language.best_matches('en-US'),
        'The accepttypes is: %s\n' % request.accept.best_match(['text/html', 'application/xml']),
        'post is %r\n' % request.POST,
        'params is %r\n' % request.params,
        'cookies is %r\n' % request.cookies,
        'body: %r\n' % request.body,
        'method: %s\n' % request.method,
        'remote_user: %r\n' % request.environ['REMOTE_USER'],
        'host_url: %r; application_url: %r; path_url: %r; url: %r\n' % (request.host_url, request.application_url, request.path_url, request.url),
        'urlvars: %r\n' % request.urlvars,
        'urlargs: %r\n' % (request.urlargs, ),
        'is_xhr: %r\n' % request.is_xhr,
        'if_modified_since: %r\n' % request.if_modified_since,
        'user_agent: %r\n' % request.user_agent,
        'if_none_match: %r\n' % request.if_none_match,
        ]

def test_gets():
    app = TestApp(simpleapp)
    res = app.get('/')
    print res
    assert 'Hello' in res
    assert "get is MultiDict([])" in res
    assert "post is <NoVars: Not a POST request>" in res
    
    res = app.get('/?name=george')
    res.mustcontain("get is MultiDict([('name', 'george')])")
    res.mustcontain("Val is george")

def test_language_parsing():
    app = TestApp(simpleapp)
    res = app.get('/')
    assert "The languages are: ['en-US']" in res
    
    res = app.get('/', headers={'Accept-Language':'da, en-gb;q=0.8, en;q=0.7'})
    assert "languages are: ['da', 'en-gb', 'en', 'en-US']" in res

    res = app.get('/', headers={'Accept-Language':'en-gb;q=0.8, da, en;q=0.7'})
    assert "languages are: ['da', 'en-gb', 'en', 'en-US']" in res

def test_mime_parsing():
    app = TestApp(simpleapp)
    res = app.get('/', headers={'Accept':'text/html'})
    assert "accepttypes is: text/html" in res
    
    res = app.get('/', headers={'Accept':'application/xml'})
    assert "accepttypes is: application/xml" in res
    
    res = app.get('/', headers={'Accept':'application/xml,*/*'})
    assert "accepttypes is: application/xml" in res

def test_headers():
    app = TestApp(simpleapp)
    headers = {
        'If-Modified-Since': 'Sat, 29 Oct 1994 19:43:31 GMT',
        'Cookie': 'var1=value1',
        'User-Agent': 'Mozilla 4.0 (compatible; MSIE)',
        'If-None-Match': '"etag001", "etag002"',
        'X-Requested-With': 'XMLHttpRequest',
        }
    res = app.get('/?foo=bar&baz', headers=headers)
    res.mustcontain(
        'if_modified_since: datetime.datetime(1994, 10, 29, 19, 43, 31, tzinfo=UTC)',
        "user_agent: 'Mozilla",
        'is_xhr: True',
        "cookies is {'var1': 'value1'}",
        "params is NestedMultiDict([('foo', 'bar'), ('baz', '')])",
        "if_none_match: <ETag etag001 or etag002>",
        )
    
def test_bad_cookie():
    req = Request.blank('/')
    req.headers['Cookie'] = '070-it-:><?0'
    assert req.cookies == {}
    req.headers['Cookie'] = 'foo=bar'
    assert req.cookies == {'foo': 'bar'}
    req.headers['Cookie'] = '...'
    assert req.cookies == {}
    req.headers['Cookie'] = '=foo'
    assert req.cookies == {}
