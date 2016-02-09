import glob
import os
import sys
import subprocess
import time
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import misc
import monit_interface
from monit_interface import MONIT

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

    watch = 'app___guestbook27'
    port = 20000
    config_file = 'appscale-{}-{}.cfg'.format(watch, port)
    flexmock(misc).should_receive('is_string_secure').and_return(False)
    self.assertFalse(monit_interface.stop(watch))

    flexmock(misc).should_receive('is_string_secure').and_return(True)
    flexmock(glob).should_receive('glob').and_return([config_file])
    flexmock(os).should_receive('remove')
    flexmock(monit_interface).should_receive('run_with_retry').\
      with_args([MONIT, 'stop', '-g', watch]).and_return(False)
    self.assertFalse(monit_interface.stop(watch))

    flexmock(monit_interface).should_receive('run_with_retry').\
      with_args([MONIT, 'stop', '-g', watch]).and_return(True)
    flexmock(monit_interface).should_receive('run_with_retry').\
      with_args([MONIT, 'reload']).and_return(False)
    self.assertFalse(monit_interface.stop(watch))

    flexmock(monit_interface).should_receive('run_with_retry').\
      with_args([MONIT, 'reload']).and_return(True)
    self.assertTrue(monit_interface.stop(watch))
       
if __name__ == "__main__":
  unittest.main()
