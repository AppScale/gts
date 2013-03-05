#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)


# General-purpose Python library imports
import os
import sys
import unittest


# Third party libraries
from flexmock import flexmock


# AppScale import, the library that we're testing here
lib = os.path.dirname(__file__) + os.sep + ".." + os.sep
sys.path.append(lib)
from xmpp_receiver import XMPPReceiver


class TestXMPPReceiver(unittest.TestCase):


  def setUp(self):
    pass


  def test_nothing_right_now(self):
    XMPPReceiver()
