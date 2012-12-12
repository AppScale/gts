# -*- coding: utf-8 -*-

import unittest
from webob import multidict

class BaseDictTests(object):
    def setUp(self):
        self._list = [('a', u'\xe9'), ('a', 'e'), ('a', 'f'), ('b', 1)]
        self.data = multidict.MultiDict(self._list)
        self.d = self._get_instance()

    def _get_instance(self, **kwargs):
        if kwargs:
            data = multidict.MultiDict(kwargs)
        else:
            data = self.data.copy()
        return self.klass(data)

    def test_len(self):
        self.assertEqual(len(self.d), 4)

    def test_getone(self):
        self.assertEqual(self.d.getone('b'),  1)

    def test_getone_missing(self):
        self.assertRaises(KeyError, self.d.getone, 'z')

    def test_getone_multiple_raises(self):
        self.assertRaises(KeyError, self.d.getone, 'a')

    def test_getall(self):
        self.assertEqual(self.d.getall('b'), [1])

    def test_dict_of_lists(self):
        self.assertEqual(
            self.d.dict_of_lists(),
            {'a': [u'\xe9', u'e', u'f'], 'b': [1]})

    def test_dict_api(self):
        self.assertTrue('a' in self.d.mixed())
        self.assertTrue('a' in self.d.keys())
        self.assertTrue('a' in self.d.iterkeys())
        self.assertTrue(('b', 1) in self.d.items())
        self.assertTrue(('b', 1) in self.d.iteritems())
        self.assertTrue(1 in self.d.values())
        self.assertTrue(1 in self.d.itervalues())
        self.assertEqual(len(self.d), 4)

    def test_set_del_item(self):
        d = self._get_instance()
        self.assertTrue('a' in d)
        del d['a']
        self.assertTrue(not 'a' in d)

    def test_pop(self):
        d = self._get_instance()
        d['a'] = 1
        self.assertEqual(d.pop('a'), 1)
        self.assertEqual(d.pop('x', 1), 1)

    def test_pop_wrong_args(self):
        d = self._get_instance()
        self.assertRaises(TypeError, d.pop, 'a', 1, 1)

    def test_pop_missing(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.pop, 'z')

    def test_popitem(self):
        d = self._get_instance()
        self.assertEqual(d.popitem(), ('b', 1))

    def test_update(self):
        d = self._get_instance()
        d.update(e=1)
        self.assertTrue('e' in d)
        d.update(dict(x=1))
        self.assertTrue('x' in d)
        d.update([('y', 1)])
        self.assertTrue('y' in d)

    def test_setdefault(self):
        d = self._get_instance()
        d.setdefault('a', 1)
        self.assertNotEqual(d['a'], 1)
        d.setdefault('e', 1)
        self.assertTrue('e' in d)

    def test_add(self):
        d = self._get_instance()
        d.add('b', 3)
        self.assertEqual(d.getall('b'), [1, 3])

    def test_copy(self):
        assert self.d.copy() is not self.d
        if hasattr(self.d, 'multi'):
            self.assertFalse(self.d.copy().multi is self.d.multi)
            self.assertFalse(self.d.copy() is self.d.multi)

    def test_clear(self):
        d = self._get_instance()
        d.clear()
        self.assertEqual(len(d), 0)

    def test_nonzero(self):
        d = self._get_instance()
        self.assertTrue(d)
        d.clear()
        self.assertFalse(d)

    def test_repr(self):
        self.assertTrue(repr(self._get_instance()))

    def test_too_many_args(self):
        from webob.multidict import MultiDict
        self.assertRaises(TypeError, MultiDict, 1, 2)

    def test_no_args(self):
        from webob.multidict import MultiDict
        md = MultiDict()
        self.assertEqual(md._items, [])

    def test_kwargs(self):
        from webob.multidict import MultiDict
        md = MultiDict(kw1='val1')
        self.assertEqual(md._items, [('kw1','val1')])

    def test_view_list_not_list(self):
        from webob.multidict import MultiDict
        d = MultiDict()
        self.assertRaises(TypeError, d.view_list, 42)

    def test_view_list(self):
        from webob.multidict import MultiDict
        d = MultiDict()
        self.assertEqual(d.view_list([1,2])._items, [1,2])

    def test_from_fieldstorage_with_filename(self):
        from webob.multidict import MultiDict
        d = MultiDict()
        fs = DummyFieldStorage('a', '1', 'file')
        self.assertEqual(d.from_fieldstorage(fs), MultiDict({'a':fs.list[0]}))

    def test_from_fieldstorage_without_filename(self):
        from webob.multidict import MultiDict
        d = MultiDict()
        fs = DummyFieldStorage('a', '1')
        self.assertEqual(d.from_fieldstorage(fs), MultiDict({'a':'1'}))

class MultiDictTestCase(BaseDictTests, unittest.TestCase):
    klass = multidict.MultiDict

    def test_update_behavior_warning(self):
        import warnings
        class Foo(dict):
            def __len__(self):
                return 0
        foo = Foo()
        foo['a'] = 1
        d = self._get_instance()
        try:
            warnings.simplefilter('error')
            self.assertRaises(UserWarning, d.update, foo)
        finally:
            warnings.resetwarnings()

    def test_repr_with_password(self):
        d = self._get_instance(password='pwd')
        self.assertEqual(repr(d), "MultiDict([('password', '******')])")

class UnicodeMultiDictTestCase(BaseDictTests, unittest.TestCase):
    klass = multidict.UnicodeMultiDict

    def test_decode_key(self):
        d = self._get_instance()
        d.decode_keys = True

        class Key(object):
            pass

        key = Key()
        self.assertEquals(key, d._decode_key(key))

    def test_decode_value(self):
        import cgi

        d = self._get_instance()
        d.decode_keys = True

        env = {'QUERY_STRING': ''}
        fs = cgi.FieldStorage(environ=env)
        fs.name = 'a'
        self.assertEqual(d._decode_value(fs).name, 'a')

    def test_encode_key(self):
        d = self._get_instance()
        value = unicode('a')
        d.decode_keys = True
        self.assertEquals(d._encode_key(value),'a')

    def test_encode_value(self):
        d = self._get_instance()
        value = unicode('a')
        self.assertEquals(d._encode_value(value),'a')

    def test_repr_with_password(self):
        d = self._get_instance(password='pwd')
        self.assertEqual(repr(d), "UnicodeMultiDict([('password', '******')])")

class NestedMultiDictTestCase(BaseDictTests, unittest.TestCase):
    klass = multidict.NestedMultiDict

    def test_getitem(self):
        d = self.klass({'a':1})
        self.assertEqual(d['a'], 1)

    def test_getitem_raises(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.__getitem__, 'z')

    def test_contains(self):
        d = self._get_instance()
        assert 'a' in d
        assert 'z' not in d

    def test_add(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.add, 'b', 3)

    def test_set_del_item(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.__delitem__, 'a')
        self.assertRaises(KeyError, d.__setitem__, 'a', 1)

    def test_update(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.update, e=1)
        self.assertRaises(KeyError, d.update, dict(x=1))
        self.assertRaises(KeyError, d.update, [('y', 1)])

    def test_setdefault(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.setdefault, 'a', 1)

    def test_pop(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.pop, 'a')
        self.assertRaises(KeyError, d.pop, 'a', 1)

    def test_popitem(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.popitem, 'a')

    def test_pop_wrong_args(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.pop, 'a', 1, 1)

    def test_clear(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.clear)

    def test_nonzero(self):
        d = self._get_instance()
        self.assertEqual(d.__nonzero__(), True)
        d.dicts = [{}]
        self.assertEqual(d.__nonzero__(), False)
        assert not d

class TrackableMultiDict(BaseDictTests, unittest.TestCase):
    klass = multidict.TrackableMultiDict

    def _get_instance(self, **kwargs):
        if kwargs:
            data = multidict.MultiDict(kwargs)
        else:
            data = self.data.copy()
        def tracker(*args, **kwargs): pass
        return self.klass(data, __tracker=tracker, __name='tracker')

    def test_inititems(self):
        #The first argument passed into the __init__ method
        class Arg:
            def items(self):
                return [('a', u'\xe9'), ('a', 'e'), ('a', 'f'), ('b', 1)]

        d = self._get_instance()
        d._items = None
        d.__init__(Arg())
        self.assertEquals(self.d._items, self._list)

    def test_nullextend(self):
        d = self._get_instance()
        self.assertEqual(d.extend(), None)
        d.extend(test = 'a')
        self.assertEqual(d['test'], 'a')

    def test_listextend(self):
        class Other:
            def items(self):
                return [u'\xe9', u'e', r'f', 1]

        other = Other()
        d = self._get_instance()
        d.extend(other)

        _list = [u'\xe9', u'e', r'f', 1]
        for v in _list:
            self.assertTrue(v in d._items)

    def test_dictextend(self):
        class Other:
            def __getitem__(self, item):
                return {'a':1, 'b':2, 'c':3}.get(item)

            def keys(self):
                return ['a', 'b', 'c']

        other = Other()
        d = self._get_instance()
        d.extend(other)

        _list = [('a', 1), ('b', 2), ('c', 3)]
        for v in _list:
            self.assertTrue(v in d._items)

    def test_otherextend(self):
        class Other(object):
            def __iter__(self):
                return iter([('a', 1)])

        other = Other()
        d = self._get_instance()
        d.extend(other)

        _list = [('a', 1)]
        for v in _list:
            self.assertTrue(v in d._items)

    def test_repr_with_password(self):
        d = self._get_instance(password='pwd')
        self.assertEqual(repr(d), "tracker([('password', '******')])")

class NoVarsTestCase(unittest.TestCase):
    klass = multidict.NoVars

    def _get_instance(self):
        return self.klass()

    def test_getitem(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.__getitem__, 'a')

    def test_setitem(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.__setitem__, 'a')

    def test_delitem(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.__delitem__, 'a')

    def test_get(self):
        d = self._get_instance()
        self.assertEqual(d.get('a', default = 'b'), 'b')

    def test_getall(self):
        d = self._get_instance()
        self.assertEqual(d.getall('a'), [])

    def test_getone(self):
        d = self._get_instance()
        self.assertRaises(KeyError, d.getone, 'a')

    def test_mixed(self):
        d = self._get_instance()
        self.assertEqual(d.mixed(), {})

    def test_contains(self):
        d = self._get_instance()
        assert 'a' not in d

    def test_copy(self):
        d = self._get_instance()
        self.assertEqual(d.copy(), d)

    def test_len(self):
        d = self._get_instance()
        self.assertEqual(len(d), 0)

    def test_repr(self):
        d = self._get_instance()
        self.assertEqual(repr(d), '<NoVars: N/A>')

    def test_keys(self):
        d = self._get_instance()
        self.assertEqual(d.keys(), [])

    def test_iterkeys(self):
        d = self._get_instance()
        self.assertEqual(list(d.iterkeys()), [])

class DummyField(object):
    def __init__(self, name, value, filename=None):
        self.name = name
        self.value = value
        self.filename = filename

class DummyFieldStorage(object):
    def __init__(self, name, value, filename=None):
        self.list = [DummyField(name, value, filename)]

