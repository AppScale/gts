"""
Represents the response header list as a dictionary-like object.
"""

from webob.multidict import MultiDict
try:
    reversed
except NameError:
    from webob.util.reversed import reversed

class HeaderDict(MultiDict):

    """
    Like a MultiDict, this wraps a list.  Keys are normalized
    for case and whitespace.
    """

    def normalize(self, key):
        return str(key).lower().strip()

    def __getitem__(self, key):
        normalize = self.normalize
        key = normalize(key)
        for k, v in reversed(self._items):
            if normalize(k) == key:
                return v
        raise KeyError(key)

    def getall(self, key):
        normalize = self.normalize
        key = normalize(key)
        result = []
        for k, v in self._items:
            if normalize(k) == key:
                result.append(v)
        return result

    def mixed(self):
        result = {}
        multi = {}
        normalize = self.normalize
        for key, value in self.iteritems():
            key = normalize(key)
            if key in result:
                if key in multi:
                    result[key].append(value)
                else:
                    result[key] = [result[key], value]
                    multi[key] = None
            else:
                result[key] = value
        return result

    def dict_of_lists(self):
        result = {}
        normalize = self.normalize
        for key, value in self.iteritems():
            key = normalize(key)
            if key in result:
                result[key].append(value)
            else:
                result[key] = [value]
        return result

    def __delitem__(self, key):
        normalize = self.normalize
        key = normalize(key)
        items = self._items
        found = False
        for i in range(len(items)-1, -1, -1):
            if normalize(items[i][0]) == key:
                del items[i]
                found = True
        if not found:
            raise KeyError(key)

    def __contains__(self, key):
        normalize = self.normalize
        key = normalize(key)
        for k, v in self._items:
            if normalize(k) == key:
                return True
        return False

    has_key = __contains__

    def setdefault(self, key, default=None):
        normalize = self.normalize
        c_key = normalize(key)
        for k, v in self._items:
            if normalize(k) == c_key:
                return v
        self._items.append((key, default))
        return default

    def pop(self, key, *args):
        if len(args) > 1:
            raise TypeError, "pop expected at most 2 arguments, got "\
                              + repr(1 + len(args))
        key = self.normalize(key)
        for i in range(len(self._items)):
            if self.normalize(self._items[i][0]) == key:
                v = self._items[i][1]
                del self._items[i]
                return v
        if args:
            return args[0]
        else:
            raise KeyError(key)

