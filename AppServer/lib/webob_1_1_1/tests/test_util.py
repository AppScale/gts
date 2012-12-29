import unittest
from webob import Request, Response

class Test_warn_deprecation(unittest.TestCase):
    def setUp(self):
        import warnings
        self.oldwarn = warnings.warn
        warnings.warn = self._warn
        self.warnings = []

    def tearDown(self):
        import warnings
        warnings.warn = self.oldwarn
        del self.warnings

    def _callFUT(self, text, version, stacklevel):
        from webob.util import warn_deprecation
        return warn_deprecation(text, version, stacklevel)

    def _warn(self, text, type, stacklevel=1):
        self.warnings.append(locals())

    def test_not_1_2(self):
        self._callFUT('text', 'version', 1)
        self.assertEqual(len(self.warnings), 2)
        unknown_version_warning = self.warnings[0]
        self.assertEqual(unknown_version_warning['text'],
                         "Unknown warn_deprecation version arg: 'version'")
        self.assertEqual(unknown_version_warning['type'], RuntimeWarning)
        self.assertEqual(unknown_version_warning['stacklevel'], 1)
        deprecation_warning = self.warnings[1]
        self.assertEqual(deprecation_warning['text'], 'text')
        self.assertEqual(deprecation_warning['type'], DeprecationWarning)
        self.assertEqual(deprecation_warning['stacklevel'], 2)

    def test_is_1_2(self):
        self._callFUT('text', '1.2', 1)
        self.assertEqual(len(self.warnings), 1)
        deprecation_warning = self.warnings[0]
        self.assertEqual(deprecation_warning['text'], 'text')
        self.assertEqual(deprecation_warning['type'], DeprecationWarning)
        self.assertEqual(deprecation_warning['stacklevel'], 2)


    def test_decode_param_names_arg(self):
        from webob import Request
        env = Request.blank('?a=b').environ
        req = Request(env, decode_param_names=False)
        self.assertEqual(len(self.warnings), 1)
        deprecation_warning = self.warnings[0]
        self.assertEqual(deprecation_warning['type'], DeprecationWarning)

    def test_decode_param_names_attr(self):
        class BadRequest(Request):
            decode_param_names = False
        req = BadRequest.blank('?a=b')
        self.assertEqual(len(self.warnings), 1)
        deprecation_warning = self.warnings[0]
        self.assertEqual(deprecation_warning['type'], DeprecationWarning)

    def test_multidict_update_warning(self):
        # test warning when duplicate keys are passed
        r = Response()
        r.headers.update([
            ('Set-Cookie', 'a=b'),
            ('Set-Cookie', 'x=y'),
        ])
        self.assertEqual(len(self.warnings), 1)
        deprecation_warning = self.warnings[0]
        self.assertEqual(deprecation_warning['type'], UserWarning)
        assert 'Consider using .extend()' in deprecation_warning['text']

    def test_multidict_update_warning_unnecessary(self):
        # no warning on normal operation
        r = Response()
        r.headers.update([('Set-Cookie', 'a=b')])
        self.assertEqual(len(self.warnings), 0)
