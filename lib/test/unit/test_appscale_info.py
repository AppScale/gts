import os
import sys
import unittest
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), "../../"))
import appscale_info

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import file_io

class TestAppScaleInfo(unittest.TestCase):
  def test_get_num_cpus(self):
    assert 0 != appscale_info.get_num_cpus()

  def test_stop(self):
    YAML_INFO="""--- 
:keyname: appscale
:replication: "1"
:table: cassandra
"""
    flexmock(file_io)\
      .should_receive('read')\
      .and_return(YAML_INFO) 
    assert 'cassandra' == appscale_info.get_db_info()[':table']
    assert '1' == appscale_info.get_db_info()[':replication']
    assert 'appscale' == appscale_info.get_db_info()[':keyname']
    assert isinstance(appscale_info.get_db_info(), dict)
       
if __name__ == "__main__":
  unittest.main()
