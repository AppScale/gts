#!/usr/bin/env python
# Programmer: Chris Bunch (chris@appscale.com)

import os
import sys
import unittest


from flexmock import flexmock


xmpp = "{0}/../../../../..".format(os.path.dirname(__file__))
sys.path.append(xmpp)
from google.appengine.api.xmpp import xmpp_service_real


class TestXMPP(unittest.TestCase):
  pass


if __name__ == "__main__":
  unittest.main()
