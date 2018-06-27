""" Implements the App Identity API. """

import logging

from kazoo.exceptions import KazooException
from kazoo.exceptions import NoNodeError
from kazoo.exceptions import NodeExistsError
from tornado.ioloop import IOLoop

from appscale.api_server import app_identity_service_pb2 as service_pb
from appscale.api_server import crypto
from appscale.api_server.base_service import BaseService
from appscale.api_server.constants import ApplicationError
from appscale.api_server.constants import CallNotFound
from appscale.api_server.crypto import PrivateKey
from appscale.api_server.crypto import PublicCertificate
from appscale.common.async_retrying import retry_children_watch_coroutine

logger = logging.getLogger('appscale-api-server')


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

        self._zk_client = zk_client
        self._key_node = '/appscale/projects/{}/private_key'.format(
            self.project_id)
        self._key = None
        self._ensure_private_key()
        self._zk_client.DataWatch(self._key_node, self._update_key)

        self._certs_node = '/appscale/projects/{}/certificates'.format(
            self.project_id)
        self._zk_client.ensure_path(self._certs_node)
        self._certs = []
        self._zk_client.ChildrenWatch(self._certs_node, self._update_certs)

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

    def get_access_token(self, scopes, service_account_id=None):
        """ Generates an access token from a service account.

        Args:
            scopes: A list of strings specifying scopes.
            service_account_id: A string specifying a service account name.
        Returns:
            An AccessToken.
        Raises:
            UnknownError if the service account is not configured.
        """
        if self._key is None:
            raise UnknownError('A private key is not configured')

        if (service_account_id is not None and
            service_account_id != self._key.key_name):
            raise UnknownError(
                '{} is not configured'.format(service_account_id))

        return self._key.generate_access_token(self.project_id, scopes)

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

            try:
                token = self.get_access_token(list(request.scope),
                                              service_account_id)
            except UnknownError as error:
                logger.exception('Unable to get access token')
                raise ApplicationError(service_pb.UNKNOWN_ERROR, str(error))

            response.access_token = token.token
            response.expiration_time = token.expiration_time
        elif method == 'GetDefaultGcsBucketName':
            response.default_gcs_bucket_name = self.DEFAULT_GCS_BUCKET_NAME

        return response.SerializeToString()

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
