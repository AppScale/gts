# $Id: 32c62bbf4b4a05fb16d4bc6894663370a8ae7ac9 $
#
# Nose program for testing grizzled.sys classes/functions

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from __future__ import absolute_import

import sys
from grizzled.system import *

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

VERSIONS = [('2.5.1', 0x020501f0),
            ('1.5',   0x010500f0),
            ('2.6',   0x020600f0),
            ('2.4.3', 0x020403f0)]

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class TestSys(object):

    def test_version_conversions(self):
        for s, i in VERSIONS:
            yield self.do_one_version_conversion, s, i
            
    def do_one_version_conversion(self, string_version, binary_version):
        h = python_version(string_version)
        s = python_version_string(binary_version)
        assert h == binary_version
        assert s == string_version
        
    def test_current_version(self):
        ensure_version(sys.hexversion)
        ensure_version(python_version_string(sys.hexversion))
        major, minor, patch, final, rem = sys.version_info
        binary_version = python_version('%d.%d.%d' % (major, minor, patch))

    def test_class_for_name(self):
        cls = class_for_name('grizzled.config.Configuration')
        got_name = '%s.%s' % (cls.__module__, cls.__name__)
        assert got_name == 'grizzled.config.Configuration'

        try:
            class_for_name('grizzled.foo.bar.baz')
            assert False
        except NameError:
            pass
        except ImportError:
            pass
