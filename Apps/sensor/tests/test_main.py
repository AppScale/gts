#!/usr/bin/env python
""" Testing for main handlers. """

import os
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import main

# Include these paths to get webapp2.
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer/lib/webob-1.2.3"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../../AppServer/lib/webapp2-2.5.2/"))
import webapp2

class TestHandlers(unittest.TestCase):
  def test_home(self):
    request = webapp2.Request.blank('/')
    response = request.get_response(main.APP)
    expected = '{"status": "up"}'
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.body, expected)

    request.method = 'POST'
    self.assertEqual(response.status_int, 200)
    self.assertEqual(response.body, expected)
