""" A SOAPpy transport that does not validate SSL certificates. """
import Cookie
import base64
import httplib
import inspect
import ssl
import urllib

from SOAPpy import (Config, HTTPError, HTTPTransport, HTTPWithTimeout,
                    SOAPAddress, SOAPUserAgent)


class UnverifiedTransport(HTTPTransport):
  """ A SOAPpy transport that does not validate SSL certificates. """
  def call(self, addr, data, namespace, soapaction=None, encoding=None,
           http_proxy=None, config=Config, timeout=None):
    """ This was taken from SOAPpy's HTTPTransport and modified to use
    Python 2.7.9's context argument. """

    if not isinstance(addr, SOAPAddress):
      addr = SOAPAddress(addr, config)

    # Build a request
    if http_proxy:
      real_addr = http_proxy
      real_path = addr.proto + "://" + addr.host + addr.path
    else:
      real_addr = addr.host
      real_path = addr.path

    if addr.proto == 'https':
      if 'context' in inspect.getargspec(httplib.HTTPS.__init__).args:
        r = httplib.HTTPS(real_addr, context=ssl._create_unverified_context())
      else:
        r = httplib.HTTPS(real_addr)
    else:
      r = HTTPWithTimeout(real_addr, timeout=timeout)

    r.putrequest("POST", real_path)

    r.putheader("Host", addr.host)
    r.putheader("User-agent", SOAPUserAgent())
    t = 'text/xml'
    if encoding != None:
      t += '; charset=%s' % encoding
    r.putheader("Content-type", t)
    r.putheader("Content-length", str(len(data)))
    self.__addcookies(r)

    if addr.user != None:
      val = base64.encodestring(urllib.unquote_plus(addr.user))
      r.putheader('Authorization', 'Basic ' + val.replace('\012', ''))

    # This fixes sending either "" or "None"
    if soapaction == None or len(soapaction) == 0:
      r.putheader("SOAPAction", "")
    else:
      r.putheader("SOAPAction", '"%s"' % soapaction)

    r.endheaders()

    # send the payload
    r.send(data)

    # read response line
    code, msg, headers = r.getreply()

    self.cookies = Cookie.SimpleCookie()
    if headers:
      content_type = headers.get("content-type", "text/xml")
      content_length = headers.get("Content-length")

      for cookie in headers.getallmatchingheaders("Set-Cookie"):
        self.cookies.load(cookie)

    else:
      content_type = None
      content_length = None

    # work around OC4J bug which does '<len>, <len>' for some reason
    if content_length:
      comma = content_length.find(',')
      if comma > 0:
        content_length = content_length[:comma]

    # attempt to extract integer message size
    try:
      message_len = int(content_length)
    except (TypeError, ValueError):
      message_len = -1

    f = r.getfile()
    if f is None:
      raise HTTPError(code, "Empty response from server\nCode: %s\nHeaders: %s" % (msg, headers))

    if message_len < 0:
      # Content-Length missing or invalid; just read the whole socket
      # This won't work with HTTP/1.1 chunked encoding
      data = f.read()
      message_len = len(data)
    else:
      data = f.read(message_len)

    def startswith(string, val):
      return string[0:len(val)] == val

    if code == 500 and not (startswith(content_type, "text/xml") and message_len > 0):
      raise HTTPError(code, msg)

    if code not in (200, 500):
      raise HTTPError(code, msg)

    # get the new namespace
    if namespace is None:
      new_ns = None
    else:
      new_ns = self.getNS(namespace, data)

    # return response payload
    return data, new_ns

  def __addcookies(self, r):
    """ Add cookies from self.cookies to request r. """
    for cname, morsel in self.cookies.items():
      attrs = []
      value = morsel.get('version', '')
      if value != '' and value != '0':
        attrs.append('$Version=%s' % value)
      attrs.append('%s=%s' % (cname, morsel.coded_value))
      value = morsel.get('path')
      if value:
        attrs.append('$Path=%s' % value)
      value = morsel.get('domain')
      if value:
        attrs.append('$Domain=%s' % value)
      r.putheader('Cookie', "; ".join(attrs))
