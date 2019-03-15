import cStringIO
import csv
import logging
import socket
import time
from collections import defaultdict
from datetime import datetime
import re
import os
import psutil

import attr

from appscale.hermes.constants import (
  HAPROXY_APPS_STATS_SOCKET_PATH,
  HAPROXY_SERVICES_STATS_SOCKET_PATH,
  HAPROXY_APPS_CONFIGS_DIR,
  HAPROXY_SERVICES_CONFIGS_DIR, MISSED,
)
from appscale.hermes.converter import include_list_name, Meta
from appscale.hermes.unified_service_names import find_service_by_pxname

logger = logging.getLogger(__name__)


class BoundIpPortNotFound(Exception):
  pass


class HAProxyStatsParsingError(Exception):
  pass


class InvalidHAProxyStats(ValueError):
  pass


HEADER_1_5_PLUS = [
  "pxname", "svname", "qcur", "qmax", "scur", "smax", "slim", "stot", "bin",
  "bout", "dreq", "dresp", "ereq", "econ", "eresp", "wretr", "wredis", "status",
  "weight", "act", "bck", "chkfail", "chkdown", "lastchg", "downtime", "qlimit",
  "pid", "iid", "sid", "throttle", "lbtot", "tracked", "type", "rate",
  "rate_lim", "rate_max", "check_status", "check_code", "check_duration",
  "hrsp_1xx", "hrsp_2xx", "hrsp_3xx", "hrsp_4xx", "hrsp_5xx", "hrsp_other",
  "hanafail", "req_rate", "req_rate_max", "req_tot", "cli_abrt", "srv_abrt",
  "comp_in", "comp_out", "comp_byp", "comp_rsp", "lastsess", "last_chk",
  "last_agt", "qtime", "ctime", "rtime", "ttime"
]
ACCEPTABLE_HEADER = [
  "pxname", "svname", "qcur", "qmax", "scur", "smax", "slim", "stot", "bin",
  "bout", "dreq", "dresp", "ereq", "econ", "eresp", "wretr", "wredis", "status",
  "weight", "act", "bck", "chkfail", "chkdown", "lastchg", "downtime", "qlimit",
  "pid", "iid", "sid", "throttle", "lbtot", "tracked", "type", "rate",
  "rate_lim", "rate_max", "check_status", "check_code", "check_duration",
  "hrsp_1xx", "hrsp_2xx", "hrsp_3xx", "hrsp_4xx", "hrsp_5xx", "hrsp_other",
  "hanafail", "req_rate", "req_rate_max", "req_tot", "cli_abrt", "srv_abrt"
]

# HAProxy stats fields numeration.
# For more details see
# https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
PXNAME = 0
SVNAME = 1
QCUR = 2
QMAX = 3
SCUR = 4
SMAX = 5
SLIM = 6
STOT = 7
BIN = 8
BOUT = 9
DREQ = 10
DRESP = 11
EREQ = 12
ECON = 13
ERESP = 14
WRETR = 15
WREDIS = 16
STATUS = 17
WEIGHT = 18
ACT = 19
BCK = 20
CHKFAIL = 21
CHKDOWN = 22
LASTCHG = 23
DOWNTIME = 24
QLIMIT = 25
PID = 26
IID = 27
SID = 28
THROTTLE = 29
LBTOT = 30
TRACKED = 31
TYPE = 32
RATE = 33
RATE_LIM = 34
RATE_MAX = 35
CHECK_STATUS = 36
CHECK_CODE = 37
CHECK_DURATION = 38
HRSP_1XX = 39
HRSP_2XX = 40
HRSP_3XX = 41
HRSP_4XX = 42
HRSP_5XX = 43
HRSP_OTHER = 44
HANAFAIL = 45
REQ_RATE = 46
REQ_RATE_MAX = 47
REQ_TOT = 48
CLI_ABRT = 49
SRV_ABRT = 50
COMP_IN = 51
COMP_OUT = 52
COMP_BYP = 53
COMP_RSP = 54
LASTSESS = 55
LAST_CHK = 56
LAST_AGT = 57
QTIME = 58
CTIME = 59
RTIME = 60
TTIME = 61

COLUMNS_NUMBER = 62

HAPROXY_STATS_STR_COLUMNS = [
  PXNAME, SVNAME, STATUS, CHECK_STATUS, LAST_CHK, LAST_AGT
]
HAPROXY_STATS_INT_COLUMNS = [
  # All stats columns but:
  # pxname, svname, status, check_status, last_chk, last_agt
  QCUR, QMAX, SCUR, SMAX, SLIM, STOT, BIN, BOUT, DREQ, DRESP,
  EREQ, ECON, ERESP, WRETR, WREDIS, WEIGHT, ACT, BCK, CHKFAIL, CHKDOWN,
  LASTCHG, DOWNTIME, QLIMIT, PID, IID, SID, THROTTLE, LBTOT, TRACKED, TYPE,
  RATE, RATE_LIM, RATE_MAX, CHECK_CODE, CHECK_DURATION, HRSP_1XX,
  HRSP_2XX, HRSP_3XX, HRSP_4XX, HRSP_5XX, HRSP_OTHER, HANAFAIL, REQ_RATE,
  REQ_RATE_MAX, REQ_TOT, CLI_ABRT, SRV_ABRT, COMP_IN, COMP_OUT, COMP_BYP,
  COMP_RSP, LASTSESS, QTIME, CTIME, RTIME, TTIME
]


def att():
  """ A short for `attr.ib(default=None)` which helps to leave
  some place for descriptive comment.
  """
  return attr.ib(default=None)


@include_list_name('proxy.listener')
@attr.s(hash=False, slots=True)
class HAProxyListenerStats(object):
  """
  For more details see
  https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
  """
  pxname = att()  # proxy name
  svname = att()  # service name (FRONTEND, BACKEND or server/listener name)
  scur = att()  # current sessions
  smax = att()  # max sessions
  slim = att()  # configured session limit
  stot = att()  # cumulative num of connections
  bin = att()  # bytes in
  bout = att()  # bytes out
  dreq = att()  # reqs denied because of security concerns
  dresp = att()  # resps denied because of security concerns
  ereq = att()  # request errors
  status = att()  # status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  pid = att()  # process id (instance serial number, e.g.: 0, 1, ..)
  iid = att()  # unique proxy id
  sid = att()  # server id (unique inside a proxy)
  type = att()  # (0=frontend, 1=backend, 2=server, 3=socket/listener)

  @staticmethod
  def from_stats_csv_row(row):
    """ Creates an instance of HAProxyListenerStats using empty
    constructor and manual filling of all attributes.
    It works ~150% faster than keyword arguments.

    Args:
      row: A list of values in stats CSV row.
    Returns:
      An instance HAProxyListenerStats.
    """
    stats = HAProxyListenerStats()
    stats.pxname = row[PXNAME]
    stats.svname = row[SVNAME]
    stats.scur = row[SCUR]
    stats.smax = row[SMAX]
    stats.slim = row[SLIM]
    stats.stot = row[STOT]
    stats.bin = row[BIN]
    stats.bout = row[BOUT]
    stats.dreq = row[DREQ]
    stats.dresp = row[DRESP]
    stats.ereq = row[EREQ]
    stats.status = row[STATUS]
    stats.pid = row[PID]
    stats.iid = row[IID]
    stats.sid = row[SID]
    stats.type = row[TYPE]
    return stats


@include_list_name('proxy.frontend')
@attr.s(hash=False, slots=True)
class HAProxyFrontendStats(object):
  """
  For more details see
  https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
  """
  pxname = att()  # proxy name
  svname = att()  # service name (FRONTEND, BACKEND or server/listener name)
  scur = att()  # current sessions
  smax = att()  # max sessions
  slim = att()  # configured session limit
  stot = att()  # cumulative num of connections
  bin = att()  # bytes in
  bout = att()  # bytes out
  dreq = att()  # reqs denied because of security concerns
  dresp = att()  # resps denied because of security concerns
  ereq = att()  # request errors
  status = att()  # status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  pid = att()  # process id (0 for first instance, 1 for second, ...)
  iid = att()  # unique proxy id
  type = att()  # (0=frontend, 1=backend, 2=server, 3=socket/listener)
  rate = att()  # num of sessions per second over last elapsed second
  rate_lim = att()  # configured limit on new sessions per second
  rate_max = att()  # max num of new sessions per second
  hrsp_1xx = att()  # http resps with 1xx code
  hrsp_2xx = att()  # http resps with 2xx code
  hrsp_3xx = att()  # http resps with 3xx code
  hrsp_4xx = att()  # http resps with 4xx code
  hrsp_5xx = att()  # http resps with 5xx code
  hrsp_other = att()  # http resps with other codes (protocol error)
  req_rate = att()  # HTTP reqs per second over last elapsed second
  req_rate_max = att()  # max num of HTTP reqs per second observed
  req_tot = att()  # total num of HTTP reqs received
  comp_in = att()  # num of HTTP resp bytes fed to the compressor
  comp_out = att()  # num of HTTP resp bytes emitted by the compressor
  comp_byp = att()  # num of bytes that bypassed the HTTP compressor
  comp_rsp = att()  # num of HTTP resps that were compressed

  @staticmethod
  def from_stats_csv_row(row):
    """ Creates an instance of HAProxyFrontendStats using empty
    constructor and manual filling of all attributes.
    It works ~150% faster than keyword arguments.

    Args:
      row: A list of values in stats CSV row.
    Returns:
      An instance HAProxyFrontendStats.
    """
    stats = HAProxyFrontendStats()
    stats.pxname = row[PXNAME]
    stats.svname = row[SVNAME]
    stats.scur = row[SCUR]
    stats.smax = row[SMAX]
    stats.slim = row[SLIM]
    stats.stot = row[STOT]
    stats.bin = row[BIN]
    stats.bout = row[BOUT]
    stats.dreq = row[DREQ]
    stats.dresp = row[DRESP]
    stats.ereq = row[EREQ]
    stats.status = row[STATUS]
    stats.pid = row[PID]
    stats.iid = row[IID]
    stats.type = row[TYPE]
    stats.rate = row[RATE]
    stats.rate_lim = row[RATE_LIM]
    stats.rate_max = row[RATE_MAX]
    stats.hrsp_1xx = row[HRSP_1XX]
    stats.hrsp_2xx = row[HRSP_2XX]
    stats.hrsp_3xx = row[HRSP_3XX]
    stats.hrsp_4xx = row[HRSP_4XX]
    stats.hrsp_5xx = row[HRSP_5XX]
    stats.hrsp_other = row[HRSP_OTHER]
    stats.req_rate = row[REQ_RATE]
    stats.req_rate_max = row[REQ_RATE_MAX]
    stats.req_tot = row[REQ_TOT]
    stats.comp_in = row[COMP_IN]
    stats.comp_out = row[COMP_OUT]
    stats.comp_byp = row[COMP_BYP]
    stats.comp_rsp = row[COMP_RSP]
    return stats


@include_list_name('proxy.backend')
@attr.s(hash=False, slots=True)
class HAProxyBackendStats(object):
  """
  For more details see
  https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
  """
  pxname = att()  # proxy name
  svname = att()  # service name (FRONTEND, BACKEND or name of server/listener)
  qcur = att()  # current queued reqs. For the backend this reports the
  qmax = att()  # max value of qcur
  scur = att()  # current sessions
  smax = att()  # max sessions
  slim = att()  # configured session limit
  stot = att()  # cumulative num of connections
  bin = att()  # bytes in
  bout = att()  # bytes out
  dreq = att()  # reqs denied because of security concerns
  dresp = att()  # resps denied because of security concerns
  econ = att()  # num of reqs that encountered an error
  eresp = att()  # resp errors. srv_abrt will be counted here also
  wretr = att()  # num of times a connection to a server was retried
  wredis = att()  # num of times a request was redispatched
  status = att()  # status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  weight = att()  # total weight
  act = att()  # num of active servers
  bck = att()  # num of backup servers
  chkdown = att()  # num of UP->DOWN transitions. The backend counter counts
  lastchg = att()  # num of seconds since the last UP<->DOWN transition
  downtime = att()  # total downtime (in seconds). The value for the backend
  pid = att()  # process id (0 for first instance, 1 for second, ...)
  iid = att()  # unique proxy id
  lbtot = att()  # total num of times a server was selected, either for new
  type = att()  # (0=frontend, 1=backend, 2=server, 3=socket/listener)
  rate = att()  # num of sessions per second over last elapsed second
  rate_max = att()  # max num of new sessions per second
  hrsp_1xx = att()  # http resps with 1xx code
  hrsp_2xx = att()  # http resps with 2xx code
  hrsp_3xx = att()  # http resps with 3xx code
  hrsp_4xx = att()  # http resps with 4xx code
  hrsp_5xx = att()  # http resps with 5xx code
  hrsp_other = att()  # http resps with other codes (protocol error)
  cli_abrt = att()  # num of data transfers aborted by the client
  srv_abrt = att()  # num of data transfers aborted by the server
  comp_in = att()  # num of HTTP resp bytes fed to the compressor
  comp_out = att()  # num of HTTP resp bytes emitted by the compressor
  comp_byp = att()  # num of bytes that bypassed the HTTP compressor
  comp_rsp = att()  # num of HTTP resps that were compressed
  lastsess = att()  # num of seconds since last session assigned to
  qtime = att()  # the avg queue time in ms over the 1024 last reqs
  ctime = att()  # the avg connect time in ms over the 1024 last reqs
  rtime = att()  # the avg resp time in ms over the 1024 last reqs
  ttime = att()  # the avg total session time in ms over the 1024 last

  @staticmethod
  def from_stats_csv_row(row):
    """ Creates an instance of HAProxyBackendStats using empty
    constructor and manual filling of all attributes.
    It works ~150% faster than keyword arguments.

    Args:
      row: A list of values in stats CSV row.
    Returns:
      An instance HAProxyBackendStats.
    """
    stats = HAProxyBackendStats()
    stats.pxname = row[PXNAME]
    stats.svname = row[SVNAME]
    stats.qcur = row[QCUR]
    stats.qmax = row[QMAX]
    stats.scur = row[SCUR]
    stats.smax = row[SMAX]
    stats.slim = row[SLIM]
    stats.stot = row[STOT]
    stats.bin = row[BIN]
    stats.bout = row[BOUT]
    stats.dreq = row[DREQ]
    stats.dresp = row[DRESP]
    stats.econ = row[ECON]
    stats.eresp = row[ERESP]
    stats.wretr = row[WRETR]
    stats.wredis = row[WREDIS]
    stats.status = row[STATUS]
    stats.weight = row[WEIGHT]
    stats.act = row[ACT]
    stats.bck = row[BCK]
    stats.chkdown = row[CHKDOWN]
    stats.lastchg = row[LASTCHG]
    stats.downtime = row[DOWNTIME]
    stats.pid = row[PID]
    stats.iid = row[IID]
    stats.lbtot = row[LBTOT]
    stats.type = row[TYPE]
    stats.rate = row[RATE]
    stats.rate_max = row[RATE_MAX]
    stats.hrsp_1xx = row[HRSP_1XX]
    stats.hrsp_2xx = row[HRSP_2XX]
    stats.hrsp_3xx = row[HRSP_3XX]
    stats.hrsp_4xx = row[HRSP_4XX]
    stats.hrsp_5xx = row[HRSP_5XX]
    stats.hrsp_other = row[HRSP_OTHER]
    stats.cli_abrt = row[CLI_ABRT]
    stats.srv_abrt = row[SRV_ABRT]
    stats.comp_in = row[COMP_IN]
    stats.comp_out = row[COMP_OUT]
    stats.comp_byp = row[COMP_BYP]
    stats.comp_rsp = row[COMP_RSP]
    stats.lastsess = row[LASTSESS]
    stats.qtime = row[QTIME]
    stats.ctime = row[CTIME]
    stats.rtime = row[RTIME]
    stats.ttime = row[TTIME]
    return stats


@include_list_name('proxy.server')
@attr.s(hash=False, slots=True)
class HAProxyServerStats(object):
  """
  For more details see
  https://cbonte.github.io/haproxy-dconv/1.5/configuration.html#9.1
  """
  private_ip = att()
  port = att()
  pxname = att()  # proxy name
  svname = att()  # service name (FRONTEND, BACKEND or name of server/listener)
  qcur = att()  # current queued reqs. For the backend this reports the
  qmax = att()  # max value of qcur
  scur = att()  # current sessions
  smax = att()  # max sessions
  slim = att()  # configured session limit
  stot = att()  # cumulative num of connections
  bin = att()  # bytes in
  bout = att()  # bytes out
  dresp = att()  # resps denied because of security concerns.
  econ = att()  # num of reqs that encountered an error trying to
  eresp = att()  # resp errors. srv_abrt will be counted here also.
  wretr = att()  # num of times a connection to a server was retried.
  wredis = att()  # num of times a request was redispatched to another
  status = att()  # status (UP/DOWN/NOLB/MAINT/MAINT(via)...)
  weight = att()  # server weight
  act = att()  # server is active
  bck = att()  # server is backup
  chkfail = att()  # num of failed checks
  chkdown = att()  # num of UP->DOWN transitions
  lastchg = att()  # num of seconds since the last UP<->DOWN transition
  downtime = att()  # total downtime (in seconds)
  qlimit = att()  # configured maxqueue for the server
  pid = att()  # process id (0 for first instance, 1 for second, ...)
  iid = att()  # unique proxy id
  sid = att()  # server id (unique inside a proxy)
  throttle = att()  # current throttle percentage for the server
  lbtot = att()  # total num of times a server was selected
  tracked = att()  # id of proxy/server if tracking is enabled.
  type = att()  # (0=frontend, 1=backend, 2=server, 3=socket/listener)
  rate = att()  # num of sessions per second over last elapsed second
  rate_max = att()  # max num of new sessions per second
  check_status = att()  # status of last health check
  check_code = att()  # layer5-7 code, if available
  check_duration = att()  # time in ms took to finish last health check
  hrsp_1xx = att()  # http resps with 1xx code
  hrsp_2xx = att()  # http resps with 2xx code
  hrsp_3xx = att()  # http resps with 3xx code
  hrsp_4xx = att()  # http resps with 4xx code
  hrsp_5xx = att()  # http resps with 5xx code
  hrsp_other = att()  # http resps with other codes (protocol error)
  hanafail = att()  # failed health checks details
  cli_abrt = att()  # num of data transfers aborted by the client
  srv_abrt = att()  # num of data transfers aborted by the server
  lastsess = att()  # num of seconds since last session assigned to
  last_chk = att()  # last health check contents or textual error
  last_agt = att()  # last agent check contents or textual error
  qtime = att()  # the avg queue time in ms over the 1024 last reqs
  ctime = att()  # the avg connect time in ms over the 1024 last reqs
  rtime = att()  # the avg resp time in ms over the 1024 last reqs
  ttime = att()  # the avg total session time in ms over the 1024 last

  @staticmethod
  def from_stats_csv_row(private_ip, port, row):
    """ Creates an instance of HAProxyServerStats using empty
    constructor and manual filling of all attributes.
    It works ~150% faster than keyword arguments.

    Args:
      private_ip: A str - private IP server listens on.
      port: An int - port server listens on
      row: A list of values in stats CSV row.
    Returns:
      An instance HAProxyServerStats.
    """
    stats = HAProxyServerStats()
    stats.private_ip = private_ip
    stats.port = port
    stats.pxname = row[PXNAME]
    stats.svname = row[SVNAME]
    stats.qcur = row[QCUR]
    stats.qmax = row[QMAX]
    stats.scur = row[SCUR]
    stats.smax = row[SMAX]
    stats.slim = row[SLIM]
    stats.stot = row[STOT]
    stats.bin = row[BIN]
    stats.bout = row[BOUT]
    stats.dresp = row[DRESP]
    stats.econ = row[ECON]
    stats.eresp = row[ERESP]
    stats.wretr = row[WRETR]
    stats.wredis = row[WREDIS]
    stats.status = row[STATUS]
    stats.weight = row[WEIGHT]
    stats.act = row[ACT]
    stats.bck = row[BCK]
    stats.chkfail = row[CHKFAIL]
    stats.chkdown = row[CHKDOWN]
    stats.lastchg = row[LASTCHG]
    stats.downtime = row[DOWNTIME]
    stats.qlimit = row[QLIMIT]
    stats.pid = row[PID]
    stats.iid = row[IID]
    stats.sid = row[SID]
    stats.throttle = row[THROTTLE]
    stats.lbtot = row[LBTOT]
    stats.tracked = row[TRACKED]
    stats.type = row[TYPE]
    stats.rate = row[RATE]
    stats.rate_max = row[RATE_MAX]
    stats.check_status = row[CHECK_STATUS]
    stats.check_code = row[CHECK_CODE]
    stats.check_duration = row[CHECK_DURATION]
    stats.hrsp_1xx = row[HRSP_1XX]
    stats.hrsp_2xx = row[HRSP_2XX]
    stats.hrsp_3xx = row[HRSP_3XX]
    stats.hrsp_4xx = row[HRSP_4XX]
    stats.hrsp_5xx = row[HRSP_5XX]
    stats.hrsp_other = row[HRSP_OTHER]
    stats.hanafail = row[HANAFAIL]
    stats.cli_abrt = row[CLI_ABRT]
    stats.srv_abrt = row[SRV_ABRT]
    stats.lastsess = row[LASTSESS]
    stats.last_chk = row[LAST_CHK]
    stats.last_agt = row[LAST_AGT]
    stats.qtime = row[QTIME]
    stats.ctime = row[CTIME]
    stats.rtime = row[RTIME]
    stats.ttime = row[TTIME]
    return stats


@include_list_name('proxy')
@attr.s(hash=False, slots=True, frozen=True)
class ProxyStats(object):
  """
  Object of ProxyStats is kind of structured container for all haproxy stats
  provided for the specific proxy (e.g.: TaskQueue, UserAppServer, ...).

  Only those Hermes nodes which are collocated with HAProxy collects this stats.
  """
  name = attr.ib()
  unified_service_name = attr.ib()  # taskqueue, appserver, datastore, ...
  application_id = attr.ib()  # application ID for appserver and None for others
  accurate_frontend_scur = attr.ib() # max of scur from haproxy and psutils
  frontend = attr.ib(metadata={Meta.ENTITY: HAProxyFrontendStats})
  backend = attr.ib(metadata={Meta.ENTITY: HAProxyBackendStats})
  servers = attr.ib(metadata={Meta.ENTITY_LIST: HAProxyServerStats})
  listeners = attr.ib(metadata={Meta.ENTITY_LIST: HAProxyListenerStats})
  servers_count = attr.ib()  # number of servers serving this proxy
  listeners_count = attr.ib()  # number of listeners serving this proxy


@attr.s(hash=False, slots=True, frozen=True)
class ProxiesStatsSnapshot(object):
  utc_timestamp = attr.ib()  # UTC timestamp
  proxies_stats = attr.ib(metadata={Meta.ENTITY_LIST: ProxyStats})


def get_stats(socket_path):
  """ Reads haproxy statistics from haproxy stats socket.

  Args:
    socket_path: A str - path to the haproxy socket on the file system.
  Returns:
    A cStringIO buffer containing data from socket.
  """
  client = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
  client.connect(socket_path)
  try:
    stats_output = cStringIO.StringIO()
    client.send(b'show stat\n')
    while True:
      data = client.recv(2048)
      if not data:
        break
      stats_output.write(data)
    stats_output.seek(0)
    return stats_output
  finally:
    client.close()


def get_frontend_ip_port(configs_dir, proxy_name):
  """ Finds IP and port bound with a proxy.

  Args:
    configs_dir: A str - path to the haproxy configs dir.
    proxy_name: A str - proxy name.
  Returns:
    A tuple (IP, port).
  """
  proxy_conf_path = os.path.join(configs_dir, '{}.cfg'.format(proxy_name))
  with open(proxy_conf_path) as proxy_conf:
    for line in proxy_conf:
      line = line.strip()
      if line.startswith('bind'):
        ip, port = line.split(' ')[1].split(':')
        return ip, int(port)
  raise BoundIpPortNotFound("Couldn't find bound IP and port for {} at {}"
                            .format(proxy_name, configs_dir))


def _convert_ints_and_missing(row):
  """ Converts cells containing numeric values (but as strings) to integers.
  It also appends MISSED if row does not contain all cell.

  Args:
    row: A list representing stats row.
  """
  if row[-1] == '':
    # Last cell is usually empty, we should consider it as MISSED.
    row[-1] = MISSED
  if len(row) < COLUMNS_NUMBER:
    row += [MISSED] * (COLUMNS_NUMBER - len(row))
  for index in HAPROXY_STATS_STR_COLUMNS:
    cell_value = row[index]
    if cell_value == '':
      row[index] = None
  for index in HAPROXY_STATS_INT_COLUMNS:
    cell_value = row[index]
    if cell_value is not MISSED:
      row[index] = int(cell_value) if cell_value else None


def get_stats_from_one_haproxy(socket_path, configs_dir, net_connections):
  """ Reads and parses data from haproxy socket and builds
  structured stats objects.

  Args:
    socket_path: A str - path to the haproxy socket on the file system.
    configs_dir: A str - path to the haproxy configs dir.
    net_connections: A list of net connections provided by psutil.
  Returns:
    A list of ProxyStats.
  """
  # Get CSV table with haproxy stats
  csv_buf = get_stats(socket_path)
  csv_buf.seek(2)  # Seek to the beginning but skip "# " in the first row
  rows = iter(csv.reader(csv_buf, delimiter=','))
  try:
    header = next(rows)
  except StopIteration:
    # No data is in stats socket
    return []

  # Warn or fail if stats header doesn't contain expected columns
  if ProxiesStatsSource.first_run:
    if header[:len(HEADER_1_5_PLUS)] != HEADER_1_5_PLUS:
      logger.warning("Old version of HAProxy is used (v1.5+ is expected).\n"
                     "Actual header starts from:\n  {}\n"
                     "Expected header should start from:\n  {}"
                     .format(header, HEADER_1_5_PLUS))
      if header[:len(ACCEPTABLE_HEADER)] != ACCEPTABLE_HEADER:
        msg = ("HAProxy stats header doesn't contain expected columns.\n"
               "Actual header starts from:\n  {}\n"
               "Expected header should start from:\n  {}\n"
               "Recommended HAProxy version is 1.5+."
               .format(header, HEADER_1_5_PLUS))
        logger.error(msg)
        raise HAProxyStatsParsingError(msg)
    ProxiesStatsSource.first_run = False

  # Parse haproxy stats output line by line
  parsed_objects = defaultdict(list)
  for row in rows:
    if not row or not row[0]:
      # Skip last empty line
      continue
    _convert_ints_and_missing(row)
    proxy_name = row[PXNAME]
    service = find_service_by_pxname(proxy_name)
    svname = row[SVNAME]
    if svname == 'FRONTEND':
      stats = HAProxyFrontendStats.from_stats_csv_row(row)
    elif svname == 'BACKEND':
      stats = HAProxyBackendStats.from_stats_csv_row(row)
    elif row[QCUR] is not None:
      # Listener stats doesn't have "current queued requests" property
      private_ip, port = service.get_ip_port_by_svname(svname)
      stats = HAProxyServerStats.from_stats_csv_row(private_ip, port, row)
    else:
      stats = HAProxyListenerStats.from_stats_csv_row(row)
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
    try:
      bound_ip, bound_port = get_frontend_ip_port(configs_dir, proxy_name)
      psutil_connections = sum(
        1 for conn in net_connections
        if conn.laddr == (bound_ip, bound_port) and conn.status == 'ESTABLISHED'
      )
    except (OSError, IOError, BoundIpPortNotFound):
      psutil_connections = 0
    proxy_stats = ProxyStats(
      name=proxy_name, unified_service_name=service_name,
      application_id=application_id,
      accurate_frontend_scur=max(psutil_connections, frontends[0].scur),
      frontend=frontends[0], backend=backends[0],
      servers=servers, listeners=listeners,
      servers_count=len(servers), listeners_count=len(listeners)
    )
    proxy_stats_list.append(proxy_stats)

  return proxy_stats_list


HAPROXY_PROCESSES = {
  'apps': {'socket': HAPROXY_APPS_STATS_SOCKET_PATH,
           'configs': HAPROXY_APPS_CONFIGS_DIR},
  'services': {'socket': HAPROXY_SERVICES_STATS_SOCKET_PATH,
               'configs': HAPROXY_SERVICES_CONFIGS_DIR},
}


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

    net_connections = psutil.net_connections()
    proxy_stats_list = []
    for haproxy_process_name, info in HAPROXY_PROCESSES.iteritems():
      logger.debug("Processing {} haproxy stats".format(haproxy_process_name))
      proxy_stats_list += get_stats_from_one_haproxy(
        info['socket'], info['configs'], net_connections
      )

    stats = ProxiesStatsSnapshot(
      utc_timestamp=time.mktime(datetime.now().timetuple()),
      proxies_stats=proxy_stats_list
    )
    logger.info("Prepared stats about {prox} proxies in {elapsed:.1f}s."
                .format(prox=len(proxy_stats_list), elapsed=time.time()-start))
    return stats


def get_service_instances(stats_socket_path, pxname):
  safe_pxname = re.escape(pxname)
  ip_port_list = []
  ip_port_pattern = re.compile(
    "\n{proxy},{proxy}-(?P<port_ip>[.\w]+:\d+)".format(proxy=safe_pxname)
  )
  stats_csv = get_stats(stats_socket_path).read()
  for match in re.finditer(ip_port_pattern, stats_csv):
    ip_port_list.append(match.group("port_ip"))
  return ip_port_list
