""" Collects information about running servers on the machine. """
from tornado.httpclient import HTTPClient

from appscale.admin.service_manager import ServiceManager


def get_services():
  """ Get dictionary of services from ServiceManager.

  Returns:
    A dictionary mapping service name to service state.
  """
  servers = {'-'.join([server.type, str(server.port)]): server.state
             for server in ServiceManager.get_state()}
  return servers
