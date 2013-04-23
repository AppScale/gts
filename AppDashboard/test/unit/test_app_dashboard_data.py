from flexmock import flexmock
import logging
import re
import sys
import os
import unittest

sys.path.append(os.path.join(os.path.expanduser("~"), "appscale/AppServer/"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
from app_dashboard_data import AppDashboardData
from app_dashboard_helper import AppDashboardHelper

from app_dashboard_data import DashboardDataRoot
from app_dashboard_data import APIstatus
from app_dashboard_data import ServerStatus
from app_dashboard_data import AppStatus
import app_dashboard_data

from google.appengine.ext import db
from google.appengine.api import users



class TestAppDashboardData(unittest.TestCase):

  def setUp(self):
    fake_root = flexmock()
    fake_root.head_node_ip = '1.1.1.1'
    fake_root.table = 'table'
    fake_root.replication = 'replication'
    fake_root.should_receive('put').and_return()
    flexmock(app_dashboard_data).should_receive('DashboardDataRoot')\
      .and_return(fake_root)
    flexmock(AppDashboardData).should_receive('get_one')\
      .with_args(app_dashboard_data.DashboardDataRoot,
        AppDashboardData.ROOT_KEYNAME)\
      .and_return(None)\
      .and_return(fake_root)

    fake_api1 = flexmock(name='APIstatus')
    fake_api1.name = 'api1'
    fake_api1.value = 'running'
    fake_api1.should_receive('put').and_return()
    fake_api2 = flexmock(name='APIstatus')
    fake_api2.name = 'api2'
    fake_api2.value = 'failed'
    fake_api2.should_receive('put').and_return()
    fake_api3 = flexmock(name='APIstatus')
    fake_api3.name = 'api3'
    fake_api3.value = 'unknown'
    fake_api3.should_receive('put').and_return()
    fake_api_q = flexmock()
    fake_api_q.should_receive('ancestor').and_return()
    fake_api_q.should_receive('run')\
      .and_yield(fake_api1, fake_api2, fake_api3)
    flexmock(AppDashboardData).should_receive('get_one')\
      .with_args(app_dashboard_data.APIstatus, re.compile('api'))\
      .and_return(fake_api1)\
      .and_return(fake_api3)\
      .and_return(fake_api3)
    flexmock(AppDashboardData).should_receive('get_all')\
      .with_args(app_dashboard_data.APIstatus)\
      .and_return(fake_api_q)

    fake_server1 = flexmock(name='ServerStatus')
    fake_server1.ip = '1.1.1.1'
    fake_server1.cpu = '25'
    fake_server1.memory = '50'
    fake_server1.disk = '100'
    fake_server1.cloud = 'cloud1'
    fake_server1.roles = 'roles2'
    fake_server1.should_receive('put').and_return()
    fake_server2 = flexmock(name='ServerStatus')
    fake_server2.ip = '2.2.2.2'
    fake_server2.cpu = '75'
    fake_server2.memory = '55'
    fake_server2.disk = '100'
    fake_server2.cloud = 'cloud1'
    fake_server2.roles = 'roles2'
    fake_server2.should_receive('put').and_return()
    flexmock(app_dashboard_data).should_receive('ServerStatus')\
      .and_return(fake_server1)
    fake_server_q = flexmock()
    fake_server_q.should_receive('ancestor').and_return()
    fake_server_q.should_receive('run')\
      .and_yield(fake_server1, fake_server2)
    fake_server_q.should_receive('get')\
      .and_return(fake_server1)\
      .and_return(fake_server2)
    flexmock(AppDashboardData).should_receive('get_all')\
      .with_args(app_dashboard_data.ServerStatus)\
      .and_return(fake_server_q)
    flexmock(AppDashboardData).should_receive('get_one')\
      .with_args(app_dashboard_data.ServerStatus, re.compile('\d'))\
      .and_return(fake_server1)\
      .and_return(fake_server2)

    fake_app1 = flexmock(name='AppStatus')
    fake_app1.name = 'app1'
    fake_app1.url = 'http://1.1.1.1:8080'
    fake_app1.should_receive('put').and_return()
    fake_app1.should_receive('delete').and_return()
    fake_app2 = flexmock(name='AppStatus')
    fake_app2.name = 'app2'
    fake_app2.url = None
    fake_app2.should_receive('put').and_return()
    fake_app2.should_receive('delete').and_return()
    flexmock(app_dashboard_data).should_receive('AppStatus')\
      .and_return(fake_app1)
    fake_app_q = flexmock()
    fake_app_q.should_receive('ancestor').and_return()
    fake_app_q.should_receive('run')\
      .and_yield(fake_app1, fake_app2)
    flexmock(AppDashboardData).should_receive('get_all')\
      .with_args(app_dashboard_data.AppStatus)\
      .and_return(fake_app_q)
    flexmock(AppDashboardData).should_receive('get_all')\
      .with_args(app_dashboard_data.AppStatus, keys_only=True)\
      .and_return(fake_app_q)
    flexmock(AppDashboardData).should_receive('get_one')\
      .with_args(app_dashboard_data.AppStatus, re.compile('app'))\
      .and_return(fake_app1)\
      .and_return(fake_app2)

    user_info1 = flexmock(name='UserInfo')
    user_info1.email = 'a@a.com'
    user_info1.is_user_cloud_admin = True
    user_info1.i_can_upload = True
    user_info1.user_app_list = 'app1:app2'
    user_info1.should_receive('put').and_return()
    user_info2 = flexmock(name='UserInfo')
    user_info2.email = 'b@a.com'
    user_info2.is_user_cloud_admin = False
    user_info2.i_can_upload = True
    user_info2.user_app_list = 'app2'
    user_info2.should_receive('put').and_return()
    user_info3 = flexmock(name='UserInfo')
    user_info3.email = 'c@a.com'
    user_info3.is_user_cloud_admin = False
    user_info3.i_can_upload = False
    user_info3.user_app_list = 'app2'
    user_info3.should_receive('put').and_return()
    flexmock(app_dashboard_data).should_receive('UserInfo')\
      .and_return(user_info1)
    flexmock(AppDashboardData).should_receive('get_one')\
      .with_args(app_dashboard_data.UserInfo, re.compile('@a.com'))\
      .and_return(user_info1)\
      .and_return(user_info2)\
      .and_return(user_info3)

    flexmock(db).should_receive('delete').and_return()
    flexmock(db).should_receive('run_in_transaction').and_return()


  def test_init(self):
    # Call the constructor, should call initialize_datastore().
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    data1 = AppDashboardData()
    self.assertNotEquals(None, data1.root)
    self.assertNotEquals(None, data1.helper)
    
    # Call the constructor a second time, it is already initialized so it 
    # should not call initialize_datastore().
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().never()
    data2 = AppDashboardData(flexmock())
    self.assertNotEquals(None, data2.root)
    self.assertNotEquals(None, data2.helper)

  def test_initialize_datastore(self):
    # call the constructor, should call initialize_datastore()
    # which calls update_all().
    flexmock(AppDashboardData).should_call('initialize_datastore')\
      .and_return().once()
    flexmock(AppDashboardData).should_receive('update_all')\
      .and_return().once()
    data1 = AppDashboardData()

  def test_update_all(self):
    # call the constructor, should call initialize_datastore()
    # which calls update_all(), which calls all the update_ methods
    flexmock(AppDashboardData).should_call('initialize_datastore')\
      .and_return().once()
    flexmock(AppDashboardData).should_call('update_all')\
      .and_return().once()
    flexmock(AppDashboardData).should_receive('update_head_node_ip')\
      .and_return().once()
    flexmock(AppDashboardData).should_receive('update_database_info')\
      .and_return().once()
    flexmock(AppDashboardData).should_receive('update_apistatus')\
      .and_return().once()
    flexmock(AppDashboardData).should_receive('update_status_info')\
      .and_return().once()
    flexmock(AppDashboardData).should_receive('update_application_info')\
      .and_return().once()
    flexmock(AppDashboardData).should_receive('update_users')\
      .and_return().once()
    data1 = AppDashboardData()

  def test_get_monitoring_url(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    fake_ip  = '1.1.1.1.'
    flexmock(AppDashboardData).should_receive('get_head_node_ip')\
    .and_return(fake_ip).once()

    data1 = AppDashboardData()
    url = data1.get_monitoring_url()
    self.assertEquals(url, "http://{0}:{1}".format(fake_ip, 
      AppDashboardData.MONITOR_PORT))

  def test_get_head_node_ip(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    data1 = AppDashboardData()
    fake_ip  = '1.1.1.1.'
    data1.root.head_node_ip = fake_ip
    self.assertEquals(data1.get_head_node_ip(), fake_ip)

  def test_update_head_node_ip(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    fake_ip  = '1.1.1.1.'
    flexmock(AppDashboardHelper).should_receive('get_host_with_role')\
      .and_return(fake_ip).once()
    data1 = AppDashboardData()
    data1.update_head_node_ip()
    self.assertEquals(data1.root.head_node_ip, fake_ip)

  def test_get_apistatus(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    
    data1 = AppDashboardData()
    output = data1.get_apistatus()
    self.assertEquals(len(output), 3)
    self.assertEquals(output['api1'], 'running')
    self.assertEquals(output['api2'], 'failed')
    self.assertEquals(output['api3'], 'unknown')

  def test_update_apistatus(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    fake_get_server = flexmock()
    fake_get_server.should_receive('get_api_status')\
      .and_return({
        'api1' : 'running',
        'api2' : 'failed',
        'api3' : 'unknown',
      })
    flexmock(AppDashboardHelper).should_receive('get_server')\
      .and_return(fake_get_server).once()
    
    data1 = AppDashboardData()
    data1.update_apistatus()
    output = data1.get_apistatus()
    self.assertEquals(len(output), 3)
    self.assertEquals(output['api1'], 'running')
    self.assertEquals(output['api2'], 'failed')
    self.assertEquals(output['api3'], 'unknown')

  def test_get_status_info(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    
    data1 = AppDashboardData()
    output = data1.get_status_info()
    self.assertEquals(len(output), 2)
    self.assertEquals(output[0]['ip'], '1.1.1.1')
    self.assertEquals(output[1]['ip'], '2.2.2.2')
    
  def test_update_status_info(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    fake_get_server = flexmock()
    fake_get_server.should_receive('get_stats')\
      .and_return([
        {'ip' : '1.1.1.1',
         'cpu' : '50',
         'memory' : '50',
         'disk' : '50',
         'cloud' : 'cloud1',
         'roles' : 'roles1'},
        {'ip' : '2.2.2.2',
         'cpu' : '50',
         'memory' : '50',
         'disk' : '50',
         'cloud' : 'cloud1',
         'roles' : 'roles1'}
      ])
    flexmock(AppDashboardHelper).should_receive('get_server')\
      .and_return(fake_get_server).once()
    
    data1 = AppDashboardData()
    data1.update_status_info()
    output = data1.get_status_info()
    self.assertEquals(len(output), 2)
    self.assertEquals(output[0]['ip'], '1.1.1.1')
    self.assertEquals(output[1]['ip'], '2.2.2.2')

  def test_get_database_info(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    data1 = AppDashboardData()
    output = data1.get_database_info()
    self.assertEquals(output['table'], 'table')
    self.assertEquals(output['replication'], 'replication')

  def test_update_database_info(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    fake_get_server = flexmock()
    fake_get_server.should_receive('get_database_information')\
      .and_return({
        'table' : 'table1',
        'replication' : 'replication1',
      })
    flexmock(AppDashboardHelper).should_receive('get_server')\
      .and_return(fake_get_server).once()
    data1 = AppDashboardData()
    data1.update_database_info()
    output = data1.get_database_info()
    self.assertEquals(output['table'], 'table1')
    self.assertEquals(output['replication'], 'replication1')

  def test_get_application_info(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    data1 = AppDashboardData()
    output = data1.get_application_info()
    self.assertEquals(len(output), 2)
    self.assertEquals(output['app1'], 'http://1.1.1.1:8080')
    self.assertEquals(output['app2'], None)
    
  def test_delete_app_from_datastore(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    flexmock(logging).should_receive('info').and_return()
    data1 = AppDashboardData()
    output = data1.delete_app_from_datastore('app2', email='a@a.com')
    app_list = output.user_app_list.split(AppDashboardData.APP_DELIMITER)
    self.assertEquals(output.email, 'a@a.com')
    self.assertFalse( 'app2' in app_list )
    self.assertTrue( 'app1' in app_list )

  def test_update_application_info__noapps(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    flexmock(AppDashboardHelper).should_receive('get_status_info')\
      .and_return([{
        'apps' : { 'none' :  False }
      }]).once()
    flexmock(AppDashboardHelper).should_receive('get_login_host')\
      .and_return('1.1.1.1').never()
    flexmock(AppDashboardHelper).should_receive('get_app_port')\
      .and_return('8080').never()

    data1 = AppDashboardData()
    output = data1.update_application_info()
    self.assertEquals(len(output), 0)

  def test_update_application_info__2apps(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    flexmock(AppDashboardHelper).should_receive('get_status_info')\
      .and_return([{
        'apps' : { 'app1' : True, 'app2' : False }
      }]).once()
    flexmock(AppDashboardHelper).should_receive('get_login_host')\
      .and_return('1.1.1.1').once()
    flexmock(AppDashboardHelper).should_receive('get_app_port')\
      .and_return('8080').once()

    data1 = AppDashboardData()
    output = data1.update_application_info()
    self.assertEquals(len(output), 2)
    self.assertEquals(output['app1'], 'http://1.1.1.1:8080')
    self.assertEquals(output['app2'], None)
    

  def test_update_users(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()
    flexmock(AppDashboardHelper).should_receive('list_all_users')\
      .and_return(['a@a.com', 'b@a.com', 'c@a.com']).once()
    flexmock(AppDashboardHelper).should_receive('is_user_cloud_admin')\
      .with_args('a@a.com').and_return(True).once()
    flexmock(AppDashboardHelper).should_receive('is_user_cloud_admin')\
      .with_args('b@a.com').and_return(False).once()
    flexmock(AppDashboardHelper).should_receive('is_user_cloud_admin')\
      .with_args('c@a.com').and_return(False).once()

    flexmock(AppDashboardHelper).should_receive('i_can_upload')\
      .with_args('a@a.com').and_return(True).once()
    flexmock(AppDashboardHelper).should_receive('i_can_upload')\
      .with_args('b@a.com').and_return(True).once()
    flexmock(AppDashboardHelper).should_receive('i_can_upload')\
      .with_args('c@a.com').and_return(False).once()

    flexmock(AppDashboardHelper).should_receive('get_user_app_list')\
      .with_args('a@a.com').and_return(['app1', 'app2']).once()
    flexmock(AppDashboardHelper).should_receive('get_user_app_list')\
      .with_args('b@a.com').and_return(['app2']).once()
    flexmock(AppDashboardHelper).should_receive('get_user_app_list')\
      .with_args('c@a.com').and_return(['app2']).once()

    data1 = AppDashboardData()
    output = data1.update_users()
    self.assertEquals(len(output), 3)
    self.assertTrue(output[0].is_user_cloud_admin)
    self.assertFalse(output[1].is_user_cloud_admin)
    self.assertFalse(output[2].is_user_cloud_admin)
    self.assertTrue(output[0].i_can_upload)
    self.assertTrue(output[1].i_can_upload)
    self.assertFalse(output[2].i_can_upload)


    

  def test_get_user_app_list(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()

    user_obj = flexmock(name='users')
    user_obj.should_receive('email')\
      .and_return(None)\
      .and_return('a@a.com')\
      .and_return('b@a.com')\
      .and_return('c@a.com')
    flexmock(users).should_receive('get_current_user').and_return(user_obj)

    data1 = AppDashboardData()
    # First call, not logged in.
    output = data1.get_user_app_list()
    self.assertEqual( len(output), 0 )
    # First user: a@a.com, apps=app1,app2
    output = data1.get_user_app_list()
    self.assertTrue( 'app1' in output  )
    self.assertTrue( 'app2' in output  )
    # Second user: b@a.com, apps=app2
    output = data1.get_user_app_list()
    self.assertTrue( 'app2' in output  )
    # Third user: c@a.com, admin=app2.
    output = data1.get_user_app_list()
    self.assertTrue( 'app2' in output  )

  def test_is_user_cloud_admin(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()

    user_obj = flexmock(name='users')
    user_obj.should_receive('email')\
      .and_return(None)\
      .and_return('a@a.com')\
      .and_return('b@a.com')\
      .and_return('c@a.com')
    flexmock(users).should_receive('get_current_user').and_return(user_obj)

    data1 = AppDashboardData()
    # First call, not logged in.
    self.assertFalse( data1.is_user_cloud_admin() )
    # First user: a@a.com, admin=True.
    self.assertTrue( data1.is_user_cloud_admin() )
    # Second user: b@a.com, admin=False.
    self.assertFalse( data1.is_user_cloud_admin() )
    # Third user: c@a.com, admin=False.
    self.assertFalse( data1.is_user_cloud_admin() )

  def test_i_can_upload(self):
    flexmock(AppDashboardData).should_receive('initialize_datastore')\
      .and_return().once()

    user_obj = flexmock(name='users')
    user_obj.should_receive('email')\
      .and_return(None)\
      .and_return('a@a.com')\
      .and_return('b@a.com')\
      .and_return('c@a.com')
    flexmock(users).should_receive('get_current_user').and_return(user_obj)

    data1 = AppDashboardData()
    # First call, not logged in.
    self.assertFalse( data1.i_can_upload() )
    # First user: a@a.com, upload=True.
    self.assertTrue( data1.i_can_upload() )
    # Second user: b@a.com, upload=True.
    self.assertTrue( data1.i_can_upload() )
    # Third user: c@a.com, upload=False.
    self.assertFalse( data1.i_can_upload() )
