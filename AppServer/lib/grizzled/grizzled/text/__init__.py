# $Id: 55b6d7323887ac09f6bfba365205e952533b847b $

"""
The ``grizzled.text`` package contains text-related classes and modules.
"""

__docformat__ = "restructuredtext en"

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from StringIO import StringIO

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['hexdump']

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REPEAT_FORMAT = '*** Repeated %d times'

# ---------------------------------------------------------------------------
# Functions
# ---------------------------------------------------------------------------

def hexdump(source, out, width=16, start=0, limit=None, show_repeats=False):
    """
    Produce a "standard" hexdump of the specified string or file-like
    object. The output consists of a series of lines like this::

        000000: 72 22 22 22 4f  53 20 72 6f 75  r'''OS rou
        00000a: 74 69 6e 65 73  20 66 6f 72 20  tines for
        000014: 4d 61 63 2c 20  4e 54 2c 20 6f  Mac, NT, o
        00001e: 72 20 50 6f 73  69 78 20 64 65  r Posix de
        000028: 70 65 6e 64 69  6e 67 20 6f 6e  pending on
        000032: 20 77 68 61 74  20 73 79 73 74   what syst
        00003c: 65 6d 20 77 65  27 72 65 20 6f  em we're o
        000046: 6e 2e 0a 0a 54  68 69 73 20 65  n...This e

    The output width (i.e., the number of decoded characters shown on a
    line) can be controlled with the ``width`` parameter.

    Adjacent repeated lines are collapsed by default. For example::

        000000: 00 00 00 00 00  00 00 00 00 00  ..........
        *** Repeated 203 times
        0007f8: 72 22 22 22 4f  53 20 72 6f 75  r'''OS rou

    This behavior can be disabled via the ``show_repeats`` parameter.

    :Parameters:
        source : str or file
            The object whose contents are to be dumped in hex. The
            object can be a string or a file-like object.

        out : file
            Where to dump the hex output

        width : int
            The number of dumped characters per line

        start : int
            Offset within ``input`` where reading should begin

        limit : int
            Total number of bytes to dump. Defaults to everything from
            ``start`` to the end.

        show_repeats : bool
            ``False`` to collapse repeated output lines, ``True`` to
            dump all lines, even if they're repeats.
    """

    def ascii(b):
        """Determine how to show a byte in ascii."""
        if 32 <= b <= 126:
            return chr(b)
        else:
            return '.'

    pos = 0
    ascii_map = [ ascii(c) for c in range(256) ]

    lastbuf = ''
    lastline = ''
    repeat_count = 0

    if width > 4:
        space_col = width/2
    else:
        space_col = -1

    if type(source) == str:
        source = StringIO(source)

    if start:
        source.seek(start)
        pos = start

    hex_field_width = (width * 3) + 1

    total_read = 0
    while True:
        if limit:
            to_read = min(limit - total_read, width)
        else:
            to_read = width

        buf = source.read(to_read)
        length = len(buf)
        total_read += length
        if length == 0:
            if repeat_count and (not show_repeats):
                if repeat_count > 1:
                    print >> out, REPEAT_FORMAT % (repeat_count - 1)
                elif repeat_count == 1:
                    print >> out, lastline
                print >> out, lastline
            break

        else:
            show_buf = True

            if buf == lastbuf:
                repeat_count += 1
                show_buf = False
            else:
                if repeat_count and (not show_repeats):
                    if repeat_count == 1:
                        print >> out, lastline
                    else:
                        print >> out, REPEAT_FORMAT % (repeat_count - 1)
                    repeat_count = 0

            # Build output line.
            hex = ""
            asc = ""
            for i in range(length):
                c = buf[i]
                if i == space_col:
                    hex = hex + " "
                hex = hex + ("%02x" % ord(c)) + " "
                asc = asc + ascii_map[ord(c)]
            line = "%06x: %-*s %s" % (pos, hex_field_width, hex, asc)

            if show_buf:
                print >> out, line

            pos = pos + length
            lastbuf = buf
            lastline = line

def str2bool(s):
    """
    Convert a string to a boolean value. The supported conversions are:

        +--------------+---------------+
        | String       | Boolean value |
        +==============+===============+
        | "false"      | False         |
        +--------------+---------------+
        | "true"       | True          |
        +--------------+---------------+
        | "f"          | False         |
        +--------------+---------------+
        | "t"          + True          |
        +--------------+---------------+
        | "0"          | False         |
        +--------------+---------------+
        | "1"          + True          |
        +--------------+---------------+
        | "n"          | False         |
        +--------------+---------------+
        | "y"          + True          |
        +--------------+---------------+
        | "no"         | False         |
        +--------------+---------------+
        | "yes"        + True          |
        +--------------+---------------+
        | "off"        | False         |
        +--------------+---------------+
        | "on"         + True          |
        +--------------+---------------+

    Strings are compared in a case-blind fashion.

    **Note**: This function is not currently localizable.

    :Parameters:
        s : str
            The string to convert to boolean

    :rtype: bool
    :return: the corresponding boolean value

    :raise ValueError: unrecognized boolean string
    """
    try:
        return {'false' : False,
                'true'  : True,
                'f'     : False,
                't'     : True,
                '0'     : False,
                '1'     : True,
                'no'    : False,
                'yes'   : True,
                'y'     : False,
                'n'     : True,
                'off'   : False,
                'on'    : True}[s.lower()]
    except KeyError:
        raise ValueError, 'Unrecognized boolean string: "%s"' % s
