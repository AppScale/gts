class Range(object):

    """
    Represents the Range header.

    This only represents ``bytes`` ranges, which are the only kind
    specified in HTTP.  This can represent multiple sets of ranges,
    but no place else is this multi-range facility supported.
    """

    def __init__(self, ranges):
        for begin, end in ranges:
            assert end is None or end >= 0, "Bad ranges: %r" % ranges
        self.ranges = ranges

    def satisfiable(self, length):
        """
        Returns true if this range can be satisfied by the resource
        with the given byte length.
        """
        for begin, end in self.ranges:
            if end is not None and end >= length:
                return False
        return True

    def range_for_length(self, length):
        """
        *If* there is only one range, and *if* it is satisfiable by
        the given length, then return a (begin, end) non-inclusive range
        of bytes to serve.  Otherwise return None

        If length is None (unknown length), then the resulting range
        may be (begin, None), meaning it should be served from that
        point.  If it's a range with a fixed endpoint we won't know if
        it is satisfiable, so this will return None.
        """
        if len(self.ranges) != 1:
            return None
        begin, end = self.ranges[0]
        if length is None:
            # Unknown; only works with ranges with no end-point
            if end is None:
                return (begin, end)
            return None
        if end >= length:
            # Overshoots the end
            return None
        return (begin, end)

    def content_range(self, length):
        """
        Works like range_for_length; returns None or a ContentRange object

        You can use it like::

            response.content_range = req.range.content_range(response.content_length)

        Though it's still up to you to actually serve that content range!
        """
        range = self.range_for_length(length)
        if range is None:
            return None
        return ContentRange(range[0], range[1], length)

    def __str__(self):
        return self.serialize_bytes('bytes', self.python_ranges_to_bytes(self.ranges))

    def __repr__(self):
        return '<%s ranges=%s>' % (
            self.__class__.__name__,
            ', '.join(map(repr, self.ranges)))

    #@classmethod
    def parse(cls, header):
        """
        Parse the header; may return None if header is invalid
        """
        bytes = cls.parse_bytes(header)
        if bytes is None:
            return None
        units, ranges = bytes
        if units.lower() != 'bytes':
            return None
        ranges = cls.bytes_to_python_ranges(ranges)
        if ranges is None:
            return None
        return cls(ranges)
    parse = classmethod(parse)

    #@staticmethod
    def parse_bytes(header):
        """
        Parse a Range header into (bytes, list_of_ranges).  Note that the
        ranges are *inclusive* (like in HTTP, not like in Python
        typically).

        Will return None if the header is invalid
        """
        if not header:
            raise TypeError(
                "The header must not be empty")
        ranges = []
        last_end = 0
        try:
            (units, range) = header.split("=", 1)
            units = units.strip().lower()
            for item in range.split(","):
                if '-' not in item:
                    raise ValueError()
                if item.startswith('-'):
                    # This is a range asking for a trailing chunk
                    if last_end < 0:
                        raise ValueError('too many end ranges')
                    begin = int(item)
                    end = None
                    last_end = -1
                else:
                    (begin, end) = item.split("-", 1)
                    begin = int(begin)
                    if begin < last_end or last_end < 0:
                        print begin, last_end
                        raise ValueError('begin<last_end, or last_end<0')
                    if not end.strip():
                        end = None
                    else:
                        end = int(end)
                    if end is not None and begin > end:
                        raise ValueError('begin>end')
                    last_end = end
                ranges.append((begin, end))
        except ValueError, e:
            # In this case where the Range header is malformed,
            # section 14.16 says to treat the request as if the
            # Range header was not present.  How do I log this?
            print e
            return None
        return (units, ranges)
    parse_bytes = staticmethod(parse_bytes)

    #@staticmethod
    def serialize_bytes(units, ranges):
        """
        Takes the output of parse_bytes and turns it into a header
        """
        parts = []
        for begin, end in ranges:
            if end is None:
                if begin >= 0:
                    parts.append('%s-' % begin)
                else:
                    parts.append(str(begin))
            else:
                if begin < 0:
                    raise ValueError(
                        "(%r, %r) should have a non-negative first value" % (begin, end))
                if end < 0:
                    raise ValueError(
                        "(%r, %r) should have a non-negative second value" % (begin, end))
                parts.append('%s-%s' % (begin, end))
        return '%s=%s' % (units, ','.join(parts))
    serialize_bytes = staticmethod(serialize_bytes)

    #@staticmethod
    def bytes_to_python_ranges(ranges, length=None):
        """
        Converts the list-of-ranges from parse_bytes() to a Python-style
        list of ranges (non-inclusive end points)

        In the list of ranges, the last item can be None to indicate that
        it should go to the end of the file, and the first item can be
        negative to indicate that it should start from an offset from the
        end.  If you give a length then this will not occur (negative
        numbers and offsets will be resolved).

        If length is given, and any range is not value, then None is
        returned.
        """
        result = []
        for begin, end in ranges:
            if begin < 0:
                if length is None:
                    result.append((begin, None))
                    continue
                else:
                    begin = length - begin
                    end = length
            if begin is None:
                begin = 0
            if end is None and length is not None:
                end = length
            if length is not None and end is not None and end > length:
                return None
            if end is not None:
                end -= 1
            result.append((begin, end))
        return result
    bytes_to_python_ranges = staticmethod(bytes_to_python_ranges)
    
    #@staticmethod
    def python_ranges_to_bytes(ranges):
        """
        Converts a Python-style list of ranges to what serialize_bytes
        expects.

        This is the inverse of bytes_to_python_ranges
        """
        result = []
        for begin, end in ranges:
            if end is None:
                result.append((begin, None))
            else:
                result.append((begin, end+1))
        return result
    python_ranges_to_bytes = staticmethod(python_ranges_to_bytes)

class ContentRange(object):

    """
    Represents the Content-Range header

    This header is ``start-stop/length``, where stop and length can be
    ``*`` (represented as None in the attributes).
    """

    def __init__(self, start, stop, length):
        assert start >= 0, "Bad start: %r" % start
        assert stop is None or (stop >= 0 and stop >= start), (
            "Bad stop: %r" % stop)
        self.start = start
        self.stop = stop
        self.length = length

    def __repr__(self):
        return '<%s %s>' % (
            self.__class__.__name__,
            self)

    def __str__(self):
        if self.stop is None:
            stop = '*'
        else:
            stop = self.stop + 1
        if self.length is None:
            length = '*'
        else:
            length = self.length
        return 'bytes %s-%s/%s' % (self.start, stop, length)

    def __iter__(self):
        """
        Mostly so you can unpack this, like:

            start, stop, length = res.content_range
        """
        return iter([self.start, self.stop, self.length])

    #@classmethod
    def parse(cls, value):
        """
        Parse the header.  May return None if it cannot parse.
        """
        if value is None:
            return None
        value = value.strip()
        if not value.startswith('bytes '):
            # Unparseable
            return None
        value = value[len('bytes '):].strip()
        if '/' not in value:
            # Invalid, no length given
            return None
        range, length = value.split('/', 1)
        if '-' not in range:
            # Invalid, no range
            return None
        start, end = range.split('-', 1)
        try:
            start = int(start)
            if end == '*':
                end = None
            else:
                end = int(end)
            if length == '*':
                length = None
            else:
                length = int(length)
        except ValueError:
            # Parse problem
            return None
        if end is None:
            return cls(start, None, length)
        else:
            return cls(start, end-1, length)
    parse = classmethod(parse)
    
