""" Collects information about running servers on the machine. """
from tornado.httpclient import HTTPClient

from appscale.admin.service_manager import ServiceManager
from appscale.common.monit_interface import MonitOperator, parse_entries


def get_combined_services():
  """ Merge list of services from Monit and ServiceManager.

  Returns:
    A dictionary mapping service name to service state.
  """
  http_client = HTTPClient()
  status_url = '{}/_status?format=xml'.format(MonitOperator.LOCATION)
  response = http_client.fetch(status_url)
  servers = parse_entries(response.body)

  servers.update({'-'.join([server.type, str(server.port)]): server.state
                  for server in ServiceManager.get_state()})
  return servers
