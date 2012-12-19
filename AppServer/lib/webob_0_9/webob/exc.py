"""
HTTP Exception

This module processes Python exceptions that relate to HTTP exceptions
by defining a set of exceptions, all subclasses of HTTPException.
Each exception, in addition to being a Python exception that can be
raised and caught, is also a WSGI application and ``webob.Response``
object.

This module defines exceptions according to RFC 2068 [1]_ : codes with
100-300 are not really errors; 400's are client errors, and 500's are
server errors.  According to the WSGI specification [2]_ , the application
can call ``start_response`` more then once only under two conditions:
(a) the response has not yet been sent, or (b) if the second and
subsequent invocations of ``start_response`` have a valid ``exc_info``
argument obtained from ``sys.exc_info()``.  The WSGI specification then
requires the server or gateway to handle the case where content has been
sent and then an exception was encountered.

Exception
  HTTPException
    HTTPOk
      * 200 - HTTPOk
      * 201 - HTTPCreated
      * 202 - HTTPAccepted
      * 203 - HTTPNonAuthoritativeInformation
      * 204 - HTTPNoContent
      * 205 - HTTPResetContent
      * 206 - HTTPPartialContent
    HTTPRedirection
      * 300 - HTTPMultipleChoices
      * 301 - HTTPMovedPermanently
      * 302 - HTTPFound
      * 303 - HTTPSeeOther
      * 304 - HTTPNotModified
      * 305 - HTTPUseProxy
      * 306 - Unused (not implemented, obviously)
      * 307 - HTTPTemporaryRedirect
    HTTPError
      HTTPClientError
        * 400 - HTTPBadRequest
        * 401 - HTTPUnauthorized
        * 402 - HTTPPaymentRequired
        * 403 - HTTPForbidden
        * 404 - HTTPNotFound
        * 405 - HTTPMethodNotAllowed
        * 406 - HTTPNotAcceptable
        * 407 - HTTPProxyAuthenticationRequired
        * 408 - HTTPRequestTimeout
        * 409 - HTTPConfict
        * 410 - HTTPGone
        * 411 - HTTPLengthRequired
        * 412 - HTTPPreconditionFailed
        * 413 - HTTPRequestEntityTooLarge
        * 414 - HTTPRequestURITooLong
        * 415 - HTTPUnsupportedMediaType
        * 416 - HTTPRequestRangeNotSatisfiable
        * 417 - HTTPExpectationFailed
      HTTPServerError
        * 500 - HTTPInternalServerError
        * 501 - HTTPNotImplemented
        * 502 - HTTPBadGateway
        * 503 - HTTPServiceUnavailable
        * 504 - HTTPGatewayTimeout
        * 505 - HTTPVersionNotSupported

References:

.. [1] http://www.python.org/peps/pep-0333.html#error-handling
.. [2] http://www.w3.org/Protocols/rfc2616/rfc2616-sec10.html#sec10.5


"""

import re
import urlparse
import sys
try:
    from string import Template
except ImportError:
    from webob.util.stringtemplate import Template
import types
from webob import Response, Request, html_escape

tag_re = re.compile(r'<.*?>', re.S)
br_re = re.compile(r'<br.*?>', re.I|re.S)
comment_re = re.compile(r'<!--|-->')

def no_escape(value):
    if value is None:
        return ''
    if not isinstance(value, basestring):
        if hasattr(value, '__unicode__'):
            value = unicode(value)
        else:
            value = str(value)
    return value

def strip_tags(value):
    value = value.replace('\n', ' ')
    value = value.replace('\r', '')
    value = br_re.sub('\n', value)
    value = comment_re.sub('', value)
    value = tag_re.sub('', value)
    return value

class HTTPException(Exception):
    """
    Exception used on pre-Python-2.5, where new-style classes cannot be used as
    an exception.
    """

    def __init__(self, message, wsgi_response):
        Exception.__init__(self, message)
        self.__dict__['wsgi_response'] = wsgi_response

    def __call__(self, environ, start_response):
        return self.wsgi_response(environ, start_response)

    def exception(self):
        return self
    
    exception = property(exception)

    if sys.version_info < (2, 5):
        def __getattr__(self, attr):
            if not attr.startswith('_'):
                return getattr(self.wsgi_response, attr)
            else:
                raise AttributeError(attr)

        def __setattr__(self, attr, value):
            if attr.startswith('_') or attr in ('args',):
                self.__dict__[attr] = value
            else:
                setattr(self.wsgi_response, attr, value)

class WSGIHTTPException(Response, HTTPException):

    ## You should set in subclasses:
    # code = 200
    # title = 'OK'
    # explanation = 'why this happens'
    # body_template_obj = Template('response template')
    code = None
    title = None
    explanation = ''
    body_template_obj = Template('''\
${explanation}<br /><br />
${detail}
${html_comment}
''')

    plain_template_obj = Template('''\
${status}

${body}''')

    html_template_obj = Template('''\
<html>
 <head>
  <title>${status}</title>
 </head>
 <body>
  <h1>${status}</h1>
  ${body}
 </body>
</html>''')

    ## Set this to True for responses that should have no request body
    empty_body = False

    def __init__(self, detail=None, headers=None, comment=None,
                 body_template=None):
        Response.__init__(self,
                          status='%s %s' % (self.code, self.title),
                          content_type='text/html')
        Exception.__init__(self, detail)
        if headers:
            self.headers.update(headers)
        self.detail = detail
        self.comment = comment
        if body_template is not None:
            self.body_template = body_template
            self.body_template_obj = Template(body_template)
        if self.empty_body:
            del self.content_type
            del self.content_length

    def _make_body(self, environ, escape):
        args = {
            'explanation': escape(self.explanation),
            'detail': escape(self.detail or ''),
            'comment': escape(self.comment or ''),
            }
        if self.comment:
            args['html_comment'] = '<!-- %s -->' % escape(self.comment)
        else:
            args['html_comment'] = ''
        body_tmpl = self.body_template_obj
        if WSGIHTTPException.body_template_obj is not self.body_template_obj:
            # Custom template; add headers to args
            for k, v in environ.items():
                args[k] = escape(v)
            for k, v in self.headers.items():
                args[k.lower()] = escape(v)
        t_obj = self.body_template_obj
        return t_obj.substitute(args)

    def plain_body(self, environ):
        body = self._make_body(environ, no_escape)
        body = strip_tags(body)
        return self.plain_template_obj.substitute(status=self.status,
                                                  title=self.title,
                                                  body=body)

    def html_body(self, environ):
        body = self._make_body(environ, html_escape)
        return self.html_template_obj.substitute(status=self.status,
                                                 body=body)

    def generate_response(self, environ, start_response):
        if self.content_length is not None:
            del self.content_length
        headerlist = list(self.headerlist)
        accept = environ.get('HTTP_ACCEPT', '')
        if accept and 'html' in accept or '*/*' in accept:
            body = self.html_body(environ)
            if not self.content_type:
                headerlist.append('text/html; charset=utf8')
        else:
            body = self.plain_body(environ)
            if not self.content_type:
                headerlist.append('text/plain; charset=utf8')
        headerlist.append(('Content-Length', str(len(body))))
        start_response(self.status, headerlist)
        return [body]

    def __call__(self, environ, start_response):
        if environ['REQUEST_METHOD'] == 'HEAD':
            start_response(self.status, self.headerlist)
            return []
        if not self.body and not self.empty_body:
            return self.generate_response(environ, start_response)
        return Response.__call__(self, environ, start_response)

    def wsgi_response(self):
        return self
    
    wsgi_response = property(wsgi_response)

    def exception(self):
        if sys.version_info >= (2, 5):
            return self
        else:
            return HTTPException(self.detail, self)

    exception = property(exception)

class HTTPError(WSGIHTTPException):
    """
    base class for status codes in the 400's and 500's

    This is an exception which indicates that an error has occurred,
    and that any work in progress should not be committed.  These are
    typically results in the 400's and 500's.
    """

class HTTPRedirection(WSGIHTTPException):
    """
    base class for 300's status code (redirections)

    This is an abstract base class for 3xx redirection.  It indicates
    that further action needs to be taken by the user agent in order
    to fulfill the request.  It does not necessarly signal an error
    condition.
    """

class HTTPOk(WSGIHTTPException):
    """
    Base class for the 200's status code (successful responses)
    """
    code = 200
    title = 'OK'

############################################################
## 2xx success
############################################################

class HTTPCreated(HTTPOk):
    code = 201
    title = 'Created'

class HTTPAccepted(HTTPOk):
    code = 202
    title = 'Accepted'
    explanation = 'The request is accepted for processing.'

class HTTPNonAuthoritativeInformation(HTTPOk):
    code = 203
    title = 'Non-Authoritative Information'

class HTTPNoContent(HTTPOk):
    code = 204
    title = 'No Content'
    empty_body = True

class HTTPResetContent(HTTPOk):
    code = 205
    title = 'Reset Content'
    empty_body = True

class HTTPPartialContent(HTTPOk):
    code = 206
    title = 'Partial Content'

## FIXME: add 207 Multi-Status (but it's complicated)

############################################################
## 3xx redirection
############################################################

class _HTTPMove(HTTPRedirection):
    """
    redirections which require a Location field

    Since a 'Location' header is a required attribute of 301, 302, 303,
    305 and 307 (but not 304), this base class provides the mechanics to
    make this easy.

    You can provide a location keyword argument to set the location
    immediately.  You may also give ``add_slash=True`` if you want to
    redirect to the same URL as the request, except with a ``/`` added
    to the end.

    Relative URLs in the location will be resolved to absolute.
    """
    explanation = 'The resource has been moved to'
    body_template_obj = Template('''\
${explanation} <a href="${location}">${location}</a>;
you should be redirected automatically.
${detail}
${html_comment}''')

    def __init__(self, detail=None, headers=None, comment=None,
                 body_template=None, location=None, add_slash=False):
        super(_HTTPMove, self).__init__(
            detail=detail, headers=headers, comment=comment,
            body_template=body_template)
        if location is not None:
            self.location = location
            if add_slash:
                raise TypeError(
                    "You can only provide one of the arguments location and add_slash")
        self.add_slash = add_slash

    def __call__(self, environ, start_response):
        req = Request(environ)
        if self.add_slash:
            url = req.path_url
            url += '/'
            if req.environ.get('QUERY_STRING'):
                url += '?' + req.environ['QUERY_STRING']
            self.location = url
        self.location = urlparse.urljoin(req.path_url, self.location)
        return super(_HTTPMove, self).__call__(
            environ, start_response)
    
class HTTPMultipleChoices(_HTTPMove):
    code = 300
    title = 'Multiple Choices'

class HTTPMovedPermanently(_HTTPMove):
    code = 301
    title = 'Moved Permanently'

class HTTPFound(_HTTPMove):
    code = 302
    title = 'Found'
    explanation = 'The resource was found at'

# This one is safe after a POST (the redirected location will be
# retrieved with GET):
class HTTPSeeOther(_HTTPMove):
    code = 303
    title = 'See Other'

class HTTPNotModified(HTTPRedirection):
    # FIXME: this should include a date or etag header
    code = 304
    title = 'Not Modified'
    empty_body = True

class HTTPUseProxy(_HTTPMove):
    # Not a move, but looks a little like one
    code = 305
    title = 'Use Proxy'
    explanation = (
        'The resource must be accessed through a proxy located at')

class HTTPTemporaryRedirect(_HTTPMove):
    code = 307
    title = 'Temporary Redirect'

############################################################
## 4xx client error
############################################################

class HTTPClientError(HTTPError):
    """
    base class for the 400's, where the client is in error

    This is an error condition in which the client is presumed to be
    in-error.  This is an expected problem, and thus is not considered
    a bug.  A server-side traceback is not warranted.  Unless specialized,
    this is a '400 Bad Request'
    """
    code = 400
    title = 'Bad Request'
    explanation = ('The server could not comply with the request since\r\n'
                   'it is either malformed or otherwise incorrect.\r\n')

class HTTPBadRequest(HTTPClientError):
    pass

class HTTPUnauthorized(HTTPClientError):
    code = 401
    title = 'Unauthorized'
    explanation = (
        'This server could not verify that you are authorized to\r\n'
        'access the document you requested.  Either you supplied the\r\n'
        'wrong credentials (e.g., bad password), or your browser\r\n'
        'does not understand how to supply the credentials required.\r\n')

class HTTPPaymentRequired(HTTPClientError):
    code = 402
    title = 'Payment Required'
    explanation = ('Access was denied for financial reasons.')

class HTTPForbidden(HTTPClientError):
    code = 403
    title = 'Forbidden'
    explanation = ('Access was denied to this resource.')

class HTTPNotFound(HTTPClientError):
    code = 404
    title = 'Not Found'
    explanation = ('The resource could not be found.')

class HTTPMethodNotAllowed(HTTPClientError):
    code = 405
    title = 'Method Not Allowed'
    # override template since we need an environment variable
    body_template_obj = Template('''\
The method ${REQUEST_METHOD} is not allowed for this resource. <br /><br />
${detail}''')

class HTTPNotAcceptable(HTTPClientError):
    code = 406
    title = 'Not Acceptable'
    # override template since we need an environment variable
    template = Template('''\
The resource could not be generated that was acceptable to your browser
(content of type ${HTTP_ACCEPT}. <br /><br />
${detail}''')

class HTTPProxyAuthenticationRequired(HTTPClientError):
    code = 407
    title = 'Proxy Authentication Required'
    explanation = ('Authentication with a local proxy is needed.')

class HTTPRequestTimeout(HTTPClientError):
    code = 408
    title = 'Request Timeout'
    explanation = ('The server has waited too long for the request to '
                   'be sent by the client.')

class HTTPConflict(HTTPClientError):
    code = 409
    title = 'Conflict'
    explanation = ('There was a conflict when trying to complete '
                   'your request.')

class HTTPGone(HTTPClientError):
    code = 410
    title = 'Gone'
    explanation = ('This resource is no longer available.  No forwarding '
                   'address is given.')

class HTTPLengthRequired(HTTPClientError):
    code = 411
    title = 'Length Required'
    explanation = ('Content-Length header required.')

class HTTPPreconditionFailed(HTTPClientError):
    code = 412
    title = 'Precondition Failed'
    explanation = ('Request precondition failed.')

class HTTPRequestEntityTooLarge(HTTPClientError):
    code = 413
    title = 'Request Entity Too Large'
    explanation = ('The body of your request was too large for this server.')

class HTTPRequestURITooLong(HTTPClientError):
    code = 414
    title = 'Request-URI Too Long'
    explanation = ('The request URI was too long for this server.')

class HTTPUnsupportedMediaType(HTTPClientError):
    code = 415
    title = 'Unsupported Media Type'
    # override template since we need an environment variable
    template_obj = Template('''\
The request media type ${CONTENT_TYPE} is not supported by this server.
<br /><br />
${detail}''')

class HTTPRequestRangeNotSatisfiable(HTTPClientError):
    code = 416
    title = 'Request Range Not Satisfiable'
    explanation = ('The Range requested is not available.')

class HTTPExpectationFailed(HTTPClientError):
    code = 417
    title = 'Expectation Failed'
    explanation = ('Expectation failed.')

class HTTPUnprocessableEntity(HTTPClientError):
    ## Note: from WebDAV
    code = 422
    title = 'Unprocessable Entity'
    explanation = 'Unable to process the contained instructions'

class HTTPLocked(HTTPClientError):
    ## Note: from WebDAV
    code = 423
    title = 'Locked'
    explanation = ('The resource is locked')

class HTTPFailedDependency(HTTPClientError):
    ## Note: from WebDAV
    code = 424
    title = 'Failed Dependency'
    explanation = ('The method could not be performed because the requested '
                   'action dependended on another action and that action failed')

############################################################
## 5xx Server Error
############################################################
#  Response status codes beginning with the digit "5" indicate cases in
#  which the server is aware that it has erred or is incapable of
#  performing the request. Except when responding to a HEAD request, the
#  server SHOULD include an entity containing an explanation of the error
#  situation, and whether it is a temporary or permanent condition. User
#  agents SHOULD display any included entity to the user. These response
#  codes are applicable to any request method.

class HTTPServerError(HTTPError):
    """
    base class for the 500's, where the server is in-error

    This is an error condition in which the server is presumed to be
    in-error.  This is usually unexpected, and thus requires a traceback;
    ideally, opening a support ticket for the customer. Unless specialized,
    this is a '500 Internal Server Error'
    """
    code = 500
    title = 'Internal Server Error'
    explanation = (
      'The server has either erred or is incapable of performing\r\n'
      'the requested operation.\r\n')

class HTTPInternalServerError(HTTPServerError):
    pass

class HTTPNotImplemented(HTTPServerError):
    code = 501
    title = 'Not Implemented'
    template = Template('''
The request method ${REQUEST_METHOD} is not implemented for this server. <br /><br />
${detail}''')

class HTTPBadGateway(HTTPServerError):
    code = 502
    title = 'Bad Gateway'
    explanation = ('Bad gateway.')

class HTTPServiceUnavailable(HTTPServerError):
    code = 503
    title = 'Service Unavailable'
    explanation = ('The server is currently unavailable. '
                   'Please try again at a later time.')

class HTTPGatewayTimeout(HTTPServerError):
    code = 504
    title = 'Gateway Timeout'
    explanation = ('The gateway has timed out.')

class HTTPVersionNotSupported(HTTPServerError):
    code = 505
    title = 'HTTP Version Not Supported'
    explanation = ('The HTTP version is not supported.')

class HTTPInsufficientStorage(HTTPServerError):
    code = 507
    title = 'Insufficient Storage'
    explanation = ('There was not enough space to save the resource')

class HTTPExceptionMiddleware(object):
    """
    Middleware that catches exceptions in the sub-application.  This
    does not catch exceptions in the app_iter; only during the initial
    calling of the application.

    This should be put *very close* to applications that might raise
    these exceptions.  This should not be applied globally; letting
    *expected* exceptions raise through the WSGI stack is dangerous.
    """

    def __init__(self, application):
        self.application = application
    def __call__(self, environ, start_response):
        try:
            return self.application(environ, start_response)
        except HTTPException, exc:
            parent_exc_info = sys.exc_info()
            def repl_start_response(status, headers, exc_info=None):
                if exc_info is None:
                    exc_info = parent_exc_info
                return start_response(status, headers, exc_info)
            return exc(environ, repl_start_response)

try:
    from paste import httpexceptions
except ImportError:
    # Without Paste we don't need to do this fixup
    pass
else:
    for name in dir(httpexceptions):
        obj = globals().get(name)
        if (obj and isinstance(obj, type) and issubclass(obj, HTTPException)
            and obj is not HTTPException
            and obj is not WSGIHTTPException):
            obj.__bases__ = obj.__bases__ + (getattr(httpexceptions, name),)
    del name, obj, httpexceptions

__all__ = ['HTTPExceptionMiddleware', 'status_map']
status_map={}
for name, value in globals().items():
    if (isinstance(value, (type, types.ClassType)) and issubclass(value, HTTPException)
        and not name.startswith('_')):
        __all__.append(name)
        if getattr(value, 'code', None):
            status_map[value.code]=value
del name, value

