import logging 
import os
import sys
import subprocess
import time
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import monit_interface

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io
import testing

class TestGodInterface(unittest.TestCase):
  def setUp(self):
    flexmock(time).should_receive('sleep').and_return()

  def test_start(self):
    testing.disable_logging()

    flexmock(file_io)\
      .should_receive('delete')\
      .and_return()

    flexmock(subprocess)\
      .should_receive('call')\
      .and_return(0) 

    self.assertEqual(True, monit_interface.start("watch_name"))

    flexmock(subprocess)\
      .should_receive('call')\
      .and_return(1) 

    self.assertEqual(False, monit_interface.start("watch_name"))

  def test_stop(self):
    testing.disable_logging()

    flexmock(subprocess)\
      .should_receive('call')\
      .and_return(0) 
    self.assertEqual(True, monit_interface.stop("watch_name"))

    flexmock(subprocess)\
      .should_receive('call')\
      .and_return(1) 
    self.assertEqual(False, monit_interface.stop("watch_name"))
       
if __name__ == "__main__":
  unittest.main()
