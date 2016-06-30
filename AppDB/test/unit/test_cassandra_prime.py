#!/usr/bin/env python2

import os
import sys
import unittest

from cassandra.cluster import Cluster
from flexmock import flexmock

sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
import dbconstants

from cassandra_env import prime_cassandra

sys.path.append(os.path.join(os.path.dirname(__file__), '../../../lib'))
import appscale_info


class TestCassandraPrimer(unittest.TestCase):
  def test_define_ua_schema(self):
    session = flexmock(execute=lambda statement, values: None)
    prime_cassandra.define_ua_schema(session)

  def test_prime_cassandra(self):
    self.assertRaises(TypeError, prime_cassandra.prime_cassandra, '1')
    self.assertRaises(
        dbconstants.AppScaleBadArg, prime_cassandra.prime_cassandra, 0)

    flexmock(appscale_info).should_receive('get_db_ips').\
      and_return(['127.0.0.1'])

    session = flexmock(execute=lambda: None, set_keyspace=lambda: None)
    flexmock(Cluster).should_receive('connect').and_return(session)
    flexmock(prime_cassandra).should_receive('define_ua_schema')
