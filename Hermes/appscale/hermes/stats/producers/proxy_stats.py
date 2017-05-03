import StringIO
import csv
import logging
import subprocess
import time
from collections import defaultdict
from datetime import datetime

import attr

from appscale.hermes.constants import MISSED, HAPROXY_STATS_SOCKET_PATH
from appscale.hermes.stats.pubsub_base import StatsSource
from appscale.hermes.stats.producers.shared import WrongIncludeLists, stats_entity_to_dict
from appscale.hermes.stats.unified_service_names import find_service_by_pxname


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


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProxiesStatsSnapshot(object):
  utc_timestamp = attr.ib()  # UTC timestamp
  proxies_stats = attr.ib()  # list[ProxyStats]

  def todict(self, include_lists):
    return proxies_stats_snapshot_to_dict(self, include_lists)


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProxyStats(object):
  """
  Object of ProxyStats is kind of structured container for all haproxy stats
  provided for the specific proxy (e.g.: TaskQueue, UserAppServer, ...)

  Only those Hermes nodes which are collocated with HAProxy collects this stats.
  """
  name = attr.ib()
  unified_service_name = attr.ib()  # taskqueue, appserver, datastore, ...
  application_id = attr.ib()  # application ID for appserver and None for others
  frontend = attr.ib()  # HAProxyFrontendStats
  backend = attr.ib()  # HAProxyBackendStats
  servers = attr.ib()  # list[HAProxyServerStats]
  listeners = attr.ib()  # list[HAProxyListenerStats]


def _get_field_value(row, field_name):
  """ Private method for getting value from csv cell """
  if field_name not in row:
    return MISSED
  value = row[field_name]
  if not value:
    return None
  if field_name in INTEGER_FIELDS:
    return int(value)
  return value


class ProxiesStatsSource(StatsSource):
  def __init__(self):
    super(ProxiesStatsSource, self).__init__("ProxiesStats")

  def get_current(self):
    """ Method which parses haproxy stats and returns detailed
    proxy statistics for all proxies.
  
    Returns:
      ProxiesStatsSnapshot
    """
    # Get CSV table with haproxy stats
    csv_text = subprocess.check_output(
      "echo 'show stat' | socat stdio unix-connect:{}"
        .format(HAPROXY_STATS_SOCKET_PATH), shell=True
    ).replace("# ", "", 1)
    csv_cache = StringIO.StringIO(csv_text)
    table = csv.DictReader(csv_cache, delimiter=',')
    missed = ALL_HAPROXY_FIELDS - set(table.fieldnames)
    if missed:
      logging.warn("HAProxy stats fields {} are missed. Old version of HAProxy "
                   "is probably used (v1.5+ is expected)".format(list(missed)))

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

    return ProxiesStatsSnapshot(
      utc_timestamp=time.mktime(datetime.utcnow().timetuple()),
      proxies_stats=proxy_stats_list
    )


def proxy_stats_from_dict(dictionary, strict=False):
  """ Addition to attr.asdict function.
  Args:
    dictionary: a dict containing fields for building ProxyStats obj.
    strict: a boolean. If True, any missed field will result in IndexError.
            If False, all missed values will be replaced with MISSED.
  Returns:
    an instance of ProxyStats
  Raises:
    IndexError if strict is set to True and dictionary is lacking any fields
  """
  frontend = dictionary.get('frontend', {})
  backend = dictionary.get('backend', {})
  servers = dictionary.get('servers', [])
  listeners = dictionary.get('listeners', [])

  if strict:
    return ProxyStats(
      name=dictionary['name'],
      unified_service_name=dictionary['unified_service_name'],
      application_id=dictionary['application_id'],
      frontend=HAProxyFrontendStats(
        **{frontend[field] for field in HAProxyFrontendStats.__slots__}),
      backend=HAProxyBackendStats(
        **{backend[field] for field in HAProxyBackendStats.__slots__}),
      servers=[
        HAProxyServerStats(
          **{server[field] for field in HAProxyServerStats.__slots__})
        for server in servers
      ],
      listeners=[
        HAProxyListenerStats(
          **{listener[field] for field in HAProxyListenerStats.__slots__})
        for listener in listeners
      ]
    )
  return ProxyStats(
    name=dictionary.get('name', MISSED),
    unified_service_name=dictionary.get('unified_service_name', MISSED),
    application_id=dictionary.get('application_id', MISSED),
    frontend=HAProxyFrontendStats(
      **{frontend.get(field, MISSED)
         for field in HAProxyFrontendStats.__slots__}),
    backend=HAProxyBackendStats(
      **{backend.get(field, MISSED)
         for field in HAProxyBackendStats.__slots__}),
    servers=[
      HAProxyServerStats(
        **{server.get(field, MISSED)
           for field in HAProxyServerStats.__slots__})
      for server in servers
    ],
    listeners=[
      HAProxyListenerStats(
        **{listener.get(field, MISSED)
           for field in HAProxyListenerStats.__slots__})
      for listener in listeners
    ]
  )


def proxies_stats_snapshot_from_dict(dictionary, strict=False):
  """ Addition to attr.asdict function.
  Args:
    dictionary: a dict containing fields for building ProxiesStatsSnapshot obj.
    strict: a boolean. If True, any missed field will result in IndexError.
            If False, all missed values will be replaced with MISSED.
  Returns:
    an instance of ProxiesStatsSnapshot
  Raises:
    IndexError if strict is set to True and dictionary is lacking any fields
  """
  if strict:
    return ProxiesStatsSnapshot(
      utc_timestamp=dictionary['utc_timestamp'],
      proxies_stats=[
        ProxyStats.fromdict(proxy_stats, strict)
        for proxy_stats in dictionary['proxies_stats']
      ]
    )
  return ProxiesStatsSnapshot(
    utc_timestamp=dictionary.get('utc_timestamp', MISSED),
    proxies_stats=[
      ProxyStats.fromdict(proxy_stats, strict)
      for proxy_stats in dictionary.get('proxies_stats', [])
    ]
  )


def proxies_stats_snapshot_to_dict(stats, include_lists=None):
  """ Converts an instance of ProxiesStatsSnapshot to dictionary. Optionally
  it can
  
  Args:
    stats: an instance of ProxiesStatsSnapshot to render
    include_lists: a dictionary containing include lists for rendering
        ProxyStats entity, HAProxyFrontendStats entity, ...
        e.g.: {
          'proxy' ['name', 'unified_service_name', 'application_id', 'frontend',
                   'backend'],
          'proxy.frontend': ['scur', 'smax', 'rate', 'req_rate', 'req_tot'],
          'proxy.backend': ['qcur', 'scur', 'hrsp_5xx', 'qtime', 'rtime'],
        }
  Returns:
    a dictionary representing an instance of ProxiesStatsSnapshot
  Raises:
    WrongIncludeLists if unknown field was specified in include_lists
  """
  if include_lists and not isinstance(include_lists, dict):
    raise WrongIncludeLists('include_lists should be dict, actual type is {}'
                            .format(type(include_lists)))
  
  include = include_lists or {}
  proxy_stats_fields = set(include.pop('proxy', ProxyStats.__slots__))
  nested_entities = {
    'frontend': set(include.pop('proxy.frontend',
                                HAProxyFrontendStats.__slots__)),
    'backend': set(include.pop('proxy.backend', HAProxyBackendStats.__slots__)),
  }
  nested_lists = {
    'servers': set(include.pop('proxy.servers', HAProxyServerStats.__slots__)),
    'listeners': set(include.pop('proxy.listeners',
                                 HAProxyListenerStats.__slots__)),
  }

  if include:
    # All known include lists were popped
    raise WrongIncludeLists(u'Following include lists are not recognized: {}'
                            .format(include))

  try:
    rendered_proxies = []
    for proxy in stats.proxies_stats:
      rendered_proxy = {}

      for field in proxy_stats_fields:
        value = getattr(proxy, field)
        if field in nested_entities:
          # render nested entity like HAProxyFrontendStats
          rendered_proxy[field] = \
            stats_entity_to_dict(value, nested_entities[field])
        elif field in nested_lists:
          # render nested list like list of HAProxyServerStats
          rendered_proxy[field] = [
            stats_entity_to_dict(entity, nested_lists[field])
            for entity in value
          ]
        else:
          rendered_proxy[field] = value

      rendered_proxies.append(rendered_proxy)
  except AttributeError as err:
    raise WrongIncludeLists(u'Unknown field in include lists ({})'.format(err))

  return {
    'utc_timestamp': stats.utc_timestamp,
    'proxies_stats': rendered_proxies
  }
