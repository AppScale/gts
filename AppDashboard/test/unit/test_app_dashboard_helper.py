from flexmock import flexmock
import logging
import re
import sys
import os
import unittest
import urllib

sys.path.append(os.path.join(os.path.expanduser("~"), "appscale/AppServer/"))
sys.path.append(os.path.join(os.path.dirname(__file__), "../../lib/"))
from app_dashboard_data import AppDashboardData
from app_dashboard_helper import AppDashboardHelper

from app_dashboard_data import DashboardDataRoot
from app_dashboard_data import ServerStatus
from app_dashboard_data import AppStatus
import app_dashboard_data

from google.appengine.ext import ndb
from google.appengine.api import users



class TestAppDashboardHelper(unittest.TestCase):

  def test_get_cookie_app_list(self):
    request = flexmock()
    request.cookies = { AppDashboardHelper.DEV_APPSERVER_LOGIN_COOKIE : 
      urllib.quote('a@a.com:a:app1,app2:FAKEHASH') }

    output = AppDashboardHelper().get_cookie_app_list(request)
    self.assertTrue( len(output) == 2 )
    self.assertEquals('app1', output[0] )
    self.assertEquals('app2', output[1] )

  def test_update_cookie_app_list(self):
    fake_user = flexmock()
    fake_user.should_receive('email').and_return('a@a.com')
    flexmock(users).should_receive('get_current_user') \
      .and_return(fake_user)
    flexmock(AppDashboardHelper).should_receive('get_cookie_app_list') \
      .and_return(['app1', 'app2'])
    flexmock(AppDashboardHelper).should_receive('set_appserver_cookie') \
      .once()

    self.assertTrue(AppDashboardHelper().update_cookie_app_list(['app1', 
      'app2', 'app3'], flexmock(), flexmock()))
    self.assertFalse(AppDashboardHelper().update_cookie_app_list(['app1', 
      'app2'], flexmock(), flexmock()))
	
      

  def test_get_user_app_list(self):
    flexmock(AppDashboardHelper).should_receive('query_user_data') \
      .and_return('\napplications:app1:app2\n')
    output = AppDashboardHelper().get_user_app_list('a@a.com')
    self.assertTrue( len(output) == 2 )
    self.assertEquals('app1', output[0] )
    self.assertEquals('app2', output[1] )
