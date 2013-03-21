"""
AppScale AppDashboard, a Python 2.7 webapp for interacting with AppScale.
"""
import cgi
import jinja2
import logging
import os
import re
import webapp2
from lib.appscale_status_helper import AppScaleStatusHelper
from lib.appscale_user_tools import AppScaleUserTools
from lib.appscale_app_tools import AppScaleAppTools

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + \
      os.sep + 'templates'))


class AppDashboard(webapp2.RequestHandler):
  """ Class that all pages in the Dashboard must inherit from. """

  @classmethod
  def render_template(cls, ash, template_file, values={}):
    """ Renders a template file with all variables loaded.
    Args: 
      ash: AppScaleStatusHelper object.
      template_file: relative path to tempate file.
      values: dict with key/value pairs used by the template file.
    Returns: str with the rendered template.
    """
    template = jinja_environment.get_template(template_file)
    sub_vars = {
      'logged_in' : AppScaleUserTools.is_user_logged_in(),
      'user_email' : AppScaleUserTools.get_user_email(),
      'is_user_cloud_admin' : AppScaleUserTools.is_user_cloud_admin(),
      'i_can_upload' : AppScaleUserTools.i_can_upload(),
      'user_perm_list' : AppScaleUserTools.list_all_users_permisions(),
      'service_info' : ash.get_service_info(),
      'dbinfo' : ash.get_database_information(),
      'apps' : ash.get_application_information(),
      'monitoring_url' : ash.get_monitoring_url(),
      'server_info' : ash.get_status_information()
    }
    for key in values.keys():
      sub_vars[key] = values[key]
    return template.render(sub_vars)
    
  def get_shared_navigation(self, ash):
    """ Renders the shared navigation.
    Returns: str with the navigation bar rendered.
    """
    return self.render_template(ash, template_file = 'shared/navigation.html')

  def render_page(self, page, template_file, values = {} ):
    """ Renders a template with the main layout and nav bar. """
    self.response.headers['Content-Type'] = 'text/html'
    template = jinja_environment.get_template('layouts/main.html')
    ash = AppScaleStatusHelper()
    self.response.out.write(template.render(
        page_name = page,
        page_body = self.render_template(ash,template_file,values),
        shared_navigation = self.get_shared_navigation(ash)
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

  @classmethod
  def process_new_user_post(cls, users, errors):
    """ Creates new user if parse was successful.
    Args 2 dicts, 1st with the form data, 
      2nd with True/False values for errors in each field.
    Returns: True if user was create, else False.
    """
    if errors['email'] or errors['password'] or errors['password_confirmation']:
      return False
    else:
      if AppScaleUserTools.create_new_user(users['email'], users['password']):
        return True
    return False

  def post(self):
    """ Handler for POST requests. """
    users, errors = self.parse_new_user_post()
    if self.process_new_user_post(users, errors):
      self.render_page(page='landing', template_file=IndexPage.TEMPLATE,
        values = {'flash_message':"Your account has been successfully created."
        })
    else:
      self.render_page(page='users', template_file=self.TEMPLATE, values={
        'display_error_messages': errors,
        'user' : users
        })

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page='users', template_file=self.TEMPLATE )


class LogoutPage(AppDashboard):
  """ Class to handle request to the /users/logout page. """

  def get(self):
    """ Handler for GET requests. """
    AppScaleUserTools.logout_user()
    self.render_page(page='landing', template_file=IndexPage.TEMPLATE,
      values = {'flash_message':"You have been logged out."
      })


class AuthorizePage(AppDashboard):
  """ Class to handle request to the /authorize page. """

  TEMPLATE = 'authorize/cloud.html'

  def parse_update_user_permissions(self):
    """ Update authorization matrix from form submission.
    Returns: str with message to be displayed to the user.
    """
    perms = AppScaleUserTools.get_all_permission_items()
    req_keys = self.request.POST.keys()
    response = ''
    for itm in self.request.POST.items():
      if re.match('^user_permission_', itm[0]):
        email = itm[1]
        for perm in perms:
          if email+'-'+perm in req_keys:
            if AppScaleUserTools.add_user_permissions(email, perm):
              response += 'Enabling '+perm+' for '+email+'. '
            else:
              response += 'Error enabling '+perm+' for '+email+'. '
          else:
            if AppScaleUserTools.remove_user_permissions(email, perm):
              response += 'Disabling '+perm+' for '+email+'. '
            else:
              response += 'Error disabling '+perm+' for '+email+'. '
    return response

  def post(self):
    """ Handler for POST requests. """
    self.render_page(page='authorize', template_file=self.TEMPLATE,
      values = {'flash_message' : self.parse_update_user_permissions()
      })

  def get(self):
    """ Handler for GET requests. """
    self.render_page(page='authorize', template_file=self.TEMPLATE)


class AppUploadPage(AppDashboard):
  """ Class to handle request to the /apps/new page. """

  TEMPLATE = 'apps/new.html'

  def post(self):
    """ Handler for POST requests. """
    message = AppScaleAppTools.upload_app(
        self.request.POST.multi['app_file_data'].file
        )
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
    message = AppScaleAppTools.delete_app(
        self.request.POST.get('appname')
        )
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
