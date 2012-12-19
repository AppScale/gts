import unittest
from webob.etag import ETagMatcher

class etag_propertyTests(unittest.TestCase):
    def _getTargetClass(self):
        from webob.etag import etag_property
        return etag_property

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def _makeDummyRequest(self, **kw):
        """
        Return a DummyRequest object with attrs from kwargs.
        Use like:     dr = _makeDummyRequest(environment={'userid': 'johngalt'})
        Then you can: uid = dr.environment.get('userid', 'SomeDefault')
        """
        class Dummy(object):
            def __init__(self, **kwargs):
                self.__dict__.update(**kwargs)
        d = Dummy(**kw)
        return d

    def test_fget_missing_key(self):
        ep = self._makeOne("KEY", "DEFAULT", "RFC_SECTION")
        req = self._makeDummyRequest(environ={})
        self.assertEquals(ep.fget(req), "DEFAULT")

    def test_fget_found_key(self):
        ep = self._makeOne("KEY", "DEFAULT", "RFC_SECTION")
        req = self._makeDummyRequest(environ={'KEY':'VALUE'})
        res = ep.fget(req)
        self.assertEquals(res.etags, ['VALUE'])
        self.assertEquals(res.weak_etags, [])

    def test_fget_star_key(self):
        ep = self._makeOne("KEY", "DEFAULT", "RFC_SECTION")
        req = self._makeDummyRequest(environ={'KEY':'*'})
        res = ep.fget(req)
        import webob.etag
        self.assertEquals(type(res), webob.etag._AnyETag)
        self.assertEquals(res.__dict__, {})

    def test_fset_None(self):
        ep = self._makeOne("KEY", "DEFAULT", "RFC_SECTION")
        req = self._makeDummyRequest(environ={'KEY':'*'})
        res = ep.fset(req, None)
        self.assertEquals(res, None)

    def test_fset_not_None(self):
        ep = self._makeOne("KEY", "DEFAULT", "RFC_SECTION")
        req = self._makeDummyRequest(environ={'KEY':'OLDVAL'})
        res = ep.fset(req, "NEWVAL")
        self.assertEquals(res, None)
        self.assertEquals(req.environ['KEY'], 'NEWVAL')

    def test_fedl(self):
        ep = self._makeOne("KEY", "DEFAULT", "RFC_SECTION")
        req = self._makeDummyRequest(environ={'KEY':'VAL', 'QUAY':'VALYOU'})
        res = ep.fdel(req)
        self.assertEquals(res, None)
        self.assertFalse('KEY' in req.environ)
        self.assertEquals(req.environ['QUAY'], 'VALYOU')

class AnyETagTests(unittest.TestCase):
    def _getTargetClass(self):
        from webob.etag import _AnyETag
        return _AnyETag

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test___repr__(self):
        etag = self._makeOne()
        self.assertEqual(etag.__repr__(), '<ETag *>')

    def test___nonzero__(self):
        etag = self._makeOne()
        self.assertEqual(etag.__nonzero__(), False)

    def test___contains__something(self):
        etag = self._makeOne()
        self.assertEqual('anything' in etag, True)

    def test_weak_match_something(self):
        etag = self._makeOne()
        self.assertEqual(etag.weak_match('anything'), True)

    def test___str__(self):
        etag = self._makeOne()
        self.assertEqual(str(etag), '*')

class NoETagTests(unittest.TestCase):
    def _getTargetClass(self):
        from webob.etag import _NoETag
        return _NoETag

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test___repr__(self):
        etag = self._makeOne()
        self.assertEqual(etag.__repr__(), '<No ETag>')

    def test___nonzero__(self):
        etag = self._makeOne()
        self.assertEqual(etag.__nonzero__(), False)

    def test___contains__something(self):
        etag = self._makeOne()
        assert 'anything' not in etag

    def test_weak_match_None(self):
        etag = self._makeOne()
        self.assertEqual(etag.weak_match(None), False)

    def test_weak_match_something(self):
        etag = self._makeOne()
        assert not etag.weak_match('anything')

    def test___str__(self):
        etag = self._makeOne()
        self.assertEqual(str(etag), '')

class ETagMatcherTests(unittest.TestCase):
    def _getTargetClass(self):
        return ETagMatcher

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test___init__wo_weak_etags(self):
        matcher = self._makeOne(("ETAGS",))
        self.assertEqual(matcher.etags, ("ETAGS",))
        self.assertEqual(matcher.weak_etags, ())

    def test___init__w_weak_etags(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertEqual(matcher.etags, ("ETAGS",))
        self.assertEqual(matcher.weak_etags, ("WEAK",))

    def test___contains__tags(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertTrue("ETAGS" in matcher)

    def test___contains__weak_tags(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertTrue("WEAK" in matcher)

    def test___contains__not(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertFalse("BEER" in matcher)

    def test___contains__None(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertFalse(None in matcher)

    def test_weak_match_etags(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertTrue(matcher.weak_match("W/ETAGS"))

    def test_weak_match_weak_etags(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertTrue(matcher.weak_match("W/WEAK"))

    def test_weak_match_weak_not(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertFalse(matcher.weak_match("W/BEER"))

    def test_weak_match_weak_wo_wslash(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertTrue(matcher.weak_match("ETAGS"))

    def test_weak_match_weak_wo_wslash_not(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertFalse(matcher.weak_match("BEER"))

    def test___repr__one(self):
        matcher = self._makeOne(("ETAGS",), ("WEAK",))
        self.assertEqual(matcher.__repr__(), '<ETag ETAGS>')

    def test___repr__multi(self):
        matcher = self._makeOne(("ETAG1","ETAG2"), ("WEAK",))
        self.assertEqual(matcher.__repr__(), '<ETag ETAG1 or ETAG2>')

    def test___str__etag(self):
        matcher = self._makeOne(("ETAG",))
        self.assertEqual(str(matcher), '"ETAG"')

    def test___str__etag_w_weak(self):
        matcher = self._makeOne(("ETAG",), ("WEAK",))
        self.assertEqual(str(matcher), '"ETAG", W/"WEAK"')



class ParseTests(unittest.TestCase):
    def test_parse_None(self):
        et = ETagMatcher.parse(None)
        self.assertEqual(et.etags, [])
        self.assertEqual(et.weak_etags, [])

    def test_parse_anyetag(self):
        # these tests smell bad, are they useful?
        et = ETagMatcher.parse('*')
        self.assertEqual(et.__dict__, {})
        self.assertEqual(et.__repr__(), '<ETag *>')

    def test_parse_one(self):
        et = ETagMatcher.parse('ONE')
        self.assertEqual(et.etags, ['ONE'])
        self.assertEqual(et.weak_etags, [])

    def test_parse_commasep(self):
        et = ETagMatcher.parse('ONE, TWO')
        self.assertEqual(et.etags, ['ONE', 'TWO'])
        self.assertEqual(et.weak_etags, [])

    def test_parse_commasep_w_weak(self):
        et = ETagMatcher.parse('ONE, w/TWO')
        self.assertEqual(et.etags, ['ONE'])
        self.assertEqual(et.weak_etags, ['TWO'])

    def test_parse_quoted(self):
        et = ETagMatcher.parse('"ONE"')
        self.assertEqual(et.etags, ['ONE'])
        self.assertEqual(et.weak_etags, [])

    def test_parse_quoted_two(self):
        et = ETagMatcher.parse('"ONE", "TWO"')
        self.assertEqual(et.etags, ['ONE', 'TWO'])
        self.assertEqual(et.weak_etags, [])

    def test_parse_quoted_two_weak(self):
        et = ETagMatcher.parse('"ONE", W/"TWO"')
        self.assertEqual(et.etags, ['ONE'])
        self.assertEqual(et.weak_etags, ['TWO'])

    def test_parse_wo_close_quote(self):
        # Unsure if this is testing likely input
        et = ETagMatcher.parse('"ONE')
        self.assertEqual(et.etags, ['ONE'])
        self.assertEqual(et.weak_etags, [])

class IfRangeTests(unittest.TestCase):
    def _getTargetClass(self):
        from webob.etag import IfRange
        return IfRange

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test___init__(self):
        ir = self._makeOne()
        self.assertEqual(ir.etag, None)
        self.assertEqual(ir.date, None)

    def test___init__etag(self):
        ir = self._makeOne(etag='ETAG')
        self.assertEqual(ir.etag, 'ETAG')
        self.assertEqual(ir.date, None)

    def test___init__date(self):
        ir = self._makeOne(date='DATE')
        self.assertEqual(ir.etag, None)
        self.assertEqual(ir.date, 'DATE')

    def test___init__etag_date(self):
        ir = self._makeOne(etag='ETAG', date='DATE')
        self.assertEqual(ir.etag, 'ETAG')
        self.assertEqual(ir.date, 'DATE')

    def test___repr__(self):
        ir = self._makeOne()
        self.assertEqual(ir.__repr__(), '<IfRange etag=*, date=*>')

    def test___repr__etag(self):
        ir = self._makeOne(etag='ETAG')
        self.assertEqual(ir.__repr__(), '<IfRange etag=ETAG, date=*>')

    def test___repr__date(self):
        ir = self._makeOne(date='Fri, 09 Nov 2001 01:08:47 -0000')
        self.assertEqual(ir.__repr__(),
                         '<IfRange etag=*, ' +
                         'date=Fri, 09 Nov 2001 01:08:47 -0000>')

    def test___repr__etag_date(self):
        ir = self._makeOne(etag='ETAG', date='Fri, 09 Nov 2001 01:08:47 -0000')
        self.assertEqual(ir.__repr__(),
                         '<IfRange etag=ETAG, ' +
                         'date=Fri, 09 Nov 2001 01:08:47 -0000>')

    def test___str__(self):
        ir = self._makeOne()
        self.assertEqual(str(ir), '')

    def test___str__etag(self):
        ir = self._makeOne(etag='ETAG', date='Fri, 09 Nov 2001 01:08:47 -0000')
        self.assertEqual(str(ir), 'ETAG')

    def test___str__date(self):
        ir = self._makeOne(date='Fri, 09 Nov 2001 01:08:47 -0000')
        self.assertEqual(str(ir), 'Fri, 09 Nov 2001 01:08:47 -0000')

    def test_match(self):
        ir = self._makeOne()
        self.assertTrue(ir.match())

    def test_match_date_none(self):
        ir = self._makeOne(date='Fri, 09 Nov 2001 01:08:47 -0000')
        self.assertFalse(ir.match())

    def test_match_date_earlier(self):
        ir = self._makeOne(date='Fri, 09 Nov 2001 01:08:47 -0000')
        self.assertTrue(ir.match(last_modified=
                                 'Fri, 09 Nov 2001 01:00:00 -0000'))

    def test_match_etag_none(self):
        ir = self._makeOne(etag="ETAG")
        self.assertFalse(ir.match())

    def test_match_etag_different(self):
        ir = self._makeOne(etag="ETAG")
        self.assertFalse(ir.match("DIFFERENT"))

    def test_match_response_no_date(self):
        class DummyResponse(object):
            etag = "ETAG"
            last_modified = None
        ir = self._makeOne(etag="ETAG", date='Fri, 09 Nov 2001 01:08:47 -0000')
        response = DummyResponse()
        self.assertFalse(ir.match_response(response))

    def test_match_response_w_date_earlier(self):
        class DummyResponse(object):
            etag = "ETAG"
            last_modified = 'Fri, 09 Nov 2001 01:00:00 -0000'
        ir = self._makeOne(etag="ETAG", date='Fri, 09 Nov 2001 01:08:47 -0000')
        response = DummyResponse()
        self.assertTrue(ir.match_response(response))

    def test_match_response_etag(self):
        class DummyResponse(object):
            etag = "ETAG"
            last_modified = None
        ir = self._makeOne(etag="ETAG")
        response = DummyResponse()
        self.assertTrue(ir.match_response(response))

    def test_parse_none(self):
        ir = self._makeOne(etag="ETAG")
        # I believe this identifies a bug: '_NoETag' object is not callable
        self.assertRaises(TypeError, ir.parse, None)

    def test_parse_wo_gmt(self):
        ir = self._makeOne(etag="ETAG")
        res = ir.parse('INTERPRETED_AS_ETAG')
        self.assertEquals(res.etag.etags, ['INTERPRETED_AS_ETAG'])
        self.assertEquals(res.date, None)

    def test_parse_with_gmt(self):
        import datetime
        class UTC(datetime.tzinfo):
            def utcoffset(self, dt):
                return datetime.timedelta(0)
            def tzname(self, dt):
                return 'UTC'
        ir = self._makeOne(etag="ETAG")
        res = ir.parse('Fri, 09 Nov 2001 01:08:47 GMT')
        self.assertEquals(res.etag, None)
        dt = datetime.datetime(2001,11,9, 1,8,47,0, UTC())
        self.assertEquals(res.date, dt)

class NoIfRangeTests(unittest.TestCase):
    def _getTargetClass(self):
        from webob.etag import _NoIfRange
        return _NoIfRange

    def _makeOne(self, *args, **kw):
        return self._getTargetClass()(*args, **kw)

    def test___repr__(self):
        ir = self._makeOne()
        self.assertEquals(ir.__repr__(), '<Empty If-Range>')

    def test___str__(self):
        ir = self._makeOne()
        self.assertEquals(str(ir), '')

    def test___nonzero__(self):
        ir = self._makeOne()
        self.assertEquals(ir.__nonzero__(), False)

    def test_match(self):
        ir = self._makeOne()
        self.assertEquals(ir.match(), True)

    def test_match_response(self):
        ir = self._makeOne()
        self.assertEquals(ir.match_response("IGNORED"), True)
