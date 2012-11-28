import unittest
import migration
import hashlib
import SOAPpy
import yaml
from dbconstants import *

TEST_TAR = '/root/appscale/AppDB/test/migration_data.tar.gz'
DATABASE_YAML = '/root/appscale/.appscale/database_info.yaml'

# Requires AppScale running
class IntegrationDirect(unittest.TestCase):
  def setUp(self):
    FILE = open(SECRET_LOCATION, 'r')
    self.secret = FILE.read()
    FILE.close()
    m = hashlib.md5()
    file = open(TEST_TAR, 'rb')
    buffer = file.read(2 ** 20)
    while buffer:
      m.update(buffer)
      buffer = file.read(2 ** 20)
      file.close()
    self.md5 = m.hexdigest()

    FILE = open(DATABASE_YAML, 'r')
    self.dbyaml = FILE.read()
    FILE.close()
    self.dbyaml = yaml.load(self.dbyaml)
    migration.setup_datastore(self.dbyaml[':table'])
    migration.setup_zookeeper(migration.get_zk_locations())
  def runTest(self):
    assert migration.start_migration(self.secret, TEST_TAR, self.md5)

  def tearDown(self):
    pass

class IntegrationSoap(unittest.TestCase):
  def setUp(self):
    pass
  def runTest(self):
    pass
  def tearDown(self):
    pass

if __name__ == "__main__":
  unittest.main()
