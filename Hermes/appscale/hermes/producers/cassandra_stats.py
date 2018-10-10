""" Fetches `nodetool status` info. """
import logging
import re
import time

import attr
from tornado import process, gen

from appscale.common import appscale_info
from appscale.hermes.converter import Meta, include_list_name

# The endpoint used for retrieving queue stats.
NODETOOL_STATUS_COMMAND = ['/opt/cassandra/cassandra/bin/nodetool', 'status']


class NodetoolStatusError(Exception):
  """ Indicates that `nodetool status` command failed. """
  pass


@include_list_name('cassandra.node')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class CassandraNodeStats(object):
  """ The fields reported for each Cassandra node. """
  address = attr.ib()
  status = attr.ib()
  state = attr.ib()
  load = attr.ib()
  owns_pct = attr.ib()
  tokens_num = attr.ib()
  host_id = attr.ib()
  rack = attr.ib()


@include_list_name('cassandra')
@attr.s(cmp=False, hash=False, slots=True, frozen=True)
class CassandraStatsSnapshot(object):
  """ A container for all Cassandra nodes status. """
  utc_timestamp = attr.ib()
  nodes = attr.ib(metadata={Meta.ENTITY_LIST: CassandraNodeStats})
  missing_nodes = attr.ib()
  unknown_nodes = attr.ib()


class CassandraStatsSource(object):
  """ Fetches Cassandra status provided by `nodetool status` command. """

  SINGLENODE_HEADER_PATTERN = re.compile(
    r'-- +Address +Load +Owns \(effective\) +Host ID +Token +Rack'
  )
  MULTINODE_HEADER_PATTERN = re.compile(
    r'-- +Address +Load +Tokens +Owns \(effective\) +Host ID +Rack'
  )
  SINGLENODE_STATUS_PATTERN = re.compile(
    r'(?P<status>[UD])(?P<state>[NLJM]) +'
    r'(?P<address>\d+\.\d+\.\d+\.\d+) +'
    r'(?P<load>[\d.]+) (?P<size_unit>[KMGTPE])iB +'
    r'(?P<owns_pct>[\d.]+)% +'
    r'(?P<host_id>[\w-]+) +'
    r'(?P<token>[\w-]+) +'
    r'(?P<rack>[\w-]+)'
  )
  MULTINODE_STATUS_PATTERN = re.compile(
    r'(?P<status>[UD])(?P<state>[NLJM]) +'
    r'(?P<address>\d+\.\d+\.\d+\.\d+) +'
    r'(?P<load>[\d.]+) (?P<size_unit>[KMGTPE])iB +'
    r'(?P<tokens_num>\d+) +'
    r'(?P<owns_pct>[\d.]+)% +'
    r'(?P<host_id>[\w-]+) +'
    r'(?P<rack>[\w-]+)'
  )
  STATUSES = {
    'U': 'Up',
    'D': 'Down',
  }
  STATES = {
    'N': 'Normal',
    'L': 'Leaving',
    'J': 'Joining',
    'M': 'Moving',
  }
  SIZE_UNITS = {
    'K': 1024,
    'M': 1024 ** 2,
    'G': 1024 ** 3,
    'T': 1024 ** 4,
    'P': 1024 ** 5,
    'E': 1024 ** 6,
  }

  @classmethod
  @gen.coroutine
  def get_current(cls):
    """ Retrieves Cassandra status info.

    Returns:
      An instance of RabbitMQStatsSnapshot.
    """
    start = time.time()
    try:
      proc = process.Subprocess(
        NODETOOL_STATUS_COMMAND,
        stdout=process.Subprocess.STREAM,
        stderr=process.Subprocess.STREAM
      )
      status = yield proc.stdout.read_until_close()
      err = yield proc.stderr.read_until_close()
      if err:
        logging.error(err)
    except process.CalledProcessError as err:
      raise NodetoolStatusError(err)

    known_db_nodes = set(appscale_info.get_db_ips())
    nodes = []
    shown_nodes = set()

    if cls.SINGLENODE_HEADER_PATTERN.search(status):
      for match in cls.SINGLENODE_STATUS_PATTERN.finditer(status):
        address = match.group('address')
        status = match.group('status')
        state = match.group('state')
        load = match.group('load')
        size_unit = match.group('size_unit')
        owns_pct = match.group('owns_pct')
        tokens_num = 1
        host_id = match.group('host_id')
        rack = match.group('rack')
        node_stats = CassandraNodeStats(
          address=address,
          status=cls.STATUSES[status],
          state=cls.STATES[state],
          load=int(float(load) * cls.SIZE_UNITS[size_unit]),
          owns_pct=float(owns_pct),
          tokens_num=int(tokens_num),
          host_id=host_id,
          rack=rack,
        )
        nodes.append(node_stats)
        shown_nodes.add(address)

    elif cls.MULTINODE_HEADER_PATTERN.search(status):
      for match in cls.MULTINODE_STATUS_PATTERN.finditer(status):
        address = match.group('address')
        status = match.group('status')
        state = match.group('state')
        load = match.group('load')
        size_unit = match.group('size_unit')
        owns_pct = match.group('owns_pct')
        tokens_num = match.group('tokens_num')
        host_id = match.group('host_id')
        rack = match.group('rack')
        node_stats = CassandraNodeStats(
          address=address,
          status=cls.STATUSES[status],
          state=cls.STATES[state],
          load=int(float(load) * cls.SIZE_UNITS[size_unit]),
          owns_pct=float(owns_pct),
          tokens_num=int(tokens_num),
          host_id=host_id,
          rack=rack,
        )
        nodes.append(node_stats)
        shown_nodes.add(address)

    else:
      raise NodetoolStatusError(
        '`nodetool status` output does not contain expected header'
      )

    snapshot = CassandraStatsSnapshot(
      utc_timestamp=int(time.time()),
      nodes=nodes,
      missing_nodes=list(known_db_nodes - shown_nodes),
      unknown_nodes=list(shown_nodes - known_db_nodes)
    )
    logging.info('Prepared Cassandra nodes status in '
                 '{elapsed:.1f}s.'.format(elapsed=time.time()-start))
    raise gen.Return(snapshot)
