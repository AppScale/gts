#!/usr/bin/env python


import unittest


from test_xmpp_receiver import TestXMPPReceiver


test_cases = [TestXMPPReceiver]
xmpp_test_suite = unittest.TestSuite()
for test_class in test_cases:
  tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
  xmpp_test_suite.addTests(tests)

all_tests = unittest.TestSuite([xmpp_test_suite])
unittest.TextTestRunner(verbosity=2).run(all_tests)
