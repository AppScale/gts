#!/usr/bin/env python
""" The AppDashboard is a Google App Engine application that implements a web UI
for interacting with running AppScale deployments. This includes the ability to
create new users, change their authorizations, and upload/remove Google App
Engine applications.
"""
# pylint: disable-msg=F0401
# pylint: disable-msg=C0103
# pylint: disable-msg=E1101
# pylint: disable-msg=W0613

import datetime
import json
import logging
import os
import re
import sys
import time
import urllib
from collections import defaultdict

import crontab
import webapp2

from google.appengine.api import memcache
from google.appengine.api import taskqueue
from google.appengine.datastore.datastore_query import Cursor
from google.appengine.ext import ndb
from google.appengine.ext.db.stats import KindStat

sys.path.append(os.path.dirname(__file__) + '/lib')
from app_dashboard import AppDashboard
from app_dashboard import jinja_environment
from app_dashboard_helper import AppDashboardHelper
from app_dashboard_helper import AppHelperException
from app_dashboard_data import RequestInfo
from dashboard_logs import RequestLogLine
from datastore_viewer import DatastoreEditRequestHandler
from datastore_viewer import DatastoreViewer
from datastore_viewer import DatastoreViewerSelector
from service_accounts import (ServiceAccountsProjectSelector,
                              ProjectServiceAccounts)
from pull_queue_viewer import (PQProjectSelector, PQQueueSelector,
                               PQTaskSelector)


# The maximum number of datapoints we send to be rendered in a graph
# charting requests per second.
MAX_REQUESTS_DATA_POINTS = 100


class LoggedService(ndb.Model):
  """ A Datastore Model that represents all of the machines running in this
  AppScale deployment.

  Fields:
    hosts: A list of strs, where each str corresponds to the hostname (an IP or
      a FQDN) of a machine running in this AppScale cloud.
  """
  hosts = ndb.StringProperty(repeated=True)


class IndexPage(AppDashboard):
  """ Class to handle requests to the / page. """

  # The template to use for the index page.
  TEMPLATE = 'landing/index.html'

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page='landing', template_file=self.TEMPLATE, values={
      'monitoring_url': self.dstore.get_monitoring_url(),
    })


class DashPage(AppDashboard):
  """ Class to handle requests to the /status page. """

  # The path for the status page.
  PATH = '/'

  # Another url that serves the status page.
  ALIAS = '/status'

  # The template to use for the status page.
  TEMPLATE = 'apps/dash.html'

  def get(self):
    """ Handler for GET requests. """
    # Called from the web.  Refresh data then display page (may be slow).
    if self.request.get('forcerefresh'):
      self.dstore.update_all()

    self.render_page(page='dash', template_file=self.TEMPLATE, values={
      'server_info': self.helper.get_status_info(),
      'dbinfo': self.dstore.get_database_info(),
      'apps': self.helper.get_version_info().keys(),
      'monitoring_url': self.dstore.get_monitoring_url(),
    })


class DashRefreshPage(AppDashboard):
  """ Class to handle requests to the /status/refresh page. """

  def get(self):
    """ Handler for GET requests. Updates all the datastore values with
        information from the AppController and UserAppServer."""
    # Called from taskqueue. Refresh data and display status message.
    self.dstore.update_all()
    self.response.out.write('datastore updated')

  def post(self):
    """ Handler for POST requests. Updates all the datastore values with
        information from the AppController and UserAppServer."""
    # Called from taskqueue. Refresh data and display status message.
    self.dstore.update_all()
    self.response.out.write('datastore updated')


class StatusPage(AppDashboard):
  """ Class to handle requests to the /status page. """

  # The path for the status page.
  PATH = '/status/cloud'

  # Another url that serves the status page.
  ALIAS = '/status/cloud'

  # The template to use for the status page.
  TEMPLATE = 'status/cloud.html'

  def get(self):
    """ Handler for GET requests. """
    # Called from the web.  Refresh data then display page (may be slow).
    if self.request.get('forcerefresh'):
      self.dstore.update_all()

    self.render_app_page(page='status', values={
      'server_info': self.helper.get_status_info(),
      'dbinfo': self.dstore.get_database_info(),
      'apps': self.helper.get_version_info(),
      'monitoring_url': self.dstore.get_monitoring_url(),
      'page_content': self.TEMPLATE,
    })


class StatusAsJSONPage(webapp2.RequestHandler):
  """ A class that exposes the same information as DashPage, but via JSON
  instead of raw HTML. """

  def get(self):
    """ Retrieves the cached information about machine-level statistics as a
    JSON-encoded dict. """
    self.response.out.write(json.dumps(AppDashboardHelper().get_status_info()))


class NewUserPage(AppDashboard):
  """ Class to handle requests to the /users/new and /users/create page. """

  # The template to use for the new user page.
  TEMPLATE = 'users/new.html'

  # An int that indicates how many characters passwords must be for new user
  # accounts.
  MIN_PASSWORD_LENGTH = 6

  def parse_new_user_post(self):
    """ Parse the input from the create user form.

    Returns:
      A dict that maps the form fields on the user creation page to None (if
        they pass our validation) or a str indicating why they fail our
        validation.
    """
    users = {}
    error_msgs = {}
    users['email'] = self.request.get('user_email')
    if re.match(self.USER_EMAIL_REGEX, users['email']):
      error_msgs['email'] = None
    else:
      error_msgs['email'] = 'Format must be foo@boo.goo.'

    users['password'] = self.request.get('user_password')
    if len(users['password']) >= self.MIN_PASSWORD_LENGTH:
      error_msgs['password'] = None
    else:
      error_msgs['password'] = 'Password must be at least {0} characters ' \
                               'long.'.format(self.MIN_PASSWORD_LENGTH)

    users['password_confirmation'] = \
        self.request.get('user_password_confirmation')
    if users['password_confirmation'] == users['password']:
      error_msgs['password_confirmation'] = None
    else:
      error_msgs['password_confirmation'] = 'Passwords do not match.'

    return error_msgs

  def process_new_user_post(self, errors):
    """ Creates new user if parse was successful.

    Args:
      errors: A dict with True/False values for errors in each of the users
              fields.
    Returns:
      True if user was created, and False otherwise.
    """
    if errors['email'] or errors['password'] or errors['password_confirmation']:
      return False
    else:
      return self.helper.create_new_user(
        self.request.get('user_email'),
        self.request.get('user_password'),
        self.response)

  def post(self):
    """ Handler for POST requests. """
    err_msgs = self.parse_new_user_post()
    try:
      user_created = self.process_new_user_post(err_msgs)
      continue_url = self.request.get('continue')
      if user_created and continue_url:
        self.redirect(str(continue_url), self.response)
        return
      elif user_created:
        self.redirect(DashPage.PATH, self.response)
        return
    except AppHelperException as err:
      err_msgs['email'] = str(err)

    users = {}
    users['email'] = self.request.get('user_email')
    users['password'] = self.request.get('user_password')
    users['password_confirmation'] = \
        self.request.get('user_password_confirmation')

    self.render_page(page='users', template_file=self.TEMPLATE, values={
      'continue': self.request.get('continue'),
      'user': users,
      'error_message_content': err_msgs,
    })

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page='users', template_file=self.TEMPLATE, values={
      'continue': self.request.get('continue'),
      'user': {},
      'error_message_content': {}
    })


class LoginVerify(AppDashboard):
  """ Class to handle requests to /users/confirm and /users/verify pages.

  This page is not currently used in the default login implementation, but the
  handler remains for compatibility with other implementations.
  """

  # The template to use for confirmation page.
  TEMPLATE = 'users/confirm.html'

  def post(self):
    """ Handler for POST requests. """
    if self.request.get('continue') != '' and \
            self.request.get('commit') == 'Yes':
      self.redirect(self.request.get('continue').encode('ascii', 'ignore'),
                    self.response)
    else:
      if AppDashboardHelper.USE_SHIBBOLETH:
        self.redirect(AppDashboardHelper.SHIBBOLETH_CONNECTOR, self.response)
      else:
        self.redirect(DashPage.PATH, self.response)

  def get(self):
    """ Handler for GET requests. """
    continue_url = urllib.unquote(self.request.get('continue'))
    url_match = re.search(self.CONTINUE_URL_REGEX, continue_url)
    if url_match:
      continue_url = url_match.group(1)

    self.render_page(page='users', template_file=self.TEMPLATE, values={
      'continue': continue_url
    })


class LogoutPage(AppDashboard):
  """ Class to handle requests to the /users/logout page. """

  def get(self):
    """ Handler for GET requests. Removes the AppScale login cookie and
        redirects the user to the landing page.
    """
    self.helper.logout_user(self.response)
    continue_url = self.request.get("continue")
    if continue_url:
      self.redirect(str(continue_url), self.response)
    else:
      if AppDashboardHelper.USE_SHIBBOLETH:
        self.redirect(AppDashboardHelper.SHIBBOLETH_CONNECTOR, self.response)
      else:
        self.redirect(DashPage.PATH, self.response)


class LoginPage(AppDashboard):
  """ Class to handle requests to the /users/login page. """

  # The path for the login page.
  PATH = '/login'

  # Another path that points to the login page.
  ALIAS = '/users/login'

  # Another path that points to the login page.
  ALIAS_2 = '/users/authenticate'

  # The template to use for rendering the login page.
  TEMPLATE = 'users/login.html'

  def post(self):
    """ Handler for POST requests. """
    user_email = self.request.get('user_email').lstrip().rstrip()
    if self.helper.login_user(user_email, self.request.get('user_password'),
                              self.response):

      if self.request.get('continue') != '':
        continue_url = self.request.get('continue').encode('ascii', 'ignore')
        self.redirect(continue_url, self.response)
      else:
        self.dstore.rebuild_dash_layout_settings_dict(email=user_email)
        self.redirect('/', self.response)
    else:
      flash_message = 'Incorrect username / password combination. ' \
                      'Please try again.'
      show_create_account = True
      if AppDashboardHelper.USE_SHIBBOLETH:
        show_create_account = False
      self.render_page(page='users', template_file=self.TEMPLATE,
                       values={
                         'continue': self.request.get('continue'),
                         'user_email': user_email,
                         'flash_message': flash_message,
                         'show_create_account': show_create_account
                       })

  def get(self):
    """ Handler for GET requests. """
    show_create_account = True
    if AppDashboardHelper.USE_SHIBBOLETH:
      show_create_account = False
    self.render_page(page='users', template_file=self.TEMPLATE, values={
      'continue': self.request.get('continue'),
      'show_create_account': show_create_account
    })


class ShibbolethLoginPage(AppDashboard):
  """ Class to handle requests to the Shibboleth login page. """

  # The path for the Shibboleth login page.
  PATH = '/login'

  # Another path that points to the login page.
  ALIAS = '/users/login'

  # Another path that points to the login page.
  ALIAS_2 = '/users/authenticate'

  def get(self):
    """ Handler for GET requests. """
    logging.info("LoginPage: continue -> {0}".format(
      self.request.get('continue')))
    user_email = self.request.get('HTTP_SHIB_INETORGPERSON_MAIL').strip(). \
      lower()
    logging.info("LoginPage: user_email: {0}".format(user_email))
    if user_email:
      self.redirect("{1}/users/shibboleth?continue={0}".format(
        self.request.get('continue'),
        AppDashboardHelper.SHIBBOLETH_CONNECTOR))
      return

    target = '{0}/users/shibboleth?continue={1}'.format(
      AppDashboardHelper.SHIBBOLETH_CONNECTOR,
      self.request.get('continue'))
    self.redirect('{0}/Shibboleth.sso/Login?target={1}'.format(
      AppDashboardHelper.SHIBBOLETH_CONNECTOR,
      urllib.quote(target, safe='')))


class ShibbolethRedirect(AppDashboard):
  """ Class that handles the Shibboleth redirect. """

  # The path for the Shibboleth redirect.
  PATH = '/users/shibboleth'

  def get(self):
    """ Handler for GET requests. """
    user_email = os.environ.get('HTTP_SHIB_INETORGPERSON_MAIL').strip() \
      .lower()

    self.helper.create_token(user_email, user_email)
    user_app_list = self.helper.get_user_app_list(user_email)
    self.helper.set_appserver_cookie(user_email, user_app_list, self.response)

    if self.request.get('continue') != '':
      continue_url = self.request.get('continue').encode('ascii', 'ignore')
      self.redirect(continue_url, self.response)
    else:
      self.redirect(AppDashboardHelper.SHIBBOLETH_CONNECTOR, self.response)


class AuthorizePage(AppDashboard):
  """ Class to handle requests to the /authorize page. """

  # The template to use for the authorize page.
  TEMPLATE = 'authorize/cloud.html'

  def parse_update_user_permissions(self):
    """ Update authorization matrix from form submission.

    Returns:
      A str with message to be displayed to the user.
    """
    perms = self.helper.get_all_permission_items()
    req_keys = self.request.POST.keys()
    response = ''
    for fieldname, email in self.request.POST.iteritems():
      if re.match(self.USER_PERMISSION_REGEX, fieldname):
        for perm in perms:
          key = "{0}-{1}".format(email, perm)
          if key in req_keys and \
                  self.request.get('CURRENT-{0}'.format(key)) == 'False':
            if self.helper.add_user_permissions(email, perm):
              response += 'Enabling {0} for {1}. '.format(perm, email)
            else:
              response += 'Error enabling {0} for {1}. '.format(perm, email)
          elif key not in req_keys and \
                  self.request.get('CURRENT-{0}'.format(key)) == 'True':
            if self.helper.remove_user_permissions(email, perm):
              response += 'Disabling {0} for {1}. '.format(perm, email)
            else:
              response += 'Error disabling {0} for {1}. '.format(perm, email)
    return response

  def post(self):
    """ Handler for POST requests. """
    if self.dstore.is_user_cloud_admin():
      try:
        taskqueue.add(url='/status/refresh')
      except Exception as err:
        logging.exception(err)
      self.render_app_page(page='authorize', values={
        'flash_message': self.parse_update_user_permissions(),
        'user_perm_list': self.helper.list_all_users_permissions(),
        'page_content': self.TEMPLATE,
      })
    else:
      self.render_app_page(page='authorize', values={
        'flash_message': "Only the cloud administrator can change permissions.",
        'user_perm_list': {},
        'page_content': self.TEMPLATE,
      })

  def get(self):
    """ Handler for GET requests. """
    if self.dstore.is_user_cloud_admin():
      self.render_app_page(page='authorize', values={
        'user_perm_list': self.helper.list_all_users_permissions(),
        'page_content': self.TEMPLATE,
      })
    else:
      self.render_app_page(page='authorize', values={
        'flash_message': "Only the cloud administrator can change permissions.",
        'user_perm_list': {},
        'page_content': self.TEMPLATE,
      })


class ChangePasswordPage(AppDashboard):
  """Class to handle user password changes."""

  # The template to use for the change password page.
  TEMPLATE = 'authorize/cloud.html'

  def post(self):
    """ Handler for POST requests. """
    email = self.request.get("email")
    password = self.request.get("password")
    if self.dstore.is_user_cloud_admin():
      success, message = self.helper.change_password(email, password)
    else:
      success = False
      message = "Only the cloud administrator can change passwords."

    flash_message = None
    error_flash_message = None
    if success:
      flash_message = message
    else:
      error_flash_message = message

    self.render_app_page(page='authorize', values={
      'flash_message': flash_message,
      'error_flash_message': error_flash_message,
      'user_perm_list': self.helper.list_all_users_permissions(),
      'page_content': self.TEMPLATE,
    })

  def get(self):
    """ Handler for GET requests. """
    if self.dstore.is_user_cloud_admin():
      self.render_app_page(page='authorize', values={
        'user_perm_list': self.helper.list_all_users_permissions(),
        'page_content': self.TEMPLATE,
      })
    else:
      self.render_app_page(page='authorize', values={
        'flash_message': "Only the cloud administrator can change permissions.",
        'user_perm_list': {},
        'page_content': self.TEMPLATE,
      })


class AppUploadPage(AppDashboard):
  """ Class to handle requests to the /apps/new page. """

  # The template to use for the upload app page.
  TEMPLATE = 'apps/new.html'

  def post(self):
    """ Handler for POST requests. """
    success_msg = ''
    err_msg = ''
    if not self.request.POST.multi or \
            'app_file_data' not in self.request.POST.multi or \
            not hasattr(self.request.POST.multi['app_file_data'], 'file'):
      self.render_app_page(page='apps', values={
        'error_message': 'You must specify a file to upload.',
        'success_message': '',
        'page_content': self.TEMPLATE,
      })
      return

    if self.dstore.can_upload_apps():
      try:
        success_msg = self.helper.upload_app(
          self.request.POST.multi['app_file_data'].filename,
          self.request.POST.multi['app_file_data'].file)
      except AppHelperException as err:
        self.response.set_status(500)
        err_msg = str(err)
      if success_msg:
        try:
          taskqueue.add(url='/status/refresh')
          taskqueue.add(url='/status/refresh', countdown=self.REFRESH_WAIT_TIME)
        except Exception as err:
          logging.exception(err)
    else:
      err_msg = "You are not authorized to upload apps."
    self.render_app_page(page='apps', values={
      'error_message': err_msg,
      'success_message': success_msg,
      'page_content': self.TEMPLATE,
    })

  def get(self):
    """ Handler for GET requests. """
    self.render_app_page(page='apps', values={
      'page_content': self.TEMPLATE,
    })


class AppDeletePage(AppDashboard):
  """ Class to handle requests to the /apps/delete page. """

  # The template to use for the app deletion page.
  TEMPLATE = 'apps/delete.html'

  def post(self):
    """ Handler for POST requests. """
    appname = self.request.POST.get('appname')
    if self.dstore.is_user_cloud_admin() or \
            appname in self.dstore.get_owned_apps():
      message = self.helper.delete_app(appname)
    else:
      message = "You do not have permission to delete the application: " \
                "{0}".format(appname)

    # Get the list of project ids the user has access to.
    is_cloud_admin = self.helper.is_user_cloud_admin()
    all_versions = self.helper.get_version_info()
    if is_cloud_admin:
      apps_user_owns = list({version.split('_')[0]
                             for version in all_versions})
    else:
      apps_user_owns = self.helper.get_owned_apps()
    self.render_app_page(page='apps', values={
      'flash_message': message,
      'page_content': self.TEMPLATE,
      'apps_user_owns': apps_user_owns,
    })

  def get(self):
    """ Handler for GET requests. """
    # Recover the list of project ids the user can delete.
    is_cloud_admin = self.helper.is_user_cloud_admin()
    all_versions = self.helper.get_version_info()
    if is_cloud_admin:
      apps_user_owns = list({version.split('_')[0]
                             for version in all_versions})
    else:
      apps_user_owns = self.helper.get_owned_apps()

    self.render_app_page(page='apps', values={
      'page_content': self.TEMPLATE,
      'apps_user_owns': apps_user_owns,
    })


class AppRelocatePage(AppDashboard):
  """ Class to handle requests to the /apps/new page. """

  # The template to use for the upload app page.
  TEMPLATE = 'apps/relocate.html'

  def post(self):
    """ Handler for POST requests. """
    success_msg = ''
    err_msg = ''
    if not self.request.POST.multi or \
            'app_id' not in self.request.POST.multi:
      self.render_app_page(page='apps', values={
        'error_message': 'You must specify an app to relocate.',
        'success_message': '',
        'page_content': self.TEMPLATE,
      })
      return

    app_id = self.request.POST.get('app_id')
    version_key = '_'.join([app_id, AppDashboardHelper.DEFAULT_SERVICE,
                            AppDashboardHelper.DEFAULT_VERSION])
    if self.dstore.is_user_cloud_admin() or \
            app_id in self.dstore.get_owned_apps():
      try:
        success_msg = self.helper.relocate_version(
          version_key,
          self.request.POST.multi['http_port'],
          self.request.POST.multi['https_port'])
      except AppHelperException as err:
        self.response.set_status(500)
        err_msg = str(err)
      if success_msg:
        try:
          taskqueue.add(url='/status/refresh')
          taskqueue.add(url='/status/refresh', countdown=self.REFRESH_WAIT_TIME)
        except Exception as err:
          logging.exception(err)
    else:
      err_msg = "You are not authorized to relocate that application."

    self.render_app_page(page='apps', values={
      'error_message': err_msg,
      'success_message': success_msg,
      'page_content': self.TEMPLATE,
    })

  def get(self):
    """ Handler for GET requests. """
    self.render_app_page(page='apps', values={
      'page_content': self.TEMPLATE,
    })


class AppsAsJSONPage(webapp2.RequestHandler):
  """ A class that exposes application-level info used on the Cloud Status page,
  but via JSON instead of raw HTML. """

  def get(self):
    """ Retrieves the cached information about applications running in this
    AppScale deployment as a JSON-encoded dict. """
    is_cloud_admin = AppDashboardHelper().is_user_cloud_admin()
    all_versions = AppDashboardHelper().get_version_info()

    if is_cloud_admin:
      apps_user_owns = {version.split('_')[0] for version in all_versions}
    else:
      apps_user_owns = AppDashboardHelper().get_owned_apps()

    versions_user_is_admin_on = {
      version: all_versions[version] for version in all_versions
      if version.split('_')[0] in apps_user_owns}

    self.response.out.write(json.dumps(versions_user_is_admin_on))


class LogMainPage(AppDashboard):
  """ Class to handle requests to the /logs page. """

  # The template to use for the logs page.
  TEMPLATE = 'logs/main.html'

  def get(self):
    """ Handler for GET requests. """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_owned_apps()
    if (not is_cloud_admin) and (not apps_user_is_admin_on):
      self.redirect(DashPage.PATH, self.response)
      return

    query = ndb.gql('SELECT * FROM LoggedService')
    all_services = []
    for entity in query:
      if entity.key.id() not in all_services:
        all_services.append(entity.key.id())

    permitted_services = []
    for service in all_services:
      if is_cloud_admin or service in apps_user_is_admin_on:
        permitted_services.append(service)

    self.render_app_page(page='logs', values={
      'services': permitted_services,
      'page_content': self.TEMPLATE,
    })


class LogServicePage(AppDashboard):
  """ Class to handle requests to the /logs/service_name page. """

  # The template to use for the logs service page.
  TEMPLATE = 'logs/service.html'

  def get(self, service_name):
    """ Displays a list of hosts that have logs for the given service. """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_owned_apps()
    if (not is_cloud_admin) and (service_name not in apps_user_is_admin_on):
      self.redirect(DashPage.PATH, self.response)
      return

    service = LoggedService.get_by_id(service_name)
    if service:
      exists = True
      hosts = service.hosts
    else:
      exists = False
      hosts = []

    self.render_app_page(page='logs', values={
      'exists': exists,
      'service_name': service_name,
      'hosts': hosts
    })


class LogServiceHostPage(AppDashboard):
  """ Class to handle requests to the /logs/service_name/host page. """

  # The template to use for the logs viewer for the instance.
  TEMPLATE = 'logs/viewer.html'

  # The number of logs we should present on each page.
  LOGS_PER_PAGE = 10

  def get(self, service_name, host):
    """ Displays all logs accumulated for the given service, on the named host.

    Specifying 'all' as the host indicates that we shouldn't restrict ourselves
    to a single machine.
    """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_owned_apps()
    if (not is_cloud_admin) and (service_name not in apps_user_is_admin_on):
      self.redirect(DashPage.PATH, self.response)
      return

    encoded_cursor = self.request.get('next_cursor')
    if encoded_cursor and encoded_cursor != "None":
      start_cursor = Cursor(urlsafe=encoded_cursor)
    else:
      start_cursor = None

    if host == "all":
      query, next_cursor, is_more = RequestLogLine.query(
        RequestLogLine.service_name == service_name).fetch_page(
        self.LOGS_PER_PAGE, produce_cursors=True, start_cursor=start_cursor)
    else:
      query, next_cursor, is_more = RequestLogLine.query(
        RequestLogLine.service_name == service_name,
        RequestLogLine.host == host).fetch_page(self.LOGS_PER_PAGE,
                                                produce_cursors=True,
                                                start_cursor=start_cursor)

    if next_cursor:
      cursor_value = next_cursor.urlsafe()
    else:
      cursor_value = None

    self.render_app_page(page='logs', values={
      'service_name': service_name,
      'host': host,
      'query': query,
      'next_cursor': cursor_value,
      'is_more': is_more,
      'page_content': self.TEMPLATE,
    })


class LogDownloader(AppDashboard):
  """ Exposes a single GET route that cloud administrators can access to
  download AppScale-generated logs.
  """

  # The location where the template file can be found that waits for logs
  # to become available before redirecting to it.
  TEMPLATE = "logs/download.html"

  def get(self):
    """ Instructs the AppController to collect logs across all machines, place
    it in this app's static file directory, and renders a page that will wait
    for the logs to become available before downloading it.
    """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    if not is_cloud_admin:
      self.redirect(DashPage.PATH)
      return

    success, uuid = self.helper.gather_logs()
    self.render_app_page(page='logs', values={
      'success': success,
      'uuid': uuid,
      'page_content': self.TEMPLATE,
    })


class CronConsolePage(AppDashboard):
  TEMPLATE = "cron/console.html"

  def get(self):
    """ Shows deployed user applications that contain cron.yaml
    """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    all_versions = self.helper.get_version_info()

    if is_cloud_admin:
      apps_user_is_admin_on = {version.split('_')[0]
                               for version in all_versions}
    else:
      apps_user_is_admin_on = self.helper.get_owned_apps()

    apps_with_cron_yaml = []
    for app_id in apps_user_is_admin_on:
      cron_info = self.helper.get_application_cron_info(app_id)
      if cron_info.get("etc_crond_file", {}):
        apps_with_cron_yaml.append(app_id)

    self.render_app_page(page='cron', values={
      'apps_with_cron_yaml': apps_with_cron_yaml,
      'page_content': self.TEMPLATE
    })


class CronViewPage(AppDashboard):
  TEMPLATE = "cron/viewer.html"

  def get(self):
    """ Shows active cron entries for given appid
    """
    app_id = self.request.get("appid")
    mail_to = []
    cron_jobs = []
    warnings = []
    cron_info = self.helper.get_application_cron_info(app_id)

    yaml_file = cron_info.get("cron_yaml_file", [])
    etc_crond_file = cron_info.get("etc_crond_file", "")
    try:
      crond_file = crontab.CronTab(tab=etc_crond_file, user=False)
    except IOError as ioe:
      logging.error(ioe)
    else:
      crond_records = defaultdict(list)
      yaml_records = {}
      for yaml_entry in yaml_file["cron"]:
        url = yaml_entry["url"]
        yaml_records[url] = yaml_entry
        for crond_entry in crond_file:
          if url in crond_entry.command:
            crond_records[url].append(crond_entry)
            logging.info(crond_entry)

      if len(yaml_records) != len(crond_records):
        warnings.append(
          "One of the cron jobs from cron.yaml is missing in crond file for appid {0}."
          "Look at controller logs for more information at /var/log/appscale/".format(app_id)
        )
        logging.warning(warnings)

      for url, entries in crond_records.iteritems():
        yaml_record = yaml_records.get(url, {})
        query_params = {"url": url, "appid": app_id}
        url_command = "/cron/run?" + urllib.urlencode(query_params)
        cron_jobs.append(
          {"url": url,
           "frequency": yaml_record.get("schedule", ""),
           "frequency_cron_format": "\n".join(str(entry.slices) for entry in entries),
           "description": yaml_record.get("description", ""),
           "url_command": url_command})
      logging.info(cron_jobs)

      self.render_app_page(page='cron', values={
        'mail_to': mail_to,
        'cron_jobs': cron_jobs,
        'warnings': warnings,
        'page_content': self.TEMPLATE
      })


class CronRun(AppDashboard):
  def get(self):
    """ Runs specific cron job according to url param and
    redirects user back to previous page.
    """
    api_url = urllib.unquote(self.request.get("url"))
    app_id = urllib.unquote(self.request.get("appid"))
    if not api_url or not app_id:
      return

    version_id = '_'.join([app_id, AppDashboardHelper.DEFAULT_SERVICE,
                           AppDashboardHelper.DEFAULT_VERSION])
    app_url = self.helper.get_version_info()[version_id][1]
    response = urllib.urlopen(app_url + api_url)
    self.redirect("/cron/view?" + urllib.urlencode({"appid": app_id}), response)


class AppConsolePage(AppDashboard):
  # The template to use for the app console page.
  TEMPLATE = "apps/console.html"

  def get(self):
    self.render_app_page(page='console', values={
      'page_content': self.TEMPLATE,
    })


class DatastoreStats(AppDashboard):
  """ Class that returns datastore statistics in JSON such as the number of
  a certain entity kind and the amount of total bytes.
  """
  # The most number of data points we pass back to render in the dashboard.
  MAX_KIND_STATS = 1000

  # The most number of days we look back to get kind statistics.
  MAX_DAYS_BACK = 30

  def get(self):
    """ Handler for GET request for the datastore statistics.

    Returns:
      The JSON output for testing.
    """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_owned_apps()
    app_name = self.request.get("appid")
    if (not is_cloud_admin) and (app_name not in apps_user_is_admin_on):
      response = json.dumps({"error": True, "message": "Not authorized"})
      self.response.out.write(response)
      return

    query = KindStat.all(_app=app_name)
    time_stamp = datetime.datetime.now() - datetime.timedelta(
      days=self.MAX_DAYS_BACK)
    query.filter("timestamp >", time_stamp)
    items = query.fetch(self.MAX_KIND_STATS)

    response = self.convert_to_json(items)
    self.response.out.write(response)
    return

  def convert_to_json(self, kind_entities):
    """ Converts KindStat entities to a json string.

    Args:
      kind_entities: A list of stats.KindStat.
    Returns:
      A JSON string containing kind statistic information.
    """
    items = []
    for ent in kind_entities:
      items.append({time.mktime(ent.timestamp.timetuple()):
                    {ent.kind_name: {'bytes': ent.bytes,
                                     "count": ent.count}}})
    return json.dumps(items)


class RequestsStats(AppDashboard):
  """ Class that returns request statistics in JSON relating to the number
  of requests an application gets per second.
  """

  def get(self):
    """ Handler for GET request for the requests statistics. """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_owned_apps()
    app_name = self.request.get("appid")
    if (not is_cloud_admin) and (app_name not in apps_user_is_admin_on):
      response = json.dumps({"error": True, "message": "Not authorized"})
      self.response.out.write(response)
      return

    appid = self.request.get("appid")
    self.response.out.write(json.dumps(RequestsStats.fetch_request_info(appid)))

  @staticmethod
  def fetch_request_info(app_id):
    """ Fetches request per second information from the datastore for
    a given application.

    Args:
      app_id: A str, the application identifier.
    Returns:
      A list of dictionaries filled with timestamps and number of
      requests per second.
    """
    query = RequestInfo.query(RequestInfo.app_id == app_id)
    request_info = []
    for request in query.iter():
      request_info.append({
        'timestamp': int(request.timestamp.strftime('%s')),
        'num_of_requests': request.num_of_requests,
        'avg_request_rate': request.avg_request_rate
      })
    return request_info


class RequestRefreshPage(AppDashboard):
  """ Class that stores request statistics about every application in the
  datastore relating to the number of requests an application gets per second.
  """

  def get(self):
    """ Handler for GET request for the requests statistics. """
    for version_key in self.helper.get_version_info():
      self.dstore.update_request_info(version_key)

    self.response.out.write('request info updated')


class InstanceStats(AppDashboard):
  """ Class that returns instance statistics in JSON relating to the number
  of AppServer processes running for a particular App Engine application.
  """

  def get(self):
    """ Makes sure the user is allowed to see instance data for the named
    application, and if so, retrieves it for them. """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_owned_apps()
    app_name = self.request.get("appid")
    if (not is_cloud_admin) and (app_name not in apps_user_is_admin_on):
      response = json.dumps({"error": True, "message": "Not authorized"})
      self.response.out.write(response)
      return

    instance_info = self.helper.get_instance_info(app_id=app_name)
    self.response.out.write(json.dumps(instance_info))


class MemcacheStats(AppDashboard):
  """ Class that returns global memcache statistics. """

  def get(self):
    """ Handler for GET request for the memcache statistics. """
    if not self.helper.is_user_cloud_admin():
      response = json.dumps({"error": True, "message": "Not authorized"})
      self.response.out.write(response)
      return

    mem_stats = memcache.get_stats()
    self.response.out.write(json.dumps(mem_stats))


class StatsPage(AppDashboard):
  """ Class to handle requests to the /apps/stats page. """

  # The template to use for the stats page.
  TEMPLATE = 'apps/stats.html'

  def get(self):
    # Only let the cloud admin and users who own this app see this page.
    app_id = self.request.get('appid')
    is_cloud_admin = self.helper.is_user_cloud_admin()
    all_versions = self.helper.get_version_info()

    if is_cloud_admin:
      apps_user_is_admin_on = list({version.split('_')[0]
                                    for version in all_versions})
    else:
      apps_user_is_admin_on = self.helper.get_owned_apps()

    if not apps_user_is_admin_on:
      self.redirect(DashPage.PATH, self.response)
      return

    if app_id not in apps_user_is_admin_on:
      self.redirect(DashPage.PATH, self.response)
      return

    self.render_app_page(page='stats', values={
      'appid': app_id,
      'all_apps_this_user_owns': apps_user_is_admin_on,
      'page_content': self.TEMPLATE,
    })


class RunGroomer(AppDashboard):
  """ Class that dynamically updates Kind statistics in the Datastore. """

  def get(self):
    """ Calls the groomer and tells it that Kind statistics need to be
    updated. """
    self.response.out.write(json.dumps({
      'result': self.helper.run_groomer()
    }))


class AjaxRenderPanel(AppDashboard):
  """ Class that adds panels to the dashboard. """

  def get(self):
    """ Calls render_template to return the correct panel """
    key_val = self.request.get('key_val')
    self.response.out.write(self.render_template(
      template_file='layouts/panel.html',
      values={'page_info': self.dstore.get_panel_key_info(key_val),
              'id': key_val}))


class AjaxSaveLayoutSettings(AppDashboard):
  """ Class that stores dashboard layout settings in the Datastore. """

  def post(self):
    """ sets the dashboard layout settings """

    nav = self.request.get("nav")
    panel = self.request.get("panel")
    saved_dict = {"nav": json.loads(nav), "panel": json.loads(panel)}
    try:
      self.dstore.set_dash_layout_settings(values=saved_dict)
      self.response.set_status(200)
      self.response.out.write("Saved")
    except Exception as err:
      logging.exception(err)
      self.response.set_status(500)
      self.response.out.write("Try Again")


class AjaxResetLayoutSettings(AppDashboard):
  """ Class that stores dashboard layout settings in the Datastore. """

  def post(self):
    """ sets the dashboard layout settings """
    try:
      self.dstore.set_dash_layout_settings()
      self.response.set_status(200)
      self.response.out.write("Layout Reset")
    except Exception as err:
      logging.exception(err)
      self.response.set_status(500)
      self.response.out.write("Try Again")


# Main Dispatcher
dashboard_pages = [
  (DashPage.PATH, DashPage),
  (DashPage.ALIAS, DashPage),
  ('/status/refresh', DashRefreshPage),
  ('/status/cloud', StatusPage),
  ('/status/json', StatusAsJSONPage),
  ('/status/requests', RequestRefreshPage),
  ('/logout', LogoutPage),
  ('/users/logout', LogoutPage),
  ('/users/verify', LoginVerify),
  ('/users/confirm', LoginVerify),
  ('/authorize', AuthorizePage),
  ('/apps/?', AppConsolePage),
  ('/apps/stats/datastore', DatastoreStats),
  ('/apps/stats/requests', RequestsStats),
  ('/apps/stats/instances', InstanceStats),
  ('/apps/stats/memcache', MemcacheStats),
  ('/apps/new', AppUploadPage),
  ('/apps/upload', AppUploadPage),
  ('/apps/relocate', AppRelocatePage),
  ('/apps/delete', AppDeletePage),
  ('/apps/json/?', AppsAsJSONPage),
  ('/apps/json/(.+)', AppsAsJSONPage),
  ('/apps/stats', StatsPage),
  ('/service_accounts', ServiceAccountsProjectSelector),
  ('/service_accounts/(.+)', ProjectServiceAccounts),
  ('/logs', LogMainPage),
  ('/logs/(.+)/(.+)', LogServiceHostPage),
  ('/logs/(.+)', LogServicePage),
  ('/cron', CronConsolePage),
  ('/cron/view', CronViewPage),
  ('/cron/run', CronRun),
  ('/gather-logs', LogDownloader),
  ('/groomer', RunGroomer),
  ('/change-password', ChangePasswordPage),
  ('/datastore_viewer', DatastoreViewerSelector),
  ('/datastore_viewer/(.+)/edit/(.*)', DatastoreEditRequestHandler),
  ('/datastore_viewer/(.+)/edit', DatastoreEditRequestHandler),
  ('/datastore_viewer/(.+)', DatastoreViewer),
  ('/pull_queue_viewer', PQProjectSelector),
  ('/pull_queue_viewer/(.+)/(.+)', PQTaskSelector),
  ('/pull_queue_viewer/(.+)', PQQueueSelector),
  ('/ajax/panel/render', AjaxRenderPanel),
  ('/ajax/layout/save', AjaxSaveLayoutSettings),
  ('/ajax/layout/reset', AjaxResetLayoutSettings)
]

if AppDashboardHelper.USE_SHIBBOLETH:
  dashboard_pages.extend([
    (ShibbolethLoginPage.PATH, ShibbolethLoginPage),
    (ShibbolethLoginPage.ALIAS, ShibbolethLoginPage),
    (ShibbolethLoginPage.ALIAS_2, ShibbolethLoginPage),
    (ShibbolethRedirect.PATH, ShibbolethRedirect)
  ])
else:
  dashboard_pages.extend([
    (LoginPage.PATH, LoginPage),
    (LoginPage.ALIAS, LoginPage),
    (LoginPage.ALIAS_2, LoginPage),
    ('/users/new', NewUserPage),
    ('/users/create', NewUserPage)
  ])

app = webapp2.WSGIApplication(dashboard_pages, debug=True)


def handle_404(_, response, exception):
  """ Handles 404, page not found exceptions. """
  logging.exception(exception)
  response.set_status(404)
  response.write(jinja_environment.get_template('404.html').render())


def handle_500(_, response, exception):
  """ Handles 500, error processing page exceptions. """
  logging.exception(exception)
  response.set_status(500)
  response.write(jinja_environment.get_template('500.html').render())


app.error_handlers[404] = handle_404
app.error_handlers[500] = handle_500
