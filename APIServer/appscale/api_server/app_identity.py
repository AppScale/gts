""" Implements the App Identity API. """

import json
import logging
import random
import ssl
import time
import urllib
import urllib2

from kazoo.exceptions import KazooException
from kazoo.exceptions import NoNodeError
from kazoo.exceptions import NodeExistsError
from tornado.ioloop import IOLoop

from appscale.api_server import app_identity_service_pb2 as service_pb
from appscale.api_server import crypto
from appscale.api_server.base_service import BaseService
from appscale.api_server.constants import ApplicationError
from appscale.api_server.constants import CallNotFound
from appscale.api_server.crypto import (
    AccessToken, PrivateKey, PublicCertificate)
from appscale.common import appscale_info
from appscale.common.async_retrying import retry_children_watch_coroutine

logger = logging.getLogger(__name__)


class UnknownError(Exception):
    """ Indicates that the request cannot be completed at this time. """
    pass


class AppIdentityService(BaseService):
    """ Implements the App Identity API. """
    SERVICE_NAME = 'app_identity_service'

    # A dummy bucket name for satisfying calls.
    DEFAULT_GCS_BUCKET_NAME = 'app_default_bucket'

    # The appropriate messages for each API call.
    METHODS = {'SignForApp': (service_pb.SignForAppRequest,
                              service_pb.SignForAppResponse),
               'GetPublicCertificatesForApp': (
                   service_pb.GetPublicCertificateForAppRequest,
                   service_pb.GetPublicCertificateForAppResponse),
               'GetServiceAccountName': (
                   service_pb.GetServiceAccountNameRequest,
                   service_pb.GetServiceAccountNameResponse),
               'GetAccessToken': (service_pb.GetAccessTokenRequest,
                                  service_pb.GetAccessTokenResponse),
               'GetDefaultGcsBucketName': (
                   service_pb.GetDefaultGcsBucketNameRequest,
                   service_pb.GetDefaultGcsBucketNameResponse)}

    def __init__(self, project_id, zk_client):
        """ Creates a new AppIdentityService.

        Args:
            project_id: A string specifying the project ID.
            zk_client: A KazooClient.
        """
        super(AppIdentityService, self).__init__(self.SERVICE_NAME)

        self.project_id = project_id
        project_node = '/appscale/projects/{}'.format(self.project_id)

        self._zk_client = zk_client
        self._key_node = '{}/private_key'.format(project_node)
        self._key = None
        self._ensure_private_key()
        self._zk_client.DataWatch(self._key_node, self._update_key)

        self._certs_node = '{}/certificates'.format(project_node)
        self._zk_client.ensure_path(self._certs_node)
        self._certs = []
        self._zk_client.ChildrenWatch(self._certs_node, self._update_certs)

        self._service_accounts_node = '{}/service_accounts'.format(
            project_node)

    def get_public_certificates(self):
        """ Retrieves a list of valid public certificates for the project.

        Returns:
            A list of PublicCertificate objects.
        Raises:
            UnknownError if unable to retrieve any certificates.
        """
        valid_certs = []
        for cert in self._certs:
            if cert.expired:
                try:
                    self._remove_cert(cert)
                except (KazooException, UnknownError):
                    pass
            else:
                valid_certs.append(cert)

        if valid_certs:
            return valid_certs

        # If there are no valid certificates, try to generate a a new one.
        if self._key is None:
            raise UnknownError('A private key is not configured')

        new_cert = PublicCertificate.from_key(self._key, self.project_id)
        try:
            self._zk_client.create('{}/cert'.format(self._certs_node),
                                   new_cert.to_json(), sequence=True)
        except KazooException:
            raise UnknownError('Unable to create new certificate')

        return [new_cert]

    def get_service_account_name(self):
        """ Retrieves the default service account name.

        Returns:
            A string specifying the service account name.
        Raises:
            UnknownError if no service account is configured.
        """
        if self._key is None:
            raise UnknownError('A private key is not configured')

        return self._key.key_name

    def get_access_token(self, scopes, service_account_id=None,
                         service_account_name=None):
        """ Generates an access token from a service account.

        Args:
            scopes: A list of strings specifying scopes.
            service_account_id: An integer specifying a service account ID.
            service_account_name: A string specifying a service account name.
        Returns:
            An AccessToken.
        Raises:
            UnknownError if the service account is not configured.
        """
        # TODO: Check if it makes sense to store the audience with the service
        # account definition.
        default_audience = 'https://www.googleapis.com/oauth2/v4/token'

        if (service_account_name is None or
                (self._key is not None and
                 self._key.key_name == service_account_name)):
            lb_ip = random.choice(appscale_info.get_load_balancer_ips())
            url = 'https://{}:17441/oauth/token'.format(lb_ip)
            payload = urllib.urlencode({'scope': ' '.join(scopes),
                                        'grant_type': 'secret',
                                        'project_id': self.project_id,
                                        'secret': appscale_info.get_secret()})
            try:
                response = urllib2.urlopen(
                    url, payload, context=ssl._create_unverified_context())
            except urllib2.HTTPError as error:
                raise UnknownError(error.msg)
            except urllib2.URLError as error:
                raise UnknownError(error.reason)

            token_details = json.loads(response.read())
            expiration_time = int(time.time()) + token_details['expires_in']
            return AccessToken(token_details['access_token'], expiration_time)

        if service_account_id is not None:
            raise UnknownError(
                '{} is not configured'.format(service_account_id))

        service_account_node = '/'.join([self._service_accounts_node,
                                         service_account_name])
        try:
            account_details = self._zk_client.get(service_account_node)[0]
        except NoNodeError:
            raise UnknownError(
                '{} is not configured'.format(service_account_name))

        try:
            account_details = json.loads(account_details)
        except ValueError:
            raise UnknownError(
                '{} has invalid data'.format(service_account_node))

        pem = account_details['privateKey'].encode('utf-8')
        key = PrivateKey.from_pem(service_account_name, pem)
        assertion = key.generate_assertion(default_audience, scopes)
        return self._get_token(default_audience, assertion)

    def sign(self, blob):
        """ Signs a message with the project's key.

        Args:
            blob: A binary type containing an arbitrary payload.
        Returns:
            A binary type containing the signed payload.
        Raises:
            UnknownError if the payload cannot be signed.
        """
        if self._key is None:
            raise UnknownError('A private key is not configured')

        return self._key.sign(blob)

    def make_call(self, method, encoded_request):
        """ Makes the appropriate API call for a given request.

        Args:
            method: A string specifying the API method.
            encoded_request: A binary type containing the request details.
        Returns:
            A binary type containing the response details.
        """
        if method not in self.METHODS:
            raise CallNotFound(
                '{}.{} does not exist'.format(self.SERVICE_NAME, method))

        request = self.METHODS[method][0]()
        request.ParseFromString(encoded_request)

        response = self.METHODS[method][1]()

        if method == 'SignForApp':
            response.key_name = self._key.key_name
            try:
                response.signature_bytes = self.sign(request.bytes_to_sign)
            except UnknownError as error:
                logger.exception('Unable to sign bytes')
                raise ApplicationError(service_pb.UNKNOWN_ERROR, str(error))
        elif method == 'GetPublicCertificatesForApp':
            try:
                public_certs = self.get_public_certificates()
            except UnknownError as error:
                logger.exception('Unable to get public certificates')
                raise ApplicationError(service_pb.UNKNOWN_ERROR, str(error))

            for public_cert in public_certs:
                cert = response.public_certificate_list.add()
                cert.key_name = cert.key_name = public_cert.key_name
                cert.x509_certificate_pem = public_cert.pem
        elif method == 'GetServiceAccountName':
            try:
                response.service_account_name = self.get_service_account_name()
            except UnknownError as error:
                logger.exception('Unable to get service account name')
                raise ApplicationError(service_pb.UNKNOWN_ERROR, str(error))
        elif method == 'GetAccessToken':
            service_account_id = None
            if request.HasField('service_account_id'):
                service_account_id = request.service_account_id

            service_account_name = None
            if request.HasField('service_account_name'):
                service_account_name = request.service_account_name

            try:
                token = self.get_access_token(
                    list(request.scope), service_account_id,
                    service_account_name)
            except UnknownError as error:
                logger.exception('Unable to get access token')
                raise ApplicationError(service_pb.UNKNOWN_ERROR, str(error))

            response.access_token = token.token.encode('utf-8')
            response.expiration_time = token.expiration_time
        elif method == 'GetDefaultGcsBucketName':
            response.default_gcs_bucket_name = self.DEFAULT_GCS_BUCKET_NAME

        return response.SerializeToString()

    @staticmethod
    def _get_token(url, assertion):
        """ Fetches a token with the given assertion.

        Args:
            url: The location of the server that generates the token.
            assertion: A string containing the signed JWT.
        Returns:
            An AccessToken object.
        Raises:
            UnknownError if unable to fetch token.
        """
        grant_type = 'urn:ietf:params:oauth:grant-type:jwt-bearer'
        payload = urllib.urlencode({'grant_type': grant_type,
                                    'assertion': assertion})
        try:
            response = urllib2.urlopen(url, payload)
        except urllib2.HTTPError as error:
            raise UnknownError(error.msg)
        except urllib2.URLError as error:
            raise UnknownError(error.reason)

        token_details = json.loads(response.read())
        expiration_time = int(time.time()) + token_details['expires_in']
        return AccessToken(token_details['access_token'], expiration_time)

    def _remove_cert(self, cert):
        """ Removes a certificate node.

        Args:
            cert: A PublicCertificate.
        Raises:
            UnknownError if the given certificate does not have node info.
        """
        if cert.node_name is None:
            raise UnknownError('Certificate has no ZooKeeper location')

        full_path = '/'.join([self._certs_node, cert.node_name])
        self._zk_client.delete(full_path)

    def _ensure_private_key(self):
        """ Ensures the project has a private key. """
        key_exists = self._zk_client.exists(self._key_node) is not None
        if key_exists:
            return

        key = PrivateKey.generate('{}_1'.format(self.project_id))
        try:
            self._zk_client.create(self._key_node, key.to_json())
        except NodeExistsError:
            pass

    def _update_key(self, new_data, _):
        """ Updates the private key.

        Args:
            new_data: A JSON string containing the new key details.
        """
        try:
            self._key = PrivateKey.from_json(new_data)
        except crypto.InvalidKey:
            logger.error('Invalid private key at {}'.format(self._key_node))
            self._key = None

    def _update_certs_sync(self, cert_nodes):
        """ Updates the list of certificates.

        Args:
            cert_nodes: A list of strings specifying certificate nodes.
        """
        certs = []
        for cert_node in cert_nodes:
            cert_path = '/'.join([self._certs_node, cert_node])
            try:
                cert_data = self._zk_client.get(cert_path)[0]
            except NoNodeError:
                continue

            try:
                cert = PublicCertificate.from_node(cert_node, cert_data)
            except crypto.InvalidCertificate:
                logger.error('Invalid certificate at {}'.format(cert_path))
                continue

            if cert.expired:
                logger.info(
                    'Ignoring expired certificate: {}'.format(cert_path))
                continue

            certs.append(cert)

        self._certs = certs

    def _update_certs(self, cert_nodes):
        """ Updates the list of certificates.

        Args:
            cert_nodes: A list of strings specifying certificate nodes.
        """
        persistent_update_certs = retry_children_watch_coroutine(
            self._certs_node, self._update_certs_sync)
        IOLoop.instance().add_callback(persistent_update_certs, cert_nodes)
