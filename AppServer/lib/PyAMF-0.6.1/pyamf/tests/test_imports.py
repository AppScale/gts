# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests pyamf.util.imports

@since: 0.3.1
"""

import unittest
import sys
import os.path

from pyamf.util import imports


class InstalledTestCase(unittest.TestCase):
    """
    Tests to ensure that L{imports.finder} is installed in L{sys.meta_path}
    """

    def test_installed(self):
        f = imports.finder

        self.assertTrue(f in sys.meta_path)
        self.assertIdentical(sys.meta_path[0], f)


class ImportsTestCase(unittest.TestCase):
    def setUp(self):
        self.finder = imports.finder

        self._state = self.finder.__getstate__()

        path = os.path.join(os.path.dirname(__file__), 'imports')
        sys.path.insert(0, path)

    def tearDown(self):
        self.finder.__setstate__(self._state)

        del sys.path[0]
        self._clearModules('spam')

    def _clearModules(self, *args):
        for mod in args:
            for k, v in sys.modules.copy().iteritems():
                if k.startswith(mod) or k == 'pyamf.tests.%s' % (mod,):
                    del sys.modules[k]


class WhenImportedTestCase(ImportsTestCase):
    """
    Tests for L{imports.when_imported}
    """

    def setUp(self):
        ImportsTestCase.setUp(self)

        self.executed = False

    def _hook(self, module):
        self.executed = True

    def _check_module(self, mod):
        name = mod.__name__

        self.assertTrue(name in sys.modules)
        self.assertIdentical(sys.modules[name], mod)

    def test_import(self):
        imports.when_imported('spam', self._hook)

        self.assertFalse(self.executed)

        import spam

        self._check_module(spam)
        self.assertTrue(self.executed)

    def test_already_imported(self):
        import spam

        self.assertFalse(self.executed)

        imports.when_imported('spam', self._hook)

        self._check_module(spam)
        self.assertTrue(self.executed)

    def test_failed_hook(self):
        def h(mod):
            raise RuntimeError

        imports.when_imported('spam', h)

        try:
            import spam
        except Exception, e:
            pass
        else:
            self.fail('expected exception')

        self.assertFalse('spam' in self.finder.loaded_modules)

        self.assertEqual(e.__class__, RuntimeError)
