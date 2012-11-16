import os
from infrastructure_manager import InfrastructureManager
from utils import utils
import SOAPpy
from M2Crypto import SSL

__author__ = 'hiranya'

DEFAULT_HOST = '0.0.0.0'
DEFAULT_PORT = 17444

APPSCALE_DIR = '/etc/appscale/'

class InfrastructureManagerService:
    """
    SOAP based web service that exposes the InfrastructureManager
    implementation to the rest of AppScale.
    """

    def __init__(self, host, port = DEFAULT_PORT, ssl = True):
        """
        Initialize a new instance of the infrastructure manager service.

        Args:
            - host  Hostname to which the service should bind
            - port  Port of the service (Optional). Default to 17444
            - ssl   True if SSL should be engaged or False otherwise (Optional).
                    Defaults to True. When engaged, this implementation expects
                    to find the necessary SSL certificates in the /etc/appscale/certs
                    directory.
        """
        self.host = host
        self.port = port

        secret = None
        while True:
            try:
                secret = utils.get_secret(APPSCALE_DIR + 'secret.key')
                break
            except Exception:
                utils.log('Waiting for the secret key to become available')
                utils.sleep(5)
        utils.log('Found the secret set to: {0}'.format(secret))

        SOAPpy.Config.simplify_objects = True

        if ssl:
            utils.log('Checking for the certificate and private key')
            cert = APPSCALE_DIR + 'certs/mycert.pem'
            key = APPSCALE_DIR + 'certs/mykey.pem'
            while True:
                if os.path.exists(cert) and os.path.exists(key):
                    break
                else:
                    utils.log('Waiting for certificates')
                    utils.sleep(5)

            ssl_context = SSL.Context()
            ssl_context.load_cert(cert, key)
            self.server = SOAPpy.SOAPServer((host, port), ssl_context = ssl_context)
        else:
            self.server = SOAPpy.SOAPServer((host, port))

        i = InfrastructureManager()
        self.server.registerFunction(i.describe_instances)
        self.server.registerFunction(i.run_instances)
        self.server.registerFunction(i.terminate_instances)
        self.started = False

    def start(self):
        """
        Start the infrastructure manager service. This method blocks
        as long as the service is alive. The caller should handle the
        threading requirements
        """
        if self.started:
            utils.log('Warning - Start called on already running server')
        else:
            utils.log('Starting AppScale Infrastructure Manager on port: ' + str(self.port))
            self.started = True
            while self.started:
                self.server.serve_forever()

    def stop(self):
        """
        Stop the infrastructure manager service.
        """
        if self.started:
            utils.log('Stopping AppScale Infrastructure Manager')
            self.started = False
            self.server.shutdown()
        else:
            utils.log('Warning - Stop called on already stopped server')

if __name__ == '__main__':
    service = InfrastructureManagerService(DEFAULT_HOST, DEFAULT_PORT)
    service.start()