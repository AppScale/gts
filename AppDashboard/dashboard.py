"""
AppScale AppDashboard, a Python 2.7 webapp for interacting with AppScale.
"""
import cgi
import jinja2
import logging
import os
import re
import webapp2
import sys
from lib.app_dashboard_helper import AppDashboardHelper

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + \
      os.sep + 'templates'))


class AppDashboard(webapp2.RequestHandler):
  """ Class that all pages in the Dashboard must inherit from. """

  def __init__(self, request, response):
    """ Constructor """
    # Set self.request, self.response and self.app.
    self.initialize(request, response)
    # initialize helper
    self.helper = AppDashboardHelper(self.response)

  def render_template(self, template_file, values={}):
    """ Renders a template file with all variables loaded.
    Args: 
      template_file: relative path to tempate file.
      values: dict with key/value pairs used by the template file.
    Returns: str with the rendered template.
    """
    template = jinja_environment.get_template(template_file)
    sub_vars = {
      'logged_in' : self.helper.is_user_logged_in(),
      'user_email' : self.helper.get_user_email(),
      'is_user_cloud_admin' : self.helper.is_user_cloud_admin(),
      'i_can_upload' : self.helper.i_can_upload(),
      'service_info' : self.helper.get_service_info(),
      'dbinfo' : self.helper.get_database_information(),
      'apps' : self.helper.get_application_information(),
      'monitoring_url' : self.helper.get_monitoring_url(),
      'server_info' : self.helper.get_status_information(),
      'app_admin_list' : self.helper.get_user_app_list()
    }
    for key in values.keys():
      sub_vars[key] = values[key]
    return template.render(sub_vars)
    
  def get_shared_navigation(self):
    """ Renders the shared navigation.
    Returns: str with the navigation bar rendered.
    """
    return self.render_template(template_file = 'shared/navigation.html')

  def render_page(self, page, template_file, values = {} ):
    """ Renders a template with the main layout and nav bar. """
    self.response.headers['Content-Type'] = 'text/html'
    template = jinja_environment.get_template('layouts/main.html')
    self.response.out.write(template.render(
        page_name = page,
        page_body = self.render_template(template_file, values),
        shared_navigation = self.get_shared_navigation()
        ))
    

class IndexPage(AppDashboard):
  """ Class to handle request to the / page. """

  TEMPLATE = 'landing/index.html'

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page='landing', template_file=self.TEMPLATE)


class StatusPage(AppDashboard):
  """ Class to handle request to the /status page. """

  TEMPLATE = 'status/cloud.html'

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page='status', template_file=self.TEMPLATE)


class NewUserPage(AppDashboard):
  """ Class to handle request to the /users/new and /users/create page. """

  TEMPLATE = 'users/new.html'

  def parse_new_user_post(self):
    """ Parse the input from the create user form.
    Returns: 2 dicts, 1st with the form data, 
      2nd with True/False values for errors in each field.
    """
    users = {}
    errors = {}
    users['email'] = cgi.escape(self.request.get('user_email'))
    if re.match('^\w[^@\s]*@[^@\s]{2,}$', users['email']):
      errors['email'] = False
    else:
      errors['email'] = True
    users['password'] = cgi.escape(self.request.get('user_password'))
    if len(users['password']) >= 6:
      errors['password'] = False
    else:
      errors['password'] = True
    users['password_confirmation'] = cgi.escape(
      self.request.get('user_password_confirmation'))
    if users['password_confirmation'] == users['password']:
      errors['password_confirmation'] = False
    else:
      errors['password_confirmation'] = True
    return users, errors

  def process_new_user_post(self, users, errors):
    """ Creates new user if parse was successful.
    Args 2 dicts, 1st with the form data, 
      2nd with True/False values for errors in each field.
    Returns: True if user was create, else False.
    """
    if errors['email'] or errors['password'] or errors['password_confirmation']:
      return False
    else:
      return self.helper.create_new_user(cgi.escape(users['email']),
           cgi.escape(users['password']) )

  def post(self):
    """ Handler for POST requests. """
    users, errors = self.parse_new_user_post()
    if self.process_new_user_post(users, errors):
      self.redirect('/',self.response)
#      self.render_page(page = 'landing', template_file = IndexPage.TEMPLATE,
#        values = {'flash_message':"Your account has been successfully created."
#        })
    else:
      self.render_page(page = 'users', template_file = self.TEMPLATE, values = {
        'display_error_messages': errors,
        'user' : users
        })

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page = 'users', template_file = self.TEMPLATE, values = {
      'display_error_messages' : {},
      'user' : {}
    })


class LogoutPage(AppDashboard):
  """ Class to handle request to the /users/logout page. """

  def get(self):
    """ Handler for GET requests. """
    self.helper.logout_user()
    self.redirect('/',self.response)
#    self.render_page(page='landing', template_file=IndexPage.TEMPLATE,
#      values = {'flash_message':"You have been logged out."
#      })


class LoginPage(AppDashboard):
  """ Class to handle request to the /users/login page. """

  TEMPLATE = 'users/login.html'

  def post(self):
    """ Handler for post requests. """
    if self.helper.login_user( self.request.POST.get('user_email'),
       self.request.POST.get('user_password') ):
#      self.render_page(page = 'landing', template_file = IndexPage.TEMPLATE )
      self.redirect('/',self.response)
    else:
      self.render_page(page = 'users', template_file = self.TEMPLATE,
        values = {
          'user_email' : self.request.POST.get('user_email'),
          'flash_message': 
          "Incorrect username / password combination. Please try again."
        })

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page = 'users', template_file = self.TEMPLATE )


class AuthorizePage(AppDashboard):
  """ Class to handle request to the /authorize page. """

  TEMPLATE = 'authorize/cloud.html'

  def parse_update_user_permissions(self):
    """ Update authorization matrix from form submission.
    Returns: str with message to be displayed to the user.
    """
    perms = self.helper.get_all_permission_items()
    req_keys = self.request.POST.keys()
    sys.stderr.write("req_keys: "+str(req_keys))
    response = ''
    for fldname, email in self.request.POST.iteritems():
      if re.match('^user_permission_', fldname):
        for perm in perms:
          if email+'-'+perm in req_keys and\
            self.request.get('CURRENT-'+email+'-'+perm) == 'False':
            if self.helper.add_user_permissions(email, perm):
              response += 'Enabling '+perm+' for '+email+'. '
            else:
              response += 'Error enabling '+perm+' for '+email+'. '
          elif email+'-'+perm not in req_keys and\
            self.request.get('CURRENT-'+email+'-'+perm) == 'True':
            if self.helper.remove_user_permissions(email, perm):
              response += 'Disabling '+perm+' for '+email+'. '
            else:
              response += 'Error disabling '+perm+' for '+email+'. '
    return response

  def post(self):
    """ Handler for POST requests. """
    if self.helper.is_user_cloud_admin():
      self.render_page(page='authorize', template_file=self.TEMPLATE,
        values = {
        'flash_message' : self.parse_update_user_permissions(),
        'user_perm_list' : self.helper.list_all_users_permisions(),
        })
    else:
      self.render_page(page='authorize', template_file=self.TEMPLATE,
        values = {
        'flash_message':"Only the cloud administrator can change permissions.",
        'user_perm_list':{},
        })

  def get(self):
    """ Handler for GET requests. """
    if self.helper.is_user_cloud_admin():
      self.render_page(page='authorize', template_file=self.TEMPLATE, values = {
        'user_perm_list' : self.helper.list_all_users_permisions(),
      })
    else:
      self.render_page(page='authorize', template_file=self.TEMPLATE,
        values = {
        'flash_message':"Only the cloud administrator can change permissions.",
        'user_perm_list':{},
        })


class AppUploadPage(AppDashboard):
  """ Class to handle request to the /apps/new page. """

  TEMPLATE = 'apps/new.html'

  def post(self):
    """ Handler for POST requests. """
    if self.helper.i_can_upload():
      message = self.helper.upload_app(
          self.request.POST.multi['app_file_data'].file
          )
    else:
      message = "You are not authorized to upload apps."
    self.render_page(page='authorize', template_file=self.TEMPLATE,
      values = {'flash_message' : message
      })

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page='authorize', template_file=self.TEMPLATE)

class AppDeletePage(AppDashboard):
  """ Class to handle request to the /apps/delete page. """

  TEMPLATE = 'apps/delete.html'

  def post(self):
    """ Handler for POST requests. """
    #TODO: check that this user can delete this app
    appname = self.request.POST.get('appname')
    if self.helper.is_user_cloud_admin() or\
       appname in self.helper.get_user_app_list():
      message = self.helper.delete_app(appname)
    else:
      message = "You do not have permission to delete the application: "+appname
    self.render_page(page='authorize', template_file=self.TEMPLATE,
      values = {'flash_message' : message
      })

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page='authorize', template_file=self.TEMPLATE)


# Main Dispatcher
app = webapp2.WSGIApplication([ ('/', IndexPage),
                                ('/status', StatusPage),
                                ('/users/new', NewUserPage),
                                ('/users/create', NewUserPage),
                                ('/users/logout', LogoutPage),
                                ('/users/login', LoginPage),
                                ('/authorize', AuthorizePage),
                                ('/apps/new', AppUploadPage),
                                ('/apps/upload', AppUploadPage),
                                ('/apps/delete', AppDeletePage),
                              ], debug=True)
# Handle errors
def handle_404(request, response, exception):
  """ Handles 404, page not found exceptions. """
  logging.exception(exception)
  response.set_status(404)
  response.write(jinja_environment.get_template('404.html').render())

def handle_500(request, response, exception):
  """ Handles 500, error processing page exceptions. """
  logging.exception(exception)
  response.set_status(500)
  response.write(jinja_environment.get_template('500.html').render())

app.error_handlers[404] = handle_404
app.error_handlers[500] = handle_500
