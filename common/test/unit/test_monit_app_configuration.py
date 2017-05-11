# Programmer: Navraj Chohan <nlake44@gmail.com>

import unittest
from flexmock import flexmock

from appscale.common import file_io
from appscale.common import monit_app_configuration


class TestGodAppInterface(unittest.TestCase):
  def test_create_config_file(self):
    flexmock(file_io).should_receive('write')
    monit_app_configuration.create_config_file(
      'mywatch', 'start_cmd', 'pidfile', 4000,
      {'ENV1': 'VALUE1', 'ENV2': 'VALUE2'})

if __name__ == "__main__":
  unittest.main()
