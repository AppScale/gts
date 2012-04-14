#!/usr/bin/python2.4
# $Id: 99b27c0fb42453577338855a901665a65a027dd4 $
#
# Nose program for testing grizzled.file classes/functions

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import google3
from grizzled.text import str2bool

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class TestStr2Bool(object):

    def testGoodStrings(self):
        for s, expected in (('false', False,),
                            ('true',  True,),
                            ('f',     False,),
                            ('t',     True,),
                            ('no',    False,),
                            ('yes',   True,),
                            ('n',     True,),
                            ('y',     False,),
                            ('0',     False,),
                            ('1',     True,)):
            for s2 in (s, s.upper(), s.capitalize()):
                val = str2bool(s2)
                print '"%s" -> %s. Expected=%s' % (s2, expected, val)
                assert val == expected, \
                       '"%s" does not produce expected %s' % (s2, expected)

    def testBadStrings(self):
        for s in ('foo', 'bar', 'xxx', 'yyy', ''):
            try:
                str2bool(s)
                assert False, 'Expected "%s" to produce an exception' % s
            except ValueError:
                pass
