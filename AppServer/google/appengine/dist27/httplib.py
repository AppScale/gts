# Copyright 2008 Google Inc. All Rights Reserved.
# Code originally from Ian Bicking
# (http://code.google.com/p/appengine-monkey/).
# Contributed by Ian and subsequently modified here at Google.
"""Copyright 2008 Python Software Foundation, Ian Bicking, and Google."""

import cStringIO
import mimetools


HTTP_PORT = 80
HTTPS_PORT = 443

_UNKNOWN = 'UNKNOWN'

# status codes
# informational
CONTINUE = 100
SWITCHING_PROTOCOLS = 101
PROCESSING = 102

# successful
OK = 200
CREATED = 201
ACCEPTED = 202
NON_AUTHORITATIVE_INFORMATION = 203
NO_CONTENT = 204
RESET_CONTENT = 205
PARTIAL_CONTENT = 206
MULTI_STATUS = 207
IM_USED = 226

# redirection
MULTIPLE_CHOICES = 300
MOVED_PERMANENTLY = 301
FOUND = 302
SEE_OTHER = 303
NOT_MODIFIED = 304
USE_PROXY = 305
TEMPORARY_REDIRECT = 307

# client error
BAD_REQUEST = 400
UNAUTHORIZED = 401
PAYMENT_REQUIRED = 402
FORBIDDEN = 403
NOT_FOUND = 404
METHOD_NOT_ALLOWED = 405
NOT_ACCEPTABLE = 406
PROXY_AUTHENTICATION_REQUIRED = 407
REQUEST_TIMEOUT = 408
CONFLICT = 409
GONE = 410
LENGTH_REQUIRED = 411
PRECONDITION_FAILED = 412
REQUEST_ENTITY_TOO_LARGE = 413
REQUEST_URI_TOO_LONG = 414
UNSUPPORTED_MEDIA_TYPE = 415
REQUESTED_RANGE_NOT_SATISFIABLE = 416
EXPECTATION_FAILED = 417
UNPROCESSABLE_ENTITY = 422
LOCKED = 423
FAILED_DEPENDENCY = 424
UPGRADE_REQUIRED = 426

# server error
INTERNAL_SERVER_ERROR = 500
NOT_IMPLEMENTED = 501
BAD_GATEWAY = 502
SERVICE_UNAVAILABLE = 503
GATEWAY_TIMEOUT = 504
HTTP_VERSION_NOT_SUPPORTED = 505
INSUFFICIENT_STORAGE = 507
NOT_EXTENDED = 510

# Mapping status codes to official W3C names
responses = {
    100: 'Continue',
    101: 'Switching Protocols',

    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',

    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    306: '(Unused)',
    307: 'Temporary Redirect',

    400: 'Bad Request',
    401: 'Unauthorized',
    402: 'Payment Required',
    403: 'Forbidden',
    404: 'Not Found',
    405: 'Method Not Allowed',
    406: 'Not Acceptable',
    407: 'Proxy Authentication Required',
    408: 'Request Timeout',
    409: 'Conflict',
    410: 'Gone',
    411: 'Length Required',
    412: 'Precondition Failed',
    413: 'Request Entity Too Large',
    414: 'Request-URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',

    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
}

# maximal amount of data to read at one time in _safe_read
MAXAMOUNT = 1048576

# maximal line length when calling readline().
_MAXLINE = 65536

# Can't get this symbol from socket since importing socket causes an import
# cycle though:
# google.net.proto.ProtocolBuffer imports...
# httplib imports ...
# socket imports ...
# remote_socket_service_pb imports ProtocolBuffer
_GLOBAL_DEFAULT_TIMEOUT = object()


class HTTPMessage(mimetools.Message):
  # App Engine Note: This class has been copied almost unchanged from
  # Python 2.7.2

  def addheader(self, key, value):
    """Add header for field key handling repeats."""
    prev = self.dict.get(key)
    if prev is None:
      self.dict[key] = value
    else:
      combined = ", ".join((prev, value))
      self.dict[key] = combined
    # App Engine Note: Headers are stored in both self.dict and self.headers, so
    # add the header to self.headers as well.
    self.headers.append('%s: %s' % (key, value))

  def addcontinue(self, key, more):
    """Add more field data from a continuation line."""
    prev = self.dict[key]
    self.dict[key] = prev + "\n " + more

  def readheaders(self):
    """Read header lines.

    Read header lines up to the entirely blank line that terminates them.
    The (normally blank) line that ends the headers is skipped, but not
    included in the returned list.  If a non-header line ends the headers,
    (which is an error), an attempt is made to backspace over it; it is
    never included in the returned list.

    The variable self.status is set to the empty string if all went well,
    otherwise it is an error message.  The variable self.headers is a
    completely uninterpreted list of lines contained in the header (so
    printing them will reproduce the header exactly as it appears in the
    file).

    If multiple header fields with the same name occur, they are combined
    according to the rules in RFC 2616 sec 4.2:

    Appending each subsequent field-value to the first, each separated
    by a comma. The order in which header fields with the same field-name
    are received is significant to the interpretation of the combined
    field value.
    """
    # XXX The implementation overrides the readheaders() method of
    # rfc822.Message.  The base class design isn't amenable to
    # customized behavior here so the method here is a copy of the
    # base class code with a few small changes.

    self.dict = {}
    self.unixfrom = ''
    self.headers = hlist = []
    self.status = ''
    headerseen = ""
    firstline = 1
    startofline = unread = tell = None
    if hasattr(self.fp, 'unread'):
      unread = self.fp.unread
    elif self.seekable:
      tell = self.fp.tell
    while True:
      if tell:
        try:
          startofline = tell()
        except IOError:
          startofline = tell = None
          self.seekable = 0
      line = self.fp.readline(_MAXLINE + 1)
      if len(line) > _MAXLINE:
        raise LineTooLong("header line")
      if not line:
        self.status = 'EOF in headers'
        break
      # Skip unix From name time lines
      if firstline and line.startswith('From '):
        self.unixfrom = self.unixfrom + line
        continue
      firstline = 0
      if headerseen and line[0] in ' \t':
        # XXX Not sure if continuation lines are handled properly
        # for http and/or for repeating headers
        # It's a continuation line.
        hlist.append(line)
        self.addcontinue(headerseen, line.strip())
        continue
      elif self.iscomment(line):
        # It's a comment.  Ignore it.
        continue
      elif self.islast(line):
        # Note! No pushback here!  The delimiter line gets eaten.
        break
      headerseen = self.isheader(line)
      if headerseen:
        # It's a legal header line, save it.
        hlist.append(line)
        self.addheader(headerseen, line[len(headerseen)+1:].strip())
        continue
      else:
        # It's not a header line; throw it back and stop here.
        if not self.dict:
          self.status = 'No headers'
        else:
          self.status = 'Non-header line where header expected'
        # Try to undo the read.
        if unread:
          unread(line)
        elif tell:
          self.fp.seek(startofline)
        else:
          self.status = self.status + '; bad seek'
        break

class HTTPResponse:
  # App Engine Note: The public interface is identical to the interface provided
  #    in Python 2.7 excep __init__ takes a
  #    google.appengine.api.urlfetch.Response instance rather than a socket.

  def __init__(self,
               fetch_response,  # App Engine Note: fetch_response was "sock".
               debuglevel=0,
               strict=0,
               method=None,
               buffering=False):
    self._fetch_response = fetch_response
    self.fp = cStringIO.StringIO(fetch_response.content)  # For the HTTP class.

    self.debuglevel = debuglevel
    self.strict = strict
    self._method = method

    self.msg = None

    # from the Status-Line of the response
    self.version = _UNKNOWN # HTTP-Version
    self.status = _UNKNOWN  # Status-Code
    self.reason = _UNKNOWN  # Reason-Phrase

    self.chunked = _UNKNOWN         # is "chunked" being used?
    self.chunk_left = _UNKNOWN      # bytes left to read in current chunk
    self.length = _UNKNOWN          # number of bytes left in response
    self.will_close = _UNKNOWN      # conn will close at end of response

  def begin(self):
    if self.msg is not None:
      # we've already started reading the response
      return

    self.msg = HTTPMessage(cStringIO.StringIO(''))
    for name, value in self._fetch_response.headers.items():
      self.msg.addheader(name.lower(), str(value))

    self.version = 11  # We can't get the real HTTP version so make one up.
    self.status = self._fetch_response.status_code
    self.reason = responses.get(self._fetch_response.status_code, 'Unknown')

    # The following are implementation details and should not be read by
    # clients - but set them to reasonable values just in case.
    self.chunked = 0
    self.chunk_left = None
    self.length = None
    self.will_close = 1

  def close(self):
    if self.fp:
      self.fp.close()
      self.fp = None

  def isclosed(self):
    return self.fp is None

  def read(self, amt=None):
    if self.fp is None:
      return ''

    if self._method == 'HEAD':
      self.close()
      return ''

    if amt is None:
      return self.fp.read()
    else:
      return self.fp.read(amt)

  def fileno(self):
    raise NotImplementedError('fileno is not supported')

  def getheader(self, name, default=None):
    if self.msg is None:
      raise ResponseNotReady()
    return self.msg.getheader(name, default)

  def getheaders(self):
    """Return list of (header, value) tuples."""
    if self.msg is None:
      raise ResponseNotReady()
    return self.msg.items()

class HTTPConnection:
  # App Engine Note: The public interface is identical to the interface provided
  #    in Python 2.7.2 but the implementation uses
  #    google.appengine.api.urlfetch. Some methods are no-ops and set_tunnel
  #    raises NotImplementedError.

  _protocol = 'http'  # passed to urlfetch.

  _http_vsn = 11
  _http_vsn_str = 'HTTP/1.1'

  response_class = HTTPResponse
  default_port = HTTP_PORT
  auto_open = 1
  debuglevel = 0
  strict = 0

  _allow_truncated = True
  _follow_redirects = False

  def __init__(self, host, port=None, strict=None,
               timeout=_GLOBAL_DEFAULT_TIMEOUT, source_address=None):
    # net.proto.ProcotolBuffer relies on httplib so importing urlfetch at the
    # module level causes a failure on prod. That means the import needs to be
    # lazy.
    from google.appengine.api import urlfetch
    self._fetch = urlfetch.fetch
    self._method_map = {
      'GET': urlfetch.GET,
      'POST': urlfetch.POST,
      'HEAD': urlfetch.HEAD,
      'PUT': urlfetch.PUT,
      'DELETE': urlfetch.DELETE,
    }
    self.host = host
    self.port = port
    self.timeout = timeout
    # Both 'strict' and 'source_address' are ignored.
    self._method = self._url = None
    self._body = ''
    self.headers = []

  def set_tunnel(self, host, port=None, headers=None):
    """ Sets up the host and the port for the HTTP CONNECT Tunnelling.

    The headers argument should be a mapping of extra HTTP headers
    to send with the CONNECT request.

    App Engine Note: This method is not supported.
    """
    raise NotImplementedError('HTTP CONNECT Tunnelling is not supported')

  def set_debuglevel(self, level):
    pass

  def connect(self):
    """Connect to the host and port specified in __init__.

    App Engine Note: This method is a no-op.
    """

  def close(self):
    """Close the connection to the HTTP server.

    App Engine Note: This method is a no-op.
    """

  def send(self, data):
    """Send `data' to the server."""
    self._body += data

  def putrequest(self, method, url, skip_host=0, skip_accept_encoding=0):
    """Send a request to the server.

    `method' specifies an HTTP request method, e.g. 'GET'.
    `url' specifies the object being requested, e.g. '/index.html'.
    `skip_host' if True does not add automatically a 'Host:' header
    `skip_accept_encoding' if True does not add automatically an
       'Accept-Encoding:' header

    App Engine Note: `skip_host' and `skip_accept_encoding' are not honored by
        the urlfetch service.
    """
    self._method = method
    self._url = url

  def putheader(self, header, *values):
    """Send a request header line to the server.

    For example: h.putheader('Accept', 'text/html')
    """
    hdr = '\r\n\t'.join([str(v) for v in values])
    self.headers.append((header, hdr))

  def endheaders(self, message_body=None):
    """Indicate that the last header line has been sent to the server.

    This method sends the request to the server.  The optional
    message_body argument can be used to pass message body
    associated with the request.  The message body will be sent in
    the same packet as the message headers if possible.  The
    message_body should be a string.
    """
    if message_body is not None:
      self.send(message_body)

  def request(self, method, url, body=None, headers=None):
    """Send a complete request to the server."""
    self._method = method
    self._url = url
    try:  # 'body' can be a file.
      self._body = body.read()
    except AttributeError:
      self._body = body
    if headers is None:
      headers = []
    elif hasattr(headers, 'items'):
      headers = headers.items()
    self.headers = headers

  def getresponse(self, buffering=False):
    """Get the response from the server.

    App Engine Note: buffering is ignored.
    """
    # net.proto.ProcotolBuffer relies on httplib so importing urlfetch at the
    # module level causes a failure on prod. That means the import needs to be
    # lazy.
    from google.appengine.api import urlfetch
    import socket  # Cannot be done at global scope due to circular import.

    if self.port and self.port != self.default_port:
      host = '%s:%s' % (self.host, self.port)
    else:
      host = self.host
    if not self._url.startswith(self._protocol):
      url = '%s://%s%s' % (self._protocol, host, self._url)
    else:
      url = self._url
    headers = dict(self.headers)

    if self.timeout in [_GLOBAL_DEFAULT_TIMEOUT,
                        socket._GLOBAL_DEFAULT_TIMEOUT]:
      deadline = socket.getdefaulttimeout()
    else:
      deadline = self.timeout

    try:
      method = self._method_map[self._method.upper()]
    except KeyError:
      raise ValueError('%r is an unrecognized HTTP method' % self._method)

    try:
      fetch_response = self._fetch(url,
                                   self._body,
                                   method, headers,
                                   self._allow_truncated,
                                   self._follow_redirects,
                                   deadline)
    except urlfetch.InvalidURLError, e:
      raise InvalidURL(str(e))
    except (urlfetch.ResponseTooLargeError, urlfetch.DeadlineExceededError), e:
      raise HTTPException(str(e))
    except urlfetch.SSLCertificateError, e:
      # Should be ssl.SSLError but the ssl module isn't available.
      raise HTTPException(str(e))
    except urlfetch.DownloadError, e:
      # One of the following occured: UNSPECIFIED_ERROR, FETCH_ERROR
      raise socket.error(
          'An error occured while connecting to the server: %s' % e)

    response = self.response_class(fetch_response, method=method)
    response.begin()
    self.close()
    return response


class HTTPSConnection(HTTPConnection):
  "This class allows communication via SSL."

  # App Engine Note: The public interface is identical to the interface provided
  #    in Python 2.7.2 but the implementation does not support key and
  #    certificate files.

  _protocol = 'https'  # passed to urlfetch.
  default_port = HTTPS_PORT

  def __init__(self, host, port=None, key_file=None, cert_file=None,
               strict=False, timeout=_GLOBAL_DEFAULT_TIMEOUT,
               source_address=None):
    if key_file is not None or cert_file is not None:
      raise NotImplementedError(
          'key_file and cert_file arguments are not implemented')

    HTTPConnection.__init__(self, host, port, strict, timeout, source_address)

class HTTP:
  "Compatibility class with httplib.py from 1.5."

  # App Engine Note: The public interface is identical to the interface provided
  #    in Python 2.7.

  _http_vsn = 10
  _http_vsn_str = 'HTTP/1.0'

  debuglevel = 0

  _connection_class = HTTPConnection

  def __init__(self, host='', port=None, strict=None):
    "Provide a default host, since the superclass requires one."

    # some joker passed 0 explicitly, meaning default port
    if port == 0:
      port = None

    # Note that we may pass an empty string as the host; this will throw
    # an error when we attempt to connect. Presumably, the client code
    # will call connect before then, with a proper host.
    self._setup(self._connection_class(host, port, strict))

  def _setup(self, conn):
    self._conn = conn

    # set up delegation to flesh out interface
    self.send = conn.send
    self.putrequest = conn.putrequest
    self.endheaders = conn.endheaders
    self.set_debuglevel = conn.set_debuglevel

    conn._http_vsn = self._http_vsn
    conn._http_vsn_str = self._http_vsn_str

    self.file = None

  def connect(self, host=None, port=None):
    "Accept arguments to set the host/port, since the superclass doesn't."
    self.__init__(host, port)

  def getfile(self):
    "Provide a getfile, since the superclass' does not use this concept."
    return self.file

  def putheader(self, header, *values):
    "The superclass allows only one value argument."
    self._conn.putheader(header, '\r\n\t'.join([str(v) for v in values]))

  def getreply(self, buffering=False):
    """Compat definition since superclass does not define it.

    Returns a tuple consisting of:
    - server status code (e.g. '200' if all goes well)
    - server "reason" corresponding to status code
    - any RFC822 headers in the response from the server
    """
    response = self._conn.getresponse()

    self.headers = response.msg
    self.file = response.fp
    return response.status, response.reason, response.msg

  def close(self):
    self._conn.close()

    # note that self.file == response.fp, which gets closed by the
    # superclass. just clear the object ref here.
    ### hmm. messy. if status==-1, then self.file is owned by us.
    ### well... we aren't explicitly closing, but losing this ref will
    ### do it
    self.file = None


# Copy from Python's httplib implementation.
class HTTPS(HTTP):
  """Compatibility with 1.5 httplib interface

  Python 1.5.2 did not have an HTTPS class, but it defined an
  interface for sending http requests that is also useful for
  https.
  """

  # App Engine Note: The public interface is identical to the interface provided
  #    in Python 2.7 except that key and certificate files are not supported.

  _connection_class = HTTPSConnection

  def __init__(self, host='', port=None, key_file=None, cert_file=None,
               strict=None):
    if key_file is not None or cert_file is not None:
      raise NotImplementedError(
          'key_file and cert_file arguments are not implemented')

    # provide a default host, pass the X509 cert info

    # urf. compensate for bad input.
    if port == 0:
      port = None
    self._setup(self._connection_class(host, port, key_file,
                                       cert_file, strict))

    # we never actually use these for anything, but we keep them
    # here for compatibility with post-1.5.2 CVS.
    self.key_file = key_file
    self.cert_file = cert_file


class HTTPException(Exception):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2

  # Subclasses that define an __init__ must call Exception.__init__
  # or define self.args.  Otherwise, str() will fail.
  pass

class NotConnected(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  pass

class InvalidURL(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  pass

class UnknownProtocol(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  def __init__(self, version):
    self.args = version,
    self.version = version

class UnknownTransferEncoding(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  pass

class UnimplementedFileMode(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  pass

class IncompleteRead(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2

  def __init__(self, partial, expected=None):
    self.args = partial,
    self.partial = partial
    self.expected = expected
  def __repr__(self):
    if self.expected is not None:
      e = ', %i more expected' % self.expected
    else:
      e = ''
    return 'IncompleteRead(%i bytes read%s)' % (len(self.partial), e)
  def __str__(self):
    return repr(self)

class ImproperConnectionState(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  pass

class CannotSendRequest(ImproperConnectionState):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  pass

class CannotSendHeader(ImproperConnectionState):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  pass

class ResponseNotReady(ImproperConnectionState):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2
  pass

class BadStatusLine(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2

  def __init__(self, line):
    if not line:
      line = repr(line)
    self.args = line,
    self.line = line

class LineTooLong(HTTPException):
  # App Engine Note: This class has been copied unchanged from Python 2.7.2

  def __init__(self, line_type):
    HTTPException.__init__(self, "got more than %d bytes when reading %s"
                                  % (_MAXLINE, line_type))

# for backwards compatibility
error = HTTPException

class LineAndFileWrapper:
  """A limited file-like object for HTTP/0.9 responses."""

  # App Engine Note: This class has been copied unchanged from Python 2.7.2

  # The status-line parsing code calls readline(), which normally
  # get the HTTP status line.  For a 0.9 response, however, this is
  # actually the first line of the body!  Clients need to get a
  # readable file object that contains that line.

  def __init__(self, line, file):
    self._line = line
    self._file = file
    self._line_consumed = 0
    self._line_offset = 0
    self._line_left = len(line)

  def __getattr__(self, attr):
    return getattr(self._file, attr)

  def _done(self):
    # called when the last byte is read from the line.  After the
    # call, all read methods are delegated to the underlying file
    # object.
    self._line_consumed = 1
    self.read = self._file.read
    self.readline = self._file.readline
    self.readlines = self._file.readlines

  def read(self, amt=None):
    if self._line_consumed:
      return self._file.read(amt)
    assert self._line_left
    if amt is None or amt > self._line_left:
      s = self._line[self._line_offset:]
      self._done()
      if amt is None:
        return s + self._file.read()
      else:
        return s + self._file.read(amt - len(s))
    else:
      assert amt <= self._line_left
      i = self._line_offset
      j = i + amt
      s = self._line[i:j]
      self._line_offset = j
      self._line_left -= amt
      if self._line_left == 0:
        self._done()
      return s

  def readline(self):
    if self._line_consumed:
      return self._file.readline()
    assert self._line_left
    s = self._line[self._line_offset:]
    self._done()
    return s

  def readlines(self, size=None):
    if self._line_consumed:
      return self._file.readlines(size)
    assert self._line_left
    L = [self._line[self._line_offset:]]
    self._done()
    if size is None:
      return L + self._file.readlines()
    else:
      return L + self._file.readlines(size)
