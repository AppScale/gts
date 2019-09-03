import json

from google.appengine.api import urlfetch

from admin_server_location import ADMIN_SERVER_LOCATION
from app_dashboard import AppDashboard
from app_dashboard_helper import AppDashboardHelper, AppHelperException
from secret_key import GLOBAL_SECRET_KEY


class ServiceAccountsProjectSelector(AppDashboard):
  TEMPLATE = 'service_accounts/project_selector.html'

  def get(self):
    if self.helper.is_user_cloud_admin():
      version_keys = self.helper.get_version_info().keys()
      owned_projects = list({version.split('_')[0] for version in version_keys
                             if version.split('_')[0] != self.PROJECT_ID})
    else:
      owned_projects = self.helper.get_owned_apps()

    context = {
      'page_content': self.TEMPLATE,
      'owned_projects': owned_projects,
    }
    self.render_app_page(page='service_accounts_project_selector',
                         values=context)


class ProjectServiceAccounts(AppDashboard):
  TEMPLATE = 'service_accounts/editor.html'

  def ensure_user_has_admin(self, project_id):
    """ Returns an error page if user does not have project permissions.

    Args:
      project_id: A string specifying a project ID.
    """
    if self.helper.is_user_cloud_admin():
      version_keys = self.helper.get_version_info().keys()
      owned_projects = list({version.split('_')[0]
                             for version in version_keys})
    else:
      owned_projects = self.helper.get_owned_apps()

    if project_id not in owned_projects:
      message = ('You do not have permission to view or edit service accounts '
                 'for this project. Please log in as a user with sufficient '
                 'permissions.')
      self.response.write(message)
      self.abort(403)

  def get(self, project_id):
    self.ensure_user_has_admin(project_id)
    admin_server = 'https://{}:{}'.format(ADMIN_SERVER_LOCATION,
                                          AppDashboardHelper.ADMIN_SERVER_PORT)
    accounts_url = '{}/v1/projects/{}/serviceAccounts'.format(
      admin_server, project_id)
    result = urlfetch.fetch(accounts_url,
                            headers={'AppScale-Secret': GLOBAL_SECRET_KEY},
                            validate_certificate=False)
    if result.status_code != 200:
      raise AppHelperException(result.content)

    try:
      accounts = json.loads(result.content)['accounts']
    except (KeyError, ValueError):
      raise AppHelperException('Invalid list of service accounts: '
                               '{}'.format(result.content))

    context = {
      'page_content': self.TEMPLATE,
      'project_id': project_id,
      'accounts': accounts
    }
    self.render_app_page(page='service_accounts', values=context)

  def post(self, project_id):
    self.ensure_user_has_admin(project_id)
    account_data = self.request.POST['service_account_json'].file.read()
    account_details = json.loads(account_data)
    required = ('client_email', 'client_id', 'private_key', 'token_uri')
    for field in required:
      if field not in account_details:
        raise AppHelperException('Missing required field: {}'.format(field))

    payload = {'email': account_details['client_email'],
               'uniqueId': account_details['client_id'],
               'privateKey': account_details['private_key'],
               'tokenUri': account_details['token_uri']}
    admin_server = 'https://{}:{}'.format(ADMIN_SERVER_LOCATION,
                                          AppDashboardHelper.ADMIN_SERVER_PORT)
    accounts_url = '{}/v1/projects/{}/serviceAccounts'.format(
      admin_server, project_id)
    result = urlfetch.fetch(accounts_url, json.dumps(payload), urlfetch.POST,
                            headers={'AppScale-Secret': GLOBAL_SECRET_KEY},
                            validate_certificate=False)
    if result.status_code != 200:
      raise AppHelperException(result.content)

    self.redirect('/service_accounts/{}'.format(project_id))
