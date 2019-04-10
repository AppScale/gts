import asyncio

import pytest
from mock import MagicMock, patch

from appscale.hermes.producers import cassandra_stats


def future(value=None):
  future_obj = asyncio.Future()
  future_obj.set_result(value)
  return future_obj


MULTINODE_STATUS = b"""Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address    Load       Tokens       Owns (effective)  Host ID                               Rack
UN  10.0.2.15  67.94 GiB  1            99.8%             a341df86-71e2-4054-83d6-c2d92dc75afc  rack1
UN  10.0.2.16  65.99 GiB  1            0.2%              2ceb81a6-4c49-456d-a38b-23667ee60ff9  rack1

"""

SINGLENODE_STATUS = b"""Datacenter: datacenter1
=======================
Status=Up/Down
|/ State=Normal/Leaving/Joining/Moving
--  Address    Load       Owns (effective)  Host ID                               Token                                    Rack
UN  10.0.2.15  337.07 MiB  100.0%            38fd1ac1-85f9-4b19-8f8f-19ef5a00d65d  bf5f65abbfab7ac2dd87145d0cde8435         rack1

"""


@pytest.mark.asyncio
async def test_multinode():
  process_mock = MagicMock(returncode=0)
  stdout = MULTINODE_STATUS
  stderr = b''
  process_mock.communicate.return_value = future((stdout, stderr))

  db_ips_patcher = patch(
    'appscale.common.appscale_info.get_db_ips',
    return_value=['10.0.2.15', '10.0.2.16']
  )
  subprocess_patcher = patch(
    'asyncio.create_subprocess_shell',
    return_value=future(process_mock)
  )

  with db_ips_patcher:
    with subprocess_patcher:
      # Calling method under test
      stats = await cassandra_stats.CassandraStatsSource.get_current()

  # Asserting expectations
  assert stats.missing_nodes == []
  assert stats.unknown_nodes == []
  assert isinstance(stats.utc_timestamp, int)
  assert len(stats.nodes) == 2

  first = stats.nodes[0]
  assert first.address == '10.0.2.15'
  assert first.status == 'Up'
  assert first.state == 'Normal'
  assert first.load == int(67.94 * 1024**3)
  assert first.owns_pct == 99.8
  assert first.tokens_num == 1
  assert first.host_id == 'a341df86-71e2-4054-83d6-c2d92dc75afc'
  assert first.rack == 'rack1'

  second = stats.nodes[1]
  assert second.address == '10.0.2.16'
  assert second.status == 'Up'
  assert second.state == 'Normal'
  assert second.load == int(65.99 * 1024**3)
  assert second.owns_pct == 0.2
  assert second.tokens_num == 1
  assert second.host_id == '2ceb81a6-4c49-456d-a38b-23667ee60ff9'
  assert second.rack == 'rack1'


@pytest.mark.asyncio
async def test_singlenode():
  process_mock = MagicMock(returncode=0)
  stdout = SINGLENODE_STATUS
  stderr = b''
  process_mock.communicate.return_value = future((stdout, stderr))

  db_ips_patcher = patch(
    'appscale.common.appscale_info.get_db_ips',
    return_value=['10.0.2.15']
  )
  subprocess_patcher = patch(
    'asyncio.create_subprocess_shell',
    return_value=future(process_mock)
  )

  with db_ips_patcher:
    with subprocess_patcher:
      # Calling method under test
      stats = await cassandra_stats.CassandraStatsSource.get_current()

  # Asserting expectations
  assert stats.missing_nodes == []
  assert stats.unknown_nodes == []
  assert isinstance(stats.utc_timestamp, int)
  assert len(stats.nodes) == 1

  first = stats.nodes[0]
  assert first.address == '10.0.2.15'
  assert first.status == 'Up'
  assert first.state == 'Normal'
  assert first.load == int(337.07 * 1024**2)
  assert first.owns_pct == 100.0
  assert first.tokens_num == 1
  assert first.host_id == '38fd1ac1-85f9-4b19-8f8f-19ef5a00d65d'
  assert first.rack == 'rack1'


@pytest.mark.asyncio
async def test_missing_and_unknown():
  process_mock = MagicMock(returncode=0)
  stdout = MULTINODE_STATUS
  stderr = b''
  process_mock.communicate.return_value = future((stdout, stderr))

  db_ips_patcher = patch(
    'appscale.common.appscale_info.get_db_ips',
    return_value=['10.0.2.15', '10.0.2.missing']
  )
  subprocess_patcher = patch(
    'asyncio.create_subprocess_shell',
    return_value=future(process_mock)
  )

  with db_ips_patcher:
    with subprocess_patcher:
      # Calling method under test
      stats = await cassandra_stats.CassandraStatsSource.get_current()

  # Asserting expectations
  assert stats.missing_nodes == ['10.0.2.missing']
  assert stats.unknown_nodes == ['10.0.2.16']
  assert isinstance(stats.utc_timestamp, int)
  assert len(stats.nodes) == 2

  first = stats.nodes[0]
  assert first.address == '10.0.2.15'
  assert first.status == 'Up'
  assert first.state == 'Normal'
  assert first.load == int(67.94 * 1024**3)
  assert first.owns_pct == 99.8
  assert first.tokens_num == 1
  assert first.host_id == 'a341df86-71e2-4054-83d6-c2d92dc75afc'
  assert first.rack == 'rack1'

  second = stats.nodes[1]
  assert second.address == '10.0.2.16'
  assert second.status == 'Up'
  assert second.state == 'Normal'
  assert second.load == int(65.99 * 1024**3)
  assert second.owns_pct == 0.2
  assert second.tokens_num == 1
  assert second.host_id == '2ceb81a6-4c49-456d-a38b-23667ee60ff9'
  assert second.rack == 'rack1'
