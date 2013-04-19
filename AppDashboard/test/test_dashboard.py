import sys
import os
cwd = os.path.dirname(__file__) + '/../'
sys.path.append(cwd)
sys.path.append(cwd + 'lib')
sys.path.append(cwd + '../AppServer/')
sys.path.append(cwd + '../AppServer/lib/webapp2')
sys.path.append(cwd + '../AppServer/lib/webob_1_1_1')
sys.path.append(cwd + '../AppServer/lib/jinja2/')
sys.path.append('/usr/local/appscale-tools/lib')
sys.path.append('/usr/local/lib/python2.6/dist-packages/flexmock-0.9.7-py2.6.egg/')
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

import unittest
import webapp2
import re
from flexmock import flexmock
import SOAPpy
import StringIO

from appcontroller_client import AppControllerClient

from google.appengine.api import users
from google.appengine.ext import db


# from the app main.py
import dashboard
from app_dashboard_helper import AppDashboardHelper
from app_dashboard_data import AppDashboardData

from app_dashboard_data import DashboardDataRoot
from app_dashboard_data import APIstatus
from app_dashboard_data import ServerStatus
from app_dashboard_data import AppStatus


#import lib
#import lib.app_dashboard_data
from secret_key import GLOBAL_SECRET_KEY

class TestAppDashboard(unittest.TestCase):

  def setUp(self):
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
    acc.should_receive('upload_tgz').and_return('true')
    acc.should_receive('stop_app').and_return('true')
   
    fake_soap = flexmock(name='fake_soap')
    soap = flexmock(SOAPpy)
    soap.should_receive('SOAPProxy').and_return(fake_soap)
    fake_soap.should_receive('get_app_data').and_return(
      "\n\n ports: 8080\n num_ports:1\n"
      )

    fake_soap.should_receive('get_capabilities')\
      .with_args('a@a.com', GLOBAL_SECRET_KEY)\
      .and_return('upload_app')
    fake_soap.should_receive('get_capabilities')\
      .with_args('b@a.com', GLOBAL_SECRET_KEY)\
      .and_return('upload_app')
    fake_soap.should_receive('get_capabilities')\
      .with_args('c@a.com', GLOBAL_SECRET_KEY)\
      .and_return('')

    fake_soap.should_receive('get_user_data')\
      .with_args('a@a.com', GLOBAL_SECRET_KEY)\
      .and_return(
      "is_cloud_admin:true\napplications:app1:app2\npassword:79951d98d43c1830c5e5e4de58244a621595dfaa\n"
      )
    fake_soap.should_receive('get_user_data')\
      .with_args('b@a.com', GLOBAL_SECRET_KEY)\
      .and_return(
      "is_cloud_admin:false\napplications:app2\npassword:79951d98d43c1830c5e5e4de58244a621595dfaa\n"
      )
    fake_soap.should_receive('get_user_data')\
      .with_args('c@a.com', GLOBAL_SECRET_KEY)\
      .and_return(
      "is_cloud_admin:false\napplications:app2\npassword:79951d98d43c1830c5e5e4de58244a621595dfaa\n"
      )

    fake_soap.should_receive('commit_new_user').and_return('true')
    fake_soap.should_receive('commit_new_token').and_return()
    fake_soap.should_receive('get_all_users').and_return("a@a.com:b@a.com")
    fake_soap.should_receive('set_capabilities').and_return('true')

    self.request = self.fakeRequest()
    self.response = self.fakeResponse()
    self.set_user()  

    fake_dataroot = flexmock(name='DashboardDataRoot')
    fake_root = flexmock(DashboardDataRoot)
    fake_root.new_instances(fake_dataroot)
    fake_root.should_receive('get_by_key_name').and_return(None)\
      .and_return(fake_dataroot)
    fake_dataroot.should_receive('put').and_return()
    fake_dataroot.head_node_ip = ''
    fake_dataroot.table = ''
    fake_dataroot.replication = ''

    fake_api1 = flexmock(name='APIstatus')
    fake_api1.name = 'api1'
    fake_api1.value = 'running'
    fake_api1.should_receive('put').and_return()
    fake_api2 = flexmock(name='APIstatus')
    fake_api2.name = 'api1'
    fake_api2.value = 'failed'
    fake_api1.should_receive('put').and_return()
    fake_api3 = flexmock(name='APIstatus')
    fake_api3.name = 'api1'
    fake_api3.value = 'unknown'
    fake_api1.should_receive('put').and_return()
    fake_query = flexmock(name='APIstatus_query')
    fake_query.should_receive('ancestor').and_return()
    fake_query.should_receive('run')\
      .and_return(fake_api1)\
      .and_return(fake_api2)\
      .and_return(fake_api3)
    fake_apistatus = flexmock(APIstatus)
    fake_apistatus.new_instances(fake_api1)
    fake_apistatus.should_receive('all').and_return(fake_query)
    fake_apistatus.should_receive('get_by_key_name')\
      .and_return(fake_api1)\
      .and_return(fake_api2)\
      .and_return(fake_api3)

    fake_server1 = flexmock(name='ServerStatus')
    fake_server1.ip = ''
    fake_server1.cpu = ''
    fake_server1.memory = ''
    fake_server1.disk = ''
    fake_server1.cloud = ''
    fake_server1.roles = ''
    fake_server1.should_receive('put').and_return()
    fake_server2 = flexmock(name='ServerStatus')
    fake_server2.ip = ''
    fake_server2.cpu = ''
    fake_server2.memory = ''
    fake_server2.disk = ''
    fake_server2.cloud = ''
    fake_server2.roles = ''
    fake_server2.should_receive('put').and_return()
    fake_server_query = flexmock(name='APIstatus_query')
    fake_server_query.should_receive('ancestor').and_return()
    fake_server_query.should_receive('run')\
      .and_return(fake_server1)\
      .and_return(fake_server2)
    fake_serverstatus = flexmock(ServerStatus)
    fake_serverstatus.new_instances(fake_server1)
    fake_serverstatus.should_receive('all').and_return(fake_server_query)
    fake_serverstatus.should_receive('get_by_key_name')\
      .and_return(fake_server1)\
      .and_return(fake_server2)

    fake_db = flexmock(db)
    fake_db.should_receive('delete').and_return()
    fake_db.should_receive('run_in_transaction').and_return()

    fake_app1 = flexmock(name='AppStatus')
    fake_app1.name = 'api1'
    fake_app1.url = 'running'
    fake_app1.should_receive('put').and_return()
    fake_app1.should_receive('delete').and_return()
    fake_app2 = flexmock(name='AppStatus')
    fake_app2.name = 'api1'
    fake_app2.url = 'running'
    fake_app2.should_receive('put').and_return()
    fake_app2.should_receive('delete').and_return()
    fake_app_query = flexmock(name='AppStatus_query')
    fake_app_query.should_receive('ancestor').and_return()
    fake_app_query.should_receive('run')\
      .and_return(fake_app1)\
      .and_return(fake_app2)
    fake_appstatus = flexmock(AppStatus)
    fake_appstatus.new_instances(fake_app1)
    fake_appstatus.should_receive('all').and_return(fake_app_query)
    fake_appstatus.should_receive('get_by_key_name')\
      .and_return(fake_app1)\
      .and_return(fake_app2)


  def set_user(self, email=None):
    self.usrs = flexmock(users)
    if email is not None:
      user_obj = flexmock(name='users')
      user_obj.should_receive('email').and_return(email)
      self.usrs.should_receive('get_current_user').and_return(user_obj)
    else:
      self.usrs.should_receive('get_current_user').and_return(None)

  def set_post(self, post_dict):
    self.request.POST = post_dict
    for key in post_dict.keys():
      self.request.should_receive('get').with_args(key)\
        .and_return(post_dict[key])

  def set_fileupload(self, fieldname):
    self.request.POST = flexmock(name='POST')
    self.request.POST.multi = {}
    self.request.POST.multi[fieldname] = flexmock(name='file')
    self.request.POST.multi[fieldname].file = StringIO.StringIO("FILE CONTENTS")

  def set_get(self, post_dict):
    self.request.GET = post_dict
    for key in post_dict.keys():
      self.request.should_receive('get').with_args(key)\
        .and_return(post_dict[key])

  def fakeRequest(self):
    req = flexmock(name='request')
    req.should_receive('get').and_return('')
    req.url = '/'
    return req

  def fakeResponse(self):
    res = flexmock(name='response')
    res.headers = {}
    res.cookies = {}
    res.deleted_cookies = {}
    res.redirect_location = None
    res.out = StringIO.StringIO()
    def fake_set_cookie(key, value='', max_age=None, path='/', domain=None, 
      secure=None, httponly=False, comment=None, expires=None, overwrite=False):
      res.cookies[key] = value
    def fake_delete_cookie(key, path='/', domain=None):
      res.deleted_cookies[key] = 1
    def fake_clear(): pass
    def fake_redirect(path, response):
      res.redirect_location = path
    res.set_cookie = fake_set_cookie
    res.delete_cookie = fake_delete_cookie
    res.clear = fake_clear
    res.redirect = fake_redirect
    return res

  def test_landing_notloggedin(self):
    from dashboard import IndexPage
    IndexPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/landing/index.html -->', html))
    self.assertTrue(re.search('<a href="/users/login">Login to this cloud.</a>', html))
    self.assertFalse(re.search('<a href="/authorize">Manage users.</a>', html))

  def test_landing_loggedin_notAdmin(self):
    self.set_user('b@a.com')
    from dashboard import IndexPage
    IndexPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/landing/index.html -->', html))
    self.assertTrue(re.search('<a href="/users/logout">Logout now.</a>', html))
    self.assertFalse(re.search('<a href="/authorize">Manage users.</a>', html))

  def test_landing_loggedin_isAdmin(self):
    self.set_user('a@a.com')
    from dashboard import IndexPage
    IndexPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/landing/index.html -->', html))
    self.assertTrue(re.search('<a href="/users/logout">Logout now.</a>', html))
    self.assertTrue(re.search('<a href="/authorize">Manage users.</a>', html))

  def test_status_notloggedin(self):
    from dashboard import StatusPage
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/status/cloud.html -->', html))
    self.assertTrue(re.search('<a href="/users/login">Login</a>', html))

  def test_status_loggedin_notAdmin(self):
    self.set_user('b@a.com')
    from dashboard import StatusPage
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/status/cloud.html -->', html))
    self.assertTrue(re.search('<a href="/users/logout">Logout</a>', html))
    self.assertFalse(re.search('<span>CPU / Memory Usage', html))

  def test_status_loggedin_isAdmin(self):
    self.set_user('a@a.com')
    from dashboard import StatusPage
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/status/cloud.html -->', html))
    self.assertTrue(re.search('<a href="/users/logout">Logout</a>', html))
    self.assertTrue(re.search('<span>CPU / Memory Usage', html))

  def test_newuser_page(self):
    from dashboard import NewUserPage
    NewUserPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/new.html -->', html))

  def test_newuser_bademail(self):
    from dashboard import NewUserPage
    self.set_post({
      'user_email' : 'c@a',
      'user_password' : 'aaaaaa',
      'user_password_confirmation' : 'aaaaaa',
    })
    NewUserPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/new.html -->', html))
    self.assertTrue(re.search('Format must be foo@boo.goo.', html))

  def test_newuser_shortpasswd(self):
    from dashboard import NewUserPage
    self.set_post({
      'user_email' : 'c@a.com',
      'user_password' : 'aaa',
      'user_password_confirmation' : 'aaa',
    })
    NewUserPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/new.html -->', html))
    self.assertTrue(re.search('Password must be at least 6 characters long.', html))

  def test_newuser_passwdnomatch(self):
    from dashboard import NewUserPage
    self.set_post({
      'user_email' : 'c@a.com',
      'user_password' : 'aaaaa',
      'user_password_confirmation' : 'aaabbb',
    })
    NewUserPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/new.html -->', html))
    self.assertTrue(re.search('Passwords do not match.', html))

  def test_newuser_success(self):
    from dashboard import NewUserPage
    self.set_post({
      'user_email' : 'c@a.com',
      'user_password' : 'aaaaaa',
      'user_password_confirmation' : 'aaaaaa',
    })
    page = NewUserPage(self.request, self.response)
    page.redirect = self.response.redirect
    page.post()
    self.assertTrue(AppDashboardHelper.DEV_APPSERVER_LOGIN_COOKIE in self.response.cookies)
    self.assertEqual(self.response.redirect_location, '/')

  def test_loginverify_page(self):
    from dashboard import LoginVerify
    self.set_get({
      'continue' : 'http%3A//192.168.33.168%3A8080/_ah/login%3Fcontinue%3Dhttp%3A//192.168.33.168%3A8080/'
    })
    LoginVerify(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/confirm.html -->', html))
    self.assertTrue(re.search('http://192.168.33.168:8080/', html))

  def test_loginverify_submitcontinue(self):
    from dashboard import LoginVerify
    self.set_post({
      'commit' : 'Yes',
      'continue' : 'http://192.168.33.168:8080/'
    })
    page = LoginVerify(self.request, self.response)
    page.redirect = self.response.redirect
    page.post()
    self.assertEqual(self.response.redirect_location, 'http://192.168.33.168:8080/')

  def test_loginverify_submitnocontinue(self):
    from dashboard import LoginVerify
    self.set_post({
      'commit' : 'No',
      'continue' : 'http://192.168.33.168:8080/'
    })
    page = LoginVerify(self.request, self.response)
    page.redirect = self.response.redirect
    page.post()
    self.assertEqual(self.response.redirect_location, '/')

  def test_logout_page(self):
    self.set_user('a@a.com')
    from dashboard import LogoutPage
    page = LogoutPage(self.request, self.response)
    page.redirect = self.response.redirect
    page.get()
    self.assertEqual(self.response.redirect_location, '/')
    self.assertTrue(AppDashboardHelper.DEV_APPSERVER_LOGIN_COOKIE in self.response.deleted_cookies)

  def test_login_page(self):
    from dashboard import LoginPage
    continue_url = 'http%3A//192.168.33.168%3A8080/_ah/login%3Fcontinue%3Dhttp%3A//192.168.33.168%3A8080/' 
    self.set_get({
      'continue' : continue_url
    })
    LoginPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/login.html -->', html))
    self.assertTrue(re.search(continue_url, html))

  def test_login_success(self):
    from dashboard import LoginPage
    self.set_post({
      'user_email' : 'a@a.com',
      'user_password' : 'aaaaaa'
    })
    page = LoginPage(self.request, self.response)
    page.redirect = self.response.redirect
    page.post()
    html =  self.response.out.getvalue()
    self.assertEqual(self.response.redirect_location, '/')
    self.assertTrue(AppDashboardHelper.DEV_APPSERVER_LOGIN_COOKIE in self.response.cookies)

  def test_login_success_redir(self):
    from dashboard import LoginPage
    continue_url = 'http%3A//192.168.33.168%3A8080/_ah/login%3Fcontinue%3Dhttp%3A//192.168.33.168%3A8080/' 
    self.set_post({
      'continue' : continue_url,
      'user_email' : 'a@a.com',
      'user_password' : 'aaaaaa'
    })
    page = LoginPage(self.request, self.response)
    page.redirect = self.response.redirect
    page.post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('/users/confirm\?continue=',self.response.redirect_location))
    self.assertTrue(AppDashboardHelper.DEV_APPSERVER_LOGIN_COOKIE in self.response.cookies)

  def test_login_fail(self):
    from dashboard import LoginPage
    self.set_post({
      'user_email' : 'a@a.com',
      'user_password' : 'bbbbbb'
    })
    page = LoginPage(self.request, self.response)
    page.redirect = self.response.redirect
    page.post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/login.html -->', html))
    self.assertTrue(re.search('Incorrect username / password combination. Please try again', html))

  def test_authorize_page_notloggedin(self):
    from dashboard import AuthorizePage
    AuthorizePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('Only the cloud administrator can change permissions.', html))

  def test_authorize_page_loggedin_notadmin(self):
    from dashboard import AuthorizePage
    self.set_user('b@a.com')
    AuthorizePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('Only the cloud administrator can change permissions.', html))

  def test_authorize_page_loggedin_admin(self):
    from dashboard import AuthorizePage
    self.set_user('a@a.com')
    AuthorizePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('a@a.com-upload_app', html))
    self.assertTrue(re.search('b@a.com-upload_app', html))

  def test_authorize_submit_notloggedin(self):
    from dashboard import AuthorizePage
    self.set_post({
      'user_permission_1' : 'a@a.com',
      'CURRENT-a@a.com-upload_app' : 'True',
      'a@a.com-upload_app' : 'a@a.com-upload_app', #this box is checked
      'user_permission_1' : 'b@a.com',
      'CURRENT-b@a.com-upload_app' : 'True', #this box is unchecked
    })
    AuthorizePage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('Only the cloud administrator can change permissions.', html))

  def test_authorize_submit_notadmin(self):
    from dashboard import AuthorizePage
    self.set_user('b@a.com')
    self.set_post({
      'user_permission_1' : 'a@a.com',
      'CURRENT-a@a.com-upload_app' : 'True',
      'a@a.com-upload_app' : 'a@a.com-upload_app', #this box is checked
      'user_permission_1' : 'b@a.com',
      'CURRENT-b@a.com-upload_app' : 'True', #this box is unchecked
    })
    AuthorizePage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('Only the cloud administrator can change permissions.', html))

  def test_authorize_submit_remove(self):
    from dashboard import AuthorizePage
    self.set_user('a@a.com')
    self.set_post({
      'user_permission_1' : 'a@a.com',
      'CURRENT-a@a.com-upload_app' : 'True',
      'a@a.com-upload_app' : 'a@a.com-upload_app', #this box is checked
      'user_permission_1' : 'b@a.com',
      'CURRENT-b@a.com-upload_app' : 'True', #this box is unchecked
    })
    AuthorizePage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('Disabling upload_app for b@a.com', html))

  def test_authorize_submit_add(self):
    from dashboard import AuthorizePage
    self.set_user('a@a.com')
    self.set_post({
      'user_permission_1' : 'a@a.com',
      'CURRENT-a@a.com-upload_app' : 'True',
      'a@a.com-upload_app' : 'a@a.com-upload_app', #this box is checked
      'user_permission_1' : 'c@a.com',
      'CURRENT-c@a.com-upload_app' : 'False', #this box is unchecked
      'c@a.com-upload_app' : 'c@a.com-upload_app', #this box is checked
    })
    AuthorizePage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('Enabling upload_app for c@a.com', html))

  def test_upload_page_notloggedin(self):
    from dashboard import AppUploadPage
    AppUploadPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/new.html -->', html))
    self.assertTrue(re.search('You do not have permission to upload application.  Please contact your cloud administrator', html))

  def test_upload_page_loggedin(self):
    from dashboard import AppUploadPage
    self.set_user('a@a.com')
    AppUploadPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/new.html -->', html))
    self.assertTrue(re.search('<input accept="tar.gz, tgz" id="app_file_data" name="app_file_data" size="30" type="file" />', html))


  def test_upload_submit_notloggedin(self):
    from dashboard import AppUploadPage
    self.set_fileupload('app_file_data')
    AppUploadPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/new.html -->', html))
    self.assertTrue(re.search('You do not have permission to upload application.  Please contact your cloud administrator', html))

  def test_upload_submit_loggedin(self):
    from dashboard import AppUploadPage
    self.set_user('a@a.com')
    self.set_fileupload('app_file_data')
    AppUploadPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/new.html -->', html))
    self.assertTrue(re.search('Application uploaded successfully.  Please wait for the application to start running.', html))

  def test_appdelete_page_nologgedin(self):
    from dashboard import AppDeletePage
    AppDeletePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertFalse(re.search('<option ', html))

  def test_appdelete_page_loggedin_twoapps(self):
    from dashboard import AppDeletePage
    self.set_user('a@a.com')
    AppDeletePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertTrue(re.search('<option value="app1">app1</option>', html))
    self.assertTrue(re.search('<option value="app2">app2</option>', html))

  def test_appdelete_page_loggedin_oneapp(self):
    from dashboard import AppDeletePage
    self.set_user('b@a.com')
    AppDeletePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertFalse(re.search('<option value="app1">app1</option>', html))
    self.assertTrue(re.search('<option value="app2">app2</option>', html))

  def test_appdelete_submit_notloggedin(self):
    from dashboard import AppDeletePage
    self.set_post({
      'appname' : 'app1'
    })
    AppDeletePage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertTrue(re.search('You do not have permission to delete the application: app1', html))

  def test_appdelete_submit_notappadmin(self):
    from dashboard import AppDeletePage
    self.set_user('b@a.com')
    self.set_post({
      'appname' : 'app1'
    })
    AppDeletePage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertTrue(re.search('You do not have permission to delete the application: app1', html))

  def test_appdelete_submit_success(self):
    from dashboard import AppDeletePage
    self.set_user('a@a.com')
    self.set_post({
      'appname' : 'app1'
    })
    AppDeletePage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertTrue(re.search('Application removed successfully. Please wait for your app to shut', html))
