""" Implements some IAM API operations. """
import json

from kazoo.exceptions import NodeExistsError, NoNodeError

from .base_handler import BaseHandler
from .constants import CustomHTTPError
from appscale.common.constants import HTTPCodes


class ServiceAccount(object):
  def __init__(self, project_id, email, id_=None, display_name=None,
               description=None, private_key=None, token_uri=None):
    self.project_id = project_id
    self.email = email
    self.id = id_
    self.display_name = display_name
    self.description = description
    self.private_key = private_key
    self.token_uri = token_uri

  def json_repr(self):
    optional_fields = (('uniqueId', self.id),
                       ('displayName', self.display_name),
                       ('description', self.description),
                       ('oauth2ClientId', self.id))
    details = {'name': '/'.join(['projects', self.project_id,
                                 'serviceAccounts', self.email]),
               'projectId': self.project_id,
               'email': self.email}
    for field, val in optional_fields:
      if val is not None:
        details[field] = val

    return details

  def zk_serialize(self):
    zk_fields = (('email', self.email),
                 ('uniqueId', self.id),
                 ('displayName', self.display_name),
                 ('description', self.description),
                 ('privateKey', self.private_key),
                 ('tokenUri', self.token_uri))
    return json.dumps({field: val for field, val in zk_fields
                       if val is not None})

  @classmethod
  def from_json(cls, project_id, data):
    required = ('privateKey', 'email', 'uniqueId', 'tokenUri')
    details = json.loads(data)
    for field in required:
      if field not in details:
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                              message='{} is a required field'.format(field))

    return cls(project_id, details['email'], details['uniqueId'],
               private_key=details['privateKey'],
               token_uri=details['tokenUri'])


class ServiceAccountsHandler(BaseHandler):
  PROJECT_NODE = '/appscale/projects/{}'

  def initialize(self, zk_client, ua_client):
    self.zk_client = zk_client
    self.ua_client = ua_client

  def get(self, project_id):
    self.authenticate(project_id, self.ua_client)
    service_accounts = []
    project_node = self.PROJECT_NODE.format(project_id)
    if not self.zk_client.exists(project_node):
      raise CustomHTTPError(HTTPCodes.NOT_FOUND, message='Project not found')

    try:
      default_data = self.zk_client.get(project_node + '/private_key')[0]
    except NoNodeError:
      default_data = None

    if default_data is not None:
      details = json.loads(default_data)
      service_accounts.append(ServiceAccount(project_id, details['key_name']))

    accounts_node = self.PROJECT_NODE.format(project_id) + '/service_accounts'
    try:
      account_names = self.zk_client.get_children(accounts_node)
    except NoNodeError:
      account_names = []

    for account_name in account_names:
      account_node = '/'.join([accounts_node, account_name])
      account_data = self.zk_client.get(account_node)[0]
      service_account = ServiceAccount.from_json(project_id, account_data)
      service_accounts.append(service_account)

    output = {'accounts': [account.json_repr()
                           for account in service_accounts]}
    self.write(json.dumps(output))

  def post(self, project_id):
    self.authenticate(project_id, self.ua_client)
    account = ServiceAccount.from_json(project_id, self.request.body)
    account_path = '/'.join([self.PROJECT_NODE.format(project_id),
                             'service_accounts', account.email])
    try:
      self.zk_client.create(account_path, account.zk_serialize(),
                            makepath=True)
    except NodeExistsError:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='{} already exists'.format(account.email))
