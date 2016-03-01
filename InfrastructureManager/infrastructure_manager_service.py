import json
import logging
import os
import SOAPpy
import sys

from M2Crypto import SSL

from infrastructure_manager import InfrastructureManager
from system_manager import SystemManager
from utils import utils
from utils.persistent_dictionary import PersistentStoreFactory

class InfrastructureManagerService:
  """
  SOAP based web service that exposes the InfrastructureManager
  implementation to the rest of AppScale.
  """

  # Default bind address for infrastructure manager service
  DEFAULT_HOST = '0.0.0.0'

  # Default port number for infrastructure manager service
  DEFAULT_PORT = 17444

  APPSCALE_DIR = '/etc/appscale/'

  CONFIG_FILE = 'conf.json'

  def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, ssl=True):
    """
    Initialize a new instance of the infrastructure manager service.

    Args:
      host  Hostname to which the service should bind (Optional). Defaults
            to 0.0.0.0.
      port  Port of the service (Optional). Default to 17444.
      ssl   True if SSL should be engaged or False otherwise (Optional).
            Defaults to True. When engaged, this implementation expects
            to find the necessary SSL certificates in the /etc/appscale/certs
            directory.
    """
    self.host = host
    self.port = port

    secret = None
    while True:
      try:
        secret = utils.get_secret(self.APPSCALE_DIR + 'secret.key')
        break
      except Exception:
        logging.info('Waiting for the secret key to become available')
        utils.sleep(5)
    logging.info('Found the secret set to: {0}'.format(secret))

    SOAPpy.Config.simplify_objects = True

    if ssl:
      logging.info('Checking for the certificate and private key')
      cert = self.APPSCALE_DIR + 'certs/mycert.pem'
      key = self.APPSCALE_DIR + 'certs/mykey.pem'
      while True:
        if os.path.exists(cert) and os.path.exists(key):
          break
        else:
          logging.info('Waiting for certificates')
          utils.sleep(5)

      ssl_context = SSL.Context()
      ssl_context.load_cert(cert, key)
      self.server = SOAPpy.SOAPServer((host, port), ssl_context=ssl_context)
    else:
      self.server = SOAPpy.SOAPServer((host, port))

    parent_dir = os.path.dirname(os.path.realpath(sys.argv[0]))
    config_file = os.path.join(parent_dir, self.CONFIG_FILE)
    if os.path.exists(config_file):
      file_handle = open(config_file, 'r')
      params = json.load(file_handle)
      file_handle.close()
      if params.has_key(PersistentStoreFactory.PARAM_STORE_TYPE):
        logging.info('Loading infrastructure manager configuration from ' +
                  config_file)
        i = InfrastructureManager(params)
      else:
        i = InfrastructureManager()
    else:
      i = InfrastructureManager()

    self.server.registerFunction(i.describe_instances)
    self.server.registerFunction(i.run_instances)
    self.server.registerFunction(i.terminate_instances)
    self.server.registerFunction(i.attach_disk)

    system_manager = SystemManager()

    self.server.registerFunction(system_manager.get_cpu_usage)
    self.server.registerFunction(system_manager.get_disk_usage)
    self.server.registerFunction(system_manager.get_memory_usage)
    self.server.registerFunction(system_manager.get_monit_summary)
    self.server.registerFunction(system_manager.get_swap_usage)

    self.started = False

  def start(self):
    """
    Start the infrastructure manager service. This method blocks
    as long as the service is alive. The caller should handle the
    threading requirements
    """
    if self.started:
      logging.warn('Start called on already running server')
    else:
      logging.info('Starting AppScale Infrastructure Manager on port: '
        '{}'.format(str(self.port)))
      self.started = True
      while self.started:
        self.server.serve_forever()

  def stop(self):
    """
    Stop the infrastructure manager service.
    """
    if self.started:
      logging.info('Stopping AppScale Infrastructure Manager')
      self.started = False
      self.server.shutdown()
    else:
      logging.warn('Stop called on already stopped server')

if __name__ == '__main__':
  logging.basicConfig(level=logging.INFO,
    format='%(levelname)-8s %(asctime)s %(filename)s:%(lineno)s] %(message)s')

  service = InfrastructureManagerService()
  service.start()
