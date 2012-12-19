import webob
from webob import Request
from nose.tools import eq_ as eq, assert_raises

def test_request_no_method():
    assert Request({}).method == 'GET'

def test_request_read_no_content_length():
    req, input = _make_read_tracked_request('abc', 'FOO')
    assert req.content_length is None
    assert req.body == ''
    assert not input.was_read

def test_request_read_no_content_length_POST():
    req, input = _make_read_tracked_request('abc', 'POST')
    assert req.content_length is None
    assert req.body == 'abc'
    assert input.was_read

def test_request_read_no_flag_but_content_length_is_present():
    req, input = _make_read_tracked_request('abc')
    req.content_length = 3
    assert req.body == 'abc'
    assert input.was_read

def test_request_read_no_content_length_but_flagged_readable():
    req, input = _make_read_tracked_request('abc')
    req.is_body_readable = True
    assert req.body == 'abc'
    assert input.was_read

def test_request_read_after_setting_body_file():
    req = _make_read_tracked_request()[0]
    input = req.body_file = ReadTracker('abc')
    assert req.content_length is None
    assert not req.is_body_seekable
    assert req.body == 'abc'
    # reading body made the input seekable and set the clen
    assert req.content_length == 3
    assert req.is_body_seekable
    assert input.was_read

def test_request_readlines():
    req = Request.blank('/', POST='a\n'*3)
    req.is_body_seekable = False
    eq(req.body_file.readlines(), ['a\n'] * 3)

def test_request_delete_with_body():
    req = Request.blank('/', method='DELETE')
    assert not req.is_body_readable
    req.body = 'abc'
    assert req.is_body_readable
    assert req.body_file.read() == 'abc'


def _make_read_tracked_request(data='', method='PUT'):
    input = ReadTracker(data)
    env = {
        'REQUEST_METHOD': method,
        'wsgi.input': input,
    }
    return Request(env), input

class ReadTracker(object):
    """
        Helper object to determine if the input was read or not
    """
    def __init__(self, data):
        self.data = data
        self.was_read = False
    def read(self, size=-1):
        if size < 0:
            size = len(self.data)
        assert size == len(self.data)
        self.was_read = True
        return self.data


def test_limited_length_file_repr():
    req = Request.blank('/', POST='x')
    req.body_file_raw = 'dummy'
    req.is_body_seekable = False
    eq(repr(req.body_file), "<LimitedLengthFile('dummy', maxlen=1)>")

def test_request_wrong_clen(is_seekable=False):
    tlen = 1<<20
    req = Request.blank('/', POST='x'*tlen)
    eq(req.content_length, tlen)
    req.body_file = _Helper_test_request_wrong_clen(req.body_file)
    eq(req.content_length, None)
    req.content_length = tlen + 100
    req.is_body_seekable = is_seekable
    eq(req.content_length, tlen+100)
    # this raises AssertionError if the body reading
    # trusts content_length too much
    assert_raises(IOError, req.copy_body)

def test_request_wrong_clen_seekable():
    test_request_wrong_clen(is_seekable=True)

def test_webob_version():
    assert isinstance(webob.__version__, str)

class _Helper_test_request_wrong_clen(object):
    def __init__(self, f):
        self.f = f
        self.file_ended = False

    def read(self, *args):
        r = self.f.read(*args)
        if not r:
            if self.file_ended:
                raise AssertionError("Reading should stop after first empty string")
            self.file_ended = True
        return r


def test_disconnect_detection_cgi():
    data = 'abc'*(1<<20)
    req = Request.blank('/', POST={'file':('test-file', data)})
    req.is_body_seekable = False
    req.POST # should not raise exceptions

def test_disconnect_detection_hinted_readline():
    data = 'abc'*(1<<20)
    req = Request.blank('/', POST=data)
    req.is_body_seekable = False
    line = req.body_file.readline(1<<16)
    assert line
    assert data.startswith(line)

