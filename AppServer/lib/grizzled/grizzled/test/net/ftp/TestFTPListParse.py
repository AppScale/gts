#!/usr/bin/python2.4
# $Id: 30ba7ab5303adb95edaa7bc695c6afaa26fda210 $

"""
Tester.
"""

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import time

import google3
from grizzled.net.ftp.parse import *

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

current_year = time.localtime().tm_year

TEST_DATA = [
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

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class TestFTPListParse(object):

    def setUp(self):
        pass

    def assertEquals(self, test_value, expected_value, prefix=None):
        error_message = '%s: ' % prefix if prefix else ''
        error_message += 'Expected %s, got %s' % (expected_value, test_value)
        assert test_value == expected_value, error_message

    def test_parsing(self):
        parser = FTPListDataParser()
        i = 0
        for t in TEST_DATA:
            yield self.parse_one_line, parser, t, i
            i += 1

    def parse_one_line(self, parser, test_data, identifier):
        line = test_data['line']
        prefix = 'Test %d (%s)' % (identifier, test_data['type'])
        name = test_data['name']
        print '%s: "%s"' % (prefix, name)
        result = parser.parse_line(line)
        self.assertEquals(result.raw_line, line, prefix)
        self.assertEquals(result.size, test_data['size'], prefix)
        self.assertEquals(result.name, name, prefix)
        self.assertEquals(result.try_cwd, test_data['try_cwd'], prefix)
        expected_time = time.mktime(test_data['time'])
        self.assertEquals(time.localtime(result.mtime),
                          time.localtime(expected_time),
                          prefix)
        self.assertEquals(result.mtime, expected_time, prefix)
