import cgi, warnings
from webob.headers import _trans_key

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
    if hasattr(s, '__html__'):
        return s.__html__()
    if not isinstance(s, basestring):
        if hasattr(s, '__unicode__'):
            s = unicode(s)
        else:
            s = str(s)
    s = cgi.escape(s, True)
    if isinstance(s, unicode):
        s = s.encode('ascii', 'xmlcharrefreplace')
    return s

def header_docstring(header, rfc_section):
    if header.isupper():
        header = _trans_key(header)
    major_section = rfc_section.split('.')[0]
    link = 'http://www.w3.org/Protocols/rfc2616/rfc2616-sec%s.html#sec%s' % (major_section, rfc_section)
    return "Gets and sets the ``%s`` header (`HTTP spec section %s <%s>`_)." \
        % (header, rfc_section, link)

def warn_deprecation(text, version, stacklevel):
    # version specifies when to start raising exceptions instead of warnings
    if version == '1.2':
        cls = DeprecationWarning
    elif version == '1.3':
        cls = PendingDeprecationWarning
    else:
        cls = DeprecationWarning
        warnings.warn("Unknown warn_deprecation version arg: %r" % version,
            RuntimeWarning,
            stacklevel=1
        )
    warnings.warn(text, cls, stacklevel=stacklevel+1)

status_reasons = {
    # Status Codes
    # Informational
    100: 'Continue',
    101: 'Switching Protocols',
    102: 'Processing',

    # Successful
    200: 'OK',
    201: 'Created',
    202: 'Accepted',
    203: 'Non-Authoritative Information',
    204: 'No Content',
    205: 'Reset Content',
    206: 'Partial Content',
    207: 'Multi Status',
    226: 'IM Used',

    # Redirection
    300: 'Multiple Choices',
    301: 'Moved Permanently',
    302: 'Found',
    303: 'See Other',
    304: 'Not Modified',
    305: 'Use Proxy',
    307: 'Temporary Redirect',

    # Client Error
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
    414: 'Request URI Too Long',
    415: 'Unsupported Media Type',
    416: 'Requested Range Not Satisfiable',
    417: 'Expectation Failed',
    422: 'Unprocessable Entity',
    423: 'Locked',
    424: 'Failed Dependency',
    426: 'Upgrade Required',

    # Server Error
    500: 'Internal Server Error',
    501: 'Not Implemented',
    502: 'Bad Gateway',
    503: 'Service Unavailable',
    504: 'Gateway Timeout',
    505: 'HTTP Version Not Supported',
    507: 'Insufficient Storage',
    510: 'Not Extended',
}
