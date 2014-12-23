import boto
import boto.ec2
from boto.ec2.spotpricehistory import SpotPriceHistory
from agents.factory import InfrastructureAgentFactory
from boto.ec2.connection import EC2Connection
from boto.ec2.instance import Reservation, Instance
from boto.ec2.keypair import KeyPair
from boto.ec2.securitygroup import SecurityGroup
from boto.exception import EC2ResponseError
from flexmock import flexmock
from infrastructure_manager import InfrastructureManager
import time
from utils import utils
try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase


__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

class TestEC2Agent(TestCase):

  def test_ec2_run_instances(self):
    self.run_instances('ec2', True)
    self.run_instances('ec2', False)
    e = EC2ResponseError('Error', 'Mock error')
    e.error_message = 'Mock error'
    self.fake_ec2.should_receive('run_instances').and_raise(e)
    self.run_instances('ec2', True, False)
    self.run_instances('ec2', False, False)

  def test_ec2_terminate_instances(self):
    self.terminate_instances('ec2', True)
    self.terminate_instances('ec2', False)

  def spot_price(self, price, ts):
    spot_price = SpotPriceHistory()
    spot_price.price = price
    spot_price.timestamp = ts
    return spot_price

  def run_instances(self, prefix, blocking, success=True):
    i = InfrastructureManager(blocking=blocking)

    # first, validate that the run_instances call goes through successfully
    # and gives the user a reservation id
    full_params = {
      'credentials': {'a': 'b', 'EC2_URL': 'http://testing.appscale.com:8773/foo/bar',
                      'EC2_ACCESS_KEY': 'access_key', 'EC2_SECRET_KEY': 'secret_key'},
      'group': 'boogroup',
      'image_id': 'booid',
      'infrastructure': prefix,
      'instance_type': 'booinstance_type',
      'keyname': 'bookeyname',
      'num_vms': '1',
      'use_spot_instances': False,
      'region' : 'my-zone-1',
      'zone' : 'my-zone-1b'
    }

    id = '0000000000'  # no longer randomly generated
    full_result = {
      'success': True,
      'reservation_id': id,
      'reason': 'none'
    }
    self.assertEquals(full_result, i.run_instances(full_params, 'secret'))

    # next, look at run_instances internally to make sure it actually is
    # updating its reservation info
    if not blocking:
      time.sleep(.1)
    if success:
      self.assertEquals(InfrastructureManager.STATE_RUNNING, i.reservations.get(id)['state'])
      vm_info = i.reservations.get(id)['vm_info']
      self.assertEquals(['public-ip'], vm_info['public_ips'])
      self.assertEquals(['private-ip'], vm_info['private_ips'])
      self.assertEquals(['i-id'], vm_info['instance_ids'])
    else:
      self.assertEquals(InfrastructureManager.STATE_FAILED, i.reservations.get(id)['state'])

  def terminate_instances(self, prefix, blocking):
    i = InfrastructureManager(blocking=blocking)

    params1 = {'infrastructure': prefix}
    result1 = i.terminate_instances(params1, 'secret')
    self.assertFalse(result1['success'])
    self.assertEquals(result1['reason'], 'no credentials')

    params2 = {
      'credentials': {'a': 'b', 'EC2_URL': 'http://ec2.url.com',
                      'EC2_ACCESS_KEY': 'access_key', 'EC2_SECRET_KEY': 'secret_key'},
      'infrastructure': prefix,
      'instance_ids': ['i-12345'],
      'region' : 'my-zone-1'
    }
    result2 = i.terminate_instances(params2, 'secret')
    if not blocking:
      time.sleep(.1)
    self.assertTrue(result2['success'])


  def setUp(self):
    self.fake_ec2 = flexmock(name='self.fake_ec2')
    self.fake_ec2.should_receive('get_key_pair')
    self.fake_ec2.should_receive('create_key_pair').with_args('bookeyname') \
      .and_return(KeyPair())
    self.fake_ec2.should_receive('get_all_security_groups').and_return([])
    self.fake_ec2.should_receive('create_security_group') \
      .with_args('boogroup', 'AppScale security group') \
      .and_return(SecurityGroup())
    self.fake_ec2.should_receive('authorize_security_group')

    reservation = Reservation()
    instance = flexmock(name='instance', private_dns_name='private-ip',
      public_dns_name='public-ip', id='i-id', state='running',
      key_name='bookeyname')
    reservation.instances = [instance]

    self.fake_ec2.should_receive('get_all_instances').and_return([]) \
      .and_return([reservation])
    self.fake_ec2.should_receive('terminate_instances').and_return([instance])
    self.fake_ec2.should_receive('run_instances')

    flexmock(boto.ec2)
    boto.ec2.should_receive('connect_to_region').and_return(self.fake_ec2)

    (flexmock(utils)
      .should_receive('get_secret')
      .and_return('secret'))
    (flexmock(utils)
      .should_receive('sleep')
      .and_return())
    (flexmock(utils)
      .should_receive('get_random_alphanumeric')
      .and_return('0000000000'))
    (flexmock(utils)
      .should_receive('write_key_file')
      .and_return())

  def tearDown(self):
    (flexmock(utils)
     .should_receive('get_secret')
     .reset())
    (flexmock(utils)
     .should_receive('sleep')
     .reset())
    (flexmock(utils)
     .should_receive('get_random_alphanumeric')
     .reset())

