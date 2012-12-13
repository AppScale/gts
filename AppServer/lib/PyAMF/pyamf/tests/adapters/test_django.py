# Copyright (c) The PyAMF Project.
# See LICENSE.txt for details.

"""
PyAMF Django adapter tests.

@since: 0.3.1
"""

import unittest
import sys
import os
import datetime

import pyamf
from pyamf.tests import util

try:
    import django
except ImportError:
    django = None

if django and django.VERSION < (1, 0):
    django = None

try:
    reload(settings)
except NameError:
    from pyamf.tests.adapters.django_app import settings


context = None

#: django modules/functions used once bootstrapped
create_test_db = None
destroy_test_db = None
management = None
setup_test_environment = None
teardown_test_environment = None

# test app data
models = None
adapter = None

def init_django():
    """
    Bootstrap Django and initialise this module
    """
    global django, management, create_test_db, destroy_test_db
    global setup_test_environment, teardown_test_environment

    if not django:
        return

    from django.core import management

    project_dir = management.setup_environ(settings)
    sys.path.insert(0, project_dir)

    try:
        from django.test.utils import create_test_db, destroy_test_db
    except ImportError:
        from django.db import connection

        create_test_db = connection.creation.create_test_db
        destroy_test_db = connection.creation.destroy_test_db

    from django.test.utils import setup_test_environment, teardown_test_environment

    return True


def setUpModule():
    """
    Called to set up the module by the test runner
    """
    global context, models, adapter

    context = {
        'sys.path': sys.path[:],
        'sys.modules': sys.modules.copy(),
        'os.environ': os.environ.copy(),
    }

    if init_django():
        from pyamf.tests.adapters.django_app.adapters import models
        from pyamf.adapters import _django_db_models_base as adapter

        setup_test_environment()

        settings.DATABASE_NAME = create_test_db(0, True)


def teadDownModule():
    # remove all the stuff that django installed
    teardown_test_environment()

    sys.path = context['sys.path']
    util.replace_dict(context['sys.modules'], sys.modules)
    util.replace_dict(context['os.environ'], os.environ)

    destroy_test_db(settings.DATABASE_NAME, 2)


class BaseTestCase(unittest.TestCase):
    """
    """

    def setUp(self):
        if not django:
            self.skipTest("'django' is not available")


class TypeMapTestCase(BaseTestCase):
    """
    Tests for basic encoding functionality
    """

    def test_objects_all(self):
        encoder = pyamf.get_encoder(pyamf.AMF0)

        encoder.writeElement(models.SimplestModel.objects.all())
        self.assertEqual(encoder.stream.getvalue(), '\n\x00\x00\x00\x00')

        encoder = pyamf.get_encoder(pyamf.AMF3)
        encoder.writeElement(models.SimplestModel.objects.all())
        self.assertEqual(encoder.stream.getvalue(), '\t\x01\x01')

    def test_NOT_PROVIDED(self):
        from django.db.models import fields

        self.assertEqual(pyamf.encode(fields.NOT_PROVIDED, encoding=pyamf.AMF0).getvalue(),
            '\x06')

        encoder = pyamf.get_encoder(pyamf.AMF3)
        encoder.writeElement(fields.NOT_PROVIDED)
        self.assertEqual(encoder.stream.getvalue(), '\x00')


class ClassAliasTestCase(BaseTestCase):
    def test_time(self):
        x = models.TimeClass()

        x.t = datetime.time(12, 12, 12)
        x.d = datetime.date(2008, 3, 12)
        x.dt = datetime.datetime(2008, 3, 12, 12, 12, 12)

        alias = adapter.DjangoClassAlias(models.TimeClass, None)
        attrs = alias.getEncodableAttributes(x)

        self.assertEqual(attrs, {
            'id': None,
            'd': datetime.datetime(2008, 3, 12, 0, 0),
            'dt': datetime.datetime(2008, 3, 12, 12, 12, 12),
            't': datetime.datetime(1970, 1, 1, 12, 12, 12)
        })

        y = models.TimeClass()

        alias.applyAttributes(y, {
            'id': None,
            'd': datetime.datetime(2008, 3, 12, 0, 0),
            'dt': datetime.datetime(2008, 3, 12, 12, 12, 12),
            't': datetime.datetime(1970, 1, 1, 12, 12, 12)
        })

        self.assertEqual(y.id, None)
        self.assertEqual(y.d, datetime.date(2008, 3, 12))
        self.assertEqual(y.dt, datetime.datetime(2008, 3, 12, 12, 12, 12))
        self.assertEqual(y.t, datetime.time(12, 12, 12))

        y = models.TimeClass()

        alias.applyAttributes(y, {
            'id': None,
            'd': None,
            'dt': None,
            't': None
        })

        self.assertEqual(y.id, None)
        self.assertEqual(y.d, None)
        self.assertEqual(y.dt, None)
        self.assertEqual(y.t, None)

    def test_undefined(self):
        from django.db import models
        from django.db.models import fields

        class UndefinedClass(models.Model):
            pass

        alias = adapter.DjangoClassAlias(UndefinedClass, None)

        x = UndefinedClass()

        alias.applyAttributes(x, {
            'id': pyamf.Undefined
        })

        self.assertEqual(x.id, fields.NOT_PROVIDED)

        x.id = fields.NOT_PROVIDED

        attrs = alias.getEncodableAttributes(x)
        self.assertEqual(attrs, {'id': pyamf.Undefined})

    def test_non_field_prop(self):
        from django.db import models

        class Book(models.Model):
            def _get_number_of_odd_pages(self):
                return 234

            # note the lack of a setter callable ..
            numberOfOddPages = property(_get_number_of_odd_pages)

        alias = adapter.DjangoClassAlias(Book, 'Book')

        x = Book()

        self.assertEqual(alias.getEncodableAttributes(x),
            {'numberOfOddPages': 234, 'id': None})

        # now we test sending the numberOfOddPages attribute
        alias.applyAttributes(x, {'numberOfOddPages': 24, 'id': None})

        # test it hasn't been set
        self.assertEqual(x.numberOfOddPages, 234)

    def test_dynamic(self):
        """
        Test for dynamic property encoding.
        """
        alias = adapter.DjangoClassAlias(models.SimplestModel, 'Book')

        x = models.SimplestModel()
        x.spam = 'eggs'

        self.assertEqual(alias.getEncodableAttributes(x),
            {'spam': 'eggs', 'id': None})

        # now we test sending the numberOfOddPages attribute
        alias.applyAttributes(x, {'spam': 'foo', 'id': None})

        # test it has been set
        self.assertEqual(x.spam, 'foo')

    def test_properties(self):
        """
        See #764
        """
        from django.db import models

        class Foob(models.Model):
            def _get_days(self):
                return 1

            def _set_days(self, val):
                assert 1 == val

            days = property(_get_days, _set_days)

        alias = adapter.DjangoClassAlias(Foob, 'Bar')

        x = Foob()

        self.assertEqual(x.days, 1)

        self.assertEqual(alias.getEncodableAttributes(x),
            {'days': 1, 'id': None})

        # now we test sending the numberOfOddPages attribute
        alias.applyAttributes(x, {'id': None})


class ForeignKeyTestCase(BaseTestCase):
    def test_one_to_many(self):
        # initialise the db ..
        r = models.Reporter(first_name='John', last_name='Smith', email='john@example.com')
        r.save()
        self.addCleanup(r.delete)

        r2 = models.Reporter(first_name='Paul', last_name='Jones', email='paul@example.com')
        r2.save()
        self.addCleanup(r2.delete)

        a = models.Article(headline="This is a test", reporter=r)
        a.save()
        self.addCleanup(a.delete)

        self.assertEqual(a.id, 1)

        del a

        a = models.Article.objects.filter(pk=1)[0]

        self.assertFalse('_reporter_cache' in a.__dict__)
        a.reporter
        self.assertTrue('_reporter_cache' in a.__dict__)

        del a

        a = models.Article.objects.filter(pk=1)[0]
        alias = adapter.DjangoClassAlias(models.Article, defer=True)

        self.assertFalse(hasattr(alias, 'fields'))
        attrs = alias.getEncodableAttributes(a)

        # note that the reporter attribute does not exist.
        self.assertEqual(attrs, {
            'headline': u'This is a test',
            'id': 1,
            'publications': []
        })

        self.assertFalse('_reporter_cache' in a.__dict__)
        self.assertEqual(pyamf.encode(a, encoding=pyamf.AMF3).getvalue(),
            '\n\x0b\x01\x11headline\x06\x1dThis is a test\x05id\x04\x01'
            '\x19publications\t\x01\x01\x01')

        del a

        # now with select_related to pull in the reporter object
        a = models.Article.objects.select_related('reporter').filter(pk=1)[0]

        alias = adapter.DjangoClassAlias(models.Article, defer=True)

        self.assertFalse(hasattr(alias, 'fields'))
        self.assertEqual(alias.getEncodableAttributes(a), {
            'headline': u'This is a test',
            'id': 1,
            'reporter': r,
            'publications': []
        })

        self.assertTrue('_reporter_cache' in a.__dict__)
        self.assertEqual(pyamf.encode(a, encoding=pyamf.AMF3).getvalue(),
            '\n\x0b\x01\x11reporter\n\x0b\x01\x15first_name\x06\tJohn\x13'
            'last_name\x06\x0bSmith\x05id\x04\x01\x0bemail\x06!john'
            '@example.com\x01\x11headline\x06\x1dThis is a test\x19'
            'publications\t\x01\x01\n\x04\x01\x01')

    def test_many_to_many(self):
        # install some test data - taken from
        # http://www.djangoproject.com/documentation/models/many_to_many/
        p1 = models.Publication(id=None, title='The Python Journal')
        p1.save()
        p2 = models.Publication(id=None, title='Science News')
        p2.save()
        p3 = models.Publication(id=None, title='Science Weekly')
        p3.save()

        self.addCleanup(p1.delete)
        self.addCleanup(p2.delete)
        self.addCleanup(p3.delete)

        # Create an Article.
        a1 = models.Article(id=None, headline='Django lets you build Web apps easily')
        a1.save()
        self.addCleanup(a1.delete)
        self.assertEqual(a1.id, 1)

        # Associate the Article with a Publication.
        a1.publications.add(p1)

        pub_alias = adapter.DjangoClassAlias(models.Publication, None)
        art_alias = adapter.DjangoClassAlias(models.Article, None)

        test_publication = models.Publication.objects.filter(pk=1)[0]
        test_article = models.Article.objects.filter(pk=1)[0]

        attrs = pub_alias.getEncodableAttributes(test_publication)
        self.assertEqual(attrs, {'id': 1, 'title': u'The Python Journal'})

        attrs = art_alias.getEncodableAttributes(test_article)
        self.assertEqual(attrs, {
            'headline': u'Django lets you build Web apps easily',
            'id': 1,
            'publications': [p1]
        })

        x = models.Article()

        art_alias.applyAttributes(x, {
            'headline': u'Test',
            'id': 1,
            'publications': [p1]
        })

        self.assertEqual(x.headline, u'Test')
        self.assertEqual(x.id, 1)
        self.assertEqual(list(x.publications.all()), [p1])

        y = models.Article()
        attrs = art_alias.getDecodableAttributes(y, {
            'headline': u'Django lets you build Web apps easily',
            'id': 0,
            'publications': []
        })

        self.assertEqual(attrs, {'headline': u'Django lets you build Web apps easily'})

    def test_nullable_foreign_keys(self):
        x = models.SimplestModel()
        x.save()
        self.addCleanup(x.delete)

        nfk_alias = adapter.DjangoClassAlias(models.NullForeignKey, None)
        bfk_alias = adapter.DjangoClassAlias(models.BlankForeignKey, None)

        nfk = models.NullForeignKey()
        attrs = nfk_alias.getEncodableAttributes(nfk)

        self.assertEqual(attrs, {'id': None})

        bfk = models.BlankForeignKey()
        attrs = bfk_alias.getEncodableAttributes(bfk)

        self.assertEqual(attrs, {'id': None})

    def test_static_relation(self):
        """
        @see: #693
        """
        from pyamf import util

        pyamf.register_class(models.StaticRelation)
        alias = adapter.DjangoClassAlias(models.StaticRelation,
            static_attrs=('gak',))

        alias.compile()

        self.assertTrue('gak' in alias.relations)
        self.assertTrue('gak' in alias.decodable_properties)
        self.assertTrue('gak' in alias.static_attrs)

        x = models.StaticRelation()

        # just run this to ensure that it doesn't blow up
        alias.getDecodableAttributes(x, {'id': None, 'gak': 'foo'})


class I18NTestCase(BaseTestCase):
    def test_encode(self):
        from django.utils.translation import ugettext_lazy

        self.assertEqual(pyamf.encode(ugettext_lazy('Hello')).getvalue(),
            '\x06\x0bHello')


class PKTestCase(BaseTestCase):
    """
    See ticket #599 for this. Check to make sure that django pk fields
    are set first
    """

    def test_behaviour(self):
        p = models.Publication(id=None, title='The Python Journal')
        a = models.Article(id=None, headline='Django lets you build Web apps easily')

        # Associate the Article with a Publication.
        self.assertRaises(ValueError, lambda a, p: a.publications.add(p), a, p)

        p.save()
        a.save()

        self.addCleanup(p.delete)
        self.addCleanup(a.delete)

        self.assertEqual(a.id, 1)

        article_alias = adapter.DjangoClassAlias(models.Article, None)
        x = models.Article()

        article_alias.applyAttributes(x, {
            'headline': 'Foo bar!',
            'id': 1,
            'publications': [p]
        })

        self.assertEqual(x.headline, 'Foo bar!')
        self.assertEqual(x.id, 1)
        self.assertEqual(list(x.publications.all()), [p])

    def test_none(self):
        """
        See #556. Make sure that PK fields with a value of 0 are actually set
        to C{None}.
        """
        alias = adapter.DjangoClassAlias(models.SimplestModel, None)

        x = models.SimplestModel()

        self.assertEqual(x.id, None)

        alias.applyAttributes(x, {
            'id': 0
        })

        self.assertEqual(x.id, None)

    def test_no_pk(self):
        """
        Ensure that Models without a primary key are correctly serialized.
        See #691.
        """
        instances = [models.NotSaved(name="a"), models.NotSaved(name="b")]
        encoded = pyamf.encode(instances, encoding=pyamf.AMF3).getvalue()

        decoded = pyamf.decode(encoded, encoding=pyamf.AMF3).next()
        self.assertEqual(decoded[0]['name'], 'a')
        self.assertEqual(decoded[1]['name'], 'b')


class ModelInheritanceTestCase(BaseTestCase):
    """
    Tests for L{Django model inheritance<http://docs.djangoproject.com/en/dev/topics/db/models/#model-inheritance>}
    """

    def test_abstract(self):
        alias = adapter.DjangoClassAlias(models.Student)

        x = models.Student()

        attrs = alias.getEncodableAttributes(x)

        self.assertEqual(attrs, {
            'age': None,
            'home_group': '',
            'id': None,
            'name': ''
        })

    def test_concrete(self):
        alias = adapter.DjangoClassAlias(models.Place)
        x = models.Place()

        attrs = alias.getEncodableAttributes(x)

        self.assertEqual(attrs, {
            'id': None,
            'name': '',
            'address': ''
        })

        alias = adapter.DjangoClassAlias(models.Restaurant)
        x = models.Restaurant()

        attrs = alias.getEncodableAttributes(x)

        self.assertEqual(attrs, {
            'id': None,
            'name': '',
            'address': '',
            'serves_hot_dogs': False,
            'serves_pizza': False
        })


class MockFile(object):
    """
    mock for L{django.core.files.base.File}
    """

    def chunks(self):
        return []

    def __len__(self):
        return 0

    def read(self, n):
        return ''


class FieldsTestCase(BaseTestCase):
    """
    Tests for L{fields}
    """

    def test_file(self):
        alias = adapter.DjangoClassAlias(models.FileModel)

        i = models.FileModel()
        i.file.save('bar', MockFile())
        self.addCleanup(i.file.delete)

        i.save()

        attrs = alias.getEncodableAttributes(i)

        self.assertEqual(attrs, {'text': '', 'id': 1, 'file': u'file_model/bar'})

        attrs = alias.getDecodableAttributes(i, attrs)

        self.assertEqual(attrs, {'text': ''})


class ImageTestCase(BaseTestCase):
    """
    Tests for L{fields}
    """

    def setUp(self):
        try:
            import PIL
        except ImportError:
            self.skipTest("'PIL' is not available")

        BaseTestCase.setUp(self)

    def test_image(self):
        alias = adapter.DjangoClassAlias(models.Profile)

        i = models.Profile()
        i.file.save('bar', MockFile())
        self.addCleanup(i.file.delete)

        i.save()
        self.addCleanup(i.delete)

        attrs = alias.getEncodableAttributes(i)

        self.assertEqual(attrs, {'text': '', 'id': 1, 'file': u'profile/bar'})

        attrs = alias.getDecodableAttributes(i, attrs)

        self.assertEqual(attrs, {'text': ''})


class ReferenceTestCase(BaseTestCase, util.EncoderMixIn):
    """
    Test case to make sure that the same object from the database is encoded
    by reference.
    """

    amf_type = pyamf.AMF3

    def setUp(self):
        BaseTestCase.setUp(self)
        util.EncoderMixIn.setUp(self)

    def test_not_referenced(self):
        """
        Test to ensure that we observe the correct behaviour in the Django
        ORM.
        """
        f = models.ParentReference()
        f.name = 'foo'

        b = models.ChildReference()
        b.name = 'bar'

        f.save()
        b.foo = f
        b.save()
        f.bar = b
        f.save()

        self.addCleanup(f.delete)
        self.addCleanup(b.delete)

        self.assertEqual(f.id, 1)
        foo = models.ParentReference.objects.select_related().get(id=1)

        self.assertFalse(foo.bar.foo is foo)

    def test_referenced_encode(self):
        f = models.ParentReference()
        f.name = 'foo'

        b = models.ChildReference()
        b.name = 'bar'

        f.save()
        b.foo = f
        b.save()
        f.bar = b
        f.save()

        self.addCleanup(f.delete)
        self.addCleanup(b.delete)

        self.assertEqual(f.id, 1)
        foo = models.ParentReference.objects.select_related().get(id=1)

        # ensure the referenced attribute resolves
        foo.bar.foo

        self.assertEncoded(foo, '\n\x0b\x01\x07bar\n\x0b\x01\x07foo\n\x00\x05'
            'id\x04\x01\tname\x06\x00\x01\x04\x04\x01\x06\x06\x02\x01')


class AuthTestCase(BaseTestCase):
    """
    Tests for L{django.contrib.auth.models}
    """

    def test_user(self):
        from django.contrib.auth import models

        alias = pyamf.get_class_alias(models.User)

        self.assertEqual(alias, 'django.contrib.auth.models.User')
        self.assertEqual(alias.exclude_attrs, ('message_set', 'password'))
        self.assertEqual(alias.readonly_attrs, ('username',))


class DBColumnTestCase(BaseTestCase):
    """
    Tests for #807
    """

    def setUp(self):
        BaseTestCase.setUp(self)

        self.alias = adapter.DjangoClassAlias(models.DBColumnModel, None)
        self.model = models.DBColumnModel()

    def test_encodable_attrs(self):
        def attrs():
            return self.alias.getEncodableAttributes(self.model)

        self.assertEqual(attrs(), {'id': None})

        x = models.SimplestModel()

        x.save()
        self.addCleanup(x.delete)

        self.model.bar = x

        self.assertEqual(attrs(), {'id': None, 'bar': x})
