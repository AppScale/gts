# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Tests for the adapters module.

@since: 0.3.1
"""

import os
import sys

from pyamf import adapters
from pyamf.tests import util
from pyamf.tests.test_imports import ImportsTestCase


class AdapterHelperTestCase(ImportsTestCase):
    def setUp(self):
        ImportsTestCase.setUp(self)

        self.old_env = os.environ.copy()
        self.mods = sys.modules.copy()

        self.path = os.path.join(os.path.dirname(__file__), 'imports')
        sys.path.append(self.path)

    def tearDown(self):
        ImportsTestCase.tearDown(self)

        util.replace_dict(os.environ, self.old_env)
        util.replace_dict(sys.modules, self.mods)
        sys.path.remove(self.path)

    def test_basic(self):
        class Foo(object):
            def __call__(self, *args, **kwargs):
                pass

        def bar(*args, **kargs):
            pass

        self.assertRaises(TypeError, adapters.register_adapter, 'foo', 1)
        self.assertRaises(TypeError, adapters.register_adapter, 'foo', 'asdf')
        adapters.register_adapter('foo', Foo())
        adapters.register_adapter('foo', bar)
        adapters.register_adapter('foo', lambda x: x)

    def test_import(self):
        self.imported = False

        def x(mod):
            self.imported = True
            self.spam = mod

        adapters.register_adapter('spam', x)

        import spam

        self.assertTrue(self.imported)
        self.assertEqual(self.spam, spam)

    def test_get_adapter(self):
        from pyamf.adapters import _decimal

        self.assertTrue(adapters.get_adapter('decimal') is _decimal)
