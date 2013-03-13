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
    self.assertNotEqual(0, appscale_info.get_num_cpus())

  def test_stop(self):
    YAML_INFO="""--- 
:keyname: appscale
:replication: "1"
:table: cassandra
"""
    flexmock(file_io)\
      .should_receive('read')\
      .and_return(YAML_INFO) 
    self.assertEqual('cassandra', appscale_info.get_db_info()[':table'])
    self.assertEqual( '1', appscale_info.get_db_info()[':replication'])
    self.assertEqual( 'appscale', appscale_info.get_db_info()[':keyname'])
    self.assertEqual(True, isinstance(appscale_info.get_db_info(), dict))

  def test_get_taskqueue_nodes(self):
    flexmock(file_io).should_receive("mkdir").and_return(None)
    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1\n129.168.0.2\n184.48.65.89")
    self.assertEquals(appscale_info.get_taskqueue_nodes(), 
                     ["192.168.0.1","129.168.0.2","184.48.65.89"])

    flexmock(file_io) \
       .should_receive("read").and_return("192.168.0.1\n129.168.0.2\n184.48.65.89\n")
    self.assertEquals(appscale_info.get_taskqueue_nodes(), 
                     ["192.168.0.1","129.168.0.2","184.48.65.89"])

    flexmock(file_io) \
       .should_receive("read").and_return("")
    self.assertEquals(appscale_info.get_taskqueue_nodes(), [])

      
if __name__ == "__main__":
  unittest.main()
