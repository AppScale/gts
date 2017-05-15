import json
import logging
import urllib

from appscale.hermes import helper, constants
from appscale.hermes.helper import JSONTags
from appscale.hermes.stats.pubsub_base import StatsSubscriber


class NodeStatsPortalSender(StatsSubscriber):
  def __init__(self):
    self._portal_method = '/{deployment_id}/stats/cluster/nodes'

  def receive(self, nodes_stats):
    deployment_id = helper.get_deployment_id()
    # If the deployment is not registered, skip.
    if not deployment_id:
      return

    # Send request to AppScale Portal.
    portal_path = self._portal_method.format(deployment_id=deployment_id)
    url = "{0}{1}".format(constants.PORTAL_URL, portal_path)
    data = {
      'deployment_id': deployment_id,
      'nodes_stats': json.dumps({
        node_ip: [snapshot.todict() for snapshot in snapshots]
        for node_ip, snapshots in nodes_stats.iteritems()
      })
    }
    snapshots_num = sum(len(snapshots) for snapshots in nodes_stats.values())
    logging.debug(
      "Sending {snapshots} node stats snapshots about {nodes} nodes to the "
      "AppScale Portal".format(snapshots=snapshots_num, nodes=len(nodes_stats))
    )

    request = helper.create_request(url=url, method='POST',
                                    body=urllib.urlencode(data))
    response = helper.urlfetch(request)

    if not response[JSONTags.SUCCESS]:
      logging.error("Inaccessible resource: {}".format(url))
      return


class ProcessesStatsPortalSender(StatsSubscriber):
  def __init__(self):
    self._portal_method = '/{deployment_id}/stats/cluster/processes'

  def receive(self, processes_stats):
    # TODO
    pass


class ProxiesStatsPortalSender(StatsSubscriber):
  def __init__(self):
    self._portal_method = '/{deployment_id}/stats/cluster/proxies'

  def receive(self, proxies_stats):
    # TODO
    pass
