""" A base class for all Dashboard pages. """
import os

import jinja2
import webapp2

from app_dashboard_data import AppDashboardData
from app_dashboard_helper import AppDashboardHelper

templates_dir = os.path.join(os.path.dirname(__file__), '..', 'templates')
jinja_environment = jinja2.Environment(
  loader=jinja2.FileSystemLoader(templates_dir))


class AppDashboard(webapp2.RequestHandler):
  """ Class that all pages in the Dashboard must inherit from. """

  # Regular expression to capture the continue url.
  CONTINUE_URL_REGEX = 'continue=(.*)$'

  # The dashboard's project ID.
  PROJECT_ID = 'appscaledashboard'

  # Regular expression for updating user permissions.
  USER_PERMISSION_REGEX = '^user_permission_'

  # Regular expression that matches email addresses.
  USER_EMAIL_REGEX = '^\w[^@\s]*@[^@\s]{2,}$'

  # The frequency, in seconds, that defines how often Task Queue tasks are fired
  # to update the Dashboard's Datastore cache.
  REFRESH_WAIT_TIME = 10

  def __init__(self, request, response):
    """ Constructor.

    Args:
      request: The webapp2.Request object that contains information about the
        current web request.
      response: The webapp2.Response object that contains the response to be
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

    is_cloud_admin = self.helper.is_user_cloud_admin()
    all_versions = self.helper.get_version_info()

    if is_cloud_admin:
      apps_user_owns = list({version.split('_')[0]
                             for version in all_versions})
    else:
      apps_user_owns = self.helper.get_owned_apps()

    versions_user_is_admin_on = {
      version: all_versions[version] for version in all_versions
      if version.split('_')[0] in apps_user_owns}

    self.helper.update_cookie_app_list(apps_user_owns, self.request,
                                       self.response)
    template = jinja_environment.get_template(template_file)
    sub_vars = {
      'logged_in': self.helper.is_user_logged_in(),
      'user_email': self.helper.get_user_email(),
      'is_user_cloud_admin': self.dstore.is_user_cloud_admin(),
      'can_upload_apps': self.dstore.can_upload_apps(),
      'versions_user_is_admin_on': versions_user_is_admin_on,
      'user_layout_pref': self.dstore.get_dash_layout_settings(),
      'flower_url': self.dstore.get_flower_url(),
    }
    for key in values.keys():
      sub_vars[key] = values[key]
    return template.render(sub_vars)

  def get_shared_navigation(self, page):
    """ Renders the shared navigation.

    Args:
      page: A string specifying the page ID.
    Returns:
      A str with the navigation bar rendered.
    """
    show_create_account = True
    if AppDashboardHelper.USE_SHIBBOLETH:
      show_create_account = False

    # These sections do not lend themselves well to having panels.
    panel_blacklist = ['taskqueue', 'datastore_viewer']
    return self.render_template(template_file='shared/navigation.html',
                                values={'show_create_account':
                                        show_create_account,
                                        'page_name': page,
                                        'panel_blacklist': panel_blacklist})

  def render_page(self, page, template_file, values=None):
    """ Renders a template with the main layout and nav bar.

    Args:
      page: A string specifying the page ID.
      template_file: A string specifying the template to use.
      values: A dictionary containing template variables.
    """
    if values is None:
      values = {}
    self.response.headers['Content-Type'] = 'text/html'
    template = jinja_environment.get_template('layouts/main.html')
    self.response.out.write(template.render(
      page_name=page,
      page_body=self.render_template(template_file, values),
      shared_navigation=self.get_shared_navigation(page)
    ))

  def render_app_page(self, page, values=None):
    """ Render a typical page using the app_page template.

    Args:
      page: A string specifying the page ID.
      values: A dictionary containing template variables.
    """
    self.render_page(page=page, template_file="layouts/app_page.html",
                     values=values)
