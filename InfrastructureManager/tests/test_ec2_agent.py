import boto
import boto.ec2
import time

from appscale.tools.agents.base_agent import AgentRuntimeException
from appscale.tools.agents.base_agent import AgentConfigurationException
from boto.ec2.spotpricehistory import SpotPriceHistory
from boto.ec2.instance import Reservation
from boto.ec2.keypair import KeyPair
from boto.ec2.securitygroup import SecurityGroup
from boto.exception import EC2ResponseError
from flexmock import flexmock
from infrastructure_manager import InfrastructureManager
from utils import utils
try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase

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

    reservation = Reservation()
    instance = flexmock(name='instance', private_dns_name='private-ip',
                        public_dns_name='public-ip', id='i-id', state='running',
                        key_name='bookeyname', ip_address='public-ip',
                        private_ip_address='private-ip')
    new_instance = flexmock(name='new-instance', private_dns_name='new-private-ip',
                        public_dns_name='new-public-ip', id='new-i-id', state='running',
                        key_name='bookeyname', ip_address='new-public-ip',
                        private_ip_address='new-private-ip')
    reservation.instances = [instance]
    new_reservation = Reservation()
    new_reservation.instances = [instance, new_instance]
    self.fake_ec2.should_receive('get_all_instances').and_return([]) \
      .and_return([reservation]).and_return([new_reservation])

    # first, validate that the run_instances call goes through successfully
    # and gives the user a reservation id
    full_params = {
      'credentials': {
        'a': 'b', 'EC2_URL': 'http://testing.appscale.com:8773/foo/bar',
        'EC2_ACCESS_KEY': 'access_key', 'EC2_SECRET_KEY': 'secret_key'},
      'group': 'boogroup',
      'image_id': 'booid',
      'infrastructure': prefix,
      'instance_type': 'booinstance_type',
      'keyname': 'bookeyname',
      'num_vms': '1',
      'use_spot_instances': False,
      'region' : 'my-zone-1',
      'zone' : 'my-zone-1b',
      'autoscale_agent': True
    }

    id = '0000000000'  # no longer randomly generated
    full_result = {
      'success': True,
      'reservation_id': id,
      'reason': 'none'
    }
    if success:
      self.assertEquals(full_result, i.run_instances(full_params, 'secret'))

    # next, look at run_instances internally to make sure it actually is
    # updating its reservation info
    if not blocking:
      time.sleep(.1)
    if success:
      self.assertEquals(InfrastructureManager.STATE_RUNNING,
        i.reservations.get(id)['state'])
      vm_info = i.reservations.get(id)['vm_info']
      self.assertEquals(['new-public-ip'], vm_info['public_ips'])
      self.assertEquals(['new-private-ip'], vm_info['private_ips'])
      self.assertEquals(['new-i-id'], vm_info['instance_ids'])
    else:
      if blocking:
        self.assertRaises(AgentRuntimeException, i.run_instances, full_params, 'secret')

  def terminate_instances(self, prefix, blocking):
    i = InfrastructureManager(blocking=blocking)

    params1 = {'infrastructure': prefix}
    self.assertRaises(AgentConfigurationException, i.terminate_instances, params1, 'secret')

    params2 = {
      'credentials': {
        'a': 'b', 'EC2_URL': 'http://ec2.url.com',
        'EC2_ACCESS_KEY': 'access_key', 'EC2_SECRET_KEY': 'secret_key'},
      'infrastructure': prefix,
      'instance_ids': ['i-12345'],
      'region' : 'my-zone-1',
      'keyname': 'bookeyname'
    }

    reservation = Reservation()
    instance = flexmock(name='instance', private_dns_name='private-ip',
                        public_dns_name='public-ip', id='i-id', state='terminated',
                        key_name='bookeyname', ip_address='public-ip',
                        private_ip_address='private-ip')
    reservation.instances = [instance]
    self.fake_ec2.should_receive('get_all_instances').and_return([reservation])

    result = i.terminate_instances(params2, 'secret')
    if not blocking:
      time.sleep(.1)
    self.assertTrue(result['success'])


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

    instance = flexmock(name='instance', private_dns_name='private-ip',
      public_dns_name='public-ip', id='i-id', state='running',
      key_name='bookeyname')

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
