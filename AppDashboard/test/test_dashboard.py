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
from local_state import LocalState

#from google.appengine.api import memcache
#from google.appengine.ext import db

from google.appengine.api import users

# from the app main.py
import dashboard
from app_dashboard_helper import AppDashboardHelper
from secret_key import GLOBAL_SECRET_KEY

class TestAppDashboardSuccess(Exception):
  pass

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
    acc.should_receive('upload_tgz').and_raise(SOAPpy.Errors.HTTPError)
    acc.should_receive('stop_app').and_return('true')
   
    fake_soap = flexmock(name='fake_soap')
    soap = flexmock(SOAPpy)
    soap.should_receive('SOAPProxy').and_return(fake_soap)
    fake_soap.should_receive('get_app_data').and_return(
      "\n\n ports: 8080\n num_ports:1\n"
      )
    fake_soap.should_receive('get_capabilities').and_return('upload_app')

    fake_soap.should_receive('get_user_data')\
      .with_args('a@a.com', GLOBAL_SECRET_KEY)\
      .and_return(
      "is_cloud_admin:true\napplications:app1:app2\npassword:XXXXXX\n"
      )
    fake_soap.should_receive('get_user_data')\
      .with_args('b@a.com', GLOBAL_SECRET_KEY)\
      .and_return(
      "is_cloud_admin:false\napplications:app1:app2\npassword:XXXXXX\n"
      )
    fake_soap.should_receive('get_user_data')\
      .with_args('c@a.com', GLOBAL_SECRET_KEY)\
      .and_return(
      "is_cloud_admin:false\napplications:app1:app2\npassword:XXXXXX\n"
      )

    fake_soap.should_receive('commit_new_user').and_return('true')
    fake_soap.should_receive('commit_new_token').and_return()
    fake_soap.should_receive('get_all_users').and_return("a@a.com:b@a.com")
    fake_soap.should_receive('set_capabilities').and_return('true')

    local = flexmock(LocalState)
    local.should_receive('encrypt_password').and_return('XXXXXX')

    self.request = self.fakeRequest()
    self.response = self.fakeResponse()
    self.set_user()  

  def set_user(self, email=None):
    self.usrs = flexmock(users)
    if email is not None:
      user_obj = flexmock(name='users')
      user_obj.should_receive('nickname').and_return(email)
      self.usrs.should_receive('get_current_user').and_return(user_obj)
    else:
      self.usrs.should_receive('get_current_user').and_return(None)

  def set_post(self, post_dict):
    self.request.POST = post_dict
    for key in post_dict.keys():
      self.request.should_receive('get').with_args(key)\
        .and_return(post_dict[key])

  def set_get(self, post_dict):
    self.request.GET = post_dict
    for key in post_dict.keys():
      self.request.should_receive('get').with_args(key)\
        .and_return(post_dict[key])

  def fakeRequest(self):
    req = flexmock(name='request')
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
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/shared/navigation.html -->', html)
    assert re.search('<!-- FILE:templates/landing/index.html -->', html)
    assert re.search('<a href="/users/login">Login to this cloud.</a>', html)
    assert not re.search('<a href="/authorize">Manage users.</a>', html)

  def test_landing_loggedin_notAdmin(self):
    self.set_user('b@a.com')
    from dashboard import IndexPage
    IndexPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/shared/navigation.html -->', html)
    assert re.search('<!-- FILE:templates/landing/index.html -->', html)
    assert re.search('<a href="/users/logout">Logout now.</a>', html)
    assert not re.search('<a href="/authorize">Manage users.</a>', html)

  def test_landing_loggedin_isAdmin(self):
    self.set_user('a@a.com')
    from dashboard import IndexPage
    IndexPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/shared/navigation.html -->', html)
    assert re.search('<!-- FILE:templates/landing/index.html -->', html)
    assert re.search('<a href="/users/logout">Logout now.</a>', html)
    assert re.search('<a href="/authorize">Manage users.</a>', html)

  def test_status_notloggedin(self):
    from dashboard import StatusPage
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/shared/navigation.html -->', html)
    assert re.search('<!-- FILE:templates/status/cloud.html -->', html)
    assert re.search('<a href="/users/login">Login</a>', html)

  def test_status_loggedin_notAdmin(self):
    self.set_user('b@a.com')
    from dashboard import StatusPage
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/shared/navigation.html -->', html)
    assert re.search('<!-- FILE:templates/status/cloud.html -->', html)
    assert re.search('<a href="/users/logout">Logout</a>', html)
    assert not re.search('<span>CPU / Memory Usage', html)

  def test_status_loggedin_isAdmin(self):
    self.set_user('a@a.com')
    from dashboard import StatusPage
    StatusPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/shared/navigation.html -->', html)
    assert re.search('<!-- FILE:templates/status/cloud.html -->', html)
    assert re.search('<a href="/users/logout">Logout</a>', html)
    assert re.search('<span>CPU / Memory Usage', html)

  def test_newuser_page(self):
    from dashboard import NewUserPage
    NewUserPage(self.request, self.response).get()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/users/new.html -->', html)

  def test_newuser_bademail(self):
    from dashboard import NewUserPage
    self.set_post({
      'user_email' : 'c@a',
      'user_password' : 'aaaaaa',
      'user_password_confirmation' : 'aaaaaa',
    })
    NewUserPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/users/new.html -->', html)
    assert re.search('Format must be foo@boo.goo.', html)

  def test_newuser_shortpasswd(self):
    from dashboard import NewUserPage
    self.set_post({
      'user_email' : 'c@a.com',
      'user_password' : 'aaa',
      'user_password_confirmation' : 'aaa',
    })
    NewUserPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/users/new.html -->', html)
    assert re.search('Password must be at least 6 characters long.', html)

  def test_newuser_passwdnomatch(self):
    from dashboard import NewUserPage
    self.set_post({
      'user_email' : 'c@a.com',
      'user_password' : 'aaaaa',
      'user_password_confirmation' : 'aaabbb',
    })
    NewUserPage(self.request, self.response).post()
    html =  self.response.out.getvalue()
    assert re.search('<!-- FILE:templates/layouts/main.html -->', html)
    assert re.search('<!-- FILE:templates/users/new.html -->', html)
    assert re.search('Passwords do not match.', html)

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
    assert AppDashboardHelper.DEV_APPSERVER_LOGIN_COOKIE in self.response.cookies
    assert self.response.redirect_location == '/'

