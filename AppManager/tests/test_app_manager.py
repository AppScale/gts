import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../"))
import app_manager

class TestAppManager(unittest.TestCase):
  def test_start_app(self):
    assert -1 == app_manager.start_app([])
  def test_stop_app(self):
    app_manager.stop_app('test')
  def test_get_app_listing(self):
    app_manager.get_app_listing()

if __name__ == "__main__":
  unittest.main()
