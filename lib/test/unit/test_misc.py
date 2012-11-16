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
    assert misc.is_app_name_valid("guestbook")
    assert misc.is_app_name_valid("guestbook132")
    assert not misc.is_app_name_valid("asdf#")
    assert not misc.is_app_name_valid("%##;")
    assert not misc.is_app_name_valid("$78;")
  def test_is_string_secure(self):
    assert misc.is_string_secure("guestbook")
    assert misc.is_string_secure("guestbook132")
    assert not misc.is_string_secure("asdf#")
    assert not misc.is_string_secure("%##;")
    assert not misc.is_string_secure("$78;")
     
if __name__ == "__main__":
  unittest.main()
