from nose.tools import eq_
from nose.tools import raises
import unittest


def test_cache_control_object_max_age_None():
    from webob.cachecontrol import CacheControl
    cc = CacheControl({}, 'a')
    cc.properties['max-age'] = None
    eq_(cc.max_age, -1)


class TestUpdateDict(unittest.TestCase):

    def setUp(self):
        self.call_queue = []
        def callback(args):
            self.call_queue.append("Called with: %s" % repr(args))
        self.callback = callback

    def make_one(self, callback):
        from webob.cachecontrol import UpdateDict
        ud = UpdateDict()
        ud.updated = callback
        return ud

    def test_clear(self):
        newone = self.make_one(self.callback)
        newone['first'] = 1
        assert len(newone) == 1
        newone.clear()
        assert len(newone) == 0

    def test_update(self):
        newone = self.make_one(self.callback)
        d = {'one' : 1 }
        newone.update(d)
        assert newone == d

    def test_set_delete(self):
        newone = self.make_one(self.callback)
        newone['first'] = 1
        assert len(self.call_queue) == 1
        assert self.call_queue[-1] == "Called with: {'first': 1}"

        del newone['first']
        assert len(self.call_queue) == 2
        assert self.call_queue[-1] == 'Called with: {}'

    def test_setdefault(self):
        newone = self.make_one(self.callback)
        assert newone.setdefault('haters', 'gonna-hate') == 'gonna-hate'
        assert len(self.call_queue) == 1
        assert self.call_queue[-1] == "Called with: {'haters': 'gonna-hate'}", self.call_queue[-1]

        # no effect if failobj is not set
        assert newone.setdefault('haters', 'gonna-love') == 'gonna-hate'
        assert len(self.call_queue) == 1

    def test_pop(self):
        newone = self.make_one(self.callback)
        newone['first'] = 1
        newone.pop('first')
        assert len(self.call_queue) == 2
        assert self.call_queue[-1] == 'Called with: {}', self.call_queue[-1]

    def test_popitem(self):
        newone = self.make_one(self.callback)
        newone['first'] = 1
        assert newone.popitem() == ('first', 1)
        assert len(self.call_queue) == 2
        assert self.call_queue[-1] == 'Called with: {}', self.call_queue[-1]

    def test_callback_args(self):
        assert True
        #assert False


class TestExistProp(unittest.TestCase):
    """
    Test webob.cachecontrol.exists_property
    """

    def setUp(self):
        pass

    def make_one(self):
        from webob.cachecontrol import exists_property

        class Dummy(object):
            properties = dict(prop=1)
            type = 'dummy'
            prop = exists_property('prop', 'dummy')
            badprop = exists_property('badprop', 'big_dummy')

        return Dummy

    def test_get_on_class(self):
        from webob.cachecontrol import exists_property
        Dummy = self.make_one()
        assert isinstance(Dummy.prop, exists_property), Dummy.prop

    def test_get_on_instance(self):
        obj = self.make_one()()
        assert obj.prop is True

    @raises(AttributeError)
    def test_type_mismatch_raise(self):
        obj = self.make_one()()
        obj.badprop = True

    def test_set_w_value(self):
        obj = self.make_one()()
        obj.prop = True
        assert obj.prop is True
        assert obj.properties['prop'] is None

    def test_del_value(self):
        obj = self.make_one()()
        del obj.prop
        assert not 'prop' in obj.properties


class TestValueProp(unittest.TestCase):
    """
    Test webob.cachecontrol.exists_property
    """

    def setUp(self):
        pass

    def make_one(self):
        from webob.cachecontrol import value_property

        class Dummy(object):
            properties = dict(prop=1)
            type = 'dummy'
            prop = value_property('prop', 'dummy')
            badprop = value_property('badprop', 'big_dummy')

        return Dummy

    def test_get_on_class(self):
        from webob.cachecontrol import value_property
        Dummy = self.make_one()
        assert isinstance(Dummy.prop, value_property), Dummy.prop

    def test_get_on_instance(self):
        dummy = self.make_one()()
        assert dummy.prop, dummy.prop
        #assert isinstance(Dummy.prop, value_property), Dummy.prop

    def test_set_on_instance(self):
        dummy = self.make_one()()
        dummy.prop = "new"
        assert dummy.prop == "new", dummy.prop
        assert dummy.properties['prop'] == "new", dict(dummy.properties)

    def test_set_on_instance_bad_attribute(self):
        dummy = self.make_one()()
        dummy.prop = "new"
        assert dummy.prop == "new", dummy.prop
        assert dummy.properties['prop'] == "new", dict(dummy.properties)

    def test_set_wrong_type(self):
        from webob.cachecontrol import value_property
        class Dummy(object):
            properties = dict(prop=1, type='fail')
            type = 'dummy'
            prop = value_property('prop', 'dummy', type='failingtype')
        dummy = Dummy()
        def assign():
            dummy.prop = 'foo'
        self.assertRaises(AttributeError, assign)

    def test_set_type_true(self):
        dummy = self.make_one()()
        dummy.prop = True
        self.assertEquals(dummy.prop, None)

    def test_set_on_instance_w_default(self):
        dummy = self.make_one()()
        dummy.prop = "dummy"
        assert dummy.prop == "dummy", dummy.prop
        #@@ this probably needs more tests

    def test_del(self):
        dummy = self.make_one()()
        dummy.prop = 'Ian Bicking likes to skip'
        del dummy.prop
        assert dummy.prop == "dummy", dummy.prop


def test_copy_cc():
    from webob.cachecontrol import CacheControl
    cc = CacheControl({'header':'%', "msg":'arewerichyet?'}, 'request')
    cc2 = cc.copy()
    assert cc.properties is not cc2.properties
    assert cc.type is cc2.type

# 212

def test_serialize_cache_control_emptydict():
    from webob.cachecontrol import serialize_cache_control
    result = serialize_cache_control(dict())
    assert result == ''

def test_serialize_cache_control_cache_control_object():
    from webob.cachecontrol import serialize_cache_control, CacheControl
    result = serialize_cache_control(CacheControl({}, 'request'))
    assert result == ''

def test_serialize_cache_control_object_with_headers():
    from webob.cachecontrol import serialize_cache_control, CacheControl
    result = serialize_cache_control(CacheControl({'header':'a'}, 'request'))
    assert result == 'header=a'

def test_serialize_cache_control_value_is_None():
    from webob.cachecontrol import serialize_cache_control, CacheControl
    result = serialize_cache_control(CacheControl({'header':None}, 'request'))
    assert result == 'header'

def test_serialize_cache_control_value_needs_quote():
    from webob.cachecontrol import serialize_cache_control, CacheControl
    result = serialize_cache_control(CacheControl({'header':'""'}, 'request'))
    assert result == 'header=""""'

class TestCacheControl(unittest.TestCase):
    def make_one(self, props, typ):
        from webob.cachecontrol import CacheControl
        return CacheControl(props, typ)

    def test_ctor(self):
        cc = self.make_one({'a':1}, 'typ')
        self.assertEquals(cc.properties, {'a':1})
        self.assertEquals(cc.type, 'typ')

    def test_parse(self):
        from webob.cachecontrol import CacheControl
        cc = CacheControl.parse("public, max-age=315360000")
        self.assertEquals(type(cc), CacheControl)
        self.assertEquals(cc.max_age, 315360000)
        self.assertEquals(cc.public, True)

    def test_parse_updates_to(self):
        from webob.cachecontrol import CacheControl
        def foo(arg): return { 'a' : 1 }
        cc = CacheControl.parse("public, max-age=315360000", updates_to=foo)
        self.assertEquals(type(cc), CacheControl)
        self.assertEquals(cc.max_age, 315360000)

    def test_parse_valueerror_int(self):
        from webob.cachecontrol import CacheControl
        def foo(arg): return { 'a' : 1 }
        cc = CacheControl.parse("public, max-age=abc")
        self.assertEquals(type(cc), CacheControl)
        self.assertEquals(cc.max_age, 'abc')

    def test_repr(self):
        cc = self.make_one({'a':'1'}, 'typ')
        result = repr(cc)
        self.assertEqual(result, "<CacheControl 'a=1'>")
        
        
        

