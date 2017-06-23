import StringIO
import csv
import logging
import socket
import time
from collections import defaultdict
from datetime import datetime

import attr

from appscale.hermes.stats.constants import HAPROXY_STATS_SOCKET_PATH, MISSED
from appscale.hermes.stats.converter import include_list_name, Meta
from appscale.hermes.stats.unified_service_names import find_service_by_pxname


@include_list_name('proxy.listener')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class HAProxyListenerStats(object):
  """
  For more details see
  https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
  """
  pxname = attr.ib()  # proxy name
  svname = attr.ib()  # service name (FRONTEND, BACKEND or name of server/listener)
  scur = attr.ib()  # current sessions
  smax = attr.ib()  # max sessions
  slim = attr.ib()  # configured session limit
  stot = attr.ib()  # cumulative num of connections
  bin = attr.ib()  # bytes in
  bout = attr.ib()  # bytes out
  dreq = attr.ib()  # reqs denied because of security concerns
  dresp = attr.ib()  # resps denied because of security concerns
  ereq = attr.ib()  # request errors
  status = attr.ib()  # status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  pid = attr.ib()  # process id (0 for first instance, 1 for second, ...)
  iid = attr.ib()  # unique proxy id
  sid = attr.ib()  # server id (unique inside a proxy)
  type = attr.ib()  # (0=frontend, 1=backend, 2=server, 3=socket/listener)


@include_list_name('proxy.frontend')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class HAProxyFrontendStats(object):
  """
  For more details see
  https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
  """
  pxname = attr.ib()  # proxy name
  svname = attr.ib()  # service name (FRONTEND, BACKEND or name of server/listener)
  scur = attr.ib()  # current sessions
  smax = attr.ib()  # max sessions
  slim = attr.ib()  # configured session limit
  stot = attr.ib()  # cumulative num of connections
  bin = attr.ib()  # bytes in
  bout = attr.ib()  # bytes out
  dreq = attr.ib()  # reqs denied because of security concerns
  dresp = attr.ib()  # resps denied because of security concerns
  ereq = attr.ib()  # request errors
  status = attr.ib()  # status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  pid = attr.ib()  # process id (0 for first instance, 1 for second, ...)
  iid = attr.ib()  # unique proxy id
  type = attr.ib()  # (0=frontend, 1=backend, 2=server, 3=socket/listener)
  rate = attr.ib()  # num of sessions per second over last elapsed second
  rate_lim = attr.ib()  # configured limit on new sessions per second
  rate_max = attr.ib()  # max num of new sessions per second
  hrsp_1xx = attr.ib()  # http resps with 1xx code
  hrsp_2xx = attr.ib()  # http resps with 2xx code
  hrsp_3xx = attr.ib()  # http resps with 3xx code
  hrsp_4xx = attr.ib()  # http resps with 4xx code
  hrsp_5xx = attr.ib()  # http resps with 5xx code
  hrsp_other = attr.ib()  # http resps with other codes (protocol error)
  req_rate = attr.ib()  # HTTP reqs per second over last elapsed second
  req_rate_max = attr.ib()  # max num of HTTP reqs per second observed
  req_tot = attr.ib()  # total num of HTTP reqs received
  comp_in = attr.ib()  # num of HTTP resp bytes fed to the compressor
  comp_out = attr.ib()  # num of HTTP resp bytes emitted by the compressor
  comp_byp = attr.ib()  # num of bytes that bypassed the HTTP compressor
  comp_rsp = attr.ib()  # num of HTTP resps that were compressed


@include_list_name('proxy.backend')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class HAProxyBackendStats(object):
  """
  For more details see
  https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
  """
  pxname = attr.ib()  # proxy name
  svname = attr.ib()  # service name (FRONTEND, BACKEND or name of server/listener)
  qcur = attr.ib()  # current queued reqs. For the backend this reports the
  qmax = attr.ib()  # max value of qcur
  scur = attr.ib()  # current sessions
  smax = attr.ib()  # max sessions
  slim = attr.ib()  # configured session limit
  stot = attr.ib()  # cumulative num of connections
  bin = attr.ib()  # bytes in
  bout = attr.ib()  # bytes out
  dreq = attr.ib()  # reqs denied because of security concerns
  dresp = attr.ib()  # resps denied because of security concerns
  econ = attr.ib()  # num of reqs that encountered an error
  eresp = attr.ib()  # resp errors. srv_abrt will be counted here also
  wretr = attr.ib()  # num of times a connection to a server was retried
  wredis = attr.ib()  # num of times a request was redispatched
  status = attr.ib()  # status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  weight = attr.ib()  # total weight
  act = attr.ib()  # num of active servers
  bck = attr.ib()  # num of backup servers
  chkdown = attr.ib()  # num of UP->DOWN transitions. The backend counter counts
  lastchg = attr.ib()  # num of seconds since the last UP<->DOWN transition
  downtime = attr.ib()  # total downtime (in seconds). The value for the backend
  pid = attr.ib()  # process id (0 for first instance, 1 for second, ...)
  iid = attr.ib()  # unique proxy id
  lbtot = attr.ib()  # total num of times a server was selected, either for new
  type = attr.ib()  # (0=frontend, 1=backend, 2=server, 3=socket/listener)
  rate = attr.ib()  # num of sessions per second over last elapsed second
  rate_max = attr.ib()  # max num of new sessions per second
  hrsp_1xx = attr.ib()  # http resps with 1xx code
  hrsp_2xx = attr.ib()  # http resps with 2xx code
  hrsp_3xx = attr.ib()  # http resps with 3xx code
  hrsp_4xx = attr.ib()  # http resps with 4xx code
  hrsp_5xx = attr.ib()  # http resps with 5xx code
  hrsp_other = attr.ib()  # http resps with other codes (protocol error)
  cli_abrt = attr.ib()  # num of data transfers aborted by the client
  srv_abrt = attr.ib()  # num of data transfers aborted by the server
  comp_in = attr.ib()  # num of HTTP resp bytes fed to the compressor
  comp_out = attr.ib()  # num of HTTP resp bytes emitted by the compressor
  comp_byp = attr.ib()  # num of bytes that bypassed the HTTP compressor
  comp_rsp = attr.ib()  # num of HTTP resps that were compressed
  lastsess = attr.ib()  # num of seconds since last session assigned to
  qtime = attr.ib()  # the avg queue time in ms over the 1024 last reqs
  ctime = attr.ib()  # the avg connect time in ms over the 1024 last reqs
  rtime = attr.ib()  # the avg resp time in ms over the 1024 last reqs
  ttime = attr.ib()  # the avg total session time in ms over the 1024 last


@include_list_name('proxy.server')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class HAProxyServerStats(object):
  """
  For more details see
  https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
  """
  private_ip = attr.ib()
  port = attr.ib()
  pxname = attr.ib()  # proxy name
  svname = attr.ib()  # service name (FRONTEND, BACKEND or name of server/listener)
  qcur = attr.ib()  # current queued reqs. For the backend this reports the
  qmax = attr.ib()  # max value of qcur
  scur = attr.ib()  # current sessions
  smax = attr.ib()  # max sessions
  slim = attr.ib()  # configured session limit
  stot = attr.ib()  # cumulative num of connections
  bin = attr.ib()  # bytes in
  bout = attr.ib()  # bytes out
  dresp = attr.ib()  # resps denied because of security concerns.
  econ = attr.ib()  # num of reqs that encountered an error trying to
  eresp = attr.ib()  # resp errors. srv_abrt will be counted here also.
  wretr = attr.ib()  # num of times a connection to a server was retried.
  wredis = attr.ib()  # num of times a request was redispatched to another
  status = attr.ib()  # status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  weight = attr.ib()  # server weight
  act = attr.ib()  # server is active
  bck = attr.ib()  # server is backup
  chkfail = attr.ib()  # num of failed checks
  chkdown = attr.ib()  # num of UP->DOWN transitions
  lastchg = attr.ib()  # num of seconds since the last UP<->DOWN transition
  downtime = attr.ib()  # total downtime (in seconds)
  qlimit = attr.ib()  # configured maxqueue for the server
  pid = attr.ib()  # process id (0 for first instance, 1 for second, ...)
  iid = attr.ib()  # unique proxy id
  sid = attr.ib()  # server id (unique inside a proxy)
  throttle = attr.ib()  # current throttle percentage for the server
  lbtot = attr.ib()  # total num of times a server was selected
  tracked = attr.ib()  # id of proxy/server if tracking is enabled.
  type = attr.ib()  # (0=frontend, 1=backend, 2=server, 3=socket/listener)
  rate = attr.ib()  # num of sessions per second over last elapsed second
  rate_max = attr.ib()  # max num of new sessions per second
  check_status = attr.ib()  # status of last health check
  check_code = attr.ib()  # layer5-7 code, if available
  check_duration = attr.ib()  # time in ms took to finish last health check
  hrsp_1xx = attr.ib()  # http resps with 1xx code
  hrsp_2xx = attr.ib()  # http resps with 2xx code
  hrsp_3xx = attr.ib()  # http resps with 3xx code
  hrsp_4xx = attr.ib()  # http resps with 4xx code
  hrsp_5xx = attr.ib()  # http resps with 5xx code
  hrsp_other = attr.ib()  # http resps with other codes (protocol error)
  hanafail = attr.ib()  # failed health checks details
  cli_abrt = attr.ib()  # num of data transfers aborted by the client
  srv_abrt = attr.ib()  # num of data transfers aborted by the server
  lastsess = attr.ib()  # num of seconds since last session assigned to
  last_chk = attr.ib()  # last health check contents or textual error
  last_agt = attr.ib()  # last agent check contents or textual error
  qtime = attr.ib()  # the avg queue time in ms over the 1024 last reqs
  ctime = attr.ib()  # the avg connect time in ms over the 1024 last reqs
  rtime = attr.ib()  # the avg resp time in ms over the 1024 last reqs
  ttime = attr.ib()  # the avg total session time in ms over the 1024 last


ALL_HAPROXY_FIELDS = set(
  HAProxyListenerStats.__slots__ + HAProxyFrontendStats.__slots__
  + HAProxyBackendStats.__slots__ + HAProxyServerStats.__slots__
) - {'private_ip', 'port'}    # HAProxy stats doesn't include IP/Port columns
                              # But we add these values by ourselves

KNOWN_NON_INTEGER_FIELDS = {
  'pxname', 'svname', 'status', 'check_status', 'last_chk', 'last_agt'
}
INTEGER_FIELDS = set(ALL_HAPROXY_FIELDS) - KNOWN_NON_INTEGER_FIELDS


class InvalidHAProxyStats(ValueError):
  pass


@include_list_name('proxy')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProxyStats(object):
  """
  Object of ProxyStats is kind of structured container for all haproxy stats
  provided for the specific proxy (e.g.: TaskQueue, UserAppServer, ...).

  Only those Hermes nodes which are collocated with HAProxy collects this stats.
  """
  name = attr.ib()
  unified_service_name = attr.ib()  # taskqueue, appserver, datastore, ...
  application_id = attr.ib()  # application ID for appserver and None for others
  frontend = attr.ib(metadata={Meta.ENTITY: HAProxyFrontendStats})
  backend = attr.ib(metadata={Meta.ENTITY: HAProxyBackendStats})
  servers = attr.ib(metadata={Meta.ENTITY_LIST: HAProxyServerStats})
  listeners = attr.ib(metadata={Meta.ENTITY_LIST: HAProxyListenerStats})


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProxiesStatsSnapshot(object):
  utc_timestamp = attr.ib()  # UTC timestamp
  proxies_stats = attr.ib(metadata={Meta.ENTITY_LIST: ProxyStats})


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
  last_debug = 0

  def get_current(self):
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
        backend=backends[0], servers=servers, listeners=listeners
      )
      proxy_stats_list.append(proxy_stats)

    stats = ProxiesStatsSnapshot(
      utc_timestamp=time.mktime(datetime.now().timetuple()),
      proxies_stats=proxy_stats_list
    )
    logging.info("Prepared stats about {prox} proxies in {elapsed:.1f}s."
                 .format(prox=len(proxy_stats_list), elapsed=time.time()-start))
    return stats
