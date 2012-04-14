#! /usr/bin/python2.4
# -*- coding: utf-8 -*-

# test/test_enum.py
# Part of enum, a package providing enumerated types for Python.
#
# Copyright © 2007–2009 Ben Finney <ben+python@benfinney.id.au>
# This is free software; you may copy, modify and/or distribute this work
# under the terms of the GNU General Public License, version 2 or later
# or, at your option, the terms of the Python license.

""" Unit test for ‘enum’ module.
    """

import unittest
import operator

import google3
from enum.test import tools

import enum


class Mock_Enum(object):
    """ Mock object for Enum testing. """

    def __init__(self, *keys):
        """ Set up a new instance. """
        pass


def setup_enum_value_fixtures(testcase):
    """ Set up fixtures for test cases using ‘EnumValue’. """

    testcase.bad_keys = [
        None, 0, 1, (), Mock_Enum(),
        enum.EnumValue(Mock_Enum(), 0, 'bogus'),
        ]

    testcase.other_values = [
        None, 0, 1, (), Mock_Enum(), "bogus",
        enum.EnumValue(Mock_Enum(), 0, 'bogus'),
        ]

    testcase.planets = [
        ('mercury', "Mercury"),
        ('venus', "Venus"),
        ('earth', "Earth"),
        ('mars', "Mars"),
        ('jupiter', "Jupiter"),
        ('saturn', "Saturn"),
        ('uranus', "Uranus"),
        ('neptune', "Neptune"),
        ]
    planet_keys = [key for (key, name) in testcase.planets]

    colour_keys = [
        'red', 'green', 'blue',
        'yellow', 'orange', 'purple',
        'white', 'black',
        ]

    simple_keys = ['spam', 'eggs', 'beans']
    testcase.SimpleEnum = testcase.enum_factory_class(*simple_keys)

    Colour = testcase.enum_factory_class(*colour_keys)
    Planet = testcase.enum_factory_class(*planet_keys)
    testcase.valid_values = {
        Colour: dict(
            keys = colour_keys,
            ),
        Planet: dict(
            keys = planet_keys,
            ),
        }

    for enumtype, params in testcase.valid_values.items():
        params['enumtype'] = enumtype
        values = {}
        for i, key in enumerate(params['keys']):
            values[key] = enum.EnumValue(enumtype, i, key)
        params['values'] = values


class Test_Module(unittest.TestCase):
    """ Test case for the module. """

    def setUp(self):
        """ Set up test fixtures. """
        from sys import modules
        self.module = modules['enum']

    def test_author_name_is_string(self):
        """ Module should have __author_name__ string. """
        mod_author_name = self.module.__author_name__
        self.failUnless(isinstance(mod_author_name, basestring))

    def test_author_email_is_string(self):
        """ Module should have __author_email__ string. """
        mod_author_email = self.module.__author_email__
        self.failUnless(isinstance(mod_author_email, basestring))

    def test_author_is_string(self):
        """ Module should have __author__ string. """
        mod_author = self.module.__author__
        self.failUnless(isinstance(mod_author, basestring))

    def test_author_contains_name(self):
        """ Module __author__ string should contain author name. """
        mod_author = self.module.__author__
        mod_author_name = self.module.__author_name__
        self.failUnless(mod_author.startswith(mod_author_name))

    def test_author_contains_email(self):
        """ Module __author__ string should contain author email. """
        mod_author = self.module.__author__
        mod_author_email = self.module.__author_email__
        self.failUnless(mod_author.endswith("<%(mod_author_email)s>" % vars()))

    def test_date_is_string(self):
        """ Module should have __date__ string. """
        mod_date = self.module.__date__
        self.failUnless(isinstance(mod_date, basestring))

    def test_copyright_is_string(self):
        """ Module should have __copyright__ string. """
        mod_copyright = self.module.__copyright__
        self.failUnless(isinstance(mod_copyright, basestring))

    def test_copyright_contains_name(self):
        """ Module __copyright__ string should contain author name. """
        mod_copyright = self.module.__copyright__
        mod_author_name = self.module.__author_name__
        self.failUnless(mod_copyright.endswith(mod_author_name))

    def test_copyright_contains_begin_year(self):
        """ Module __copyright__ string should contain beginning year. """
        mod_copyright = self.module.__copyright__
        year_begin = self.module._copyright_year_begin
        self.failUnless(year_begin in mod_copyright)

    def test_copyright_contains_latest_year(self):
        """ Module __copyright__ string should contain latest year.. """
        mod_copyright = self.module.__copyright__
        year_latest = self.module.__date__.split('-')[0]
        self.failUnless(year_latest in mod_copyright)

    def test_license_is_string(self):
        """ Module should have __license__ string. """
        mod_license = self.module.__license__
        self.failUnless(isinstance(mod_license, basestring))

    def test_url_is_string(self):
        """ Module should have __url__ string. """
        mod_url = self.module.__url__
        self.failUnless(isinstance(mod_url, basestring))

    def test_version_is_string(self):
        """ Module should have __version__ string. """
        mod_version = self.module.__version__
        self.failUnless(isinstance(mod_version, basestring))


class Test_EnumException(unittest.TestCase):
    """ Test case for the Enum exception classes. """

    def setUp(self):
        """ Set up test fixtures. """
        self.valid_exceptions = {
            enum.EnumEmptyError: dict(
                min_args = 0,
                types = (enum.EnumException, AssertionError),
                ),
            enum.EnumBadKeyError: dict(
                min_args = 1,
                types = (enum.EnumException, TypeError),
                ),
            enum.EnumImmutableError: dict(
                min_args = 1,
                types = (enum.EnumException, TypeError),
                ),
            }

        for exc_type, params in self.valid_exceptions.items():
            args = (None,) * params['min_args']
            instance = exc_type(*args)
            self.valid_exceptions[exc_type]['instance'] = instance

    def test_EnumException_abstract(self):
        """ The module exception base class should be abstract. """
        self.failUnlessRaises(
            NotImplementedError, enum.EnumException)

    def test_exception_instance(self):
        """ Exception instance should be created. """
        for exc_type, params in self.valid_exceptions.items():
            instance = params['instance']
            self.failUnless(instance)

    def test_exception_types(self):
        """ Exception instances should match expected types. """
        for exc_type, params in self.valid_exceptions.items():
            instance = params['instance']
            for match_type in params['types']:
                self.failUnless(
                    isinstance(instance, match_type),
                    msg=(
                        "instance: %(instance)r, match_type: %(match_type)s"
                        ) % vars())


compare_functions = [
    getattr(operator, name)
    for name in ['__eq__', '__ne__', '__lt__', '__le__', '__gt__', '__ge__']]

class Test_EnumValue(unittest.TestCase):
    """ Test case for the EnumValue class. """

    enum_factory_class = Mock_Enum

    def setUp(self):
        """ Set up the test fixtures. """
        setup_enum_value_fixtures(self)

    def test_instantiate(self):
        """ Creating an EnumValue instance should succeed. """
        for enumtype, params in self.valid_values.items():
            for key, instance in params['values'].items():
                self.failUnless(instance)

    def test_enumtype_equal(self):
        """ EnumValue should export its enum type. """
        for enumtype, params in self.valid_values.items():
            for key, instance in params['values'].items():
                self.failUnlessEqual(enumtype, instance.enumtype)

    def test_key_equal(self):
        """ EnumValue should export its string key. """
        for enumtype, params in self.valid_values.items():
            for key, instance in params['values'].items():
                self.failUnlessEqual(key, instance.key)

    def test_str_key(self):
        """ String value for EnumValue should be its key string. """
        for enumtype, params in self.valid_values.items():
            for key, instance in params['values'].items():
                self.failUnlessEqual(key, str(instance))

    def test_index_equal(self):
        """ EnumValue should export its sequence index. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                instance = params['values'][key]
                self.failUnlessEqual(i, instance.index)

    def test_repr(self):
        """ Representation of EnumValue should be meaningful. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                instance = params['values'][key]
                repr_str = repr(instance)
                self.failUnless(repr_str.startswith('EnumValue('))
                self.failUnless(repr_str.count(repr(enumtype)))
                self.failUnless(repr_str.count(repr(i)))
                self.failUnless(repr_str.count(repr(key)))
                self.failUnless(repr_str.endswith(')'))

    def test_hash_equal(self):
        """ Each EnumValue instance should have same hash as its value. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                instance = params['values'][key]
                self.failUnlessEqual(hash(i), hash(instance))

    def test_hash_unequal(self):
        """ Different EnumValue instances should have different hashes. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                instance = params['values'][key]
                for j, other_key in enumerate(params['keys']):
                    if i == j:
                        continue
                    other_instance = params['values'][other_key]
                    self.failIfEqual(
                        hash(instance), hash(other_instance))

    def test_comparison_method_has_matching_name(self):
        """ Comparison method should have matching name for attribute. """
        for compare_func in compare_functions:
            func_name = compare_func.__name__
            expect_name = func_name
            compare_method = getattr(enum.EnumValue, func_name)
            self.failUnlessEqual(
                expect_name, compare_method.__name__)

    def test_comparison_method_has_docstring(self):
        """ Comparison method should have docstring. """
        for compare_func in compare_functions:
            func_name = compare_func.__name__
            compare_method = getattr(enum.EnumValue, func_name)
            self.failUnless(
                isinstance(compare_method.__doc__, basestring))

    def test_compare_equal(self):
        """ An EnumValue should compare equal to its value. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                instance = params['values'][key]
                self.failUnlessEqual(
                    instance, enum.EnumValue(enumtype, i, key))

    def test_compare_unequal(self):
        """ An EnumValue should compare different to other values. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                instance = params['values'][key]
                self.failIfEqual(
                    instance,
                    enum.EnumValue(enumtype, None, None))

    def test_compare_sequence(self):
        """ EnumValue instances should compare as their sequence order. """
        for enumtype, params in self.valid_values.items():
            for i, left_key in enumerate(params['keys']):
                for j, right_key in enumerate(params['keys']):
                    for compare_func in compare_functions:
                        self.failUnlessEqual(
                            compare_func(i, j),
                            compare_func(params['values'][left_key],
                                enum.EnumValue(enumtype, j, right_key))
                            )

    def test_compare_different_enum(self):
        """ An EnumValue should not implement comparison to other enums. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                for compare_func in compare_functions:
                    instance = params['values'][key]
                    test_value = enum.EnumValue(self.SimpleEnum, i, key)
                    compare_method = getattr(instance, compare_func.__name__)
                    compare_result = compare_method(test_value)
                    self.failUnlessEqual(NotImplemented, compare_result)

    def test_compare_non_enum(self):
        """ An EnumValue should not implement comparison to other types. """
        test_value = enum.EnumValue(self.SimpleEnum, 0, 'test')
        for other_value in self.other_values:
            for compare_func in compare_functions:
                compare_method = getattr(test_value, compare_func.__name__)
                compare_result = compare_method(other_value)
                self.failUnlessEqual(NotImplemented, compare_result)

    def test_compare_equality_different_enum(self):
        """ An EnumValue should compare inequal to values of other enums. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                instance = params['values'][key]
                test_value = enum.EnumValue(self.SimpleEnum, i, key)
                self.failIfEqual(test_value, instance)

    def test_compare_equality_non_enum(self):
        """ An EnumValue should compare inequal to any other value. """
        test_value = enum.EnumValue(self.SimpleEnum, 0, 'test')
        for other_value in self.other_values:
            self.failIfEqual(test_value, other_value)

    def test_sequence_other_values(self):
        """ An EnumValue should compare sequentially to other values. """
        test_value = enum.EnumValue(self.SimpleEnum, 0, 'test')
        test_list = list(self.other_values)
        test_list.append(test_value)
        test_list.sort()
        self.failUnless(test_value in test_list)

    def test_value_key(self):
        """ An EnumValue should have the specified key. """
        for enumtype, params in self.valid_values.items():
            for key, instance in params['values'].items():
                self.failUnlessEqual(key, instance.key)

    def test_value_enumtype(self):
        """ An EnumValue should have its associated enumtype. """
        for enumtype, params in self.valid_values.items():
            for key, instance in params['values'].items():
                self.failUnlessEqual(enumtype, instance.enumtype)


class Test_Enum(unittest.TestCase):
    """ Test case for the Enum class. """

    enum_factory_class = enum.Enum

    def setUp(self):
        """ Set up the test fixtures. """
        setup_enum_value_fixtures(self)

    def test_empty_enum(self):
        """ Enum constructor should refuse empty keys sequence. """
        self.failUnlessRaises(
            enum.EnumEmptyError,
            enum.Enum)

    def test_bad_key(self):
        """ Enum constructor should refuse non-string keys. """
        for key in self.bad_keys:
            args = ("valid", key, "valid")
            self.failUnlessRaises(
                enum.EnumBadKeyError,
                enum.Enum, *args)

    def test_value_attributes(self):
        """ Enumeration should have attributes for each value. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                instance = getattr(enumtype, key)
                test_value = enum.EnumValue(enumtype, i, key)
                self.failUnlessEqual(test_value, instance)

    def test_length(self):
        """ Enumeration should have length of its value set. """
        for enumtype, params in self.valid_values.items():
            self.failUnlessEqual(len(params['values']), len(enumtype))

    def test_value_items(self):
        """ Enumeration should have items for each value. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                value = enumtype[i]
                test_value = enum.EnumValue(enumtype, i, key)
                self.failUnlessEqual(test_value, value)

    def test_iterable(self):
        """ Enumeration class should iterate over its values. """
        for enumtype, params in self.valid_values.items():
            for i, value in enumerate(enumtype):
                key = params['keys'][i]
                test_value = params['values'][key]
            self.failUnlessEqual(value, test_value)

    def test_iterate_sequence(self):
        """ Enumeration iteration should match specified sequence. """
        for enumtype, params in self.valid_values.items():
            values_dict = params['values']
            values_seq = [values_dict[key] for key in params['keys']]
            enum_seq = [val for val in enumtype]
            self.failUnlessEqual(values_seq, enum_seq)
            self.failIfEqual(values_seq.reverse(), enum_seq)

    def test_membership_bogus(self):
        """ Enumeration should not contain bogus values. """
        for enumtype, params in self.valid_values.items():
            for value in self.other_values:
                self.failIf(value in enumtype)

    def test_membership_value(self):
        """ Enumeration should contain explicit value. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                value = params['values'][key]
                self.failUnless(value in enumtype)

    def test_membership_key(self):
        """ Enumeration should contain key string. """
        for enumtype, params in self.valid_values.items():
            for key in params['keys']:
                self.failUnless(key in enumtype)

    def test_add_attribute(self):
        """ Enumeration should refuse attribute addition. """
        for enumtype, params in self.valid_values.items():
            self.failUnlessRaises(
                enum.EnumImmutableError,
                setattr, enumtype, 'bogus', "bogus")

    def test_modify_attribute(self):
        """ Enumeration should refuse attribute modification. """
        for enumtype, params in self.valid_values.items():
            for key in params['keys']:
                self.failUnlessRaises(
                    enum.EnumImmutableError,
                    setattr, enumtype, key, "bogus")

    def test_delete_attribute(self):
        """ Enumeration should refuse attribute deletion. """
        for enumtype, params in self.valid_values.items():
            for key in params['keys']:
                self.failUnlessRaises(
                    enum.EnumImmutableError,
                    delattr, enumtype, key)

    def test_add_item(self):
        """ Enumeration should refuse item addition. """
        for enumtype, params in self.valid_values.items():
            index = len(params['keys'])
            self.failUnlessRaises(
                enum.EnumImmutableError,
                enumtype.__setitem__, index, "bogus")

    def test_modify_item(self):
        """ Enumeration should refuse item modification. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                self.failUnlessRaises(
                    enum.EnumImmutableError,
                    enumtype.__setitem__, i, "bogus")

    def test_delete_item(self):
        """ Enumeration should refuse item deletion. """
        for enumtype, params in self.valid_values.items():
            for i, key in enumerate(params['keys']):
                self.failUnlessRaises(
                    enum.EnumImmutableError,
                    enumtype.__delitem__, i)


def suite():
    """ Create the test suite for this module. """
    from sys import modules
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromModule(modules[__name__])
    return suite


def __main__(argv=None):
    """ Mainline function for this module. """
    import sys as _sys
    if not argv:
        argv = _sys.argv

    exitcode = None
    try:
        unittest.main(argv=argv, defaultTest='suite')
    except SystemExit, exc:
        exitcode = exc.code

    return exitcode

if __name__ == '__main__':
    import sys
    exitcode = __main__(sys.argv)
    sys.exit(exitcode)


# Local variables:
# mode: python
# End:
# vim: filetype=python fileencoding=utf-8 :
