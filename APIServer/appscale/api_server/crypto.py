""" Manages cryptography-related data and operations. """

import base64
import datetime
import json
import time

import six
from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

# The length of time a certificate should remain valid for.
CERTIFICATE_TTL = datetime.timedelta(days=10)

# The generated key length in bits.
KEY_SIZE = 2048

# The public exponent to use when generating keys.
PUBLIC_EXPONENT = 65537


class InvalidKey(Exception):
    """ Indicates that a private key is invalid. """
    pass


class InvalidCertificate(Exception):
    """ Indicates that a certificate is invalid. """
    pass


class AccessToken(object):
    """ Holds an access token and its metadata. """
    def __init__(self, token, expiration_time):
        """ Creates a new AccessToken.

        Args:
            token: A string containing an access token.
            expiration_time: An integer specifying a unix timestamp.
        """
        self.token = token
        self.expiration_time = expiration_time


class PrivateKey(object):
    """ Holds a private key and its metadata. """
    ENCODING = serialization.Encoding.PEM
    ENCRYPTION = serialization.NoEncryption()
    FORMAT = serialization.PrivateFormat.PKCS8
    PADDING = padding.PKCS1v15()
    TOKEN_LIFETIME = 3600

    def __init__(self, key_name, key):
        """ Creates a new PrivateKey.

        Args:
            key_name: A string specifying the key name.
            key: An RSAPrivateKey.
        """
        self.key_name = key_name
        self.key = key

    @property
    def pem(self):
        """ Serializes the private key.

        Returns:
            A binary type containing a PEM-formatted key.
        """
        return self.key.private_bytes(self.ENCODING, self.FORMAT,
                                      self.ENCRYPTION)

    def generate_assertion(self, audience, scopes):
        """ Creates an access token signed by the key.

        Args:
            project_id: A string specifying the project ID.
            scopes: A list of strings specifying scopes.
        Returns:
            An AccessToken.
        """
        def encode_part(part):
            if isinstance(part, dict):
                part = json.dumps(part, separators=(',', ':')).encode('utf-8')

            return base64.urlsafe_b64encode(part).rstrip('=')

        header = encode_part({'typ': 'JWT', 'alg': 'RS256'})
        current_time = int(time.time())
        metadata = encode_part({'iss': self.key_name,
                                'aud': audience,
                                'scope': ' '.join(scopes),
                                'iat': current_time,
                                'exp': current_time + self.TOKEN_LIFETIME})

        signature = self.sign('.'.join([header, metadata]))
        return '.'.join([header, metadata, encode_part(signature)])

    def sign(self, blob):
        """ Signs a given payload.

        Args:
            blob: A binary type containing an arbitrary payload.
        Returns:
            A binary type containing the signed payload.
        """
        return self.key.sign(blob, self.PADDING, hashes.SHA256())

    def to_json(self):
        """ Serializes the key details as JSON.

        Returns:
            A string containing the JSON-encoded key details.
        """
        return json.dumps({'key_name': self.key_name, 'pem': self.pem})

    @classmethod
    def generate(cls, key_name):
        """ Creates a new key with the given name.

        Args:
            key_name: A string specifying the key name.
        Returns:
            A PrivateKey.
        """
        key = rsa.generate_private_key(PUBLIC_EXPONENT, KEY_SIZE,
                                       default_backend())
        return cls(key_name, key)

    @classmethod
    def from_json(cls, key_data):
        """ Creates a new key from a JSON-encoded string.

        Args:
            key_data: A JSON string containing key details.
        Returns:
            A PrivateKey.
        """
        try:
            key_details = json.loads(key_data)
        except (TypeError, ValueError):
            raise InvalidKey('Invalid JSON')

        try:
            key_name = key_details['key_name']
            pem = key_details['pem'].encode('utf-8')
        except KeyError as error:
            raise InvalidKey(str(error))

        return cls.from_pem(key_name, pem)

    @classmethod
    def from_pem(cls, key_name, pem):
        try:
            key = serialization.load_pem_private_key(
                pem, password=None, backend=default_backend())
        except ValueError as error:
            raise InvalidKey(str(error))

        return cls(key_name, key)


class PublicCertificate(object):
    """ Holds a certificate and its metadata. """
    ENCODING = serialization.Encoding.PEM

    def __init__(self, key_name, cert, node_name=None):
        """ Creates a new PublicCertificate.

        Args:
            key_name: A string specifying the key name.
            cert: A PEM-formatted binary type specifying the certificate.
            node_name: A string specifying the ZooKeeper node name.
        """
        self.key_name = key_name
        self.cert = cert
        self.node_name = node_name

    @property
    def expired(self):
        """ Indicates whether or not the certificate has expired.

        Returns:
            A boolean.
        """
        return datetime.datetime.utcnow() > self.cert.not_valid_after

    @property
    def pem(self):
        """ Serializes the certificate.

        Returns:
            A binary type containing a PEM-formatted certificate. """
        return self.cert.public_bytes(self.ENCODING)

    def to_json(self):
        """ Serializes the certificate details as JSON.

        Returns:
            A string containing the JSON-encoded certificate details.
        """
        return json.dumps({'key_name': self.key_name, 'pem': self.pem})

    @classmethod
    def from_key(cls, private_key, project_id):
        """ Creates a new certificate from a private key.

        Args:
            private_key: An RSAPrivateKey.
            project_id: A string specifying the project ID.
        Returns:
            A PublicCertificate.
        """
        # NameAttribute requires unicode objects in Python 2.
        if not isinstance(project_id, six.text_type):
            project_id = six.u(project_id)

        subject = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, project_id)])
        issuer = x509.Name(
            [x509.NameAttribute(NameOID.COMMON_NAME, u'AppScale')])

        cert = x509.CertificateBuilder().\
            subject_name(subject).\
            issuer_name(issuer).\
            public_key(private_key.key.public_key()).\
            serial_number(x509.random_serial_number()).\
            not_valid_before(datetime.datetime.utcnow()).\
            not_valid_after(datetime.datetime.utcnow() + CERTIFICATE_TTL).\
            sign(private_key.key, hashes.SHA256(), default_backend())

        return cls(private_key.key_name, cert)

    @classmethod
    def from_node(cls, node_name, cert_data):
        """ Creates a new certificate from a ZooKeeper node.

        Args:
            node_name: The name of the ZooKeeper node.
            cert_data: A JSON string containing the certificate details.
        Returns:
            A PublicCertificate.
        """
        try:
            cert_details = json.loads(cert_data)
        except ValueError:
            raise InvalidCertificate('Invalid JSON')

        try:
            key_name = cert_details['key_name']
            pem = cert_details['pem'].encode('utf-8')
        except KeyError as error:
            raise InvalidCertificate(str(error))

        try:
            cert = x509.load_pem_x509_certificate(pem, default_backend())
        except ValueError as error:
            raise InvalidCertificate(str(error))

        return cls(key_name, cert, node_name)
