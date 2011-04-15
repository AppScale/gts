"""
Contains some data structures.
"""

from webob.util.dictmixin import DictMixin

class EnvironHeaders(DictMixin):
    """An object that represents the headers as present in a
    WSGI environment.

    This object is a wrapper (with no internal state) for a WSGI
    request object, representing the CGI-style HTTP_* keys as a
    dictionary.  Because a CGI environment can only hold one value for
    each key, this dictionary is single-valued (unlike outgoing
    headers).
    """

    def __init__(self, environ):
        self.environ = environ

    def _trans_name(self, name):
        key = 'HTTP_'+name.replace('-', '_').upper()
        if key == 'HTTP_CONTENT_LENGTH':
            key = 'CONTENT_LENGTH'
        elif key == 'HTTP_CONTENT_TYPE':
            key = 'CONTENT_TYPE'
        return key

    def _trans_key(self, key):
        if key == 'CONTENT_TYPE':
            return 'Content-Type'
        elif key == 'CONTENT_LENGTH':
            return 'Content-Length'
        elif key.startswith('HTTP_'):
            return key[5:].replace('_', '-').title()
        else:
            return None
        
    def __getitem__(self, item):
        return self.environ[self._trans_name(item)]

    def __setitem__(self, item, value):
        self.environ[self._trans_name(item)] = value

    def __delitem__(self, item):
        del self.environ[self._trans_name(item)]

    def __iter__(self):
        for key in self.environ:
            name = self._trans_key(key)
            if name is not None:
                yield name

    def keys(self):
        return list(iter(self))

    def __contains__(self, item):
        return self._trans_name(item) in self.environ
