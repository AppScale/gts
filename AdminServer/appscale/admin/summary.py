""" Collects information about running servers on the machine. """
from tornado.httpclient import HTTPClient

from appscale.admin.service_manager import ServiceManager
from appscale.common import service_helper


def get_combined_services():
  """ Merge list of services from Systemd and ServiceManager.

  Returns:
    A dictionary mapping service name to service state.
  """
  servers = service_helper.list()
  servers.update({'-'.join([server.type, str(server.port)]): server.state
                  for server in ServiceManager.get_state()})
  return servers
