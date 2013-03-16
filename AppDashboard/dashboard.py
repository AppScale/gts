import cgi
import datetime
import urllib
import webapp2
import jinja2
import os
import logging
from appscale_status_helper import AppScaleStatusHelper

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + \
      os.sep + 'templates'))

from google.appengine.ext import db
from google.appengine.api import users

class AppDashboard(webapp2.RequestHandler):
  def get_shared_navigation(self):
    template = jinja_environment.get_template('shared'+os.sep+'navigation.html')
    # There are the default values
    logged_in = False
    user_email = ''
    is_user_cloud_admin = False
    i_can_upload = False
    user = users.get_current_user()
    if user:
      logged_in = True
      user_email =  user.nickname()
      if users.is_current_user_admin():
        is_user_cloud_admin = True
        i_can_upload = True  #TODO: fix 
        # need to query UserAppServer via SOAP, get permissions

    return template.render(
      logged_in = logged_in,
      user_email = user_email,
      is_user_cloud_admin = is_user_cloud_admin,
      i_can_upload = i_can_upload
      )

  def render_page(self, page='status', content='Hello World'):
    self.response.headers['Content-Type'] = 'text/html'
    template = jinja_environment.get_template('layouts'+os.sep+'main.html')
    # shared_navigation => shared/navigation
    # page_body => 'main body of the page
    self.response.out.write(template.render(
        page_name = page,
        page_body = content,
        shared_navigation = self.get_shared_navigation()
        ))

  def get_flash_message(self):
    #TODO
    return ""
    

class StatusPage(AppDashboard):
  """ Class to handle request to the /status page. """
  def get(self):
    template = jinja_environment.get_template('status'+os.sep+'cloud.html')
    is_user_cloud_admin = False
    if users.get_current_user() and users.is_current_user_admin():
      is_user_cloud_admin = True
      print "is_admin = TRUE"
    else:
      print "is_admin = FALSE"
      if users.get_current_user():
        print "users.get_current_user() == TRUE"
      if users.is_current_user_admin():
        print "users.is_current_user_admin ==TRUE"

    body = template.render(
      flash_message = self.get_flash_message(),
      service_info = AppScaleStatusHelper.get_service_info(),
      db = AppScaleStatusHelper.get_database_information(),
      apps = AppScaleStatusHelper.get_application_information(),
      is_user_cloud_admin = is_user_cloud_admin,
      monitoring_url = AppScaleStatusHelper.get_monitoring_url(),
      servers = AppScaleStatusHelper.get_status_information()
    )
    self.render_page(page='status', content=body)

# Main Dispatcher
app = webapp2.WSGIApplication([ ('/', StatusPage),
                                ('/status', StatusPage),
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
