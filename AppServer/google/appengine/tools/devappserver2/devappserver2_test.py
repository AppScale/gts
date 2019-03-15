#!/usr/bin/env python
#
# Copyright 2007 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
"""Tests for google.apphosting.tools.devappserver2.devappserver2."""


import argparse
import os
import unittest

from google.appengine.tools.devappserver2 import devappserver2


class WinError(Exception):
  pass


class PortParserTest(unittest.TestCase):

  def test_valid_port(self):
    self.assertEqual(8080, devappserver2.PortParser()('8080'))

  def test_port_zero_allowed(self):
    self.assertEqual(0, devappserver2.PortParser()('0'))

  def test_port_zero_not_allowed(self):
    self.assertRaises(argparse.ArgumentTypeError,
                      devappserver2.PortParser(allow_port_zero=False), '0')

  def test_negative_port(self):
    self.assertRaises(argparse.ArgumentTypeError, devappserver2.PortParser(),
                      '-1')

  def test_port_too_high(self):
    self.assertRaises(argparse.ArgumentTypeError, devappserver2.PortParser(),
                      '65536')

  def test_port_max_value(self):
    self.assertEqual(65535, devappserver2.PortParser()('65535'))

  def test_not_an_int(self):
    self.assertRaises(argparse.ArgumentTypeError, devappserver2.PortParser(),
                      'a port')


class ParseMaxServerInstancesTest(unittest.TestCase):

  def test_single_valid_arg(self):
    self.assertEqual(1, devappserver2.parse_max_module_instances('1'))

  def test_single_zero_arg(self):
    self.assertRaisesRegexp(argparse.ArgumentTypeError,
                            'Cannot specify zero instances for all',
                            devappserver2.parse_max_module_instances, '0')

  def test_single_nonint_arg(self):
    self.assertRaisesRegexp(argparse.ArgumentTypeError,
                            'Invalid instance count:',
                            devappserver2.parse_max_module_instances, 'cat')

  def test_multiple_valid_args(self):
    self.assertEqual(
        {'default': 10,
         'foo': 5},
        devappserver2.parse_max_module_instances('default:10,foo:5'))

  def test_multiple_non_colon(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError,
        'Expected "module:max_instances"',
        devappserver2.parse_max_module_instances, 'default:10,foo')

  def test_multiple_non_int(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError,
        'Expected "module:max_instances"',
        devappserver2.parse_max_module_instances, 'default:cat')

  def test_duplicate_modules(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError,
        'Duplicate max instance value',
        devappserver2.parse_max_module_instances, 'default:5,default:10')

  def test_multiple_with_zero(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError,
        'Cannot specify zero instances for module',
        devappserver2.parse_max_module_instances, 'default:5,foo:0')

  def test_multiple_missing_name(self):
    self.assertEqual(
        {'default': 10},
        devappserver2.parse_max_module_instances(':10'))

  def test_multiple_missing_value(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError,
        'Expected "module:max_instances"',
        devappserver2.parse_max_module_instances, 'default:')


class ParseThreadsafeOverrideTest(unittest.TestCase):

  def test_single_valid_arg(self):
    self.assertTrue(devappserver2.parse_threadsafe_override('True'))
    self.assertFalse(devappserver2.parse_threadsafe_override('No'))

  def test_single_nonbool_art(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError, 'Invalid threadsafe override',
        devappserver2.parse_threadsafe_override, 'okaydokey')

  def test_multiple_valid_args(self):
    self.assertEqual(
        {'default': False,
         'foo': True},
        devappserver2.parse_threadsafe_override('default:False,foo:True'))

  def test_multiple_non_colon(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError, 'Expected "module:threadsafe_override"',
        devappserver2.parse_threadsafe_override, 'default:False,foo')

  def test_multiple_non_int(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError, 'Expected "module:threadsafe_override"',
        devappserver2.parse_threadsafe_override, 'default:okaydokey')

  def test_duplicate_modules(self):
    self.assertRaisesRegexp(
        argparse.ArgumentTypeError,
        'Duplicate threadsafe override value',
        devappserver2.parse_threadsafe_override, 'default:False,default:True')

  def test_multiple_missing_name(self):
    self.assertEqual(
        {'default': False},
        devappserver2.parse_threadsafe_override(':No'))


if __name__ == '__main__':
  unittest.main()
