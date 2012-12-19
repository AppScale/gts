# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
Unit tests.

@since: 0.1.0
"""

import os.path

try:
    import unittest2 as unittest
    import sys

    sys.modules['unittest'] = unittest
except ImportError:
    import unittest


if not hasattr(unittest.TestCase, 'assertIdentical'):
    def assertIdentical(self, first, second, msg=None):
        """
        Fail the test if C{first} is not C{second}.  This is an
        obect-identity-equality test, not an object equality (i.e. C{__eq__}) test.

        @param msg: if msg is None, then the failure message will be
            '%r is not %r' % (first, second)
        """
        if first is not second:
            raise AssertionError(msg or '%r is not %r' % (first, second))

        return first

    unittest.TestCase.assertIdentical = assertIdentical

if not hasattr(unittest.TestCase, 'assertNotIdentical'):
    def assertNotIdentical(self, first, second, msg=None):
        """
        Fail the test if C{first} is C{second}.  This is an
        object-identity-equality test, not an object equality
        (i.e. C{__eq__}) test.

        @param msg: if msg is None, then the failure message will be
            '%r is %r' % (first, second)
        """
        if first is second:
            raise AssertionError(msg or '%r is %r' % (first, second))

        return first

    unittest.TestCase.assertNotIdentical = assertNotIdentical

if not hasattr(unittest.TestCase, 'patch'):
    import inspect

    def unpatch(self):
        for orig, part, replaced in self.__patches:
            setattr(orig, part, replaced)

    def patch(self, orig, replace):
        if not hasattr(self, '__patches'):
            self.__patches = []
            self.addCleanup(unpatch, self)

        f = inspect.stack()[1][0]

        parts = orig.split('.')

        v = f.f_globals.copy()
        v.update(f.f_locals)

        orig = v[parts[0]]

        for part in parts[1:-1]:
            orig = getattr(orig, part)

        to_replace = getattr(orig, parts[-1])

        self.__patches.append((orig, parts[-1], to_replace))

        setattr(orig, parts[-1], replace)

    unittest.TestCase.patch = patch


def get_suite():
    """
    Discover the entire test suite.
    """
    loader = unittest.TestLoader()

    # this could be cleaned up but it works ..
    tld = __file__.split(os.path.sep)

    tld.reverse()

    for i, x in enumerate(tld):
        if x == 'pyamf':
            tld.reverse()

            tld = os.path.sep.join(tld[:-1 - i])

            break

    return loader.discover('pyamf', top_level_dir=tld)


def main():
    """
    Run all of the tests when run as a module with -m.
    """
    runner = unittest.TextTestRunner()
    runner.run(get_suite())


if __name__ == '__main__':
    main()
