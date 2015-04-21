#!/usr/bin/env python

import datetime
import os
import sys
import time
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../backup/"))  
import cassandra_backup

class TestCassandraBackup(unittest.TestCase):
  """
  A set of test cases for the cassandra backup.
  """
  def test_get_snapshot_file_names(self):
    os_mock = flexmock(os)
    os_mock.should_call('walk')
    os_mock.should_receive('walk').and_yield(('', ['dirname'], ['/snapshots/xxx'])).once()
    self.assertEquals(['/snapshots/xxx'], cassandra_backup.get_snapshot_file_names("xxx"))
    
if __name__ == "__main__":
  unittest.main()    
