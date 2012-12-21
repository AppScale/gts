#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#




"""Copyright 2008 Python Software Foundation, Ian Bicking, and Google."""

import mimetools
import StringIO
import sys


CONTINUE = 100
SWITCHING_PROTOCOLS = 101
PROCESSING  = 102
OK = 200
CREATED = 201
ACCEPTED = 202
NON_AUTHORITATIVE_INFORMATION = 203
NO_CONTENT = 204
RESET_CONTENT = 205
PARTIAL_CONTENT = 206
MULTI_STATUS = 207
IM_USED = 226
MULTIPLE_CHOICES = 300
MOVED_PERMANENTLY = 301
FOUND = 302
SEE_OTHER = 303
NOT_MODIFIED = 304
USE_PROXY = 305
TEMPORARY_REDIRECT = 307
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
INTERNAL_SERVER_ERROR = 500
NOT_IMPLEMENTED = 501
BAD_GATEWAY = 502
SERVICE_UNAVAILABLE = 503
GATEWAY_TIMEOUT = 504
HTTP_VERSION_NOT_SUPPORTED = 505
INSUFFICIENT_STORAGE = 507
NOT_EXTENDED = 510

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

HTTP_PORT = 80
HTTPS_PORT = 443





class HTTPConnection:


  protocol = 'http'
  default_port = HTTP_PORT
  _allow_truncated = True
  _follow_redirects = False

  def __init__(self, host, port=None, strict=False, timeout=None):



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

    self._method = self._url = None
    self._body = ''
    self.headers = []



    if not isinstance(timeout, (float, int, long)):
      timeout = None
    self.timeout = timeout

  def connect(self):
    pass

  def request(self, method, url, body=None, headers=None):
    self._method = method
    self._url = url
    try:
      self._body = body.read()
    except AttributeError:
      self._body = body
    if headers is None:
      headers = []
    elif hasattr(headers, 'items'):
      headers = headers.items()
    self.headers = headers

  def putrequest(self, request, selector, skip_host=False, skip_accept_encoding=False):

    self._method = request
    self._url = selector

  def putheader(self, header, *lines):
    line = '\r\n\t'.join([str(line) for line in lines])
    self.headers.append((header, line))

  def endheaders(self, message_body=None):

    if message_body is not None:
      self.send(message_body)

  def set_debuglevel(self, level=None):
    pass

  def send(self, data):
    self._body += data

  def getresponse(self):
    if self.port and self.port != self.default_port:
        host = '%s:%s' % (self.host, self.port)
    else:
        host = self.host
    if not self._url.startswith(self.protocol):
      url = '%s://%s%s' % (self.protocol, host, self._url)
    else:
      url = self._url
    headers = dict(self.headers)

    try:
      method = self._method_map[self._method.upper()]
    except KeyError:
      raise ValueError("%r is an unrecognized HTTP method" % self._method)

    response = self._fetch(url, self._body, method, headers,
                           self._allow_truncated, self._follow_redirects,
                           deadline=self.timeout)
    return HTTPResponse(response)

  def close(self):
      pass


class HTTPSConnection(HTTPConnection):

    protocol = 'https'
    default_port = HTTPS_PORT

    def __init__(self, host, port=None, key_file=None, cert_file=None,
                 strict=False, timeout=None):

        if key_file is not None or cert_file is not None:
            raise NotImplementedError(
                "key_file and cert_file arguments are not implemented")
        HTTPConnection.__init__(self, host, port=port, strict=strict,
                                timeout=timeout)


class HTTPMessage(mimetools.Message):

    def addheader(self, key, value):
        """Add header for field key handling repeats."""
        prev = self.dict.get(key)
        if prev is None:
            self.dict[key] = value
        else:
            combined = ", ".join((prev, value))
            self.dict[key] = combined

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
            line = self.fp.readline()
            if not line:
                self.status = 'EOF in headers'
                break

            if firstline and line.startswith('From '):
                self.unixfrom = self.unixfrom + line
                continue
            firstline = 0
            if headerseen and line[0] in ' \t':



                hlist.append(line)
                self.addcontinue(headerseen, line.strip())
                continue
            elif self.iscomment(line):

                continue
            elif self.islast(line):

                break
            headerseen = self.isheader(line)
            if headerseen:

                hlist.append(line)
                self.addheader(headerseen, line[len(headerseen)+1:].strip())
                continue
            else:

                if not self.dict:
                    self.status = 'No headers'
                else:
                    self.status = 'Non-header line where header expected'

                if unread:
                    unread(line)
                elif tell:
                    self.fp.seek(startofline)
                else:
                    self.status = self.status + '; bad seek'
                break

class HTTPResponse(object):

  def __init__(self, fetch_response):
    self._fetch_response = fetch_response
    self.fp = StringIO.StringIO(fetch_response.content)

  def __getattr__(self, attr):
    return getattr(self.fp, attr)

  def getheader(self, name, default=None):
    return self._fetch_response.headers.get(name, default)

  def getheaders(self):
    return self._fetch_response.headers.items()

  @property
  def msg(self):
    return self._fetch_response.header_msg

  version = 11

  @property
  def status(self):
    return self._fetch_response.status_code

  @property
  def reason(self):
    return responses.get(self._fetch_response.status_code, 'Unknown')



class HTTP:
  "Compatibility class with httplib.py from 1.5."

  _http_vsn = 11
  _http_vsn_str = 'HTTP/1.1'

  debuglevel = 0

  _connection_class = HTTPConnection

  def __init__(self, host='', port=None, strict=None):
    "Provide a default host, since the superclass requires one."


    if port == 0:
      port = None




    self._setup(self._connection_class(host, port, strict))

  def _setup(self, conn):
    self._conn = conn


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

  def getreply(self):
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






    self.file = None



class HTTPS(HTTP):
  """Compatibility with 1.5 httplib interface

  Python 1.5.2 did not have an HTTPS class, but it defined an
  interface for sending http requests that is also useful for
  https.
  """

  _connection_class = HTTPSConnection

  def __init__(self, host='', port=None, key_file=None, cert_file=None,
               strict=None):
    if key_file is not None or cert_file is not None:
      raise NotImplementedError(
          "key_file and cert_file arguments are not implemented")




    if port == 0:
      port = None
    self._setup(self._connection_class(host, port, key_file,
                                       cert_file, strict))



    self.key_file = key_file
    self.cert_file = cert_file


class HTTPException(Exception):
  pass

class NotConnected(HTTPException):
  pass

class InvalidURL(HTTPException):
  pass

class UnknownProtocol(HTTPException):
  def __init__(self, version):
    self.version = version
    HTTPException.__init__(self, version)

class UnknownTransferEncoding(HTTPException):
  pass

class UnimplementedFileMode(HTTPException):
  pass

class IncompleteRead(HTTPException):
  def __init__(self, partial):
    self.partial = partial
    HTTPException.__init__(self, partial)

class ImproperConnectionState(HTTPException):
  pass

class CannotSendRequest(ImproperConnectionState):
  pass

class CannotSendHeader(ImproperConnectionState):
  pass

class ResponseNotReady(ImproperConnectionState):
  pass

class BadStatusLine(HTTPException):
  def __init__(self, line):
    self.line = line
    HTTPException.__init__(self, line)

error = HTTPException
