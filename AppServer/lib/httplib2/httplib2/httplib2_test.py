#!/usr/bin/python2.4
#
# Copyright 2008 Google Inc. All Rights Reserved.

"""Tests for google3.third_party.py.httplib2."""

__author__ = 'vbarathan@google.com (Prakash Barathan)'

import google3

from google3.pyglib import logging
from google3.testing.pybase import googletest
from google3.third_party.py import httplib2

class HttpLib2Test(googletest.TestCase):

  def testHttpLib2(self):
    logging.debug('httplib2 loaded from %s' % str(httplib2))

if __name__ == '__main__':
  googletest.main()
