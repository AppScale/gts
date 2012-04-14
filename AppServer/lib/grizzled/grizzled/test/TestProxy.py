# Nose program for testing grizzled.proxy class.

from __future__ import absolute_import

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------

from grizzled.proxy import Forwarder
import tempfile
from grizzled.file import unlink_quietly
from .test_helpers import exception_expected

# ---------------------------------------------------------------------------
# Globals
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Classes
# ---------------------------------------------------------------------------

class ForwardToFile(Forwarder):
    def __init__(self, file, *exceptions):
        Forwarder.__init__(self, file, exceptions)

class TestProxyPackage(object):

    def test_forward_all(self):
        path = self._create_file()
        try:
            with open(path) as f:
                contents = ''.join(f.readlines())

            with open(path) as f:
                fwd = ForwardToFile(f)
                contents2 = ''.join(fwd.readlines())

            assert contents2 == contents

        finally:
            unlink_quietly(path)

    def test_forward_all_but_name(self):
        path = self._create_file()
        try:
            with exception_expected(AttributeError):
                with open(path) as f:
                    fwd = ForwardToFile(f, 'name', 'foo')
                    fwd.name
        finally:
            unlink_quietly(path)

    def test_forward_all_but_name_mode(self):
        path = self._create_file()
        try:
            with open(path) as f:
                fwd = ForwardToFile(f, 'name', 'mode')
                fwd.closed # should not fail
                with exception_expected(AttributeError):
                    fwd.name
                with exception_expected(AttributeError):
                    fwd.mode
        finally:
            unlink_quietly(path)

    def _create_file(self):
        temp = tempfile.NamedTemporaryFile(prefix="fwdtest", delete=False)
        temp.write(', '.join([str(x) for x in range(1, 81)]))
        temp.write(', '.join([str(x) for x in range(1, 21)]))
        temp.close
        return temp.name
