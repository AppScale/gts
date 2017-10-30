import attr

from appscale.hermes.stats.converter import include_list_name, Meta


@include_list_name('node.cpu')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeCPU(object):
  user = attr.ib()
  system = attr.ib()
  idle = attr.ib()
  percent = attr.ib()
  count = attr.ib()


@include_list_name('node.loadavg')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeLoadAvg(object):
  last_1min = attr.ib()
  last_5min = attr.ib()
  last_15min = attr.ib()


@include_list_name('node.memory')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeMemory(object):
  total = attr.ib()
  available = attr.ib()
  used = attr.ib()


@include_list_name('node.swap')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeSwap(object):
  total = attr.ib()
  free = attr.ib()
  used = attr.ib()


@include_list_name('node.disk_io')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeDiskIO(object):
  read_count = attr.ib()
  write_count = attr.ib()
  read_bytes = attr.ib()
  write_bytes = attr.ib()
  read_time = attr.ib()
  write_time = attr.ib()


@include_list_name('node.partition')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodePartition(object):
  total = attr.ib()
  free = attr.ib()
  used = attr.ib()


@include_list_name('node.network')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeNetwork(object):
  bytes_sent = attr.ib()
  bytes_recv = attr.ib()
  packets_sent = attr.ib()
  packets_recv = attr.ib()
  errin = attr.ib()
  errout = attr.ib()
  dropin = attr.ib()
  dropout = attr.ib()
  connections_num = attr.ib()


@include_list_name('node')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class NodeStatsSnapshot(object):
  """
  Object of NodeStatsSnapshot is kind of structured container for all info related
  to resources used on the machine. Additionally it stores UTC timestamp
  which reflects the moment when stats were taken.

  Every Hermes node collects its machine statistics, but Master node also
  requests this statistics of all nodes in cluster.
  """
  utc_timestamp = attr.ib()
  private_ip = attr.ib()
  cpu = attr.ib(metadata={Meta.ENTITY: NodeCPU})
  memory = attr.ib(metadata={Meta.ENTITY: NodeMemory})
  swap = attr.ib(metadata={Meta.ENTITY: NodeSwap})
  disk_io = attr.ib(metadata={Meta.ENTITY: NodeDiskIO})
  partitions_dict = attr.ib(metadata={Meta.ENTITY_DICT: NodePartition})
  network = attr.ib(metadata={Meta.ENTITY: NodeNetwork})
  loadavg = attr.ib(metadata={Meta.ENTITY: NodeLoadAvg})


@include_list_name('process.cpu')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessCPU(object):
  user = attr.ib()
  system = attr.ib()
  percent = attr.ib()


@include_list_name('process.memory')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessMemory(object):
  resident = attr.ib()
  virtual = attr.ib()
  unique = attr.ib()


@include_list_name('process.disk_io')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessDiskIO(object):
  read_count = attr.ib()
  write_count = attr.ib()
  read_bytes = attr.ib()
  write_bytes = attr.ib()


@include_list_name('process.network')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessNetwork(object):
  connections_num = attr.ib()


@include_list_name('process.children_stats_sum')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessChildrenSum(object):
  cpu = attr.ib(metadata={Meta.ENTITY: ProcessCPU})
  memory = attr.ib(metadata={Meta.ENTITY: ProcessMemory})
  disk_io = attr.ib(metadata={Meta.ENTITY: ProcessDiskIO})
  network = attr.ib(metadata={Meta.ENTITY: ProcessNetwork})
  threads_num = attr.ib()


@include_list_name('process')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessStats(object):
  """
  Object of ProcessStats is kind of structured container for all info related
  to resources used by specific process. Additionally it stores UTC timestamp
  which reflects the moment when stats were taken.

  Every Hermes node collects its processes statistics, but Master node also
  requests this statistics of all nodes in cluster.
  All processes started by monit should be profiled.
  """
  pid = attr.ib()
  monit_name = attr.ib()

  unified_service_name = attr.ib()  #| These 4 fields are primary key
  application_id = attr.ib()        #| for an instance of appscale service
  private_ip = attr.ib()            #| - Application ID can be None if
  port = attr.ib()                  #|   process is not related to specific app
                                    #| - port can be missed if it is not
                                    #|   mentioned in monit process name
  cmdline = attr.ib()
  cpu = attr.ib(metadata={Meta.ENTITY: ProcessCPU})
  memory = attr.ib(metadata={Meta.ENTITY: ProcessMemory})
  disk_io = attr.ib(metadata={Meta.ENTITY: ProcessDiskIO})
  network = attr.ib(metadata={Meta.ENTITY: ProcessNetwork})
  threads_num = attr.ib()
  children_stats_sum = attr.ib(metadata={Meta.ENTITY: ProcessChildrenSum})
  children_num = attr.ib()


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProcessesStatsSnapshot(object):
  utc_timestamp = attr.ib()  # UTC timestamp
  processes_stats = attr.ib(metadata={Meta.ENTITY_LIST: ProcessStats})


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
  servers_count = attr.ib()  # number of servers serving this proxy
  listeners_count = attr.ib()  # number of listeners serving this proxy


@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class ProxiesStatsSnapshot(object):
  utc_timestamp = attr.ib()  # UTC timestamp
  proxies_stats = attr.ib(metadata={Meta.ENTITY_LIST: ProxyStats})
