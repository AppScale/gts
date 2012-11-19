import os
import unittest
import subprocess
from migration import * 
from dbconstants import *
TEST_TAR = '/root/appscale/AppDB/test/migration_data.tar.gz'

class SecretTestCase(unittest.TestCase):
  def setUp(self):
    self.removeSecret = False
    try:
      FILE = open(SECRET_LOCATION, 'r')
      self.secret = FILE.read()
      FILE.close()
    except:
      self.removeSecret = True
      FILE = open(SECRET_LOCATION, 'w')
      self.secret = 'x'
      FILE.write(self.secret)
      FILE.close() 

  def runTest(self):
    assert secret_check(self.secret)
    assert not secret_check(self.secret + 'x')
    assert not secret_check('')
  
  def tearDown(self):
    if self.removeSecret:
      os.remove(SECRET_LOCATION)

class MD5TestCase(unittest.TestCase):
  def setUp(self):
    process = subprocess.Popen(['/usr/bin/md5sum', TEST_TAR], 
                               shell=False, 
                               stdout=subprocess.PIPE)
    
    output = process.communicate()[0]
    self.md5sum = output.split()[0]
  
  def runTest(self):
    assert md5_check(TEST_TAR, self.md5sum)
    assert not md5_check(TEST_TAR, self.md5sum + "1")

class TarTestCase(unittest.TestCase):
  def setUp(self):
    full_list = os.listdir('./')
    self.file_list = []
    self.tarname = 'test.tar.gz'
    tar = tarfile.open(self.tarname, 'w:gz')
    tar.add('LICENSE')
    self.file_list.append('LICENSE')
    tar.close()

  def runTest(self): 
    self.assertEquals(untar_file(self.tarname), self.file_list)

  def tearDown(self):
    remove_tar('/root/appscale/AppDB/migration_data/LICENSE')
    remove_tar('/root/appscale/AppDB/'+self.tarname)

class TestDataCase(unittest.TestCase):
  def runTest(self):
    assert untar_file(TEST_TAR) != []

class DataLoadCase(unittest.TestCase):
  def setUp(self):
    self.data_file = untar_file(TEST_TAR)[0]
    self.data = get_file_buffer(self.data_file)

  def runTest(self):
    dict_data = get_dictionary(self.data)     
    assert dict_data != [] 
    trans, nontrans = dict_transform(dict_data)
   
class TableTesting(unittest.TestCase):
  def runTest(self):
    assert is_non_trans_table("__key__")
    assert is_non_trans_table("USERS__")
    assert is_non_trans_table("APPS__")
    assert is_non_trans_table("JOURNAL_____guestbook___")
    assert not is_non_trans_table("guestbook___Greeting___")
    self.assertEquals(get_table( \
                    "guestbook___Greeting___/guestbook/Greeting:00000"), \
                    "guestbook___Greeting___")
    self.assertEquals(get_table( \
                    "__key__/APPS__"), \
                    "__key__")
    self.assertEquals(get_root_key_table_appid( \
                    "guestbook___Greeting___/guestbook/Greeting:00000"), \
                    ["guestbook/Greeting:00000", \
                     "guestbook___Greeting___", \
                     "guestbook"])
    self.assertEquals(get_table("APPS__/sisyphus"), "APPS__")

if __name__ == "__main__":
  unittest.main() 
