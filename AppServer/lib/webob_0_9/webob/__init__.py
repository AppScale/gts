from cStringIO import StringIO
import sys
import cgi
import urllib
import urlparse
import re
import textwrap
from Cookie import BaseCookie
from rfc822 import parsedate_tz, mktime_tz, formatdate
from datetime import datetime, date, timedelta, tzinfo
import time
import calendar
import tempfile
import warnings
from webob.datastruct import EnvironHeaders
from webob.multidict import MultiDict, UnicodeMultiDict, NestedMultiDict, NoVars
from webob.etag import AnyETag, NoETag, ETagMatcher, IfRange, NoIfRange
from webob.headerdict import HeaderDict
from webob.statusreasons import status_reasons
from webob.cachecontrol import CacheControl, serialize_cache_control
from webob.acceptparse import Accept, MIMEAccept, NilAccept, MIMENilAccept, NoAccept
from webob.byterange import Range, ContentRange

_CHARSET_RE = re.compile(r';\s*charset=([^;]*)', re.I)
_SCHEME_RE = re.compile(r'^[a-z]+:', re.I)
_PARAM_RE = re.compile(r'([a-z0-9]+)=(?:"([^"]*)"|([a-z0-9_.-]*))', re.I)
_OK_PARAM_RE = re.compile(r'^[a-z0-9_.-]+$', re.I)

__all__ = ['Request', 'Response', 'UTC', 'day', 'week', 'hour', 'minute', 'second', 'month', 'year', 'html_escape']

class _UTC(tzinfo):
    def dst(self, dt):
        return timedelta(0)
    def utcoffset(self, dt):
        return timedelta(0)
    def tzname(self, dt):
        return 'UTC'
    def __repr__(self):
        return 'UTC'

UTC = _UTC()

def html_escape(s):
    """HTML-escape a string or object
    
    This converts any non-string objects passed into it to strings
    (actually, using ``unicode()``).  All values returned are
    non-unicode strings (using ``&#num;`` entities for all non-ASCII
    characters).
    
    None is treated specially, and returns the empty string.
    """
    if s is None:
        return ''
    if not isinstance(s, basestring):
        if hasattr(s, '__unicode__'):
            s = unicode(s)
        else:
            s = str(s)
    s = cgi.escape(s, True)
    if isinstance(s, unicode):
        s = s.encode('ascii', 'xmlcharrefreplace')
    return s

def timedelta_to_seconds(td):
    """
    Converts a timedelta instance to seconds.
    """
    return td.seconds + (td.days*24*60*60)

day = timedelta(days=1)
week = timedelta(weeks=1)
hour = timedelta(hours=1)
minute = timedelta(minutes=1)
second = timedelta(seconds=1)
# Estimate, I know; good enough for expirations
month = timedelta(days=30)
year = timedelta(days=365)

class _NoDefault:
    def __repr__(self):
        return '(No Default)'
NoDefault = _NoDefault()

class environ_getter(object):
    """For delegating an attribute to a key in self.environ."""

    def __init__(self, key, default='', default_factory=None,
                 settable=True, deletable=True, doc=None,
                 rfc_section=None):
        self.key = key
        self.default = default
        self.default_factory = default_factory
        self.settable = settable
        self.deletable = deletable
        docstring = "Gets"
        if self.settable:
            docstring += " and sets"
        if self.deletable:
            docstring += " and deletes"
        docstring += " the %r key from the environment." % self.key
        docstring += _rfc_reference(self.key, rfc_section)
        if doc:
            docstring += '\n\n' + textwrap.dedent(doc)
        self.__doc__ = docstring

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        if self.key not in obj.environ:
            if self.default_factory:
                val = obj.environ[self.key] = self.default_factory()
                return val
            else:
                return self.default
        return obj.environ[self.key]

    def __set__(self, obj, value):
        if not self.settable:
            raise AttributeError("Read-only attribute (key %r)" % self.key)
        if value is None:
            if self.key in obj.environ:
                del obj.environ[self.key]
        else:
            obj.environ[self.key] = value

    def __delete__(self, obj):
        if not self.deletable:
            raise AttributeError("You cannot delete the key %r" % self.key)
        del obj.environ[self.key]

    def __repr__(self):
        return '<Proxy for WSGI environ %r key>' % self.key

class header_getter(object):
    """For delegating an attribute to a header in self.headers"""

    def __init__(self, header, default=None,
                 settable=True, deletable=True, doc=None, rfc_section=None):
        self.header = header
        self.default = default
        self.settable = settable
        self.deletable = deletable
        docstring = "Gets"
        if self.settable:
            docstring += " and sets"
        if self.deletable:
            docstring += " and deletes"
        docstring += " they header %s from the headers" % self.header
        docstring += _rfc_reference(self.header, rfc_section)
        if doc:
            docstring += '\n\n' + textwrap.dedent(doc)
        self.__doc__ = docstring

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        if self.header not in obj.headers:
            return self.default
        else:
            return obj.headers[self.header]

    def __set__(self, obj, value):
        if not self.settable:
            raise AttributeError("Read-only attribute (header %s)" % self.header)
        if value is None:
            if self.header in obj.headers:
                del obj.headers[self.header]
        else:
            obj.headers[self.header] = value

    def __delete__(self, obj):
        if not self.deletable:
            raise AttributeError("You cannot delete the header %s" % self.header)
        del obj.headers[self.header]

    def __repr__(self):
        return '<Proxy for header %s>' % self.header

class converter(object):
    """
    Wraps a decorator, and applies conversion for that decorator
    """
    def __init__(self, decorator, getter_converter, setter_converter, convert_name=None, doc=None, converter_args=()):
        self.decorator = decorator
        self.getter_converter = getter_converter
        self.setter_converter = setter_converter
        self.convert_name = convert_name
        self.converter_args = converter_args
        docstring = decorator.__doc__ or ''
        docstring += "  Converts it as a "
        if convert_name:
            docstring += convert_name + '.'
        else:
            docstring += "%r and %r." % (getter_converter, setter_converter)
        if doc:
            docstring += '\n\n' + textwrap.dedent(doc)
        self.__doc__ = docstring

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        value = self.decorator.__get__(obj, type)
        return self.getter_converter(value, *self.converter_args)

    def __set__(self, obj, value):
        value = self.setter_converter(value, *self.converter_args)
        self.decorator.__set__(obj, value)

    def __delete__(self, obj):
        self.decorator.__delete__(obj)

    def __repr__(self):
        if self.convert_name:
            name = ' %s' % self.convert_name
        else:
            name = ''
        return '<Converted %r%s>' % (self.decorator, name)

def _rfc_reference(header, section):
    if not section:
        return ''
    major_section = section.split('.')[0]
    link = 'http://www.w3.org/Protocols/rfc2616/rfc2616-sec%s.html#sec%s' % (
        major_section, section)
    if header.startswith('HTTP_'):
        header = header[5:].title().replace('_', '-')
    return "  For more information on %s see `section %s <%s>`_." % (
        header, section, link)

class deprecated_property(object):
    """
    Wraps a decorator, with a deprecation warning or error
    """
    def __init__(self, decorator, attr, message, warning=True):
        self.decorator = decorator
        self.attr = attr
        self.message = message
        self.warning = warning

    def __get__(self, obj, type=None):
        if obj is None:
            return self
        self.warn()
        return self.decorator.__get__(obj, type)

    def __set__(self, obj, value):
        self.warn()
        self.decorator.__set__(obj, value)

    def __delete__(self, obj):
        self.warn()
        self.decorator.__delete__(obj)

    def __repr__(self):
        return '<Deprecated attribute %s: %r>' % (
            self.attr,
            self.decorator)

    def warn(self):
        if not self.warning:
            raise DeprecationWarning(
                'The attribute %s is deprecated: %s' % (self.attr, self.message))
        else:
            warnings.warn(
                'The attribute %s is deprecated: %s' % (self.attr, self.message),
                DeprecationWarning,
                stacklevel=3)

def _parse_date(value):
    if not value:
        return None
    t = parsedate_tz(value)
    if t is None:
        # Could not parse
        return None
    t = mktime_tz(t)
    return datetime.fromtimestamp(t, UTC)

def _serialize_date(dt):
    if dt is None:
        return None
    if isinstance(dt, unicode):
        dt = dt.encode('ascii')
    if isinstance(dt, str):
        return dt
    if isinstance(dt, timedelta):
        dt = datetime.now() + dt
    if isinstance(dt, (datetime, date)):
        dt = dt.timetuple()
    if isinstance(dt, (tuple, time.struct_time)):
        dt = calendar.timegm(dt)
    if not isinstance(dt, (float, int)):
        raise ValueError(
            "You must pass in a datetime, date, time tuple, or integer object, not %r" % dt)
    return formatdate(dt)

def _parse_date_delta(value):
    """
    like _parse_date, but also handle delta seconds
    """
    if not value:
        return None
    try:
        value = int(value)
    except ValueError:
        pass
    else:
        delta = timedelta(seconds=value)
        return datetime.now() + delta
    return _parse_date(value)

def _serialize_date_delta(value):
    if not value and value != 0:
        return None
    if isinstance(value, (float, int)):
        return str(int(value))
    return _serialize_date(value)

def _parse_etag(value, default=True):
    if value is None:
        value = ''
    value = value.strip()
    if not value:
        if default:
            return AnyETag
        else:
            return NoETag
    if value == '*':
        return AnyETag
    else:
        return ETagMatcher.parse(value)

def _serialize_etag(value, default=True):
    if value is None:
        return None
    if value is AnyETag:
        if default:
            return None
        else:
            return '*'
    return str(value)

def _parse_if_range(value):
    if not value:
        return NoIfRange
    else:
        return IfRange.parse(value)

def _serialize_if_range(value):
    if value is None:
        return value
    if isinstance(value, (datetime, date)):
        return _serialize_date(value)
    if not isinstance(value, str):
        value = str(value)
    return value or None

def _parse_range(value):
    if not value:
        return None
    # Might return None too:
    return Range.parse(value)

def _serialize_range(value):
    if isinstance(value, (list, tuple)):
        if len(value) != 2:
            raise ValueError(
                "If setting .range to a list or tuple, it must be of length 2 (not %r)"
                % value)
        value = Range([value])
    if value is None:
        return None
    value = str(value)
    return value or None

def _parse_int(value):
    if value is None or value == '':
        return None
    return int(value)

def _parse_int_safe(value):
    if value is None or value == '':
        return None
    try:
        return int(value)
    except ValueError:
        return None

def _serialize_int(value):
    if value is None:
        return None
    return str(value)

def _parse_content_range(value):
    if not value or not value.strip():
        return None
    # May still return None
    return ContentRange.parse(value)

def _serialize_content_range(value):
    if value is None:
        return None
    if isinstance(value, (tuple, list)):
        if len(value) not in (2, 3):
            raise ValueError(
                "When setting content_range to a list/tuple, it must "
                "be length 2 or 3 (not %r)" % value)
        if len(value) == 2:
            begin, end = value
            length = None
        else:
            begin, end, length = value
        value = ContentRange(begin, end, length)
    value = str(value).strip()
    if not value:
        return None
    return value

def _parse_list(value):
    if value is None:
        return None
    value = value.strip()
    if not value:
        return None
    return [v.strip() for v in value.split(',')
            if v.strip()]

def _serialize_list(value):
    if not value:
        return None
    if isinstance(value, unicode):
        value = str(value)
    if isinstance(value, str):
        return value
    return ', '.join(map(str, value))

def _parse_accept(value, header_name, AcceptClass, NilClass):
    if not value:
        return NilClass(header_name)
    return AcceptClass(header_name, value)

def _serialize_accept(value, header_name, AcceptClass, NilClass):
    if not value or isinstance(value, NilClass):
        return None
    if isinstance(value, (list, tuple, dict)):
        value = NilClass(header_name) + value
    value = str(value).strip()
    if not value:
        return None
    return value

class Request(object):

    ## Options:
    charset = None
    unicode_errors = 'strict'
    decode_param_names = False
    ## The limit after which request bodies should be stored on disk
    ## if they are read in (under this, and the request body is stored
    ## in memory):
    request_body_tempfile_limit = 10*1024

    def __init__(self, environ=None, environ_getter=None, charset=NoDefault, unicode_errors=NoDefault,
                 decode_param_names=NoDefault):
        if environ is None and environ_getter is None:
            raise TypeError(
                "You must provide one of environ or environ_getter")
        if environ is not None and environ_getter is not None:
            raise TypeError(
                "You can only provide one of the environ and environ_getter arguments")
        if environ is None:
            self._environ_getter = environ_getter
        else:
            if not isinstance(environ, dict):
                raise TypeError(
                    "Bad type for environ: %s" % type(environ))
            self._environ = environ
        if charset is not NoDefault:
            self.__dict__['charset'] = charset
        if unicode_errors is not NoDefault:
            self.__dict__['unicode_errors'] = unicode_errors
        if decode_param_names is not NoDefault:
            self.__dict__['decode_param_names'] = decode_param_names

    def __setattr__(self, attr, value, DEFAULT=[]):
        ## FIXME: I don't know why I need this guard (though experimentation says I do)
        if getattr(self.__class__, attr, DEFAULT) is not DEFAULT or attr.startswith('_'):
            object.__setattr__(self, attr, value)
        else:
            self.environ.setdefault('webob.adhoc_attrs', {})[attr] = value

    def __getattr__(self, attr):
        ## FIXME: I don't know why I need this guard (though experimentation says I do)
        if attr in self.__class__.__dict__:
            return object.__getattribute__(self, attr)
        try:
            return self.environ['webob.adhoc_attrs'][attr]
        except KeyError:
            raise AttributeError(attr)

    def __delattr__(self, attr):
        ## FIXME: I don't know why I need this guard (though experimentation says I do)
        if attr in self.__class__.__dict__:
            return object.__delattr__(self, attr)
        try:
            del self.environ['webob.adhoc_attrs'][attr]
        except KeyError:
            raise AttributeError(attr)

    def environ(self):
        """
        The WSGI environment dictionary for this request
        """
        return self._environ_getter()
    environ = property(environ, doc=environ.__doc__)

    def _environ_getter(self):
        return self._environ

    def _body_file__get(self):
        """
        Access the body of the request (wsgi.input) as a file-like
        object.

        If you set this value, CONTENT_LENGTH will also be updated
        (either set to -1, 0 if you delete the attribute, or if you
        set the attribute to a string then the length of the string).
        """
        return self.environ['wsgi.input']
    def _body_file__set(self, value):
        if isinstance(value, str):
            length = len(value)
            value = StringIO(value)
        else:
            length = -1
        self.environ['wsgi.input'] = value
        self.environ['CONTENT_LENGTH'] = str(length)
    def _body_file__del(self):
        self.environ['wsgi.input'] = StringIO('')
        self.environ['CONTENT_LENGTH'] = '0'
    body_file = property(_body_file__get, _body_file__set, _body_file__del, doc=_body_file__get.__doc__)

    scheme = environ_getter('wsgi.url_scheme')
    method = environ_getter('REQUEST_METHOD')
    script_name = environ_getter('SCRIPT_NAME')
    path_info = environ_getter('PATH_INFO')
    ## FIXME: should I strip out parameters?:
    content_type = environ_getter('CONTENT_TYPE', rfc_section='14.17')
    content_length = converter(
        environ_getter('CONTENT_LENGTH', rfc_section='14.13'),
        _parse_int_safe, _serialize_int, 'int')
    remote_user = environ_getter('REMOTE_USER', default=None)
    remote_addr = environ_getter('REMOTE_ADDR', default=None)
    query_string = environ_getter('QUERY_STRING')
    server_name = environ_getter('SERVER_NAME')
    server_port = converter(
        environ_getter('SERVER_PORT'),
        _parse_int, _serialize_int, 'int')

    _headers = None

    def _headers__get(self):
        """
        All the request headers as a case-insensitive dictionary-like
        object.
        """
        if self._headers is None:
            self._headers = EnvironHeaders(self.environ)
        return self._headers

    def _headers__set(self, value):
        self.headers.clear()
        self.headers.update(value)

    headers = property(_headers__get, _headers__set, doc=_headers__get.__doc__)

    def host_url(self):
        """
        The URL through the host (no path)
        """
        e = self.environ
        url = e['wsgi.url_scheme'] + '://'
        if e.get('HTTP_HOST'):
            host = e['HTTP_HOST']
            if ':' in host:
                host, port = host.split(':', 1)
            else:

                port = None
        else:
            host = e['SERVER_NAME']
            port = e['SERVER_PORT']
        if self.environ['wsgi.url_scheme'] == 'https':
            if port == '443':
                port = None
        elif self.environ['wsgi.url_scheme'] == 'http':
            if port == '80':
                port = None
        url += host
        if port:
            url += ':%s' % port
        return url
    host_url = property(host_url, doc=host_url.__doc__)

    def application_url(self):
        """
        The URL including SCRIPT_NAME (no PATH_INFO or query string)
        """
        return self.host_url + urllib.quote(self.environ.get('SCRIPT_NAME', ''))
    application_url = property(application_url, doc=application_url.__doc__)

    def path_url(self):
        """
        The URL including SCRIPT_NAME and PATH_INFO, but not QUERY_STRING
        """
        return self.application_url + urllib.quote(self.environ.get('PATH_INFO', ''))
    path_url = property(path_url, doc=path_url.__doc__)

    def path(self):
        """
        The path of the request, without host or query string
        """
        return urllib.quote(self.script_name) + urllib.quote(self.path_info)
    path = property(path, doc=path.__doc__)

    def path_qs(self):
        """
        The path of the request, without host but with query string
        """
        path = self.path
        qs = self.environ.get('QUERY_STRING')
        if qs:
            path += '?' + qs
        return path
    path_qs = property(path_qs, doc=path_qs.__doc__)

    def url(self):
        """
        The full request URL, including QUERY_STRING
        """
        url = self.path_url
        if self.environ.get('QUERY_STRING'):
            url += '?' + self.environ['QUERY_STRING']
        return url
    url = property(url, doc=url.__doc__)

    def relative_url(self, other_url, to_application=False):
        """
        Resolve other_url relative to the request URL.

        If ``to_application`` is True, then resolve it relative to the
        URL with only SCRIPT_NAME
        """
        if to_application:
            url = self.application_url
            if not url.endswith('/'):
                url += '/'
        else:
            url = self.path_url
        return urlparse.urljoin(url, other_url)

    def path_info_pop(self):
        """
        'Pops' off the next segment of PATH_INFO, pushing it onto
        SCRIPT_NAME, and returning the popped segment.  Returns None if
        there is nothing left on PATH_INFO.

        Does not return ``''`` when there's an empty segment (like
        ``/path//path``); these segments are just ignored.
        """
        path = self.path_info
        if not path:
            return None
        while path.startswith('/'):
            self.script_name += '/'
            path = path[1:]
        if '/' not in path:
            self.script_name += path
            self.path_info = ''
            return path
        else:
            segment, path = path.split('/', 1)
            self.path_info = '/' + path
            self.script_name += segment
            return segment

    def path_info_peek(self):
        """
        Returns the next segment on PATH_INFO, or None if there is no
        next segment.  Doesn't modify the environment.
        """
        path = self.path_info
        if not path:
            return None
        path = path.lstrip('/')
        return path.split('/', 1)[0]

    def _urlvars__get(self):
        """
        Return any *named* variables matched in the URL.

        Takes values from ``environ['wsgiorg.routing_args']``.
        Systems like ``routes`` set this value.
        """
        if 'paste.urlvars' in self.environ:
            return self.environ['paste.urlvars']
        elif 'wsgiorg.routing_args' in self.environ:
            return self.environ['wsgiorg.routing_args'][1]
        else:
            result = {}
            self.environ['wsgiorg.routing_args'] = ((), result)
            return result

    def _urlvars__set(self, value):
        environ = self.environ
        if 'wsgiorg.routing_args' in environ:
            environ['wsgiorg.routing_args'] = (environ['wsgiorg.routing_args'][0], value)
            if 'paste.urlvars' in environ:
                del environ['paste.urlvars']
        elif 'paste.urlvars' in environ:
            environ['paste.urlvars'] = value
        else:
            environ['wsgiorg.routing_args'] = ((), value)

    def _urlvars__del(self):
        if 'paste.urlvars' in self.environ:
            del self.environ['paste.urlvars']
        if 'wsgiorg.routing_args' in self.environ:
            if not self.environ['wsgiorg.routing_args'][0]:
                del self.environ['wsgiorg.routing_args']
            else:
                self.environ['wsgiorg.routing_args'] = (self.environ['wsgiorg.routing_args'][0], {})
            
    urlvars = property(_urlvars__get, _urlvars__set, _urlvars__del, doc=_urlvars__get.__doc__)

    def _urlargs__get(self):
        """
        Return any *positional* variables matched in the URL.

        Takes values from ``environ['wsgiorg.routing_args']``.
        Systems like ``routes`` set this value.
        """
        if 'wsgiorg.routing_args' in self.environ:
            return self.environ['wsgiorg.routing_args'][0]
        else:
            # Since you can't update this value in-place, we don't need
            # to set the key in the environment
            return ()

    def _urlargs__set(self, value):
        environ = self.environ
        if 'paste.urlvars' in environ:
            # Some overlap between this and wsgiorg.routing_args; we need
            # wsgiorg.routing_args to make this work
            routing_args = (value, environ.pop('paste.urlvars'))
        elif 'wsgiorg.routing_args' in environ:
            routing_args = (value, environ['wsgiorg.routing_args'][1])
        else:
            routing_args = (value, {})
        environ['wsgiorg.routing_args'] = routing_args

    def _urlargs__del(self):
        if 'wsgiorg.routing_args' in self.environ:
            if not self.environ['wsgiorg.routing_args'][1]:
                del self.environ['wsgiorg.routing_args']
            else:
                self.environ['wsgiorg.routing_args'] = ((), self.environ['wsgiorg.routing_args'][1])

    urlargs = property(_urlargs__get, _urlargs__set, _urlargs__del, _urlargs__get.__doc__)

    def is_xhr(self):
        """Returns a boolean if X-Requested-With is present and ``XMLHttpRequest``

        Note: this isn't set by every XMLHttpRequest request, it is
        only set if you are using a Javascript library that sets it
        (or you set the header yourself manually).  Currently
        Prototype and jQuery are known to set this header."""
        return self.environ.get('HTTP_X_REQUESTED_WITH', '') == 'XMLHttpRequest'
    is_xhr = property(is_xhr, doc=is_xhr.__doc__)

    def _host__get(self):
        """Host name provided in HTTP_HOST, with fall-back to SERVER_NAME"""
        if 'HTTP_HOST' in self.environ:
            return self.environ['HTTP_HOST']
        else:
            return '%(SERVER_NAME)s:%(SERVER_PORT)s' % self.environ
    def _host__set(self, value):
        self.environ['HTTP_HOST'] = value
    def _host__del(self):
        if 'HTTP_HOST' in self.environ:
            del self.environ['HTTP_HOST']
    host = property(_host__get, _host__set, _host__del, doc=_host__get.__doc__)

    def _body__get(self):
        """
        Return the content of the request body.
        """
        try:
            length = int(self.environ.get('CONTENT_LENGTH', '0'))
        except ValueError:
            return ''
        c = self.body_file.read(length)
        tempfile_limit = self.request_body_tempfile_limit
        if tempfile_limit and len(c) > tempfile_limit:
            fileobj = tempfile.TemporaryFile()
            fileobj.write(c)
            fileobj.seek(0)
        else:
            fileobj = StringIO(c)
        # We don't want/need to lose CONTENT_LENGTH here (as setting
        # self.body_file would do):
        self.environ['wsgi.input'] = fileobj
        return c

    def _body__set(self, value):
        if value is None:
            del self.body
            return
        if not isinstance(value, str):
            raise TypeError(
                "You can only set Request.body to a str (not %r)" % type(value))
        body_file = StringIO(value)
        self.body_file = body_file
        self.environ['CONTENT_LENGTH'] = str(len(value))

    def _body__del(self, value):
        del self.body_file

    body = property(_body__get, _body__set, _body__del, doc=_body__get.__doc__)

    def str_POST(self):
        """
        Return a MultiDict containing all the variables from a POST
        form request.  Does *not* return anything for non-POST
        requests or for non-form requests (returns empty dict-like
        object in that case).
        """
        env = self.environ
        if self.method != 'POST':
            return NoVars('Not a POST request')
        if 'webob._parsed_post_vars' in env:
            vars, body_file = env['webob._parsed_post_vars']
            if body_file is self.body_file:
                return vars
        # Paste compatibility:
        if 'paste.parsed_formvars' in env:
            # from paste.request.parse_formvars
            vars, body_file = env['paste.parsed_formvars']
            if body_file is self.body_file:
                # FIXME: is it okay that this isn't *our* MultiDict?
                return vars
        content_type = self.content_type
        if ';' in content_type:
            content_type = content_type.split(';', 1)[0]
        if content_type not in ('', 'application/x-www-form-urlencoded',
                                'multipart/form-data'):
            # Not an HTML form submission
            return NoVars('Not an HTML form submission (Content-Type: %s)'
                          % content_type)
        if 'CONTENT_LENGTH' not in env:
            # FieldStorage assumes a default CONTENT_LENGTH of -1, but a
            # default of 0 is better:
            env['CONTENT_TYPE'] = '0'
        fs_environ = env.copy()
        fs_environ['QUERY_STRING'] = ''
        fs = cgi.FieldStorage(fp=self.body_file,
                              environ=fs_environ,
                              keep_blank_values=True)
        vars = MultiDict.from_fieldstorage(fs)
        FakeCGIBody.update_environ(env, vars)
        env['webob._parsed_post_vars'] = (vars, self.body_file)
        return vars

    str_POST = property(str_POST, doc=str_POST.__doc__)

    str_postvars = deprecated_property(str_POST, 'str_postvars',
                                       'use str_POST instead')

    def POST(self):
        """
        Like ``.str_POST``, but may decode values and keys
        """
        vars = self.str_POST
        if self.charset:
            vars = UnicodeMultiDict(vars, encoding=self.charset,
                                    errors=self.unicode_errors,
                                    decode_keys=self.decode_param_names)
        return vars

    POST = property(POST, doc=POST.__doc__)

    postvars = deprecated_property(POST, 'postvars',
                                   'use POST instead')

    def str_GET(self):
        """
        Return a MultiDict containing all the variables from the
        QUERY_STRING.
        """
        env = self.environ
        source = env.get('QUERY_STRING', '')
        if 'webob._parsed_query_vars' in env:
            vars, qs = env['webob._parsed_query_vars']
            if qs == source:
                return vars
        if not source:
            vars = MultiDict()
        else:
            vars = MultiDict(cgi.parse_qsl(
                source, keep_blank_values=True,
                strict_parsing=False))
        env['webob._parsed_query_vars'] = (vars, source)
        return vars

    str_GET = property(str_GET, doc=str_GET.__doc__)

    str_queryvars = deprecated_property(str_GET, 'str_queryvars',
                                        'use str_GET instead')
                                        

    def GET(self):
        """
        Like ``.str_GET``, but may decode values and keys
        """
        vars = self.str_GET
        if self.charset:
            vars = UnicodeMultiDict(vars, encoding=self.charset,
                                    errors=self.unicode_errors,
                                    decode_keys=self.decode_param_names)
        return vars

    GET = property(GET, doc=GET.__doc__)

    queryvars = deprecated_property(GET, 'queryvars',
                                    'use GET instead')

    def str_params(self):
        """
        A dictionary-like object containing both the parameters from
        the query string and request body.
        """
        return NestedMultiDict(self.str_GET, self.str_POST)

    str_params = property(str_params, doc=str_params.__doc__)

    def params(self):
        """
        Like ``.str_params``, but may decode values and keys
        """
        params = self.str_params
        if self.charset:
            params = UnicodeMultiDict(params, encoding=self.charset,
                                      errors=self.unicode_errors,
                                      decode_keys=self.decode_param_names)
        return params

    params = property(params, doc=params.__doc__)

    def str_cookies(self):
        """
        Return a *plain* dictionary of cookies as found in the request.
        """
        env = self.environ
        source = env.get('HTTP_COOKIE', '')
        if 'webob._parsed_cookies' in env:
            vars, var_source = env['webob._parsed_cookies']
            if var_source == source:
                return vars
        vars = {}
        if source:
            cookies = BaseCookie()
            cookies.load(source)
            for name in cookies:
                vars[name] = cookies[name].value
        env['webob._parsed_cookies'] = (vars, source)
        return vars

    str_cookies = property(str_cookies, doc=str_cookies.__doc__)

    def cookies(self):
        """
        Like ``.str_cookies``, but may decode values and keys
        """
        vars = self.str_cookies
        if self.charset:
            vars = UnicodeMultiDict(vars, encoding=self.charset,
                                    errors=self.unicode_errors,
                                    decode_keys=self.decode_param_names)
        return vars

    cookies = property(cookies, doc=cookies.__doc__)

    def copy(self):
        """
        Copy the request and environment object.

        This only does a shallow copy, except of wsgi.input
        """
        env = self.environ.copy()
        data = self.body
        tempfile_limit = self.request_body_tempfile_limit
        if tempfile_limit and len(data) > tempfile_limit:
            fileobj = tempfile.TemporaryFile()
            fileobj.write(data)
            fileobj.seek(0)
        else:
            fileobj = StringIO(data)
        env['wsgi.input'] = fileobj
        return self.__class__(env)

    def copy_get(self):
        """
        Copies the request and environment object, but turning this request
        into a GET along the way.  If this was a POST request (or any other verb)
        then it becomes GET, and the request body is thrown away.
        """
        env = self.environ.copy()
        env['wsgi.input'] = StringIO('')
        env['CONTENT_LENGTH'] = '0'
        if 'CONTENT_TYPE' in env:
            del env['CONTENT_TYPE']
        env['REQUEST_METHOD'] = 'GET'
        return self.__class__(env)

    def remove_conditional_headers(self, remove_encoding=True):
        """
        Remove headers that make the request conditional.

        These headers can cause the response to be 304 Not Modified,
        which in some cases you may not want to be possible.

        This does not remove headers like If-Match, which are used for
        conflict detection.
        """
        for key in ['HTTP_IF_MATCH', 'HTTP_IF_MODIFIED_SINCE',
                    'HTTP_IF_RANGE', 'HTTP_RANGE']:
            if key in self.environ:
                del self.environ[key]
        if remove_encoding:
            if 'HTTP_ACCEPT_ENCODING' in self.environ:
                del self.environ['HTTP_ACCEPT_ENCODING']

    accept = converter(
        environ_getter('HTTP_ACCEPT', rfc_section='14.1'),
        _parse_accept, _serialize_accept, 'MIME Accept',
        converter_args=('Accept', MIMEAccept, MIMENilAccept))

    accept_charset = converter(
        environ_getter('HTTP_ACCEPT_CHARSET', rfc_section='14.2'),
        _parse_accept, _serialize_accept, 'accept header',
        converter_args=('Accept-Charset', Accept, NilAccept))

    accept_encoding = converter(
        environ_getter('HTTP_ACCEPT_ENCODING', rfc_section='14.3'),
        _parse_accept, _serialize_accept, 'accept header',
        converter_args=('Accept-Encoding', Accept, NoAccept))

    accept_language = converter(
        environ_getter('HTTP_ACCEPT_LANGUAGE', rfc_section='14.4'),
        _parse_accept, _serialize_accept, 'accept header',
        converter_args=('Accept-Language', Accept, NilAccept))

    ## FIXME: 14.8 Authorization
    ## http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.8

    def _cache_control__get(self):
        """
        Get/set/modify the Cache-Control header (section `14.9
        <http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.9>`_)
        """
        env = self.environ
        value = env.get('HTTP_CACHE_CONTROL', '')
        cache_header, cache_obj = env.get('webob._cache_control', (None, None))
        if cache_obj is not None and cache_header == value:
            return cache_obj
        cache_obj = CacheControl.parse(value, type='request')
        env['webob._cache_control'] = (value, cache_obj)
        return cache_obj

    def _cache_control__set(self, value):
        env = self.environ
        if not value:
            value = ""
        if isinstance(value, dict):
            value = CacheControl(value, type='request')
        elif isinstance(value, CacheControl):
            str_value = str(value)
            env['HTTP_CACHE_CONTROL'] = str_value
            env['webob._cache_control'] = (str_value, value)
        else:
            env['HTTP_CACHE_CONTROL'] = str(value)
            if 'webob._cache_control' in env:
                del env['webob._cache_control']

    def _cache_control__del(self, value):
        env = self.environ
        if 'HTTP_CACHE_CONTROL' in env:
            del env['HTTP_CACHE_CONTROL']
        if 'webob._cache_control' in env:
            del env['webob._cache_control']

    cache_control = property(_cache_control__get, _cache_control__set, _cache_control__del, doc=_cache_control__get.__doc__)

    date = converter(
        environ_getter('HTTP_DATE', rfc_section='14.8'),
        _parse_date, _serialize_date, 'HTTP date')

    if_match = converter(
        environ_getter('HTTP_IF_MATCH', rfc_section='14.24'),
        _parse_etag, _serialize_etag, 'ETag', converter_args=(True,))

    if_modified_since = converter(
        environ_getter('HTTP_IF_MODIFIED_SINCE', rfc_section='14.25'),
        _parse_date, _serialize_date, 'HTTP date')

    if_none_match = converter(
        environ_getter('HTTP_IF_NONE_MATCH', rfc_section='14.26'),
        _parse_etag, _serialize_etag, 'ETag', converter_args=(False,))

    if_range = converter(
        environ_getter('HTTP_IF_RANGE', rfc_section='14.27'),
        _parse_if_range, _serialize_if_range, 'IfRange object')

    if_unmodified_since = converter(
        environ_getter('HTTP_IF_UNMODIFIED_SINCE', rfc_section='14.28'),
        _parse_date, _serialize_date, 'HTTP date')

    max_forwards = converter(
        environ_getter('HTTP_MAX_FORWARDS', rfc_section='14.31'),
        _parse_int, _serialize_int, 'int')

    pragma = environ_getter('HTTP_PRAGMA', rfc_section='14.32')

    range = converter(
        environ_getter('HTTP_RANGE', rfc_section='14.35'),
        _parse_range, _serialize_range, 'Range object')

    referer = environ_getter('HTTP_REFERER', rfc_section='14.36')
    referrer = referer

    user_agent = environ_getter('HTTP_USER_AGENT', rfc_section='14.43')

    def __repr__(self):
        msg = '<%s at %x %s %s>' % (
            self.__class__.__name__,
            abs(id(self)), self.method, self.url)
        return msg

    def __str__(self):
        url = self.url
        host = self.host_url
        assert url.startswith(host)
        url = url[len(host):]
        if 'Host' not in self.headers:
            self.headers['Host'] = self.host
        parts = ['%s %s' % (self.method, url)]
        for name, value in sorted(self.headers.items()):
            parts.append('%s: %s' % (name, value))
        parts.append('')
        parts.append(self.body)
        return '\r\n'.join(parts)

    def call_application(self, application, catch_exc_info=False):
        """
        Call the given WSGI application, returning ``(status_string,
        headerlist, app_iter)``

        Be sure to call ``app_iter.close()`` if it's there.

        If catch_exc_info is true, then returns ``(status_string,
        headerlist, app_iter, exc_info)``, where the fourth item may
        be None, but won't be if there was an exception.  If you don't
        do this and there was an exception, the exception will be
        raised directly.
        """
        captured = []
        output = []
        def start_response(status, headers, exc_info=None):
            if exc_info is not None and not catch_exc_info:
                raise exc_info[0], exc_info[1], exc_info[2]
            captured[:] = [status, headers, exc_info]
            return output.append
        app_iter = application(self.environ, start_response)
        if (not captured
            or output):
            try:
                output.extend(app_iter)
            finally:
                if hasattr(app_iter, 'close'):
                    app_iter.close()
            app_iter = output
        if catch_exc_info:
            return (captured[0], captured[1], app_iter, captured[2])
        else:
            return (captured[0], captured[1], app_iter)

    # Will be filled in later:
    ResponseClass = None

    def get_response(self, application, catch_exc_info=False):
        """
        Like ``.call_application(application)``, except returns a
        response object with ``.status``, ``.headers``, and ``.body``
        attributes.

        This will use ``self.ResponseClass`` to figure out the class
        of the response object to return.
        """
        if catch_exc_info:
            status, headers, app_iter, exc_info = self.call_application(
                application, catch_exc_info=True)
            del exc_info
        else:
            status, headers, app_iter = self.call_application(
                application, catch_exc_info=False)
        return self.ResponseClass(
            status=status, headerlist=headers, app_iter=app_iter,
            request=self)

    #@classmethod
    def blank(cls, path, environ=None, base_url=None, headers=None):
        """
        Create a blank request environ (and Request wrapper) with the
        given path (path should be urlencoded), and any keys from
        environ.

        The path will become path_info, with any query string split
        off and used.

        All necessary keys will be added to the environ, but the
        values you pass in will take precedence.  If you pass in
        base_url then wsgi.url_scheme, HTTP_HOST, and SCRIPT_NAME will
        be filled in from that value.
        """
        if _SCHEME_RE.search(path):
            scheme, netloc, path, qs, fragment = urlparse.urlsplit(path)
            if fragment:
                raise TypeError(
                    "Path cannot contain a fragment (%r)" % fragment)
            if qs:
                path += '?' + qs
            if ':' not in netloc:
                if scheme == 'http':
                    netloc += ':80'
                elif scheme == 'https':
                    netloc += ':443'
                else:
                    raise TypeError("Unknown scheme: %r" % scheme)
        else:
            scheme = 'http'
            netloc = 'localhost:80'
        if path and '?' in path:
            path_info, query_string = path.split('?', 1)
            path_info = urllib.unquote(path_info)
        else:
            path_info = urllib.unquote(path)
            query_string = ''
        env = {
            'REQUEST_METHOD': 'GET',
            'SCRIPT_NAME': '',
            'PATH_INFO': path_info or '',
            'QUERY_STRING': query_string,
            'SERVER_NAME': netloc.split(':')[0],
            'SERVER_PORT': netloc.split(':')[1],
            'HTTP_HOST': netloc,
            'SERVER_PROTOCOL': 'HTTP/1.0',
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': scheme,
            'wsgi.input': StringIO(''),
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
            }
        if base_url:
            scheme, netloc, path, query, fragment = urlparse.urlsplit(base_url)
            if query or fragment:
                raise ValueError(
                    "base_url (%r) cannot have a query or fragment"
                    % base_url)
            if scheme:
                env['wsgi.url_scheme'] = scheme
            if netloc:
                if ':' not in netloc:
                    if scheme == 'http':
                        netloc += ':80'
                    elif scheme == 'https':
                        netloc += ':443'
                    else:
                        raise ValueError(
                            "Unknown scheme: %r" % scheme)
                host, port = netloc.split(':', 1)
                env['SERVER_PORT'] = port
                env['SERVER_NAME'] = host
                env['HTTP_HOST'] = netloc
            if path:
                env['SCRIPT_NAME'] = urllib.unquote(path)
        if environ:
            env.update(environ)
        obj = cls(env)
        if headers is not None:
            obj.headers.update(headers)
        return obj

    blank = classmethod(blank)

class Response(object):

    """
    Represents a WSGI response
    """

    default_content_type = 'text/html'
    default_charset = 'utf8'
    default_conditional_response = False

    def __init__(self, body=None, status='200 OK', headerlist=None, app_iter=None,
                 request=None, content_type=None, conditional_response=NoDefault,
                 **kw):
        if app_iter is None:
            if body is None:
                body = ''
        elif body is not None:
            raise TypeError(
                "You may only give one of the body and app_iter arguments")
        self.status = status
        if headerlist is None:
            self._headerlist = []
        else:
            self._headerlist = headerlist
        self._headers = None
        if request is not None:
            if hasattr(request, 'environ'):
                self._environ = request.environ
                self._request = request
            else:
                self._environ = request
                self._request = None
        else:
            self._environ = self._request = None
        if content_type is not None:
            self.content_type = content_type
        elif self.default_content_type is not None and headerlist is None:
            self.content_type = self.default_content_type
        if conditional_response is NoDefault:
            self.conditional_response = self.default_conditional_response
        else:
            self.conditional_response = conditional_response
        if 'charset' in kw:
            # We set this early, so something like unicode_body works later
            value = kw.pop('charset')
            if value:
                self.charset = value
        elif self.default_charset and not self.charset and headerlist is None:
            ct = self.content_type
            if ct and (ct.startswith('text/') or ct.startswith('application/xml')
                       or (ct.startswith('application/') and ct.endswith('+xml'))):
                self.charset = self.default_charset
        if app_iter is not None:
            self._app_iter = app_iter
            self._body = None
        else:
            if isinstance(body, unicode):
                self.unicode_body = body
            else:
                self.body = body
            self._app_iter = None
        for name, value in kw.items():
            if not hasattr(self.__class__, name):
                # Not a basic attribute
                raise TypeError(
                    "Unexpected keyword: %s=%r in %r" % (name, value))
            setattr(self, name, value)

    def __repr__(self):
        return '<%s %x %s>' % (
            self.__class__.__name__,
            abs(id(self)),
            self.status)

    def __str__(self):
        return (self.status + '\n'
                + '\n'.join(['%s: %s' % (name, value)
                             for name, value in self.headerlist])
                + '\n\n'
                + self.body)

    def _status__get(self):
        """
        The status string
        """
        return self._status

    def _status__set(self, value):
        if isinstance(value, int):
            value = str(value)
        if not isinstance(value, str):
            raise TypeError(
                "You must set status to a string or integer (not %s)"
                % type(value))
        if ' ' not in value:
            # Need to add a reason:
            code = int(value)
            reason = status_reasons[code]
            value += ' ' + reason
        self._status = value

    status = property(_status__get, _status__set, doc=_status__get.__doc__)

    def _status_int__get(self):
        """
        The status as an integer
        """
        return int(self.status.split()[0])
    def _status_int__set(self, value):
        self.status = value
    status_int = property(_status_int__get, _status_int__set, doc=_status_int__get.__doc__)

    def _headerlist__get(self):
        """
        The list of response headers
        """
        return self._headerlist

    def _headerlist__set(self, value):
        self._headers = None
        if not isinstance(value, list):
            if hasattr(value, 'items'):
                value = value.items()
            value = list(value)
        self._headerlist = value

    def _headerlist__del(self):
        self.headerlist = []

    headerlist = property(_headerlist__get, _headerlist__set, _headerlist__del, doc=_headerlist__get.__doc__)

    def _charset__get(self):
        """
        Get/set the charset (in the Content-Type)
        """
        header = self.headers.get('content-type')
        if not header:
            return None
        match = _CHARSET_RE.search(header)
        if match:
            return match.group(1)
        return None

    def _charset__set(self, charset):
        if charset is None:
            del self.charset
            return
        try:
            header = self.headers.pop('content-type')
        except KeyError:
            raise AttributeError(
                "You cannot set the charset when no content-type is defined")
        match = _CHARSET_RE.search(header)
        if match:
            header = header[:match.start()] + header[match.end():]
        header += '; charset=%s' % charset
        self.headers['content-type'] = header

    def _charset__del(self):
        try:
            header = self.headers.pop('content-type')
        except KeyError:
            # Don't need to remove anything
            return
        match = _CHARSET_RE.search(header)
        if match:
            header = header[:match.start()] + header[match.end():]
        self.headers['content-type'] = header

    charset = property(_charset__get, _charset__set, _charset__del, doc=_charset__get.__doc__)

    def _content_type__get(self):
        """
        Get/set the Content-Type header (or None), *without* the
        charset or any parameters.

        If you include parameters (or ``;`` at all) when setting the
        content_type, any existing parameters will be deleted;
        otherwise they will be preserved.
        """
        header = self.headers.get('content-type')
        if not header:
            return None
        return header.split(';', 1)[0]

    def _content_type__set(self, value):
        if ';' not in value:
            header = self.headers.get('content-type', '')
            if ';' in header:
                params = header.split(';', 1)[1]
                value += ';' + params
        self.headers['content-type'] = value

    def _content_type__del(self):
        try:
            del self.headers['content-type']
        except KeyError:
            pass

    content_type = property(_content_type__get, _content_type__set,
                            _content_type__del, doc=_content_type__get.__doc__)

    def _content_type_params__get(self):
        """
        Returns a dictionary of all the parameters in the content type.
        """
        params = self.headers.get('content-type', '')
        if ';' not in params:
            return {}
        params = params.split(';', 1)[1]
        result = {}
        for match in _PARAM_RE.finditer(params):
            result[match.group(1)] = match.group(2) or match.group(3) or ''
        return result
        
    def _content_type_params__set(self, value_dict):
        if not value_dict:
            del self.content_type_params
            return
        params = []
        for k, v in sorted(value_dict.items()):
            if not _OK_PARAM_RE.search(v):
                ## FIXME: I'm not sure what to do with "'s in the parameter value
                ## I think it might be simply illegal
                v = '"%s"' % v.replace('"', '\\"')
            params.append('; %s=%s' % (k, v))
        ct = self.headers.pop('content-type', '').split(';', 1)[0]
        ct += ''.join(params)
        self.headers['content-type'] = ct

    def _content_type_params__del(self, value):
        self.headers['content-type'] = self.headers.get('content-type', '').split(';', 1)[0]

    content_type_params = property(_content_type_params__get, _content_type_params__set, _content_type_params__del, doc=_content_type_params__get.__doc__)

    def _headers__get(self):
        """
        The headers in a dictionary-like object
        """
        if self._headers is None:
            self._headers = HeaderDict.view_list(self.headerlist)
        return self._headers

    def _headers__set(self, value):
        if hasattr(value, 'items'):
            value = value.items()
        self.headerlist = value
        self._headers = None

    headers = property(_headers__get, _headers__set, doc=_headers__get.__doc__)

    def _body__get(self):
        """
        The body of the response, as a ``str``.  This will read in the
        entire app_iter if necessary.
        """
        if self._body is None:
            if self._app_iter is None:
                raise AttributeError(
                    "No body has been set")
            try:
                self._body = ''.join(self._app_iter)
            finally:
                if hasattr(self._app_iter, 'close'):
                    self._app_iter.close()
            self._app_iter = None
            self.content_length = len(self._body)
        return self._body

    def _body__set(self, value):
        if isinstance(value, unicode):
            raise TypeError(
                "You cannot set Response.body to a unicode object (use Response.unicode_body)")
        if not isinstance(value, str):
            raise TypeError(
                "You can only set the body to a str (not %s)"
                % type(value))
        self._body = value
        self.content_length = len(value)
        self._app_iter = None

    def _body__del(self):
        self._body = None
        self.content_length = None
        self._app_iter = None

    body = property(_body__get, _body__set, _body__del, doc=_body__get.__doc__)

    def _body_file__get(self):
        """
        Returns a file-like object that can be used to write to the
        body.  If you passed in a list app_iter, that app_iter will be
        modified by writes.
        """
        return ResponseBodyFile(self)

    def _body_file__del(self):
        del self.body

    body_file = property(_body_file__get, fdel=_body_file__del, doc=_body_file__get.__doc__)

    def write(self, text):
        if isinstance(text, unicode):
            self.unicode_body += text
        else:
            self.body += text

    def _unicode_body__get(self):
        """
        Get/set the unicode value of the body (using the charset of the Content-Type)
        """
        if not self.charset:
            raise AttributeError(
                "You cannot access Response.unicode_body unless charset is set")
        body = self.body
        return body.decode(self.charset)

    def _unicode_body__set(self, value):
        if not self.charset:
            raise AttributeError(
                "You cannot access Response.unicode_body unless charset is set")
        if not isinstance(value, unicode):
            raise TypeError(
                "You can only set Response.unicode_body to a unicode string (not %s)" % type(value))
        self.body = value.encode(self.charset)

    def _unicode_body__del(self):
        del self.body

    unicode_body = property(_unicode_body__get, _unicode_body__set, _unicode_body__del, doc=_unicode_body__get.__doc__)

    def _app_iter__get(self):
        """
        Returns the app_iter of the response.

        If body was set, this will create an app_iter from that body
        (a single-item list)
        """
        if self._app_iter is None:
            if self._body is None:
                raise AttributeError(
                    "No body or app_iter has been set")
            return [self._body]
        else:
            return self._app_iter

    def _app_iter__set(self, value):
        if self._body is not None:
            # Undo the automatically-set content-length
            self.content_length = None
        self._app_iter = value
        self._body = None

    def _app_iter__del(self):
        self.content_length = None
        self._app_iter = self._body = None

    app_iter = property(_app_iter__get, _app_iter__set, _app_iter__del, doc=_app_iter__get.__doc__)

    def set_cookie(self, key, value='', max_age=None,
                   path='/', domain=None, secure=None, httponly=False,
                   version=None, comment=None):
        """
        Set (add) a cookie for the response
        """
        cookies = BaseCookie()
        cookies[key] = value
        for var_name, var_value in [
            ('max_age', max_age),
            ('path', path),
            ('domain', domain),
            ('secure', secure),
            ('HttpOnly', httponly),
            ('version', version),
            ('comment', comment),
            ]:
            if var_value is not None and var_value is not False:
                cookies[key][var_name.replace('_', '-')] = str(var_value)
        header_value = cookies[key].output(header='').lstrip()
        self.headerlist.append(('Set-Cookie', header_value))

    def delete_cookie(self, key, path='/', domain=None):
        """
        Delete a cookie from the client.  Note that path and domain must match
        how the cookie was originally set.

        This sets the cookie to the empty string, and max_age=0 so
        that it should expire immediately.
        """
        self.set_cookie(key, '', path=path, domain=domain,
                        max_age=0)

    def unset_cookie(self, key):
        """
        Unset a cookie with the given name (remove it from the
        response).  If there are multiple cookies (e.g., two cookies
        with the same name and different paths or domains), all such
        cookies will be deleted.
        """
        existing = self.headers.getall('Set-Cookie')
        if not existing:
            raise KeyError(
                "No cookies at all have been set")
        del self.headers['Set-Cookie']
        found = False
        for header in existing:
            cookies = BaseCookie()
            cookies.load(header)
            if key in cookies:
                found = True
                del cookies[key]
            header = cookies.output(header='').lstrip()
            if header:
                self.headers.add('Set-Cookie', header)
        if not found:
            raise KeyError(
                "No cookie has been set with the name %r" % key)

    def _location__get(self):
        """
        Retrieve the Location header of the response, or None if there
        is no header.  If the header is not absolute and this response
        is associated with a request, make the header absolute.

        For more information see `section 14.30
        <http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.30>`_.
        """
        if 'location' not in self.headers:
            return None
        location = self.headers['location']
        if _SCHEME_RE.search(location):
            # Absolute
            return location
        if self.request is not None:
            base_uri = self.request.url
            location = urlparse.urljoin(base_uri, location)
        return location

    def _location__set(self, value):
        if not _SCHEME_RE.search(value):
            # Not absolute, see if we can make it absolute
            if self.request is not None:
                value = urlparse.urljoin(self.request.url, value)
        self.headers['location'] = value

    def _location__del(self):
        if 'location' in self.headers:
            del self.headers['location']

    location = property(_location__get, _location__set, _location__del, doc=_location__get.__doc__)

    accept_ranges = header_getter('Accept-Ranges', rfc_section='14.5')

    age = converter(
        header_getter('Age', rfc_section='14.6'),
        _parse_int_safe, _serialize_int, 'int')

    allow = converter(
        header_getter('Allow', rfc_section='14.7'),
        _parse_list, _serialize_list, 'list')

    _cache_control_obj = None

    def _cache_control__get(self):
        """
        Get/set/modify the Cache-Control header (section `14.9
        <http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.9>`_)
        """
        value = self.headers.get('cache-control', '')
        if self._cache_control_obj is None:
            self._cache_control_obj = CacheControl.parse(value, updates_to=self._update_cache_control, type='response')
            self._cache_control_obj.header_value = value
        if self._cache_control_obj.header_value != value:
            new_obj = CacheControl.parse(value, type='response')
            self._cache_control_obj.properties.clear()
            self._cache_control_obj.properties.update(new_obj.properties)
            self._cache_control_obj.header_value = value
        return self._cache_control_obj

    def _cache_control__set(self, value):
        # This actually becomes a copy
        if not value:
            value = ""
        if isinstance(value, dict):
            value = CacheControl(value, 'response')
        if isinstance(value, unicode):
            value = str(value)
        if isinstance(value, str):
            if self._cache_control_obj is None:
                self.headers['Cache-Control'] = value
                return
            value = CacheControl.parse(value, 'response')
        cache = self.cache_control
        cache.properties.clear()
        cache.properties.update(value.properties)

    def _cache_control__del(self):
        self.cache_control = {}

    def _update_cache_control(self, prop_dict):
        value = serialize_cache_control(prop_dict)
        if not value:
            if 'Cache-Control' in self.headers:
                del self.headers['Cache-Control']
        else:
            self.headers['Cache-Control'] = value

    cache_control = property(_cache_control__get, _cache_control__set, _cache_control__del, doc=_cache_control__get.__doc__)

    def cache_expires(self, seconds=0, **kw):
        """
        Set expiration on this request.  This sets the response to
        expire in the given seconds, and any other attributes are used
        for cache_control (e.g., private=True, etc).
        """
        cache_control = self.cache_control
        if isinstance(seconds, timedelta):
            seconds = timedelta_to_seconds(seconds)
        if not seconds:
            # To really expire something, you have to force a
            # bunch of these cache control attributes, and IE may
            # not pay attention to those still so we also set
            # Expires.
            cache_control.no_store = True
            cache_control.no_cache = True
            cache_control.must_revalidate = True
            cache_control.max_age = 0
            cache_control.post_check = 0
            cache_control.pre_check = 0
            self.expires = datetime.utcnow()
            if 'last-modified' not in self.headers:
                self.last_modified = datetime.utcnow()
            self.pragma = 'no-cache'
        else:
            cache_control.max_age = seconds
            self.expires = datetime.utcnow() + timedelta(seconds=seconds)
        for name, value in kw.items():
            setattr(cache_control, name, value)

    content_encoding = header_getter('Content-Encoding', rfc_section='14.11')

    def encode_content(self, encoding='gzip'):
        """
        Encode the content with the given encoding (only gzip and
        identity are supported).
        """
        if encoding == 'identity':
            return
        if encoding != 'gzip':
            raise ValueError(
                "Unknown encoding: %r" % encoding)
        if self.content_encoding:
            if self.content_encoding == encoding:
                return
            self.decode_content()
        from webob.util.safegzip import GzipFile
        f = StringIO()
        gzip_f = GzipFile(filename='', mode='w', fileobj=f)
        gzip_f.write(self.body)
        gzip_f.close()
        new_body = f.getvalue()
        f.close()
        self.content_encoding = 'gzip'
        self.body = new_body

    def decode_content(self):
        content_encoding = self.content_encoding
        if not content_encoding or content_encoding == 'identity':
            return
        if content_encoding != 'gzip':
            raise ValueError(
                "I don't know how to decode the content %s" % content_encoding)
        from webob.util.safegzip import GzipFile
        f = StringIO(self.body)
        gzip_f = GzipFile(filename='', mode='r', fileobj=f)
        new_body = gzip_f.read()
        gzip_f.close()
        f.close()
        self.content_encoding = None
        self.body = new_body

    content_language = converter(
        header_getter('Content-Language', rfc_section='14.12'),
        _parse_list, _serialize_list, 'list')

    content_location = header_getter(
        'Content-Location', rfc_section='14.14')

    content_md5 = header_getter(
        'Content-MD5', rfc_section='14.14')

    content_range = converter(
        header_getter('Content-Range', rfc_section='14.16'),
        _parse_content_range, _serialize_content_range, 'ContentRange object')

    content_length = converter(
        header_getter('Content-Length', rfc_section='14.17'),
        _parse_int, _serialize_int, 'int')

    date = converter(
        header_getter('Date', rfc_section='14.18'),
        _parse_date, _serialize_date, 'HTTP date')

    etag = header_getter('ETag', rfc_section='14.19')

    def md5_etag(self, body=None):
        """
        Generate an etag for the response object using an MD5 hash of
        the body (the body parameter, or ``self.body`` if not given)

        Sets ``self.etag``
        """
        if body is None:
            body = self.body
        import md5
        h = md5.new(body)
        self.etag = h.digest().encode('base64').replace('\n', '').strip('=')

    expires = converter(
        header_getter('Expires', rfc_section='14.21'),
        _parse_date, _serialize_date, 'HTTP date')

    last_modified = converter(
        header_getter('Last-Modified', rfc_section='14.29'),
        _parse_date, _serialize_date, 'HTTP date')

    pragma = header_getter('Pragma', rfc_section='14.32')

    retry_after = converter(
        header_getter('Retry-After', rfc_section='14.37'),
        _parse_date_delta, _serialize_date_delta, 'HTTP date or delta seconds')

    server = header_getter('Server', rfc_section='14.38')

    ## FIXME: I realize response.vary += 'something' won't work.  It should.
    ## Maybe for all listy headers.
    vary = converter(
        header_getter('Vary', rfc_section='14.44'),
        _parse_list, _serialize_list, 'list')

    ## FIXME: 14.47 WWW-Authenticate
    ## http://www.w3.org/Protocols/rfc2616/rfc2616-sec14.html#sec14.47


    def _request__get(self):
        """
        Return the request associated with this response if any.
        """
        if self._request is None and self._environ is not None:
            self._request = self.RequestClass(self._environ)
        return self._request

    def _request__set(self, value):
        if value is None:
            del self.request
            return
        if isinstance(value, dict):
            self._environ = value
            self._request = None
        else:
            self._request = value
            self._environ = value.environ

    def _request__del(self):
        self._request = self._environ = None

    request = property(_request__get, _request__set, _request__del, doc=_request__get.__doc__)

    def _environ__get(self):
        """
        Get/set the request environ associated with this response, if
        any.
        """
        return self._environ

    def _environ__set(self, value):
        if value is None:
            del self.environ
        self._environ = value
        self._request = None

    def _environ__del(self):
        self._request = self._environ = None

    environ = property(_environ__get, _environ__set, _environ__del, doc=_environ__get.__doc__)

    def __call__(self, environ, start_response):
        """
        WSGI application interface
        """
        if self.conditional_response:
            return self.conditional_response_app(environ, start_response)
        start_response(self.status, self.headerlist)
        if environ['REQUEST_METHOD'] == 'HEAD':
            # Special case here...
            return []
        return self.app_iter

    _safe_methods = ('GET', 'HEAD')

    def conditional_response_app(self, environ, start_response):
        """
        Like the normal __call__ interface, but checks conditional headers:

        * If-Modified-Since   (304 Not Modified; only on GET, HEAD)
        * If-None-Match       (304 Not Modified; only on GET, HEAD)
        * Range               (406 Partial Content; only on GET, HEAD)
        """
        req = self.RequestClass(environ)
        status304 = False
        if req.method in self._safe_methods:
            if req.if_modified_since and self.last_modified and self.last_modified <= req.if_modified_since:
                status304 = True
            if req.if_none_match and self.etag:
                ## FIXME: should a weak match be okay?
                if self.etag in req.if_none_match:
                    status304 = True
                else:
                    # Even if If-Modified-Since matched, if ETag doesn't then reject it
                    status304 = False
        if status304:
            start_response('304 Not Modified', self.headerlist)
            return []
        if req.method == 'HEAD':
            start_response(self.status, self.headerlist)
            return []
        if (req.range and req.if_range.match_response(self)
            and self.content_range is None
            and req.method == 'GET'
            and self.status_int == 200):
            content_range = req.range.content_range(self.content_length)
            if content_range is not None:
                app_iter = self.app_iter_range(content_range.start, content_range.stop)
                if app_iter is not None:
                    headers = list(self.headerlist)
                    headers.append(('Content-Range', str(content_range)))
                    start_response('206 Partial Content', headers)
                    return app_iter
        start_response(self.status, self.headerlist)
        return self.app_iter

    def app_iter_range(self, start, stop):
        """
        Return a new app_iter built from the response app_iter, that
        serves up only the given ``start:stop`` range.
        """
        if self._app_iter is None:
            return [self.body[start:stop]]
        app_iter = self.app_iter
        if hasattr(app_iter, 'app_iter_range'):
            return app_iter.app_iter_range(start, stop)
        return AppIterRange(app_iter, start, stop)
        
        
Request.ResponseClass = Response
Response.RequestClass = Request

def _cgi_FieldStorage__repr__patch(self):
    """ monkey patch for FieldStorage.__repr__

    Unbelievely, the default __repr__ on FieldStorage reads
    the entire file content instead of being sane about it.
    This is a simple replacement that doesn't do that
    """
    if self.file:
        return "FieldStorage(%r, %r)" % (
                self.name, self.filename)
    return "FieldStorage(%r, %r, %r)" % (
             self.name, self.filename, self.value)

cgi.FieldStorage.__repr__ = _cgi_FieldStorage__repr__patch

class FakeCGIBody(object):

    def __init__(self, vars):
        self.vars = vars
        self._body = None
        self.position = 0

    def read(self, size=-1):
        body = self._get_body()
        if size == -1:
            v = body[self.position:]
            self.position = len(body)
            return v
        else:
            v = body[self.position:self.position+size]
            self.position = min(len(body), self.position+size)
            return v

    def _get_body(self):
        if self._body is None:
            self._body = urllib.urlencode(self.vars.items())
        return self._body

    def readline(self, size=None):
        # We ignore size, but allow it to be hinted
        rest = self._get_body()[self.position:]
        next = rest.find('\r\n')
        if next == -1:
            return self.read()
        self.position += next+2
        return rest[:next+2]

    def readlines(self, hint=None):
        # Again, allow hint but ignore
        body = self._get_body()
        rest = body[self.position:]
        self.position = len(body)
        result = []
        while 1:
            next = rest.find('\r\n')
            if next == -1:
                result.append(rest)
                break
            result.append(rest[:next+2])
            rest = rest[next+2:]
        return result

    def __iter__(self):
        return iter(self.readlines())

    def __repr__(self):
        inner = repr(self.vars)
        if len(inner) > 20:
            inner = inner[:15] + '...' + inner[-5:]
        return '<%s at %x viewing %s>' % (
            self.__class__.__name__,
            abs(id(self)), inner)

    #@classmethod
    def update_environ(cls, environ, vars):
        obj = cls(vars)
        environ['CONTENT_LENGTH'] = '-1'
        environ['wsgi.input'] = obj

    update_environ = classmethod(update_environ)

class ResponseBodyFile(object):

    def __init__(self, response):
        self.response = response

    def __repr__(self):
        return '<body_file for %r>' % (
            self.response)

    def close(self):
        raise NotImplementedError(
            "Response bodies cannot be closed")

    def flush(self):
        pass

    def write(self, s):
        if isinstance(s, unicode):
            if self.response.charset is not None:
                s = s.encode(self.response.charset)
            else:
                raise TypeError(
                    "You can only write unicode to Response.body_file "
                    "if charset has been set")
        if not isinstance(s, str):
            raise TypeError(
                "You can only write str to a Response.body_file, not %s"
                % type(s))
        if not isinstance(self.response._app_iter, list):
            body = self.response.body
            if body:
                self.response.app_iter = [body]
            else:
                self.response.app_iter = []
        self.response.app_iter.append(s)

    def writelines(self, seq):
        for item in seq:
            self.write(item)
        
    closed = False

    def encoding(self):
        """
        The encoding of the file (inherited from response.charset)
        """
        return self.response.charset

    encoding = property(encoding, doc=encoding.__doc__)

    mode = 'wb'

class AppIterRange(object):
    """
    Wraps an app_iter, returning just a range of bytes
    """

    def __init__(self, app_iter, start, stop):
        assert start >= 0, "Bad start: %r" % start
        assert stop is None or (stop >= 0 and stop >= start), (
            "Bad stop: %r" % stop)
        self.app_iter = app_iter
        self.app_iterator = iter(app_iter)
        self.start = start
        if stop is None:
            self.length = -1
        else:
            self.length = stop - start
        if start:
            self._served = None
        else:
            self._served = 0
        if hasattr(app_iter, 'close'):
            self.close = app_iter.close

    def __iter__(self):
        return self

    def next(self):
        if self._served is None:
            # Haven't served anything; need to skip some leading bytes
            skipped = 0
            start = self.start
            while 1:
                chunk = self.app_iterator.next()
                skipped += len(chunk)
                extra = skipped - start
                if extra == 0:
                    self._served = 0
                    break
                elif extra > 0:
                    self._served = extra
                    return chunk[-extra:]
        length = self.length
        if length is None:
            # Spent
            raise StopIteration
        chunk = self.app_iterator.next()
        if length == -1:
            return chunk
        if self._served + len(chunk) > length:
            extra = self._served + len(chunk) - length
            self.length = None
            return chunk[:-extra]
        self._served += len(chunk)
        return chunk
            
