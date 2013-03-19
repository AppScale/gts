import cgi
import datetime
import urllib
import webapp2
import jinja2
import os
import re
import logging
from appscale_status_helper import AppScaleStatusHelper
from appscale_user_tools import AppScaleUserTools

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + \
      os.sep + 'templates'))

from google.appengine.ext import db
#from google.appengine.api import users #moved to AppScaleUserTools

class AppDashboard(webapp2.RequestHandler):
  """ Class that all pages in the Dashboard must inherit from. """

  def render_template(self, template_file, values={}):
    """ Renders a template file with all variables loaded. """
    template = jinja_environment.get_template(template_file)
    sub_vars = {
      'logged_in' : AppScaleUserTools.is_user_logged_in(),
      'user_email' : AppScaleUserTools.get_user_email(),
      'is_user_cloud_admin' : AppScaleUserTools.is_user_cloud_admin(),
      'i_can_upload' : AppScaleUserTools.i_can_upload(),
      'user_perm_list' : AppScaleUserTools.list_all_users_permisions(),
      'service_info' : AppScaleStatusHelper.get_service_info(),
      'dbinfo' : AppScaleStatusHelper.get_database_information(),
      'apps' : AppScaleStatusHelper.get_application_information(),
      'monitoring_url' : AppScaleStatusHelper.get_monitoring_url(),
      'servers' : AppScaleStatusHelper.get_status_information()
    }
    for key in values.keys():
      sub_vars[key] = values[key]
    return template.render(sub_vars)
    
  def get_shared_navigation(self):
    """ Renders the shared navigation. """
    return self.render_template(template_file = 'shared/navigation.html')

  def render_page(self, page, template_file, values = {} ):
    """ Renders a template with the main layout and nav bar. """
    self.response.headers['Content-Type'] = 'text/html'
    template = jinja_environment.get_template('layouts/main.html')
    self.response.out.write(template.render(
        page_name = page,
        page_body = self.render_template(template_file,values),
        shared_navigation = self.get_shared_navigation()
        ))
    

class IndexPage(AppDashboard):
  """ Class to handle request to the / page. """
  TEMPLATE = 'landing/index.html'
  def get(self):
    self.render_page(page='landing', template_file=self.TEMPLATE)


class StatusPage(AppDashboard):
  """ Class to handle request to the /status page. """
  TEMPLATE = 'status/cloud.html'
  def get(self):
    self.render_page(page='status', template_file=self.TEMPLATE)


class NewUserPage(AppDashboard):
  """ Class to handle request to the /users/new and /users/create page. """
  TEMPLATE = 'users/new.html'

  def parse_new_user_post(self):
    """ Parse the input from the create user form.
    Returns: 2 dicts, 1st with the form data, 
      2nd with True/False values for errors in each field
    """
    users = {}
    errors = {}
    users['email'] = cgi.escape(self.request.get('user_email'))
    if re.match('^\w[^@\s]*@[^@\s]{2,}$',users['email']):
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

  def process_new_user_post(self,users,errors):
    """ Creates new user if parse was successful.
    Args 2 dicts, 1st with the form data, 
      2nd with True/False values for errors in each field
    Returns: True if user was create, else False.
    """
    if not errors['email'] and \
       not errors['password'] and \
       not errors['password_confirmation']:
      if AppScaleUserTools.create_new_user(users['email'], users['password']):
        return True
    return False

  def post(self):
    users, errors = self.parse_new_user_post()
    #if self.process_new_user_post(users,errors):
    if True:
      self.render_page(page='landing', template_file=IndexPage.TEMPLATE,
        values = {'flash_message':"Your account has been successfully created."
        })
    else:
      self.render_page(page='users', template_file=self.TEMPLATE ,values={
        'display_error_messages': errors,
        'user' : users
        })

  def get(self):
    self.render_page(page='users', template_file=self.TEMPLATE ,values={
      'display_error_messages': {},
      'user' : {}
      })


class LogoutPage(AppDashboard):
  def get(self):
    AppScaleUserTools.logout_user()
    self.render_page(page='landing', template_file=IndexPage.TEMPLATE,
      values = {'flash_message':"You have been logged out."
      })


class AuthorizePage(AppDashboard):
  """ Class to handle request to the /status page. """

  TEMPLATE = 'authorize/cloud.html'

  def parse_update_user_permissions(self):
    """ Update authorization matrix from submission. """
    perms = AppScaleUserTools.get_all_permission_items()
    req_keys = self.request.POST.keys()
    response = ''
    for itm in self.request.POST.items():
      if re.match('^user_permission_',itm[0]):
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

  def post(self):
    self.render_page(page='authorize', template_file=self.TEMPLATE,
      values = {'flash_message' : self.parse_update_user_permissions()
      })

  def get(self):
    self.render_page(page='authorize', template_file=self.TEMPLATE)


class AppUploadPage(AppDashboard):
  """ Class to handle request to the /apps/new page. """

  TEMPLATE = 'apps/new.html'

  def post(self):
    self.render_page(page='authorize', template_file=self.TEMPLATE,
      values = {'flash_message' : "FIXME" 
      })

  def get(self):
    self.render_page(page='authorize', template_file=self.TEMPLATE)

class AppDeletePage(AppDashboard):
  """ Class to handle request to the /apps/delete page. """

  TEMPLATE = 'apps/delete.html'

  def post(self):
    self.render_page(page='authorize', template_file=self.TEMPLATE,
      values = {'flash_message' : "FIXME" 
      })

  def get(self):
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
    logging.exception(exception)
    response.set_status(404)
    response.write(jinja_environment.get_template('404.html').render())

def handle_500(request, response, exception):
    logging.exception(exception)
    response.set_status(500)
    response.write(jinja_environment.get_template('500.html').render())

app.error_handlers[404] = handle_404
app.error_handlers[500] = handle_500
