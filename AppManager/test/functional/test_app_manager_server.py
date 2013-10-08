# Programmer: Navraj Chohan <nlake44@gmail.com>

import json
import os 
import sys
import SOAPpy
import time
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), "../../../lib"))
import constants

server = SOAPpy.SOAPProxy("http://127.0.0.1:" + str(constants.APP_MANAGER_PORT))

def setup_app_dir(appname):
  os.system('mkdir /var/apps/' + appname)
  os.system('mkdir /var/apps/' + appname + '/app')
  os.system('mkdir /var/apps/' + appname + '/log')
  os.system('cp -r ./apps/' + appname + '/* /var/apps/' + appname + '/app')

def teardown_app_dir(appname):
  os.system('rm -rf /var/apps/' + appname)

class RunPythonAppTestCase(unittest.TestCase):
  def setUp(self):
    self.appname = 'pythontest1'
    self.port = 20100
    setup_app_dir(self.appname)
    config = {'app_name': self.appname,
              'app_port': self.port,
              'language': 'python27',
              'load_balancer_ip': 'localhost',
              'load_balancer_port': '8090',
              'xmpp_ip': 'localhost',
              'dblocations': ['appscale-image0'] }
    config = json.dumps(config)
    self.pid = server.start_app(config)
    self.assertNotEqual(-1, self.pid)
  
  def runTest(self):
    self.assertEqual(True, os.path.exists("/proc/"+str(self.pid)))

  def tearDown(self):
    self.assertEqual(True, server.stop_app(self.appname))
    teardown_app_dir(self.appname)
    time.sleep(1)
    self.assertEqual(False, os.path.exists("/proc/"+str(self.pid)))

class RunJavaAppTestCase(unittest.TestCase):
  def setUp(self):
    self.appname = 'javatest1'
    self.port = 20101
    setup_app_dir(self.appname)
    config = {'app_name': self.appname,
              'app_port': self.port,
              'language': 'java',
              'load_balancer_ip': 'localhost',
              'load_balancer_port': '8091',
              'xmpp_ip': 'localhost',
              'dblocations': ['appscale-image0'] }
    config = json.dumps(config)
    self.pid = server.start_app(config)
    self.assertNotEqual(-1, self.pid)

  def runTest(self):
    self.assertEqual(True, os.path.exists("/proc/"+str(self.pid)))

  def tearDown(self):
    self.assertEqual(True, server.stop_app(self.appname))
    teardown_app_dir(self.appname)
    time.sleep(1)
    self.assertEqual(False, os.path.exists("/proc/"+str(self.pid)))
  
if __name__ == "__main__":
  unittest.main()
