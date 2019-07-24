import json
import logging

from appscale.search.constants import SERVICE_SETTINGS_NODE

logger = logging.getLogger(__name__)


class SearchServiceSettings(object):

  def __init__(self, zk_client):
    self._zk_client = zk_client
    self._replication_factor = None
    self._shards_number = None
    self._max_shards_per_node = None
    zk_client.DataWatch(SERVICE_SETTINGS_NODE, self._update_settings)

  def _update_settings(self, new_settings, znode_stat):
    if not new_settings:
      logger.warning('Search service settings node is empty or missing ({}). '
                     'Using default settings.'.format(SERVICE_SETTINGS_NODE))
      return
    try:
      logger.info('Got new search service settings: {}'.format(new_settings))
      settings = json.loads(new_settings.decode('utf-8'))
      self._replication_factor = settings.get('replication_factor')
      self._shards_number = settings.get('shards_number')
      self._max_shards_per_node = settings.get('max_shards_per_node')
    except (ValueError, KeyError):
      logger.error('New settings is not valid settings JSON string.')
      self._replication_factor = None
      self._shards_number = None
      self._max_shards_per_node = None

  @property
  def replication_factor(self):
    if not self._replication_factor:
      logger.warning('replication_factor setting is not specified. '
                     'Using default value (number of search nodes).')
      # TODO store search nodes information in zk (e.g.: /appscale/search/nodes)
      try:
        with open('/etc/appscale/search2_ips') as search2_ips:
          return sum(1 for line in search2_ips if line.strip())
      except IOError:
        return 1
    return self._replication_factor

  @property
  def shards_number(self):
    if not self._shards_number:
      logger.warning('shards_number setting is not specified in zookeeper. '
                     'Using default value (1).')
      return 1
    return self._shards_number

  @property
  def max_shards_per_node(self):
    if not self._max_shards_per_node:
      logger.warning('max_shards_per_node setting is not specified in '
                     'zookeeper. Using default value (shards_number).')
      return self.shards_number
    return self._max_shards_per_node
