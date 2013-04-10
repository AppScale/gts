import sys
sys.path.append('/root/appscale/AppServer/lib/webapp2')
sys.path.append('/root/appscale/AppServer/lib/webob_1_1_1')
sys.path.append('..')
sys.path.append('/root/appscale/AppServer/lib/jinja2/')
sys.path.append('/root/appscale-tools/lib/')
sys.path.append('/usr/local/lib/python2.6/dist-packages/flexmock-0.9.7-py2.6.egg/')
sys.path.append('/root/appscale/AppServer/')
#from /root/appscale/AppServer/dev_appserver.py
sys.path.extend(['/usr/share/pyshared',
  '/usr/local/lib/python2.7/site-packages',
  '/usr/local/lib/python2.6/dist-packages/xmpppy-0.5.0rc1-py2.6.egg',
  '/usr/lib/pymodules/python2.6/',
  '/usr/share/python-support/python-soappy/SOAPpy',
  '/usr/local/lib/python2.6/dist-packages/SOAPpy-0.12.5-py2.6.egg',
  '/root/appscale/AppServer/google/appengine/api/SOAPpy/',
  '/usr/local/lib/python2.6/dist-packages/termcolor-1.1.0-py2.6.egg',
  '/usr/local/lib/python2.6/dist-packages/lxml-3.1.1-py2.6-linux-x86_64.egg',
  '/usr/lib/python2.6/dist-packages/',
])

print "\n".join( sys.path )


import unittest
import webapp2
import re
from flexmock import flexmock
import SOAPpy

from appcontroller_client import AppControllerClient
from local_state import LocalState

from google.appengine.api import memcache
from google.appengine.ext import db
from google.appengine.ext import testbed
from google.appengine.datastore import datastore_stub_util

#from google.appengine.api import users

# from the app main.py
import dashboard

class TestAppDashboard(unittest.TestCase):

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    #self.testbed.init_user_stub()
    #self.testbed.init_datastore_v3_stub()
    #self.testbed.init_taskqueue_stub()
    #self.testbed.init_memcache_stub()

    acc = flexmock(AppControllerClient)
    acc.should_receive('get_uaserver_host').and_return('public1')
    acc.should_receive('get_stats').and_return(
        [{'apps':{ 'app1':True, 'app2':False } }]
      )
    acc.should_receive('get_role_info').and_return(
     [{'jobs':['shadow', 'login'], 'public_ip':'1.1.1.1'} ]
     )
    acc.should_receive('get_database_information').and_return(
      {'table':'fake_database', 'replication':1}
      )
    acc.should_receive('get_api_status').and_return(
      {'api1':'running', 'api2':'failed', 'api3':'unknown'}
      )
    acc.should_receive('upload_tgz').and_raise(SOAPpy.Errors.HTTPError)
    acc.should_receive('stop_app').and_return('true')
   
    fake_soap = flexmock(name='fake_soap')
    soap = flexmock(SOAPpy)
    soap.should_receive('SOAPProxy').and_return(fake_soap)
    fake_soap.should_receive('get_app_data').and_return(
      "\n\n ports: 8080\n num_ports:1\n"
      )
    fake_soap.should_receive('get_capabilities').and_return(['upload_app'])
    fake_soap.should_receive('get_user_data').and_return(
      "is_cloud_admin:true\napplications:app1:app2\npassword:XXXXXX\n"
      )
    fake_soap.should_receive('commit_new_user').and_return('true')
    fake_soap.should_receive('commit_new_token').and_return()
    fake_soap.should_receive('get_all_users').and_return("a@a.com:b@a.com")
    fake_soap.should_receive('set_capabilities').and_return('true')


    local = flexmock(LocalState)
    local.should_receive('encrypt_password').and_return('XXXXXX')


  def test_landing(self):
    request = webapp2.Request.blank('/')
    request.method = 'GET'
    response = request.get_response(dashboard.app)

    assert response.status_int == 200
    assert re.match('FILE:templates/landing/index.html',response)
    
 
