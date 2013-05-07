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
from app_dashboard_data import ApiStatus
from app_dashboard_data import ServerStatus
from app_dashboard_data import AppStatus
import app_dashboard_data

from google.appengine.ext import ndb
from google.appengine.api import users



class TestAppDashboardData(unittest.TestCase):


  def setUp(self):
    fake_root = flexmock()
    fake_root.head_node_ip = '1.1.1.1'
    fake_root.table = 'table'
    fake_root.replication = 'replication'
    fake_root.should_receive('put').and_return()

    flexmock(app_dashboard_data).should_receive('DashboardDataRoot') \
      .and_return(fake_root)
    flexmock(AppDashboardData).should_receive('get_by_id') \
      .with_args(app_dashboard_data.DashboardDataRoot,
        AppDashboardData.ROOT_KEYNAME)\
      .and_return(None)\
      .and_return(fake_root)


  def setupApiStatusMocks(self):
    fake_api1 = flexmock(name='api1', value='running')
    fake_api1.should_receive('put').and_return()

    fake_api2 = flexmock(name='api2', value='failed')
    fake_api2.should_receive('put').and_return()

    fake_api3 = flexmock(name='api3', value='unknown')
    fake_api3.should_receive('put').and_return()

    flexmock(AppDashboardData).should_receive('get_by_id') \
      .with_args(app_dashboard_data.ApiStatus, re.compile('api')) \
      .and_return(fake_api1) \
      .and_return(fake_api2) \
      .and_return(fake_api3)
    flexmock(AppDashboardData).should_receive('get_all') \
      .with_args(app_dashboard_data.ApiStatus) \
      .and_return([fake_api1, fake_api2, fake_api3])


  def setupServerStatusMocks(self):
    fake_key1 = flexmock(name='key1', id=lambda: '1.1.1.1')
    fake_server1 = flexmock(name='ServerStatus', ip='1.1.1.1', cpu='25',
      memory='50', disk='100', roles='roles2', key=fake_key1)
    fake_server1.should_receive('put').and_return()

    fake_key2 = flexmock(name='key1', id=lambda: '2.2.2.2')
    fake_server2 = flexmock(name='ServerStatus', ip='2.2.2.2', cpu='75',
      memory='55', disk='100', roles='roles2', key=fake_key2)
    fake_server2.should_receive('put').and_return()

    flexmock(app_dashboard_data).should_receive('ServerStatus') \
      .and_return(fake_server1)
    fake_server_q = flexmock()
    fake_server_q.should_receive('get') \
      .and_return(fake_server1) \
      .and_return(fake_server2)
    flexmock(AppDashboardData).should_receive('get_all') \
      .with_args(app_dashboard_data.ServerStatus)\
      .and_return([fake_server1, fake_server2])
    flexmock(AppDashboardData).should_receive('get_by_id') \
      .with_args(app_dashboard_data.ServerStatus, re.compile('\d')) \
      .and_return(fake_server1) \
      .and_return(fake_server2)


  def setupAppStatusMocks(self):
    fake_key1 = flexmock(name='key1')
    fake_key1.should_receive('delete').and_return()

    fake_app1 = flexmock(name='app1', url='http://1.1.1.1:8080', key=fake_key1)
    fake_app1.should_receive('put').and_return()

    fake_key2 = flexmock(name='key2')
    fake_key2.should_receive('delete').and_return()

    fake_app2 = flexmock(name='app2', url=None, key=fake_key2)
    fake_app2.should_receive('put').and_return()

    flexmock(app_dashboard_data).should_receive('AppStatus') \
      .and_return(fake_app1)
    flexmock(AppDashboardData).should_receive('get_all')\
      .with_args(app_dashboard_data.AppStatus)\
      .and_return([fake_app1, fake_app2])
    flexmock(AppDashboardData).should_receive('get_all') \
      .with_args(app_dashboard_data.AppStatus, keys_only=True) \
      .and_return([fake_app1, fake_app2])
    flexmock(AppDashboardData).should_receive('get_by_id') \
      .with_args(app_dashboard_data.AppStatus, re.compile('app')) \
      .and_return(fake_app1) \
      .and_return(fake_app2)


  def setupUserInfoMocks(self):
    user_info1 = flexmock(name='UserInfo', email='a@a.com',
      is_user_cloud_admin=True, can_upload_apps=True, owned_apps=['app1',
      'app2'])
    user_info1.should_receive('put').and_return()

    user_info2 = flexmock(name='UserInfo', email='b@a.com',
      is_user_cloud_admin=False, can_upload_apps=True, owned_apps=['app2'])
    user_info2.should_receive('put').and_return()

    user_info3 = flexmock(name='UserInfo', email='c@a.com',
      is_user_cloud_admin=False, can_upload_apps=False, owned_apps=['app2'])
    user_info3.should_receive('put').and_return()

    flexmock(app_dashboard_data).should_receive('UserInfo')\
      .and_return(user_info1)
    flexmock(AppDashboardData).should_receive('get_by_id')\
      .with_args(app_dashboard_data.UserInfo, re.compile('@a.com'))\
      .and_return(user_info1) \
      .and_return(user_info2) \
      .and_return(user_info3)


  def setupFakeDeletes(self):
    flexmock(ndb).should_receive('delete_multi').and_return()


  def setupUsersAPIMocks(self):
    flexmock(users)
    users.should_receive('get_current_user').and_return(None) \
      .and_return(flexmock(email=lambda:'a@a.com')) \
      .and_return(flexmock(email=lambda:'b@a.com')) \
      .and_return(flexmock(email=lambda:'c@a.com'))


  def test_init(self):
    data1 = AppDashboardData()
    self.assertNotEquals(None, data1.root)
    self.assertNotEquals(None, data1.helper)
    
    data2 = AppDashboardData(flexmock())
    self.assertNotEquals(None, data2.root)
    self.assertNotEquals(None, data2.helper)


  def test_get_monitoring_url(self):
    fake_ip  = '1.1.1.1.'
    flexmock(AppDashboardData).should_receive('get_head_node_ip')\
    .and_return(fake_ip).once()

    data1 = AppDashboardData()
    url = data1.get_monitoring_url()
    self.assertEquals(url, "http://{0}:{1}".format(fake_ip, 
      AppDashboardData.MONITOR_PORT))


  def test_get_head_node_ip(self):
    data1 = AppDashboardData()
    fake_ip  = '1.1.1.1.'
    data1.root.head_node_ip = fake_ip
    self.assertEquals(data1.get_head_node_ip(), fake_ip)


  def test_update_head_node_ip(self):
    fake_ip  = '1.1.1.1.'
    flexmock(AppDashboardHelper).should_receive('get_host_with_role')\
      .and_return(fake_ip).once()
    data1 = AppDashboardData()
    data1.update_head_node_ip()
    self.assertEquals(data1.root.head_node_ip, fake_ip)


  def test_get_api_status(self):
    self.setupApiStatusMocks()
    data1 = AppDashboardData()
    output = data1.get_api_status()
    self.assertEquals(len(output), 3)
    self.assertEquals(output['api1'], 'running')
    self.assertEquals(output['api2'], 'failed')
    self.assertEquals(output['api3'], 'unknown')


  def test_update_api_status(self):
    self.setupApiStatusMocks()
    fake_get_appcontroller_client = flexmock()
    fake_get_appcontroller_client.should_receive('get_api_status')\
      .and_return({
        'api1' : 'running',
        'api2' : 'failed',
        'api3' : 'unknown',
      })
    flexmock(AppDashboardHelper).should_receive('get_appcontroller_client')\
      .and_return(fake_get_appcontroller_client).once()
    
    data1 = AppDashboardData()
    data1.update_api_status()
    output = data1.get_api_status()
    self.assertEquals(len(output), 3)
    self.assertEquals(output['api1'], 'running')
    self.assertEquals(output['api2'], 'failed')
    self.assertEquals(output['api3'], 'unknown')


  def test_get_status_info(self):
    self.setupServerStatusMocks()
    data1 = AppDashboardData()
    output = data1.get_status_info()
    self.assertEquals(len(output), 2)
    self.assertEquals(output[0]['ip'], '1.1.1.1')
    self.assertEquals(output[1]['ip'], '2.2.2.2')
    

  def test_update_status_info(self):
    self.setupServerStatusMocks()
    fake_get_appcontroller_client = flexmock()
    fake_get_appcontroller_client.should_receive('get_stats') \
      .and_return([
        {'ip' : '1.1.1.1',
         'cpu' : '50',
         'memory' : '50',
         'disk' : '50',
         'roles' : 'roles1'},
        {'ip' : '2.2.2.2',
         'cpu' : '50',
         'memory' : '50',
         'disk' : '50',
         'roles' : 'roles1'}
      ])
    flexmock(AppDashboardHelper).should_receive('get_appcontroller_client') \
      .and_return(fake_get_appcontroller_client).once()
    
    data1 = AppDashboardData()
    data1.update_status_info()
    output = data1.get_status_info()
    self.assertEquals(len(output), 2)
    self.assertEquals(output[0]['ip'], '1.1.1.1')
    self.assertEquals(output[1]['ip'], '2.2.2.2')


  def test_get_database_info(self):
    data1 = AppDashboardData()
    output = data1.get_database_info()
    self.assertEquals(output['table'], 'table')
    self.assertEquals(output['replication'], 'replication')


  def test_update_database_info(self):
    fake_get_appcontroller_client = flexmock()
    fake_get_appcontroller_client.should_receive('get_database_information')\
      .and_return({
        'table' : 'table1',
        'replication' : '20',
      })
    flexmock(AppDashboardHelper).should_receive('get_appcontroller_client')\
      .and_return(fake_get_appcontroller_client).once()
    data1 = AppDashboardData()
    data1.update_database_info()
    output = data1.get_database_info()
    self.assertEquals(output['table'], 'table1')
    self.assertEquals(output['replication'], 20)


  def test_get_application_info(self):
    self.setupAppStatusMocks()
    data1 = AppDashboardData()
    output = data1.get_application_info()
    self.assertEquals(len(output), 2)
    self.assertEquals(output['app1'], 'http://1.1.1.1:8080')
    self.assertEquals(output['app2'], None)
    
  def test_delete_app_from_datastore(self):
    flexmock(logging).should_receive('info').and_return()
    self.setupUserInfoMocks()
    self.setupAppStatusMocks()
    data1 = AppDashboardData()
    output = data1.delete_app_from_datastore('app2', email='a@a.com')
    app_list = output.owned_apps
    self.assertEquals(output.email, 'a@a.com')
    self.assertFalse('app2' in app_list)
    self.assertTrue('app1' in app_list)

  def test_update_application_info_no_apps(self):
    flexmock(AppDashboardHelper).should_receive('get_status_info')\
      .and_return([{
        'apps' : { 'none' :  False }
      }]).once()
    flexmock(AppDashboardHelper).should_receive('get_login_host')\
      .and_return('1.1.1.1').never()
    flexmock(AppDashboardHelper).should_receive('get_app_port')\
      .and_return('8080').never()
    self.setupAppStatusMocks()
    self.setupFakeDeletes()

    data1 = AppDashboardData()
    output = data1.update_application_info()
    self.assertEquals(len(output), 0)


  def test_update_application_info_two_apps(self):
    flexmock(AppDashboardHelper).should_receive('get_status_info')\
      .and_return([{
        'apps' : { 'app1' : True, 'app2' : False }
      }]).once()
    flexmock(AppDashboardHelper).should_receive('get_login_host')\
      .and_return('1.1.1.1').once()
    flexmock(AppDashboardHelper).should_receive('get_app_port')\
      .and_return('8080').once()
    self.setupAppStatusMocks()
    self.setupFakeDeletes()

    data1 = AppDashboardData()
    output = data1.update_application_info()
    self.assertEquals(len(output), 2)
    self.assertEquals(output['app1'], 'http://1.1.1.1:8080')
    self.assertEquals(output['app2'], None)
    

  def test_update_users(self):
    flexmock(AppDashboardHelper).should_receive('list_all_users')\
      .and_return(['a@a.com', 'b@a.com', 'c@a.com']).once()
    flexmock(AppDashboardHelper).should_receive('is_user_cloud_admin')\
      .with_args('a@a.com').and_return(True).once()
    flexmock(AppDashboardHelper).should_receive('is_user_cloud_admin')\
      .with_args('b@a.com').and_return(False).once()
    flexmock(AppDashboardHelper).should_receive('is_user_cloud_admin')\
      .with_args('c@a.com').and_return(False).once()

    flexmock(AppDashboardHelper).should_receive('can_upload_apps')\
      .with_args('a@a.com').and_return(True).once()
    flexmock(AppDashboardHelper).should_receive('can_upload_apps')\
      .with_args('b@a.com').and_return(True).once()
    flexmock(AppDashboardHelper).should_receive('can_upload_apps')\
      .with_args('c@a.com').and_return(False).once()

    flexmock(AppDashboardHelper).should_receive('get_owned_apps')\
      .with_args('a@a.com').and_return(['app1', 'app2']).once()
    flexmock(AppDashboardHelper).should_receive('get_owned_apps')\
      .with_args('b@a.com').and_return(['app2']).once()
    flexmock(AppDashboardHelper).should_receive('get_owned_apps')\
      .with_args('c@a.com').and_return(['app2']).once()

    self.setupUserInfoMocks()

    data1 = AppDashboardData()
    output = data1.update_users()
    self.assertEquals(len(output), 3)
    self.assertTrue(output[0].is_user_cloud_admin)
    self.assertFalse(output[1].is_user_cloud_admin)
    self.assertFalse(output[2].is_user_cloud_admin)
    self.assertTrue(output[0].can_upload_apps)
    self.assertTrue(output[1].can_upload_apps)
    self.assertFalse(output[2].can_upload_apps)


  def test_get_owned_apps(self):
    # slip in some fake users
    self.setupUserInfoMocks()

    # mock out the App Engine Users API
    self.setupUsersAPIMocks()

    data1 = AppDashboardData()

    # First call, not logged in.
    output = data1.get_owned_apps()
    self.assertEqual(len(output), 0)

    # First user: a@a.com, apps=app1,app2
    output = data1.get_owned_apps()
    self.assertTrue('app1' in output)
    self.assertTrue('app2' in output)

    # Second user: b@a.com, apps=app2
    output = data1.get_owned_apps()
    self.assertTrue('app2' in output)

    # Third user: c@a.com, admin=app2.
    output = data1.get_owned_apps()
    self.assertTrue('app2' in output)


  def test_is_user_cloud_admin(self):
    # slip in some fake users
    self.setupUserInfoMocks()

    # mock out the App Engine Users API
    self.setupUsersAPIMocks()

    data1 = AppDashboardData()

    # First call, not logged in.
    self.assertFalse(data1.is_user_cloud_admin())

    # First user: a@a.com, admin=True.
    self.assertTrue(data1.is_user_cloud_admin())

    # Second user: b@a.com, admin=False.
    self.assertFalse(data1.is_user_cloud_admin())

    # Third user: c@a.com, admin=False.
    self.assertFalse(data1.is_user_cloud_admin())


  def test_can_upload_apps(self):
    # slip in some fake users
    self.setupUserInfoMocks()

    # mock out the App Engine Users API
    self.setupUsersAPIMocks()

    data1 = AppDashboardData()

    # First call, not logged in.
    self.assertFalse(data1.can_upload_apps())

    # First user: a@a.com, upload=True.
    self.assertTrue(data1.can_upload_apps())

    # Second user: b@a.com, upload=True.
    self.assertTrue(data1.can_upload_apps())

    # Third user: c@a.com, upload=False.
    self.assertFalse(data1.can_upload_apps())
