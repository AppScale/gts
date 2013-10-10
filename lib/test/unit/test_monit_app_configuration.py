# Programmer: Navraj Chohan <nlake44@gmail.com>

import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import monit_app_configuration

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

class TestGodAppInterface(unittest.TestCase):
  def test_create_config_file(self):
    flexmock(file_io)\
      .should_receive('write')\
      .and_return()
    temp_file = monit_app_configuration.create_config_file("mywatch",
                                                     "start_cmd",
                                                     "stop_cmd",
                                                     [1,2,3],
                                                     {'ENV1':"VALUE1",
                                                      'ENV2':"VALUE2"})
    self.assertIsNone(temp_file)
    
if __name__ == "__main__":
  unittest.main()
