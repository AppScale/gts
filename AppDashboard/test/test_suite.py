#!/usr/bin/env python
# Programmer: Brian Drawert

import sys
import unittest

from functional_test_dashboard import FunctionalTestAppDashboard
from test_app_dashboard_data import TestAppDashboardData


test_cases = [
  TestAppDashboardData,
  FunctionalTestAppDashboard,
  ]

test_case_names = []
for cls in test_cases:
  test_case_names.append(str(cls.__name__))

appscale_test_suite = unittest.TestSuite()
if len(sys.argv) > 1:
  if sys.argv[1] in test_case_names:
    print "only running test "+sys.argv[1]
    run_test_cases = [sys.argv[1]]
  else:
    print "ERROR: unknown test "+sys.argv[1]
    print "Options are: "+", ".join(test_case_names)
    sys.exit(1)
else:
  run_test_cases = test_case_names

for test_class, test_name in zip(test_cases,test_case_names):
  if test_name in run_test_cases:
    tests = unittest.TestLoader().loadTestsFromTestCase(test_class)
    appscale_test_suite.addTests(tests)

all_tests = unittest.TestSuite([appscale_test_suite])
unittest.TextTestRunner(verbosity=2).run(all_tests)
