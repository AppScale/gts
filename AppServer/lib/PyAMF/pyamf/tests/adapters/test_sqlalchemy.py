# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
PyAMF SQLAlchemy adapter tests.

@since 0.4
"""

import unittest

try:
    import sqlalchemy
    from sqlalchemy import MetaData, Table, Column, Integer, String, ForeignKey, \
        create_engine
    from sqlalchemy.orm import mapper, relation, sessionmaker, clear_mappers

    from pyamf.adapters import _sqlalchemy_orm as adapter
except ImportError:
    sqlalchemy = None

import pyamf.flex
from pyamf.tests.util import Spam


class BaseObject(object):
    def __init__(self, **kwargs):
        self.__dict__.update(kwargs)


class User(BaseObject):
    def __init__(self, **kwargs):
        BaseObject.__init__(self, **kwargs)

        self.lazy_loaded = [LazyLoaded()]


class Address(BaseObject):
    pass


class LazyLoaded(BaseObject):
    pass


class AnotherLazyLoaded(BaseObject):
    pass


class BaseTestCase(unittest.TestCase):
    """
    Initialise up all table/mappers.
    """

    def setUp(self):
        if not sqlalchemy:
            self.skipTest("'sqlalchemy' is not available")

        # Create DB and map objects
        self.metadata = MetaData()
        self.engine = create_engine('sqlite:///:memory:', echo=False)

        Session = sessionmaker(bind=self.engine)

        self.session = Session()
        self.tables = {}

        self.tables['users'] = Table('users', self.metadata,
            Column('id', Integer, primary_key=True),
            Column('name', String(64)))

        self.tables['addresses'] = Table('addresses', self.metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', Integer, ForeignKey('users.id')),
            Column('email_address', String(128)))

        self.tables['lazy_loaded'] = Table('lazy_loaded', self.metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', Integer, ForeignKey('users.id')))

        self.tables['another_lazy_loaded'] = Table('another_lazy_loaded', self.metadata,
            Column('id', Integer, primary_key=True),
            Column('user_id', Integer, ForeignKey('users.id')))

        self.mappers = {}

        self.mappers['user'] = mapper(User, self.tables['users'], properties={
            'addresses': relation(Address, backref='user', lazy=False),
            'lazy_loaded': relation(LazyLoaded, lazy=True),
            'another_lazy_loaded': relation(AnotherLazyLoaded, lazy=True)
        })

        self.mappers['addresses'] = mapper(Address, self.tables['addresses'])
        self.mappers['lazy_loaded'] = mapper(LazyLoaded,
            self.tables['lazy_loaded'])
        self.mappers['another_lazy_loaded'] = mapper(AnotherLazyLoaded,
            self.tables['another_lazy_loaded'])

        self.metadata.create_all(self.engine)

        pyamf.register_class(User, 'server.User')
        pyamf.register_class(Address, 'server.Address')
        pyamf.register_class(LazyLoaded, 'server.LazyLoaded')

    def tearDown(self):
        clear_mappers()

        pyamf.unregister_class(User)
        pyamf.unregister_class(Address)
        pyamf.unregister_class(LazyLoaded)

    def _build_obj(self):
        user = User()
        user.name = "test_user"
        user.addresses.append(Address(email_address="test@example.org"))

        return user

    def _save(self, obj):
        # this covers deprecation warnings etc.
        if hasattr(self.session, 'add'):
            self.session.add(obj)
        elif hasattr(self.session, 'save'):
            self.session.save(obj)
        else:
            raise AttributeError('Don\'t know how to save an object')

    def _clear(self):
        # this covers deprecation warnings etc.
        if hasattr(self.session, 'expunge_all'):
            self.session.expunge_all()
        elif hasattr(self.session, 'clear'):
            self.session.clear()
        else:
            raise AttributeError('Don\'t know how to clear session')


class SATestCase(BaseTestCase):
    def _test_obj(self, encoded, decoded):
        self.assertEqual(User, decoded.__class__)
        self.assertEqual(encoded.name, decoded.name)
        self.assertEqual(encoded.addresses[0].email_address, decoded.addresses[0].email_address)

    def test_encode_decode_transient(self):
        user = self._build_obj()

        encoder = pyamf.get_encoder(pyamf.AMF3)
        encoder.writeElement(user)
        encoded = encoder.stream.getvalue()
        decoded = pyamf.get_decoder(pyamf.AMF3, encoded).readElement()

        self._test_obj(user, decoded)

    def test_encode_decode_persistent(self):
        user = self._build_obj()
        self._save(user)
        self.session.commit()
        self.session.refresh(user)

        encoder = pyamf.get_encoder(pyamf.AMF3)
        encoder.writeElement(user)
        encoded = encoder.stream.getvalue()
        decoded = pyamf.get_decoder(pyamf.AMF3, encoded).readElement()

        self._test_obj(user, decoded)

    def test_encode_decode_list(self):
        max = 5
        for i in range(0, max):
            user = self._build_obj()
            user.name = "%s" % i
            self._save(user)

        self.session.commit()
        users = self.session.query(User).all()

        encoder = pyamf.get_encoder(pyamf.AMF3)

        encoder.writeElement(users)
        encoded = encoder.stream.getvalue()
        decoded = pyamf.get_decoder(pyamf.AMF3, encoded).readElement()
        self.assertEqual([].__class__, decoded.__class__)

        for i in range(0, max):
            self._test_obj(users[i], decoded[i])

    def test_sa_merge(self):
        user = self._build_obj()

        for i, string in enumerate(['one', 'two', 'three']):
            addr = Address(email_address="%s@example.org" % string)
            user.addresses.append(addr)

        self._save(user)
        self.session.commit()
        self.session.refresh(user)

        encoder = pyamf.get_encoder(pyamf.AMF3)
        encoder.writeElement(user)
        encoded = encoder.stream.getvalue()

        decoded = pyamf.get_decoder(pyamf.AMF3, encoded).readElement()
        del decoded.addresses[0]
        del decoded.addresses[1]

        merged_user = self.session.merge(decoded)
        self.assertEqual(len(merged_user.addresses), 2)

    def test_encode_decode_with_references(self):
        user = self._build_obj()
        self._save(user)
        self.session.commit()
        self.session.refresh(user)

        max = 5
        users = []
        for i in range(0, max):
            users.append(user)

        encoder = pyamf.get_encoder(pyamf.AMF3)
        encoder.writeElement(users)
        encoded = encoder.stream.getvalue()

        decoded = pyamf.get_decoder(pyamf.AMF3, encoded).readElement()

        for i in range(0, max):
            self.assertEqual(id(decoded[0]), id(decoded[i]))


class BaseClassAliasTestCase(BaseTestCase):
    def setUp(self):
        BaseTestCase.setUp(self)

        self.alias = pyamf.get_class_alias(User)


class ClassAliasTestCase(BaseClassAliasTestCase):
    def test_type(self):
        self.assertEqual(self.alias.__class__, adapter.SaMappedClassAlias)

    def test_get_mapper(self):
        self.assertFalse(hasattr(self.alias, 'mapper'))

        self.alias.compile()
        mapper = adapter.class_mapper(User)

        self.assertTrue(hasattr(self.alias, 'mapper'))
        self.assertEqual(id(mapper), id(self.alias.mapper))

        self.assertEqual(self.alias.static_attrs, [])

    def test_get_attrs(self):
        u = self._build_obj()
        attrs = self.alias.getEncodableAttributes(u)

        self.assertEqual(sorted(attrs.keys()), [
            'addresses',
            'another_lazy_loaded',
            'id',
            'lazy_loaded',
            'name',
            'sa_key',
            'sa_lazy'
        ])

        self.assertEqual(attrs['sa_key'], [None])
        self.assertEqual(attrs['sa_lazy'], [])

    def test_get_attributes(self):
        u = self._build_obj()

        self.assertFalse(u in self.session)
        self.assertEqual([None], self.mappers['user'].primary_key_from_instance(u))
        attrs = self.alias.getEncodableAttributes(u)

        self.assertEqual(attrs, {
            'addresses': u.addresses,
            'lazy_loaded': u.lazy_loaded,
            'another_lazy_loaded': [],
            'id': None,
            'name': 'test_user',
            'sa_lazy': [],
            'sa_key': [None]
        })

    def test_property(self):
        class Person(object):
            foo = 'bar'
            baz = 'gak'

            def _get_rw_property(self):
                return self.foo

            def _set_rw_property(self, val):
                self.foo = val

            def _get_ro_property(self):
                return self.baz

            rw = property(_get_rw_property, _set_rw_property)
            ro = property(_get_ro_property)

        self.mappers['person'] = mapper(Person, self.tables['users'])

        alias = adapter.SaMappedClassAlias(Person, 'person')

        obj = Person()

        attrs = alias.getEncodableAttributes(obj)
        self.assertEqual(attrs, {
            'id': None,
            'name': None,
            'sa_key': [None],
            'sa_lazy': [],
            'rw': 'bar',
            'ro': 'gak'})

        self.assertEqual(obj.ro, 'gak')
        alias.applyAttributes(obj, {
            'sa_key': [None],
            'sa_lazy': [],
            'id': None,
            'name': None,
            'rw': 'bar',
            'ro': 'baz'})
        self.assertEqual(obj.ro, 'gak')


class ApplyAttributesTestCase(BaseClassAliasTestCase):
    def test_undefined(self):
        u = self.alias.createInstance()

        attrs = {
            'sa_lazy': ['another_lazy_loaded'],
            'sa_key': [None],
            'addresses': [],
            'lazy_loaded': [],
            'another_lazy_loaded': pyamf.Undefined, # <-- the important bit
            'id': None,
            'name': 'test_user'
        }

        self.alias.applyAttributes(u, attrs)

        d = u.__dict__.copy()

        if sqlalchemy.__version__.startswith('0.4'):
            self.assertTrue('_state' in d)
            del d['_state']
        else:
            self.assertTrue('_sa_instance_state' in d)
            del d['_sa_instance_state']

        self.assertEqual(d, {
            'lazy_loaded': [],
            'addresses': [],
            'name': 'test_user',
            'id': None
        })

    def test_decode_unaliased(self):
        u = self.alias.createInstance()

        attrs = {
            'sa_lazy': [],
            'sa_key': [None],
            'addresses': [],
            'lazy_loaded': [],
            # this is important because we haven't registered AnotherLazyLoaded
            # as an alias and the decoded object for an untyped object is an
            # instance of pyamf.ASObject
            'another_lazy_loaded': [pyamf.ASObject({'id': 1, 'user_id': None})],
            'id': None,
            'name': 'test_user'
        }

        # sqlalchemy can't find any state to work with
        self.assertRaises(AttributeError, self.alias.applyAttributes, u, attrs)


class AdapterTestCase(BaseTestCase):
    """
    Checks to see if the adapter will actually intercept a class correctly.
    """

    def test_mapped(self):
        self.assertNotEquals(None, adapter.class_mapper(User))
        self.assertTrue(adapter.is_class_sa_mapped(User))

    def test_instance(self):
        u = User()

        self.assertTrue(adapter.is_class_sa_mapped(u))

    def test_not_mapped(self):
        self.assertRaises(adapter.UnmappedInstanceError, adapter.class_mapper, Spam)
        self.assertFalse(adapter.is_class_sa_mapped(Spam))


class ExcludableAttrsTestCase(BaseTestCase):
    """
    Tests for #790
    """

    def test_core_attrs(self):
        """
        Ensure that sa_key and sa_lazy can be excluded
        """
        a = adapter.SaMappedClassAlias(Address, exclude_attrs=['sa_lazy', 'sa_key'])
        u = Address()

        attrs = a.getEncodableAttributes(u)

        self.assertFalse('sa_key' in attrs)
        self.assertFalse('sa_lazy' in attrs)