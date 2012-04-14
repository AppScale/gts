#!/usr/bin/python2.4
# $Id: 528e646aad5388398e2cfcb7a2cb6af49473c630 $
#
# Nose program for testing grizzled.file classes/functions

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

import google3
from grizzled.file import *
from cStringIO import StringIO
import os
import tempfile
import atexit

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class TestFilePackage(object):

    def testUnlinkQuietly(self):
        fd, path = tempfile.mkstemp()
        os.unlink(path)

        try:
            os.unlink(path)
            assert False, 'Expected an exception'
        except OSError:
            pass

        unlink_quietly(path)

    def testRecursivelyRemove(self):
        path = tempfile.mkdtemp()
        print 'Created directory "%s"' % path

        # Create some files underneath

        touch([os.path.join(path, 'foo'),
               os.path.join(path, 'bar')])

        try:
            os.unlink(path)
            assert False, 'Expected an exception'
        except OSError:
            pass

        recursively_remove(path)

    def testTouch(self):
        path = tempfile.mkdtemp()
        atexit.register(recursively_remove, path)
        f = os.path.join(path, 'foo')
        assert not os.path.exists(f)
        touch(f)
        assert os.path.exists(f)
