""" Handles operations related to instance registration. """
import json
import logging
import random

from kazoo.exceptions import NodeExistsError, NoNodeError
from tornado import gen
from tornado.httpclient import AsyncHTTPClient

from appscale.admin.instance_manager.constants import VERSION_REGISTRATION_NODE
from appscale.admin.instance_manager.instance import Instance
from appscale.common import appscale_info
from appscale.common.constants import GAE_PREFIX, VERSION_PATH_SEPARATOR
from appscale.hermes.constants import HERMES_PORT

logger = logging.getLogger(__name__)


class RoutingClient(object):
  """ Handles operations related to instance registration. """
  def __init__(self, zk_client, private_ip, secret):
    """ Creates a new RoutingClient.

    Args:
      zk_client: A kazoo.client.KazooClient object.
      private_ip: A string specifying the current machine's private IP address.
      secret: A string specifying the deployment secret.
    """
    self._private_ip = private_ip
    self._secret = secret
    self._zk_client = zk_client

  @gen.coroutine
  def get_failed_instances(self):
    """ Fetches a list of failed instances on this machine according to HAProxy.

    Returns:
      A set of tuples specifying the version key and port of failed instances.
    """
    load_balancer = random.choice(appscale_info.get_load_balancer_ips())
    payload = {'include_lists': {
      'proxy': ['name', 'servers'],
      'proxy.server': ['private_ip', 'port', 'status']}
    }
    headers = {'AppScale-Secret': self._secret}
    url = 'http://{}:{}/stats/local/proxies'.format(load_balancer, HERMES_PORT)
    client = AsyncHTTPClient()

    response = yield client.fetch(url, headers=headers, body=json.dumps(payload),
                                  allow_nonstandard_methods=True)
    proxy_stats = json.loads(response.body)['proxies_stats']

    routed_versions = [server for server in proxy_stats
                       if server['name'].startswith(GAE_PREFIX)]
    failed_instances = set()
    for version in routed_versions:
      version_key = version['name'][len(GAE_PREFIX):]
      for server in version['servers']:
        if server['private_ip'] != self._private_ip:
          continue

        if not server['status'].startswith('DOWN'):
          continue

        failed_instances.add((version_key, server['port']))

    raise gen.Return(failed_instances)

  def register_instance(self, instance):
    """ Adds a registration entry for an instance.

    Args:
      instance: An Instance.
    """
    instance_entry = ':'.join([self._private_ip, str(instance.port)])
    instance_node = '/'.join([VERSION_REGISTRATION_NODE, instance.version_key,
                              instance_entry])

    try:
      self._zk_client.create(instance_node, instance.revision.encode('utf-8'))
    except NodeExistsError:
      self._zk_client.set(instance_node, instance.revision.encode('utf-8'))

  def unregister_instance(self, instance):
    """ Removes a registration entry for an instance.

    Args:
      instance: An Instance.
    """
    instance_entry = ':'.join([self._private_ip, str(instance.port)])
    instance_node = '/'.join([VERSION_REGISTRATION_NODE, instance.version_key,
                              instance_entry])

    try:
      self._zk_client.delete(instance_node)
    except NoNodeError:
      pass

  def declare_instance_nodes(self, running_instances):
    """ Removes dead ZooKeeper instance entries and adds running ones.

    Args:
      running_instances: An iterable of Instances.
    """
    registered_instances = set()
    for version_key in self._zk_client.get_children(VERSION_REGISTRATION_NODE):
      version_node = '/'.join([VERSION_REGISTRATION_NODE, version_key])
      for instance_entry in self._zk_client.get_children(version_node):
        machine_ip = instance_entry.split(':')[0]
        if machine_ip != self._private_ip:
          continue

        port = int(instance_entry.split(':')[-1])
        instance_node = '/'.join([version_node, instance_entry])
        revision = self._zk_client.get(instance_node)[0]
        revision_key = VERSION_PATH_SEPARATOR.join([version_key, revision])
        registered_instances.add(Instance(revision_key, port))

    # Remove outdated nodes.
    for instance in registered_instances - running_instances:
      self.unregister_instance(instance)

    # Add nodes for running instances.
    for instance in running_instances - registered_instances:
      self.register_instance(instance)
