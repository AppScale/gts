"""
Module for parsing FTP data.

Currently, this module contains classes for parsing FTP ``LIST`` command
output from a variety of FTP servers. In the future, this module may be
extended to handle other FTP parsing chores. (Or not.)

The FTP ``LIST`` parsing logic was adapted for Python from D. J. Bernstein's
``ftpparse.c`` library. See http://cr.yp.to/ftpparse.html. The logic in this
module is functionally similar to Bernstein's parser, with the following
differences:

    - Bernstein's C-specific logic has been made more Python-like.
    - The basic parser is encapsulated inside an `FTPListDataParser` class,
      instead of a function.
    - The ``ID_TYPE`` and ``MTIME_TYPE`` values are enumerations.
    - ``SIZE_TYPE`` is not supported (since it was always being set to the
      same value anyway).

Currently covered formats:

    - `EPLF`_
    - UNIX *ls*, with or without group ID
    - Microsoft FTP Service
    - Windows NT FTP Server
    - VMS
    - WFTPD
    - NetPresenz (Mac)
    - NetWare
    - MSDOS

.. _EPLF: http://cr.yp.to/ftp/list/eplf.html

Definitely not covered:

    - Long VMS filenames, with information split across two lines.
    - NCSA Telnet FTP server. Has LIST = NLST (and bad NLST for directories).
"""

__docformat__ = 'restructuredtext en'

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

import time
from enum import Enum

# ---------------------------------------------------------------------------
# Exports
# ---------------------------------------------------------------------------

__all__ = ['parse_ftp_list_line',
           'FTPListData',
           'FTPListDataParser',
           'ID_TYPE',
           'MTIME_TYPE']

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

MONTHS = ('jan', 'feb', 'mar', 'apr', 'may', 'jun',
          'jul', 'aug', 'sep', 'oct', 'nov', 'dec')

MTIME_TYPE = Enum('UNKNOWN', 'LOCAL', 'REMOTE_MINUTE', 'REMOTE_DAY')
"""
``MTIME_TYPE`` identifies how a modification time ought to be interpreted
(assuming the caller cares).

    - ``LOCAL``: Time is local to the client, granular to (at least) the minute
    - ``REMOTE_MINUTE``: Time is local to the server and granular to the minute
    - ``REMOTE_DAY``: Time is local to the server and granular to the day.
    - ``UNKNOWN``: Time's locale is unknown.
"""

ID_TYPE = Enum('UNKNOWN', 'FULL')
"""
``ID_TYPE`` identifies how a file's identifier should be interpreted.

    - ``FULL``: The ID is known to be complete.
    - ``UNKNOWN``: The ID is not set or its type is unknown.
"""

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

now = time.time()
current_year = time.localtime().tm_year

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class FTPListData(object):
    """
    The `FTPListDataParser` class's ``parse_line()`` method returns an
    instance of this class, capturing the parsed data.

    :IVariables:
        name : str
            The name of the file, if parsable
        try_cwd : bool
            ``True`` if the entry might be a directory (i.e., the caller
            might want to try an FTP ``CWD`` command), ``False`` if it
            cannot possibly be a directory.
        try_retr : bool
            ``True`` if the entry might be a retrievable file (i.e., the caller
            might want to try an FTP ``RETR`` command), ``False`` if it
            cannot possibly be a file.
        size : long
            The file's size, in bytes
        mtime : long
            The file's modification time, as a value that can be passed to
            ``time.localtime()``.
        mtime_type : `MTIME_TYPE`
            How to interpret the modification time. See `MTIME_TYPE`.
        id : str
            A unique identifier for the file. The unique identifier is unique
            on the *server*. On a Unix system, this identifier might be the
            device number and the file's inode; on other system's, it might
            be something else. It's also possible for this field to be ``None``.
        id_type : `ID_TYPE`
            How to interpret the identifier. See `ID_TYPE`.
   """

    def __init__(self, raw_line):
        self.raw_line = raw_line
        self.name = None
        self.try_cwd = False
        self.try_retr = False
        self.size = 0
        self.mtime_type = MTIME_TYPE.UNKNOWN
        self.mtime = 0
        self.id_type = ID_TYPE.UNKNOWN
        self.id = None

class FTPListDataParser(object):
    """
    An ``FTPListDataParser`` object can be used to parse one or more lines
    that were retrieved by an FTP ``LIST`` command that was sent to a remote
    server.
    """
    def __init__(self):
        pass

    def parse_line(self, ftp_list_line):
        """
        Parse a line from an FTP ``LIST`` command.

        :Parameters:
            ftp_list_line : str
                The line of output

        :rtype: `FTPListData`
        :return: An `FTPListData` object describing the parsed line, or
                 ``None`` if the line could not be parsed. Note that it's
                 possible for this method to return a partially-filled
                 `FTPListData` object (e.g., one without a name).
        """
        buf = ftp_list_line

        if len(buf) < 2: # an empty name in EPLF, with no info, could be 2 chars
            return None

        c = buf[0]
        if c == '+':
            return self._parse_EPLF(buf)

        elif c in 'bcdlps-':
            return self._parse_unix_style(buf)

        i = buf.find(';')
        if i > 0:
            return self._parse_multinet(buf, i)

        if c in '0123456789':
            return self._parse_msdos(buf)

        return None

    # UNIX ls does not show the year for dates in the last six months.
    # So we have to guess the year.
    #
    # Apparently NetWare uses ``twelve months'' instead of ``six months''; ugh.
    # Some versions of ls also fail to show the year for future dates.

    def _guess_time(self, month, mday, hour=0, minute=0):
        year = None
        t = None

        for year in range(current_year - 1, current_year + 100):
            t = self._get_mtime(year, month, mday, hour, minute)
            if (now - t) < (350 * 86400):
                return t

        return 0

    def _get_mtime(self, year, month, mday, hour=0, minute=0, second=0):
        return time.mktime((year, month, mday, hour, minute, second, 0, 0, -1))

    def _get_month(self, buf):
        if len(buf) == 3:
            for i in range(0, 12):
                if buf.lower().startswith(MONTHS[i]):
                    return i+1
        return -1

    def _parse_EPLF(self, buf):
        result = FTPListData(buf)

        # see http://cr.yp.to/ftp/list/eplf.html
        #"+i8388621.29609,m824255902,/,\tdev"
        #"+i8388621.44468,m839956783,r,s10376,\tRFCEPLF"
        i = 1
        for j in range(1, len(buf)):
            if buf[j] == '\t':
                result.name = buf[j+1:]
                break

            if buf[j] == ',':
                c = buf[i]
                if c == '/':
                    result.try_cwd = True
                elif c == 'r':
                    result.try_retr = True
                elif c == 's':
                    result.size = long(buf[i+1:j])
                elif c == 'm':
                    result.mtime_type = MTIME_TYPE.LOCAL
                    result.mtime = long(buf[i+1:j])
                elif c == 'i':
                    result.id_type = ID_TYPE.FULL
                    result.id = buf[i+1:j-i-1]

                i = j + 1

        return result

    def _parse_unix_style(self, buf):
        # UNIX-style listing, without inum and without blocks:
        # "-rw-r--r--   1 root     other        531 Jan 29 03:26 README"
        # "dr-xr-xr-x   2 root     other        512 Apr  8  1994 etc"
        # "dr-xr-xr-x   2 root     512 Apr  8  1994 etc"
        # "lrwxrwxrwx   1 root     other          7 Jan 25 00:17 bin -> usr/bin"
        #
        # Also produced by Microsoft's FTP servers for Windows:
        # "----------   1 owner    group         1803128 Jul 10 10:18 ls-lR.Z"
        # "d---------   1 owner    group               0 May  9 19:45 Softlib"
        #
        # Also WFTPD for MSDOS:
        # "-rwxrwxrwx   1 noone    nogroup      322 Aug 19  1996 message.ftp"
        #
        # Also NetWare:
        # "d [R----F--] supervisor            512       Jan 16 18:53    login"
        # "- [R----F--] rhesus             214059       Oct 20 15:27    cx.exe"
        #
        # Also NetPresenz for the Mac:
        # "-------r--         326  1391972  1392298 Nov 22  1995 MegaPhone.sit"
        # "drwxrwxr-x               folder        2 May 10  1996 network"

        result = FTPListData(buf)

        buflen = len(buf)
        c = buf[0]
        if c == 'd':
            result.try_cwd = True
        if c == '-':
            result.try_retr = True
        if c == 'l':
            result.try_retr = True
            result.try_cwd = True

        state = 1
        i = 0
        tokens = buf.split()
        for j in range(1, buflen):
            if (buf[j] == ' ') and (buf[j - 1] != ' '):
                if state == 1:  # skipping perm
                    state = 2

                elif state == 2: # skipping nlink
                    state = 3
                    if ((j - i) == 6) and (buf[i] == 'f'): # NetPresenz
                        state = 4

                elif state == 3: # skipping UID/GID
                    state = 4

                elif state == 4: # getting tentative size
                    try:
                        size = long(buf[i:j])
                    except ValueError:
                        pass
                    state = 5

                elif state == 5: # searching for month, else getting tentative size
                    month = self._get_month(buf[i:j])
                    if month >= 0:
                        state = 6
                    else:
                        size = long(buf[i:j])

                elif state == 6: # have size and month
                    mday = long(buf[i:j])
                    state = 7

                elif state == 7: # have size, month, mday
                    if (j - i == 4) and (buf[i+1] == ':'):
                        hour = long(buf[i])
                        minute = long(buf[i+2:i+4])
                        result.mtime_type = MTIME_TYPE.REMOTE_MINUTE
                        result.mtime = self._guess_time(month, mday, hour, minute)
                    elif (j - i == 5) and (buf[i+2] == ':'):
                        hour = long(buf[i:i+2])
                        minute = long(buf[i+3:i+5])
                        result.mtime_type = MTIME_TYPE.REMOTE_MINUTE
                        result.mtime = self._guess_time(month, mday, hour, minute)
                    elif j - i >= 4:
                        year = long(buf[i:j])
                        result.mtimetype = MTIME_TYPE.REMOTE_DAY
                        result.mtime = self._get_mtime(year, month, mday)
                    else:
                        break

                    result.name = buf[j+1:]
                    state = 8
                elif state == 8: # twiddling thumbs
                    pass

                i = j + 1
                while (i < buflen) and (buf[i] == ' '):
                    i += 1

        #if state != 8:
            #return None

        result.size = size

        if c == 'l':
            i = 0
            while (i + 3) < len(result.name):
                if result.name[i:i+4] == ' -> ':
                    result.name = result.name[:i]
                    break
                i += 1

        # eliminate extra NetWare spaces
        if (buf[1] == ' ') or (buf[1] == '['):
            namelen = len(result.name)
            if namelen > 3:
                result.name = result.name.strip()

        return result

    def _parse_multinet(self, buf, i):

        # MultiNet (some spaces removed from examples)
        # "00README.TXT;1      2 30-DEC-1996 17:44 [SYSTEM] (RWED,RWED,RE,RE)"
        # "CORE.DIR;1          1  8-SEP-1996 16:09 [SYSTEM] (RWE,RWE,RE,RE)"
        # and non-MultiNet VMS:
        #"CII-MANUAL.TEX;1  213/216  29-JAN-1996 03:33:12  [ANONYMOU,ANONYMOUS]   (RWED,RWED,,)"

        result = FTPListData(buf)
        result.name = buf[:i]
        buflen = len(buf)

        if i > 4:
            if buf[i-4:i] == '.DIR':
                result.name = result.name[0:-4]
                result.try_cwd = True

        if not result.try_cwd:
            result.try_retr = True

        try:
            i = buf.index(' ', i)
            i = _skip(buf, i, ' ')
            i = buf.index(' ', i)
            i = _skip(buf, i, ' ')

            j = i

            j = buf.index('-', j)
            mday = long(buf[i:j])

            j = _skip(buf, j, '-')
            i = j
            j = buf.index('-', j)
            month = self._get_month(buf[i:j])
            if month < 0:
                raise IndexError

            j = _skip(buf, j, '-')
            i = j
            j = buf.index(' ', j)
            year = long(buf[i:j])

            j = _skip(buf, j, ' ')
            i = j

            j = buf.index(':', j)
            hour = long(buf[i:j])
            j = _skip(buf, j, ':')
            i = j

            while (buf[j] != ':') and (buf[j] != ' '):
                j += 1
                if j == buflen:
                    raise IndexError # abort, abort!

            minute = long(buf[i:j])

            result.mtimetype = MTIME_TYPE.REMOTE_MINUTE
            result.mtime = self._get_mtime(year, month, mday, hour, minute)

        except IndexError:
            pass

        return result

    def _parse_msdos(self, buf):
        # MSDOS format
        # 04-27-00  09:09PM       <DIR>          licensed
        # 07-18-00  10:16AM       <DIR>          pub
        # 04-14-00  03:47PM                  589 readme.htm

        buflen = len(buf)
        i = 0
        j = 0

        try:
            result = FTPListData(buf)

            j = buf.index('-', j)
            month = long(buf[i:j])

            j = _skip(buf, j, '-')
            i = j
            j = buf.index('-', j)
            mday = long(buf[i:j])

            j = _skip(buf, j, '-')
            i = j
            j = buf.index(' ', j)
            year = long(buf[i:j])
            if year < 50:
                year += 2000
            if year < 1000:
                year += 1900

            j = _skip(buf, j, ' ')
            i = j
            j = buf.index(':', j)
            hour = long(buf[i:j])
            j = _skip(buf, j, ':')
            i = j
            while not (buf[j] in 'AP'):
                j += 1
                if j == buflen:
                    raise IndexError
            minute = long(buf[i:j])

            if buf[j] == 'A':
                j += 1
                if j == buflen:
                    raise IndexError

            if buf[j] == 'P':
                hour = (hour + 12) % 24
                j += 1
                if j == buflen:
                    raise IndexError

            if buf[j] == 'M':
                j += 1
                if j == buflen:
                    raise IndexError

            j = _skip(buf, j, ' ')
            if buf[j] == '<':
                result.try_cwd = True
                j = buf.index(' ', j)
            else:
                i = j
                j = buf.index(' ', j)

                result.size = long(buf[i:j])
                result.try_retr = True

            j = _skip(buf, j, ' ')

            result.name = buf[j:]
            result.mtimetype = MTIME_TYPE.REMOTE_MINUTE
            result.mtime = self._get_mtime(year, month, mday, hour, minute)
        except IndexError:
            pass

        return result


# ---------------------------------------------------------------------------
# Public Functions
# ---------------------------------------------------------------------------

def parse_ftp_list_line(ftp_list_line):
    """
    Convenience function that instantiates an `FTPListDataParser` object
    and passes ``ftp_list_line`` to the object's ``parse_line()`` method,
    returning the result.

    :Parameters:
        ftp_list_line : str
            The line of output

    :rtype: `FTPListData`
    :return: An `FTPListData` object describing the parsed line, or
             ``None`` if the line could not be parsed. Note that it's
             possible for this method to return a partially-filled
             `FTPListData` object (e.g., one without a name).
    """
    return FTPListDataParser().parse_line(ftp_list_line)

# ---------------------------------------------------------------------------
# Private Functions
# ---------------------------------------------------------------------------

def _skip(s, i, c):
    while s[i] == c:
        i += 1
        if i == len(s):
            raise IndexError
    return i

# ---------------------------------------------------------------------------
# Main (Tester)
# ---------------------------------------------------------------------------

if __name__ == '__main__':
    test_data = [
        # ELPF

        {'line':    '+i9872342.32142,m1229473595,/,\tpub',
         'type':    'ELPF',
         'size':    0,
         'time':    (2008, 12, 16, 19, 26, 35, 0, 0, -1),
         'name':    'pub',
         'try_cwd': True},

        {'line':    '+i9872342.32142,m1229473595,r,s10376,\tREADME.txt',
         'type':    'ELPF',
         'size':    10376,
         'time':    (2008, 12, 16, 19, 26, 35, 0, 0, -1),
         'name':    'README.txt',
         'try_cwd': False},

        # Unix

        {'line':    '-rw-r--r--   1 root     other     531 Jan 29 03:26 README',
         'type':    'Unix',
         'size':    531,
         'time':    (current_year, 1, 29, 03, 26, 0, 0, 0, -1),
         'name':    'README',
         'try_cwd': False},

        {'line':    'dr-xr-xr-x   2 root     other        512 Apr  8  2003 etc',
         'type':    'Unix',
         'size':    512,
         'time':    (2003, 4, 8, 0, 0, 0, 0, 0, -1),
         'name':    'etc',
         'try_cwd': True},

        {'line':    '-rw-r--r--   1 1356107  15000      4356349 Nov 23 11:34 09 Ribbons Undone.wma',
         'type':    'Unix',
         'size':    4356349,
         'time':    (current_year, 11, 23, 11, 34, 0, 0, 0, -1),
         'name':    '09 Ribbons Undone.wma',
         'try_cwd': False},

        # Microsoft Windows

        {'line':    '----------   1 owner    group         1803128 Jul 10 10:18 ls-lR.Z',
         'type':    'Windows',
         'size':    1803128,
         'time':    (current_year, 7, 10, 10, 18, 0, 0, 0, -1),
         'name':    'ls-lR.Z',
         'try_cwd': False},

        {'line':    'd---------   1 owner    group               0 May  9 19:45 foo bar',
         'type':    'Windows',
         'size':    0,
         'time':    (current_year, 5, 9, 19, 45, 0, 0, 0, -1),
         'name':    'foo bar',
         'try_cwd': True},

        # NetWare

        {'line':    'd [R----F--] supervisor    512    Jan 16 18:53    login',
         'type':    'NetWare',
         'size':    512,
         'time':    (current_year, 1, 16, 18, 53, 0, 0, 0, -1),
         'name':    'login',
         'try_cwd': True},

        # NetPresenz

        {'line':    'drwxrwxr-x               folder   2 May 10  1996 bar.sit',
         'type':    'NetPresenz/Mac',
         'size':    2,
         'time':    (1996, 5, 10, 0, 0, 0, 0, 0, -1),
         'name':    'bar.sit',
         'try_cwd': True},

        # MultiNet/VMS (no size with these)

        {'line':    'CORE.DIR;1      1 8-NOV-1999 07:02 [SYSTEM] (RWED,RWED,RE,RE)',
         'type':    'MultiNet/VMS',
         'size':    0,
         'time':    (1999, 11, 8, 7, 2, 0, 0, 0, -1),
         'name':    'CORE',
         'try_cwd': True},

        {'line':    '00README.TXT;1      2 30-DEC-1976 17:44 [SYSTEM] (RWED,RWED,RE,RE)',
         'type':    'MultiNet/VMS',
         'size':    0,
         'time':    (1976, 12, 30, 17, 44, 0, 0, 0, -1),
         'name':    '00README.TXT',
         'try_cwd': False},

        {'line':    'CII-MANUAL.TEX;1  213/216  29-JAN-1996 03:33:12  [ANONYMOU,ANONYMOUS]   (RWED,RWED,,)',
         'type':    'MultiNet/VMS',
         'size':    0,
         # Doesn't parse the seconds
         'time':    (1996, 1, 29, 03, 33, 0, 0, 0, -1),
         'name':    'CII-MANUAL.TEX',
         'try_cwd': False},

        # MS-DOS

        {'line':    '04-27-00  09:09PM       <DIR>          licensed',
         'type':    'MS-DOS',
         'size':    0,
         'time':    (2000, 4, 27, 21, 9, 0, 0, 0, -1),
         'name':    'licensed',
         'try_cwd': True},

        {'line':    '11-18-03  10:16AM       <DIR>          pub',
         'type':    'MS-DOS',
         'size':    0,
         'time':    (2003, 11, 18, 10, 16, 0, 0, 0, -1),
         'name':    'pub',
         'try_cwd': True},

        {'line':    '04-14-99  03:47PM                  589 readme.htm',
         'type':    'MS-DOS',
         'size':    589,
         'time':    (1999, 04, 14, 15, 47, 0, 0, 0, -1),
         'name':    'readme.htm',
         'try_cwd': False},
    ]

    def assertEquals(test_value, expected_value, prefix=None):
        error_message = '%s: ' % prefix if prefix else ''
        error_message += 'Expected %s, got %s' % (expected_value, test_value)
        assert test_value == expected_value, error_message


    parser = FTPListDataParser()
    i = 0
    for test in test_data:
        line = test['line']
        prefix = 'Test %d (%s)' % (i, test['type'])
        print '%s: "%s"' % (prefix, test['name'])
        result = parser.parse_line(line)
        assertEquals(result.raw_line, line, prefix)
        assertEquals(result.size, test['size'], prefix)
        assertEquals(result.name, test['name'], prefix)
        assertEquals(result.try_cwd, test['try_cwd'], prefix)
        expected_time = time.mktime(test['time'])
        assertEquals(time.localtime(result.mtime),
                     time.localtime(expected_time),
                     prefix)
        assertEquals(result.mtime, expected_time, prefix)
        i += 1

