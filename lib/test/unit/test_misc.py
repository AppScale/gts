# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import file_io
import misc

class TestMisc(unittest.TestCase):
  def test_is_app_name_valid(self):
    self.assertEqual(True, misc.is_app_name_valid("guestbook"))
    self.assertEqual(True, misc.is_app_name_valid("guestbook132"))
    self.assertEqual(True, misc.is_app_name_valid("guestbook_132"))
    self.assertEqual(True, misc.is_app_name_valid("guestbook-132"))
    self.assertEqual(False, misc.is_app_name_valid("asdf#"))
    self.assertEqual(False, misc.is_app_name_valid("%##;"))
    self.assertEqual(False, misc.is_app_name_valid("$78;"))

  def test_is_string_secure(self):
    self.assertEqual(True, misc.is_string_secure("guestbook"))
    self.assertEqual(True, misc.is_string_secure("guestbook132"))
    self.assertEqual(True, misc.is_string_secure("guestbook_132"))
    self.assertEqual(True, misc.is_string_secure("guestbook-132"))
    self.assertEqual(False, misc.is_string_secure("asdf#"))
    self.assertEqual(False, misc.is_string_secure("%##;"))
    self.assertEqual(False, misc.is_string_secure("$78;"))
     
if __name__ == "__main__":
  unittest.main()
