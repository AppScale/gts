#!/usr/bin/env python

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup/"))
import backup_recovery_helper

class TestBRHelper(unittest.TestCase):
  """ A set of test cases for the BR helper functions. """

  def test_does_file_exist(self):
    flexmock(os.path).should_receive('isfile').and_return().at_least().times(1)
    backup_recovery_helper.does_file_exist('foo')

  def test_mkdir(self):
    flexmock(os).should_receive('mkdir').and_return().at_least().times(1)
    self.assertEquals(True, backup_recovery_helper.mkdir('foo'))

    flexmock(os).should_receive('mkdir').and_raise(OSError)
    self.assertEquals(False, backup_recovery_helper.mkdir('foo'))

  def test_rename(self):
    flexmock(os).should_receive('rename').and_return().at_least().times(1)
    self.assertEquals(True, backup_recovery_helper.rename('foo', 'bar'))

    flexmock(os).should_receive('rename').and_raise(OSError)
    self.assertEquals(False, backup_recovery_helper.rename('foo', 'bar'))

  def test_remove(self):
    flexmock(os).should_receive('remove').and_return().at_least().times(1)
    self.assertEquals(True, backup_recovery_helper.remove('foo'))

    flexmock(os).should_receive('remove').and_raise(OSError)
    self.assertEquals(False, backup_recovery_helper.remove('foo'))

if __name__ == "__main__":
  unittest.main()    
