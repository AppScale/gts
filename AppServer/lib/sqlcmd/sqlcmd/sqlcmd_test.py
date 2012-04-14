#!/usr/bin/python2.4
#
# Copyright 2011 Google Inc. All Rights Reserved.

"""Tests for google3.third_party.py.sqlcmd."""

__author__ = 'mmcdonald@google.com (Matt McDonald)'

import google3
import sqlcmd

from google3.testing.pybase import googletest


class SqlcmdTest(googletest.TestCase):
  def testImport(self):
    """Tests that we can import the module; very basic sanity check."""
    sqlcmd.Main()
