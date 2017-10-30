import StringIO
import csv
import logging
import socket
import time
from collections import defaultdict
from datetime import datetime

from appscale.hermes.stats.constants import HAPROXY_STATS_SOCKET_PATH, MISSED
from appscale.hermes.stats.models import (
  HAProxyListenerStats, HAProxyFrontendStats, HAProxyBackendStats,
  HAProxyServerStats, ALL_HAPROXY_FIELDS, INTEGER_FIELDS, ProxyStats,
  ProxiesStatsSnapshot
)
from appscale.hermes.stats.unified_service_names import find_service_by_pxname


class InvalidHAProxyStats(ValueError):
  pass


def _get_field_value(row, field_name):
  """ Private method for getting value from csv cell. """
  if field_name not in row:
    return MISSED
  value = row[field_name]
  if not value:
    return None
  if field_name in INTEGER_FIELDS:
    return int(value)
  return value


def get_stats():
  client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
  client.connect(HAPROXY_STATS_SOCKET_PATH)
  try:
    stats_output = StringIO.StringIO()
    client.send('show stat\n')
    while True:
      data = client.recv(1024)
      if not data:
        break
      stats_output.write(data)
    return stats_output
  finally:
    client.close()


class ProxiesStatsSource(object):

  first_run = True

  @staticmethod
  def get_current():
    """ Method which parses haproxy stats and returns detailed
    proxy statistics for all proxies.

    Returns:
      An instance of ProxiesStatsSnapshot.
    """
    start = time.time()
    # Get CSV table with haproxy stats
    csv_buf = get_stats()
    csv_buf.seek(2)  # Seek to the beginning but skip "# " in the first row
    table = csv.DictReader(csv_buf, delimiter=',')
    if ProxiesStatsSource.first_run:
      missed = ALL_HAPROXY_FIELDS - set(table.fieldnames)
      if missed:
        logging.warn("HAProxy stats fields {} are missed. Old version of HAProxy "
                     "is probably used (v1.5+ is expected)".format(list(missed)))
      ProxiesStatsSource.first_run = False

    # Parse haproxy stats output line by line
    parsed_objects = defaultdict(list)
    for row in table:
      proxy_name = row['pxname']
      service = find_service_by_pxname(proxy_name)
      svname = row['svname']
      extra_values = {}
      if svname == 'FRONTEND':
        stats_type = HAProxyFrontendStats
      elif svname == 'BACKEND':
        stats_type = HAProxyBackendStats
      elif row['qcur']:
        # Listener stats doesn't have "current queued requests" property
        stats_type = HAProxyServerStats
        private_ip, port = service.get_ip_port_by_svname(svname)
        extra_values['private_ip'] = private_ip
        extra_values['port'] = port
      else:
        stats_type = HAProxyListenerStats

      stats_values = {
        field: _get_field_value(row, field)
        for field in stats_type.__slots__
      }
      stats_values.update(**extra_values)

      stats = stats_type(**stats_values)
      parsed_objects[proxy_name].append(stats)

    # Attempt to merge separate stats object to ProxyStats instances
    proxy_stats_list = []
    for proxy_name, stats_objects in parsed_objects.iteritems():
      service = find_service_by_pxname(proxy_name)
      frontends = [stats for stats in stats_objects
                   if isinstance(stats, HAProxyFrontendStats)]
      backends = [stats for stats in stats_objects
                  if isinstance(stats, HAProxyBackendStats)]
      servers = [stats for stats in stats_objects
                 if isinstance(stats, HAProxyServerStats)]
      listeners = [stats for stats in stats_objects
                   if isinstance(stats, HAProxyListenerStats)]
      if len(frontends) != 1 or len(backends) != 1:
        raise InvalidHAProxyStats(
          "Exactly one FRONTEND and one BACKEND line should correspond to "
          "a single proxy. Proxy '{}' has {} frontends and {} backends"
            .format(proxy_name, len(frontends), len(backends))
        )

      # Create ProxyStats object which contains all stats related to the proxy
      service_name = service.name
      application_id = service.get_application_id_by_pxname(proxy_name)
      proxy_stats = ProxyStats(
        name=proxy_name, unified_service_name=service_name,
        application_id=application_id, frontend=frontends[0],
        backend=backends[0], servers=servers, listeners=listeners,
        servers_count=len(servers), listeners_count=len(listeners)
      )
      proxy_stats_list.append(proxy_stats)

    stats = ProxiesStatsSnapshot(
      utc_timestamp=time.mktime(datetime.now().timetuple()),
      proxies_stats=proxy_stats_list
    )
    logging.info("Prepared stats about {prox} proxies in {elapsed:.1f}s."
                 .format(prox=len(proxy_stats_list), elapsed=time.time()-start))
    return stats
