"""
AppScale AppDashboard, a Python 2.7 webapp for interacting with AppScale.
"""
# pylint: disable-msg=F0401
# pylint: disable-msg=C0103
# pylint: disable-msg=E1101
# pylint: disable-msg=W0613

import cgi
import datetime
import jinja2
import logging
import os
import re
import sys
import traceback
import urllib
import webapp2

try:
  import json
except ImportError:
  import simplejson as json

from google.appengine.api import taskqueue
from google.appengine.ext import ndb
from google.appengine.datastore.datastore_query import Cursor

sys.path.append(os.path.dirname(__file__) + '/lib')
from app_dashboard_helper import AppDashboardHelper
from app_dashboard_helper import AppHelperException
from app_dashboard_data import AppDashboardData

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + \
      os.sep + 'templates'))


class LoggedService(ndb.Model):
  hosts = ndb.StringProperty(repeated=True)

class AppLogLine(ndb.Model):
  message = ndb.TextProperty()
  level = ndb.IntegerProperty()
  timestamp = ndb.DateTimeProperty()

class RequestLogLine(ndb.Model):
  service_name = ndb.StringProperty()
  host = ndb.StringProperty()
  app_logs = ndb.StructuredProperty(AppLogLine, repeated=True)


class AppDashboard(webapp2.RequestHandler):
  """ Class that all pages in the Dashboard must inherit from. """

  # Regular expression to capture the continue url.
  CONTINUE_URL_REGEX = 'continue=(.*)$'

  # Regular expression for updating user permissions.
  USER_PERMISSION_REGEX = '^user_permission_'

  # Regular expression that matches email addresses.
  USER_EMAIL_REGEX = '^\w[^@\s]*@[^@\s]{2,}$'

  # Number of seconds taskqueue works waits to refresh page.
  REFRESH_WAIT_TIME = 30

  def __init__(self, request, response):
    """ Constructor.
    
    Args:
      request: The webapp2.Request object, contains the information about
        the web request. 
      response: The webapp2.Response object, for building a respose to be
        sent back to the browser.
    """
    self.initialize(request, response)
    self.helper = AppDashboardHelper()
    self.dstore = AppDashboardData(self.helper)

  def render_template(self, template_file, values=None):
    """ Renders a template file with all variables loaded.

    Args: 
      template_file: A str with the relative path to template file.
      values: A dict with key/value pairs used as variables in the jinja
        template files.
    Returns:
      A str with the rendered template.
    """
    if values is None:
      values = {}
    template = jinja_environment.get_template(template_file)
    sub_vars = {
      'logged_in' : self.helper.is_user_logged_in(),
      'user_email' : self.helper.get_user_email(),
      'is_user_cloud_admin' : self.dstore.is_user_cloud_admin(),
      'i_can_upload' : self.dstore.i_can_upload(),
      'apps_user_is_admin_on' : self.dstore.get_user_app_list()
    }
    for key in values.keys():
      sub_vars[key] = values[key]
    return template.render(sub_vars)
    
  def get_shared_navigation(self):
    """ Renders the shared navigation.

    Returns:
      A str with the navigation bar rendered.
    """
    return self.render_template(template_file='shared/navigation.html')

  def render_page(self, page, template_file, values=None ):
    """ Renders a template with the main layout and nav bar. """
    if values is None:
      values = {}
    self.response.headers['Content-Type'] = 'text/html'
    template = jinja_environment.get_template('layouts/main.html')
    self.response.out.write(template.render(
        page_name=page,
        page_body=self.render_template(template_file, values),
        shared_navigation=self.get_shared_navigation()
        ))
    

class IndexPage(AppDashboard):
  """ Class to handle requests to the / page. """

  TEMPLATE = 'landing/index.html'

  def get(self):
    """ Handler for GET requests. Reads the template file and returns the
        jinja rendered HTML of the landing page to the requestor."""
    self.render_page(page='landing', template_file=self.TEMPLATE, values={
      'monitoring_url' : self.dstore.get_monitoring_url(),
    })


class StatusRefreshPage(AppDashboard):
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

  TEMPLATE = 'status/cloud.html'

  def get(self):
    """ Handler for GET requests. Reads the template file and returns the
        jinja rendered HTML of the status page to the requestor.  This page has
        information on the API status, Database status, Name and status of
        each app, and the status of each server in this AppScale deployment.
     """
    # Called from the web.  Refresh data then display page (may be slow).
    if self.request.get('forcerefresh'):
      self.dstore.update_all()

    self.render_page(page='status', template_file=self.TEMPLATE, values={
      'server_info' : self.dstore.get_status_info(),
      'dbinfo' : self.dstore.get_database_info(),
      'service_info' : self.dstore.get_apistatus(),
      'apps' : self.dstore.get_application_info(),
      'monitoring_url' : self.dstore.get_monitoring_url(),
    })


class NewUserPage(AppDashboard):
  """ Class to handle requests to the /users/new and /users/create page. """

  TEMPLATE = 'users/new.html'

  def parse_new_user_post(self):
    """ Parse the input from the create user form.

    Returns:
      A dict with specific error messages for each 
    """
    users = {}
    error_msgs = {}
    users['email'] = cgi.escape(self.request.get('user_email'))
    if re.match(self.USER_EMAIL_REGEX, users['email']):
      error_msgs['email'] = None
    else:
      error_msgs['email'] = 'Format must be foo@boo.goo.' 

    users['password'] = cgi.escape(self.request.get('user_password'))
    if len(users['password']) >= 6:
      error_msgs['password'] = None
    else:
      error_msgs['password'] = 'Password must be at least 6 characters long.'

    users['password_confirmation'] = cgi.escape(
      self.request.get('user_password_confirmation'))
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
      return self.helper.create_new_user(cgi.escape(
           self.request.get('user_email')), cgi.escape(
           self.request.get('user_password')), self.response)

  def post(self):
    """ Handler for POST requests. If the user creation was successful, the 
        requestor is redirected to the landing page.  If the user creation was
        unsuccessful, it reads the template file and returns the jinja rendered
        HTML of the create user page to the requestor with error messages."""
    err_msgs = self.parse_new_user_post()
    try:
      if self.process_new_user_post(err_msgs):
        self.redirect('/', self.response)
        return
    except AppHelperException as err:
      err_msgs['email'] = str(err)
   
    users = {}
    users['email'] = cgi.escape(self.request.get('user_email'))
    users['password'] = cgi.escape(self.request.get('user_password'))
    users['password_confirmation'] = cgi.escape(
      self.request.get('user_password_confirmation'))

    self.render_page(page='users', template_file=self.TEMPLATE, values={
        'user' : users,
        'error_message_content' : err_msgs,
        })

  def get(self):
    """ Handler for GET requests. Reads the template file and returns the
        jinja rendered HTML of the create user page to the requestor.  Web users
        can use this page to create a user in the AppScale deployment."""
    self.render_page(page='users', template_file=self.TEMPLATE, values={
      #'display_error_messages' : {},
      'user' : {},
      'error_message_content' : {}
    })

class LoginVerify(AppDashboard):
  """ Class to handle requests to /users/confirm and /users/verify pages. """

  TEMPLATE = 'users/confirm.html'
  
  def post(self):
    """ Handler for POST requests. If the user clicks the 'Yes' button, they
        are redirected to the continue url location.  If they click 'No', they
        are redirected to the landing page.
    """
    if self.request.get('continue') != '' and\
       self.request.get('commit') == 'Yes':
      self.redirect(self.request.get('continue').encode('ascii','ignore'), 
        self.response)
    else:
      self.redirect('/', self.response)

  def get(self):
    """ Handler for GET requests. Reads the template file and returns the
        jinja rendered HTML of the continue url page to the requestor.
    """
    continue_url = urllib.unquote(self.request.get('continue'))
    url_match = re.search(self.CONTINUE_URL_REGEX, continue_url)
    if url_match:
      continue_url = url_match.group(1)

    self.render_page(page='users', template_file=self.TEMPLATE, values={
      'continue' : continue_url
    })


class LogoutPage(AppDashboard):
  """ Class to handle requests to the /users/logout page. """

  def get(self):
    """ Handler for GET requests. Removes the AppScale login cookie and
        redirects the user to the landing page.
    """
    self.helper.logout_user(self.response)
    self.redirect('/', self.response)


class LoginPage(AppDashboard):
  """ Class to handle requests to the /users/login page. """

  TEMPLATE = 'users/login.html'

  def post(self):
    """ Handler for post requests. If the correct email address and password
        combination is given, the AppScale login cookie is set and the user is
        redirected to the landing page, or to the continue url page if the 
        continue url is given.  If the wrong email address and password
        combination is given, the it reads the template file and returns the
        jinja rendered HTML of the login page to the requestor with error 
        messages.
    """
    if self.helper.login_user(self.request.get('user_email'),
       self.request.get('user_password'), self.response):
    
      if self.request.get('continue') != '':
        self.redirect('/users/confirm?continue={0}'.format(
          urllib.quote(str(self.request.get('continue')))\
          .encode('ascii','ignore')), self.response)
      else:
        self.redirect('/', self.response)
    else:
      self.render_page(page='users', template_file=self.TEMPLATE, values={
          'continue' : self.request.get('continue'),
          'user_email' : self.request.get('user_email'),
          'flash_message': 
          "Incorrect username / password combination. Please try again."
        })

  def get(self):
    """ Handler for GET requests. Reads the template file and returns the
        jinja rendered HTML of the login page to the requestor.
    """
    self.render_page(page='users', template_file=self.TEMPLATE, values={
      'continue' : self.request.get('continue')
    })


class AuthorizePage(AppDashboard):
  """ Class to handle requests to the /authorize page. """

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
          if email + '-' + perm in req_keys and \
            self.request.get('CURRENT-' + email + '-' + perm) == 'False':
            if self.helper.add_user_permissions(email, perm):
              response += 'Enabling {0} for {1}. '.format(perm, email)
            else:
              response += 'Error enabling {0} for {1}. '.format(perm, email)
          elif email+'-'+perm not in req_keys and \
            self.request.get('CURRENT-' + email + '-' + perm) == 'True':
            if self.helper.remove_user_permissions(email, perm):
              response += 'Disabling {0} for {1}. '.format(perm, email)
            else:
              response += 'Error disabling {0} for {1}. '.format(perm, email)
    return response

  def post(self):
    """ Handler for POST requests. Calls parse_update_user_permissions() to 
        update the user permissions in the AppScale deployment, and launches a
        taskqueue task to update the datastore with the new values 
        asynchronously.  Then reads the template file and returns the jinja 
        rendered HTML of the authorize page to the requestor with either success
        or error messages."""
    if self.dstore.is_user_cloud_admin():
      try:
        logging.info("taskqueue.add(url='/status/refresh')")
        taskqueue.add(url='/status/refresh')
      except Exception as err:
        logging.exception(err)
      self.render_page(page='authorize', template_file=self.TEMPLATE, values={
        'flash_message' : self.parse_update_user_permissions(),
        'user_perm_list' : self.helper.list_all_users_permissions(),
        })
    else:
      self.render_page(page='authorize', template_file=self.TEMPLATE, values={
        'flash_message':"Only the cloud administrator can change permissions.",
        'user_perm_list':{},
        })

  def get(self):
    """ Handler for GET requests. Reads the template file and returns the
        jinja rendered HTML of the authorize page to the requestor."""
    if self.dstore.is_user_cloud_admin():
      self.render_page(page='authorize', template_file=self.TEMPLATE, values={
        'user_perm_list' : self.helper.list_all_users_permissions(),
      })
    else:
      self.render_page(page='authorize', template_file=self.TEMPLATE, values={
        'flash_message':"Only the cloud administrator can change permissions.",
        'user_perm_list':{},
        })


class AppUploadPage(AppDashboard):
  """ Class to handle requests to the /apps/new page. """

  TEMPLATE = 'apps/new.html'

  def post(self):
    """ Handler for POST requests.

    Receives the app upload request, saves the file in a temporary location, and
    transfers it to the AppScale deployment. Then it reads the template file and
    returns the jinja rendered HTML of the app upload page to the requestor with
    success or error messages."""
    success_msg = ''
    err_msg = ''
    if self.dstore.i_can_upload():
      try: 
        success_msg = self.helper.upload_app(
          self.request.POST.multi['app_file_data'].file
          )
      except AppHelperException as err:
        err_msg = str(err)
      if success_msg:
        try:
          logging.info("taskqueue.add(url='/status/refresh')")
          taskqueue.add(url='/status/refresh')
          logging.info("taskqueue.add(url='/status/refresh', countdown={0})"\
            .format(self.REFRESH_WAIT_TIME))
          taskqueue.add(url='/status/refresh', countdown=self.REFRESH_WAIT_TIME)
        except Exception as err:
          logging.exception(err)
    else:
      err_msg = "You are not authorized to upload apps."
    self.render_page(page='apps', template_file=self.TEMPLATE, values={
        'error_message' : err_msg,
        'success_message' : success_msg
      })

  def get(self):
    """ Handler for GET requests. Reads the template file and returns the jinja 
        rendered HTML of the of the app upload page to the requestor"""
    self.render_page(page='apps', template_file=self.TEMPLATE)

class AppDeletePage(AppDashboard):
  """ Class to handle requests to the /apps/delete page. """

  TEMPLATE = 'apps/delete.html'

  def get_app_list(self):
    """ Returns a list of apps that the currently logged-in user is an admin of.

    Returns:
      A dict that maps the names of the applications the user is an admin on to
      the URL that the app is hosted at.
    """
    if self.dstore.is_user_cloud_admin():
      return self.dstore.get_application_info()
    else:
      ret_list = {}
      app_list = self.dstore.get_application_info()
      my_apps = self.dstore.get_user_app_list()
      for app in app_list.keys():
        if app in my_apps:
          ret_list[app] = app_list[app]
      return ret_list

  def post(self):
    """ Handler for POST requests. Receives the delete app request and instructs
        the AppScale deployment to stop serving the app.  Then it launches two
        taskqueue tasks to refresh the datastore and reads the template file and
        returns the jinja rendered HTML of the app delete page to the requestor.
     """
    appname = self.request.POST.get('appname')
    if self.dstore.is_user_cloud_admin() or \
       appname in self.dstore.get_user_app_list():
      message = self.helper.delete_app(appname)
      self.dstore.delete_app_from_datastore(appname)
      try:
        logging.info("taskqueue.add(url='/status/refresh')")
        taskqueue.add(url='/status/refresh')
        logging.info("taskqueue.add(url='/status/refresh', countdown={0})"\
          .format(self.REFRESH_WAIT_TIME))
        taskqueue.add(url='/status/refresh', countdown=self.REFRESH_WAIT_TIME)
      except Exception as err:
        logging.exception(err)
    else:
      message = "You do not have permission to delete the application: " + \
        appname
    self.render_page(page='apps', template_file=self.TEMPLATE, values={
      'flash_message' : message,
      'apps' : self.get_app_list(),
      })

  def get(self):
    """ Handler for GET requests. Reads the template file and returns the
        jinja rendered HTML of the app delete page to the requestor."""
    self.render_page(page='apps', template_file=self.TEMPLATE, values={
      'apps' : self.get_app_list(),
    })


class LogMainPage(AppDashboard):
  """ Class to handle requests to the /logs page. """

  TEMPLATE = 'logs/main.html'

  def get(self):
    """ Handler for GET requests. """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_user_app_list()
    if (not is_cloud_admin) and (not apps_user_is_admin_on):
      self.redirect('/', self.response)

    query = ndb.gql('SELECT * FROM LoggedService')
    all_services = []
    for entity in query:
      if entity.key.id() not in all_services:
        all_services.append(entity.key.id())

    permitted_services = []
    for service in all_services:
      if is_cloud_admin or service in apps_user_is_admin_on:
        permitted_services.append(service)

    self.render_page(page='logs', template_file=self.TEMPLATE, values = {
      'services' : permitted_services
    })

class LogServicePage(AppDashboard):
  """ Class to handle requests to the /logs/service_name page. """

  TEMPLATE = 'logs/service.html'

  def get(self, service_name):
    """ Displays a list of hosts that have logs for the given service. """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_user_app_list()
    if (not is_cloud_admin) and (service_name not in apps_user_is_admin_on):
      self.redirect('/', self.response)

    service = LoggedService.get_by_id(service_name)
    if service:
      exists = True
      hosts = service.hosts
    else:
      exists = False
      hosts = []

    self.render_page(page='logs', template_file=self.TEMPLATE, values = {
      'exists' : exists,
      'service_name' : service_name,
      'hosts' : hosts
    })

class LogServiceHostPage(AppDashboard):
  """ Class to handle requests to the /logs/service_name/host page. """

  TEMPLATE = 'logs/viewer.html'

  def get(self, service_name, host):
    """ Displays all logs accumulated for the given service, on the named host.

    Specifying 'all' as the host indicates that we shouldn't restrict ourselves
    to a single machine.
    """
    is_cloud_admin = self.helper.is_user_cloud_admin()
    apps_user_is_admin_on = self.helper.get_user_app_list()
    if (not is_cloud_admin) and (service_name not in apps_user_is_admin_on):
      self.redirect('/', self.response)

    encoded_cursor = self.request.get('next_cursor')
    if encoded_cursor:
      start_cursor = Cursor(urlsafe=encoded_cursor)
    else:
      start_cursor = None

    if host == "all":
      query, next_cursor, is_more = RequestLogLine.query(
        RequestLogLine.service_name == service_name).fetch_page(20, produce_cursors=True,
        start_cursor=start_cursor)
    else:
      query, next_cursor, is_more = RequestLogLine.query(
        RequestLogLine.service_name == service_name,
        RequestLogLine.host == host).fetch_page(20, produce_cursors=True,
        start_cursor=start_cursor)

    self.render_page(page='logs', template_file=self.TEMPLATE, values = {
      'service_name' : service_name,
      'host' : host,
      'query' : query,
      'next_cursor' : next_cursor.urlsafe(),
      'is_more' : is_more
    })

class LogUploadPage(webapp2.RequestHandler):
  """ Class to handle requests to the /logs/upload page. """

  def post(self):
    """ Saves logs records to the Datastore for later viewing. """
    encoded_data = self.request.body
    data = json.loads(encoded_data)
    service_name = data['service_name']
    host = data['host']
    log_lines = data['logs']

    # see if this service has been registered
    service = LoggedService.get_by_id(service_name)
    if service is None:
      service = LoggedService(id = service_name)
      service.hosts = [host]
      service.put()
    else:
      if host not in service.hosts:
        service.hosts.append(host)
        service.put()

    # add in each log line as an AppLogLine
    for log_line_dict in log_lines:
      the_time = int(log_line_dict['timestamp'])
      reversed_time = (2**34 - the_time) * 1000000
      key_name = service_name + host + str(reversed_time)
      log_line = RequestLogLine.get_by_id(id = key_name)
      if not log_line:
        log_line = RequestLogLine(id = reversed_time)
        log_line.service_name = service_name
        log_line.host = host

      app_log_line = AppLogLine()
      app_log_line.message = log_line_dict['message']
      app_log_line.level = log_line_dict['level']
      app_log_line.timestamp = datetime.datetime.fromtimestamp(the_time)
      log_line.app_logs.append(app_log_line)
      log_line.put()


# Main Dispatcher
app = webapp2.WSGIApplication([ ('/', IndexPage),
                                ('/status/refresh', StatusRefreshPage),
                                ('/status', StatusPage),
                                ('/users/new', NewUserPage),
                                ('/users/create', NewUserPage),
                                ('/logout', LogoutPage),
                                ('/users/logout', LogoutPage),
                                ('/users/login', LoginPage),
                                ('/users/authenticate', LoginPage),
                                ('/login', LoginPage),
                                ('/users/verify',LoginVerify),
                                ('/users/confirm',LoginVerify),
                                ('/authorize', AuthorizePage),
                                ('/apps/new', AppUploadPage),
                                ('/apps/upload', AppUploadPage),
                                ('/apps/delete', AppDeletePage),
                                ('/logs', LogMainPage),
                                ('/logs/upload', LogUploadPage),
                                ('/logs/(.+)/(.+)', LogServiceHostPage),
                                ('/logs/(.+)', LogServicePage)
                              ], debug=True)
# Handle errors
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
