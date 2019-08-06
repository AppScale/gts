#!/usr/bin/env python2

from flexmock import flexmock
import os
import re
import SOAPpy
import StringIO
import sys
import unittest

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../AppDashboard'))
from dashboard import AppDeletePage
from dashboard import AppUploadPage
from dashboard import AuthorizePage
from dashboard import IndexPage
from dashboard import LoginPage
from dashboard import LoginVerify
from dashboard import LogoutPage
from dashboard import NewUserPage
from dashboard import StatusPage
from dashboard import StatusRefreshPage

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../AppServer'))
from appscale.appcontroller_client import AppControllerClient
from google.appengine.ext import db
from google.appengine.api import taskqueue
from google.appengine.api import users

sys.path.append(os.path.join(os.path.dirname(__file__), '../../lib'))
import app_dashboard_data
from app_dashboard_data import AppDashboardData
from app_dashboard_helper import AppDashboardHelper
from secret_key import GLOBAL_SECRET_KEY

class FunctionalTestAppDashboard(unittest.TestCase):

  def setUp(self):
    acc = flexmock(AppControllerClient)
    acc.should_receive('get_uaserver_host').and_return('public1')
    acc.should_receive('get_cluster_stats').and_return([
      # TODO make up example of cluster stats
      # TODO and make sure that this change doesn't break tests
      {
        # System stats provided by Hermes
        "cpu": {
          "idle": 50.0,
          "system": 28.2,
          "user": 10.5,
          "count": 2,
        },
        "partitions_dict": [
          {
            "/" : {
              "total": 30965743616,
              "free": 15482871808,
              "used": 15482871808,
            }
          }
        ],
        "memory": {
          "total": 12365412865,
          "available": 6472179712,
          "used": 8186245120
        },
        "swap": {
          "total": 2097147904,
          "free": 1210527744,
          "used": 886620160
        },
        "services": {
          # For each Process monitored by monit
          "cassandra": "Running",
        },
        "loadavg": {
           "last_1min": 0.08,
           "last_5min": 0.27,
           "last_15min": 0.33
        },
        # Node information provided by AppController itself
        "apps": {
          # This hash is empty for non-shadow nodes
          "language": "python",
          "appservers": 4,
          "pending_appservers": 2,
          "http": 8080,
          "https": 4380,
          "reqs_enqueued": 15,
          "total_reqs": 6513
        },
        "cloud": "cloud1",
        "state": "Done starting up AppScale, now in heartbeat mode",
        "db_location": "192.168.33.10",
        "public_ip": "1.1.1.1",
        "private_ip": "10.10.105.18",
        "roles": ["shadow", "zookeeper", "datastore", "taskqueue"],
      },
      {
        # System stats provided by Hermes
        "cpu": {
          "idle": 50.0,
          "system": 28.2,
          "user": 10.5,
          "count": 2,
        },
        "partitions_dict": [
          {
            "/" : {
              "total": 30965743616,
              "free": 15482871808,
              "used": 15482871808,
            }
          }
        ],
        "memory": {
          "total": 12365412865,
          "available": 6472179712,
          "used": 8186245120
        },
        "swap": {
          "free": 0,
          "used": 0
        },
        "services": {
          # For each Process monitored by monit
          # TODO
        },
        "loadavg": {
           "last_1min": 0.08,
           "last_5min": 0.27,
           "last_15min": 0.33
        },
        # Node information provided by AppController itself
        "apps": {},
        "cloud": "cloud1",
        "state": "Done starting up AppScale, now in heartbeat mode",
        "db_location": "192.168.33.10",
        "public_ip": "2.2.2.2",
        "private_ip": "10.10.105.19",
        "roles": ["appengine"],
      }
    ])
    acc.should_receive('get_role_info').and_return(
     [{'roles': ['shadow', 'login'], 'public_ip':'1.1.1.1'} ]
     )
    acc.should_receive('get_database_information').and_return(
      {'table':'fake_database', 'replication':1}
      )
    acc.should_receive('upload_tgz').and_return('true')

    fake_soap = flexmock(name='fake_soap')
    soap = flexmock(SOAPpy)
    soap.should_receive('SOAPProxy').and_return(fake_soap)

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

    fake_tq = flexmock(taskqueue)
    fake_tq.should_receive('add').and_return()

    self.setup_fake_db()


  def setup_fake_db(self):
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

    user_info1 = flexmock(name='UserInfo')
    user_info1.email = 'a@a.com'
    user_info1.is_user_cloud_admin = True
    user_info1.can_upload_apps = True
    user_info1.owned_apps = 'app1:app2'
    user_info1.should_receive('put').and_return()
    user_info2 = flexmock(name='UserInfo')
    user_info2.email = 'b@a.com'
    user_info2.is_user_cloud_admin = False
    user_info2.can_upload_apps = True
    user_info2.owned_apps = 'app2'
    user_info2.should_receive('put').and_return()
    user_info3 = flexmock(name='UserInfo')
    user_info3.email = 'c@a.com'
    user_info3.is_user_cloud_admin = False
    user_info3.can_upload_apps = False
    user_info3.owned_apps = 'app2'
    user_info3.should_receive('put').and_return()
    flexmock(app_dashboard_data).should_receive('UserInfo')\
      .and_return(user_info1)
    flexmock(AppDashboardData).should_receive('get_one')\
      .with_args(app_dashboard_data.UserInfo, re.compile('a@a.com'))\
      .and_return(user_info1)
    flexmock(AppDashboardData).should_receive('get_one')\
      .with_args(app_dashboard_data.UserInfo, re.compile('b@a.com'))\
      .and_return(user_info2)
    flexmock(AppDashboardData).should_receive('get_one')\
      .with_args(app_dashboard_data.UserInfo, re.compile('c@a.com'))\
      .and_return(user_info3)

    flexmock(db).should_receive('delete').and_return()
    flexmock(db).should_receive('run_in_transaction').and_return()


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
    IndexPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/landing/index.html -->', html))
    self.assertTrue(re.search('<a href="/users/login">Login to this cloud.</a>', html))
    self.assertFalse(re.search('<a href="/authorize">Manage users.</a>', html))

  def test_landing_loggedin_notAdmin(self):
    self.set_user('b@a.com')
    IndexPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/landing/index.html -->', html))
    self.assertTrue(re.search('<a href="/users/logout">Logout now.</a>', html))
    self.assertFalse(re.search('<a href="/authorize">Manage users.</a>', html))

  def test_landing_loggedin_isAdmin(self):
    self.set_user('a@a.com')
    IndexPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/landing/index.html -->', html))
    self.assertTrue(re.search('<a href="/users/logout">Logout now.</a>', html))
    self.assertTrue(re.search('<a href="/authorize">Manage users.</a>', html))

  def test_status_notloggedin_refresh(self):
    self.set_get({
      'forcerefresh' : '1',
    })
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/status/cloud.html -->', html))
    self.assertTrue(re.search('<a href="/users/login">Login</a>', html))

  def test_status_notloggedin(self):
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/status/cloud.html -->', html))
    self.assertTrue(re.search('<a href="/users/login">Login</a>', html))

  def test_status_loggedin_notAdmin(self):
    self.set_user('b@a.com')
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/status/cloud.html -->', html))
    self.assertTrue(re.search('<a href="/users/logout">Logout</a>', html))
    self.assertFalse(re.search('<span>CPU / Memory Usage', html))

  def test_status_loggedin_isAdmin(self):
    self.set_user('a@a.com')
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/status/cloud.html -->', html))
    self.assertTrue(re.search('<a href="/users/logout">Logout</a>', html))
    self.assertTrue(re.search('<span>CPU / Memory Usage', html))

  def test_newuser_page(self):
    NewUserPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/new.html -->', html))

  def test_newuser_bademail(self):
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
    self.set_get({
      'continue' : 'http%3A//192.168.33.168%3A8080/_ah/login%3Fcontinue%3Dhttp%3A//192.168.33.168%3A8080/'
    })
    LoginVerify(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/users/confirm.html -->', html))
    self.assertTrue(re.search('http://192.168.33.168:8080/', html))

  def test_loginverify_submitcontinue(self):
    self.set_post({
      'commit' : 'Yes',
      'continue' : 'http://192.168.33.168:8080/'
    })
    page = LoginVerify(self.request, self.response)
    page.redirect = self.response.redirect
    page.post()
    self.assertEqual(self.response.redirect_location, 'http://192.168.33.168:8080/')

  def test_loginverify_submitnocontinue(self):
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
    page = LogoutPage(self.request, self.response)
    page.redirect = self.response.redirect
    page.get()
    self.assertEqual(self.response.redirect_location, '/')
    self.assertTrue(AppDashboardHelper.DEV_APPSERVER_LOGIN_COOKIE in self.response.deleted_cookies)

  def test_login_page(self):
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
    AuthorizePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('Only the cloud administrator can change permissions.', html))

  def test_authorize_page_loggedin_notadmin(self):
    self.set_user('b@a.com')
    AuthorizePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('Only the cloud administrator can change permissions.', html))

  def test_authorize_page_loggedin_admin(self):
    self.set_user('a@a.com')
    AuthorizePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/authorize/cloud.html -->', html))
    self.assertTrue(re.search('a@a.com-upload_app', html))
    self.assertTrue(re.search('b@a.com-upload_app', html))

  def test_authorize_submit_notloggedin(self):
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
    AppUploadPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/new.html -->', html))
    self.assertTrue(re.search('You do not have permission to upload application.  Please contact your cloud administrator', html))

  def test_upload_page_loggedin(self):
    self.set_user('a@a.com')
    AppUploadPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/new.html -->', html))
    self.assertTrue(re.search('<input accept="tar.gz, tgz" id="app_file_data" name="app_file_data" size="30" type="file" />', html))


  def test_upload_submit_notloggedin(self):
    self.set_fileupload('app_file_data')
    AppUploadPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/new.html -->', html))
    self.assertTrue(re.search('You do not have permission to upload application.  Please contact your cloud administrator', html))

  def test_upload_submit_loggedin(self):
    self.set_user('a@a.com')
    self.set_fileupload('app_file_data')
    AppUploadPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/new.html -->', html))
    self.assertTrue(re.search('Application uploaded successfully.  Please wait for the application to start running.', html))

  def test_appdelete_page_nologgedin(self):
    AppDeletePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertFalse(re.search('<option ', html))

  def test_appdelete_page_loggedin_twoapps(self):
    self.set_user('a@a.com')
    AppDeletePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertTrue(re.search('<option value="app1">app1</option>', html))
    self.assertTrue(re.search('<option value="app2">app2</option>', html))

  def test_appdelete_page_loggedin_oneapp(self):
    self.set_user('b@a.com')
    AppDeletePage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertFalse(re.search('<option value="app1">app1</option>', html))
    self.assertTrue(re.search('<option value="app2">app2</option>', html))

  def test_appdelete_submit_notloggedin(self):
    self.set_post({
      'appname' : 'app1'
    })
    AppDeletePage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('<!-- FILE:templates/layouts/main.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/shared/navigation.html -->', html))
    self.assertTrue(re.search('<!-- FILE:templates/apps/delete.html -->', html))
    self.assertTrue(re.search('There are no running applications that you have permission to delete.', html))

  def test_appdelete_submit_notappadmin(self):
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

  def test_refresh_data_get(self):
    StatusRefreshPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('datastore updated', html))

  def test_refresh_data_post(self):
    StatusRefreshPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    self.assertTrue(re.search('datastore updated', html))
