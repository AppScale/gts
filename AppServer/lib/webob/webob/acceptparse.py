"""
Parses a variety of ``Accept-*`` headers.

These headers generally take the form of::

    value1; q=0.5, value2; q=0

Where the ``q`` parameter is optional.  In theory other parameters
exists, but this ignores them.
"""

import re

part_re = re.compile(
    r',\s*([^\s;,\n]+)(?:[^,]*?;\s*q=([0-9.]*))?')

def parse_accept(value):
    """
    Parses an ``Accept-*`` style header.

    A list of ``[(value, quality), ...]`` is returned.  ``quality``
    will be 1 if it was not given.
    """
    result = []
    for match in part_re.finditer(','+value):
        name = match.group(1)
        if name == 'q':
            continue
        quality = match.group(2) or ''
        if not quality:
            quality = 1
        else:
            try:
                quality = max(min(float(quality), 1), 0)
            except ValueError:
                quality = 1
        result.append((name, quality))
    return result

class Accept(object):
    """
    Represents a generic ``Accept-*`` style header.

    This object should not be modified.  To add items you can use
    ``accept_obj + 'accept_thing'`` to get a new object
    """

    def __init__(self, header_name, header_value):
        self.header_name = header_name
        self.header_value = header_value
        self._parsed = parse_accept(header_value)

    def __repr__(self):
        return '<%s at %x %s: %s>' % (
            self.__class__.__name__,
            abs(id(self)),
            self.header_name, str(self))

    def __str__(self):
        result = []
        for match, quality in self._parsed:
            if quality != 1:
                match = '%s;q=%0.1f' % (match, quality)
            result.append(match)
        return ', '.join(result)

    # FIXME: should subtraction be allowed?
    def __add__(self, other, reversed=False):
        if isinstance(other, Accept):
            other = other.header_value
        if hasattr(other, 'items'):
            other = sorted(other.items(), key=lambda item: -item[1])
        if isinstance(other, (list, tuple)):
            result = []
            for item in other:
                if isinstance(item, (list, tuple)):
                    name, quality = item
                    result.append('%s; q=%s' % (name, quality))
                else:
                    result.append(item)
            other = ', '.join(result)
        other = str(other)
        my_value = self.header_value
        if reversed:
            other, my_value = my_value, other
        if not other:
            new_value = my_value
        elif not my_value:
            new_value = other
        else:
            new_value = my_value + ', ' + other
        return self.__class__(self.header_name, new_value)

    def __radd__(self, other):
        return self.__add__(other, True)

    def __contains__(self, match):
        """
        Returns true if the given object is listed in the accepted
        types.
        """
        for item, quality in self._parsed:
            if self._match(item, match):
                return True

    def quality(self, match):
        """
        Return the quality of the given match.  Returns None if there
        is no match (not 0).
        """
        for item, quality in self._parsed:
            if self._match(item, match):
                return quality
        return None
    
    def first_match(self, matches):
        """
        Returns the first match in the sequences of matches that is
        allowed.  Ignores quality.  Returns the first item if nothing
        else matches; or if you include None at the end of the match
        list then that will be returned.
        """
        if not matches:
            raise ValueError(
                "You must pass in a non-empty list")
        for match in matches:
            for item, quality in self._parsed:
                if self._match(item, match):
                    return match
            if match is None:
                return None
        return matches[0]
    
    def best_match(self, matches, default_match=None):
        """
        Returns the best match in the sequence of matches.

        The sequence can be a simple sequence, or you can have
        ``(match, server_quality)`` items in the sequence.  If you
        have these tuples then the client quality is multiplied by the
        server_quality to get a total.

        default_match (default None) is returned if there is no intersection.
        """
        best_quality = -1
        best_match = default_match
        for match_item in matches:
            if isinstance(match_item, (tuple, list)):
                match, server_quality = match_item
            else:
                match = match_item
                server_quality = 1
            for item, quality in self._parsed:
                possible_quality = server_quality * quality
                if possible_quality < best_quality:
                    continue
                if self._match(item, match):
                    best_quality = possible_quality
                    best_match = match
        return best_match

    def best_matches(self, fallback=None):
        """
        Return all the matches in order of quality, with fallback (if
        given) at the end.
        """
        items = [
            i for i, q in sorted(self._parsed, key=lambda iq: -iq[1])]
        if fallback:
            for index, item in enumerate(items):
                if self._match(item, fallback):
                    items[index+1:] = []
                    break
            else:
                items.append(fallback)
        return items

    def _match(self, item, match):
        return item.lower() == match.lower() or item == '*'

class NilAccept(object):

    """
    Represents an Accept header with no value.
    """

    MasterClass = Accept

    def __init__(self, header_name):
        self.header_name = header_name

    def __repr__(self):
        return '<%s for %s: %s>' % (
            self.__class__.__name__, self.header_name, self.MasterClass)

    def __str__(self):
        return ''

    def __add__(self, item):
        if isinstance(item, self.MasterClass):
            return item
        else:
            return self.MasterClass(self.header_name, '') + item

    def __radd__(self, item):
        if isinstance(item, self.MasterClass):
            return item
        else:
            return item + self.MasterClass(self.header_name, '')

    def __contains__(self, item):
        return True

    def quality(self, match, default_quality=1):
        return 0

    def first_match(self, matches):
        return matches[0]

    def best_match(self, matches, default_match=None):
        best_quality = -1
        best_match = default_match
        for match_item in matches:
            if isinstance(match_item, (list, tuple)):
                match, quality = match_item
            else:
                match = match_item
                quality = 1
            if quality > best_quality:
                best_match = match
                best_quality = quality
        return best_match

    def best_matches(self, fallback=None):
        if fallback:
            return [fallback]
        else:
            return []

class NoAccept(NilAccept):

    def __contains__(self, item):
        return False

class MIMEAccept(Accept):

    """
    Represents the ``Accept`` header, which is a list of mimetypes.

    This class knows about mime wildcards, like ``image/*``
    """

    def _match(self, item, match):
        item = item.lower()
        if item == '*':
            item = '*/*'
        match = match.lower()
        if match == '*':
            match = '*/*'
        if '/' not in item:
            # Bad, but we ignore
            return False
        if '/' not in match:
            raise ValueError(
                "MIME matches must include / (bad: %r)" % match)
        item_major, item_minor = item.split('/', 1)
        match_major, match_minor = match.split('/', 1)
        if match_major == '*' and match_minor != '*':
            raise ValueError(
                "A MIME type of %r doesn't make sense" % match)
        if item_major == '*' and item_minor != '*':
            # Bad, but we ignore
            return False
        if ((item_major == '*' and item_minor == '*')
            or (match_major == '*' and match_minor == '*')):
            return True
        if (item_major == match_major
            and ((item_minor == '*' or match_minor == '*')
                 or item_minor == match_minor)):
            return True
        return False

    def accept_html(self):
        """
        Returns true if any HTML-like type is accepted
        """
        return ('text/html' in self
                or 'application/xhtml+xml' in self
                or 'application/xml' in self
                or 'text/xml' in self)

class MIMENilAccept(NilAccept):
    MasterClass = MIMEAccept
