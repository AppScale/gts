import os
from infrastructure_manager import InfrastructureManager
from utils import utils
import SOAPpy
from M2Crypto import SSL

__author__ = 'hiranya'

DEFAULT_HOST = '127.0.0.1'
DEFAULT_PORT = 8080

APPSCALE_DIR = '/etc/appscale/'

if __name__ == '__main__':
    utils.log('Starting AppScale Infrastructure Manager')
    secret = None
    while True:
        try:
            secret = utils.get_secret(APPSCALE_DIR + 'secret.key')
            break
        except Exception:
            utils.log('Waiting for the secret key')
            utils.sleep(5)
    utils.log('Found the secret set to: {0}'.format(secret))
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

    i = InfrastructureManager()
    SOAPpy.Config.simplify_objects = True
    server = SOAPpy.SOAPServer((DEFAULT_HOST, DEFAULT_PORT), ssl_context = ssl_context)
    server.registerFunction(i.describe_instances)
    server.registerFunction(i.run_instances)
    server.registerFunction(i.terminate_instances)
    while True:
        utils.log('All set. Starting Infrastructure Manager service on port {0}'.format(DEFAULT_PORT))
        server.serve_forever()
