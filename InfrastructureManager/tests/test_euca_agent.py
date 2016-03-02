from boto.ec2.connection import EC2Connection
from boto.ec2.instance import Reservation, Instance
from boto.ec2.keypair import KeyPair
from boto.ec2.securitygroup import SecurityGroup
from flexmock import flexmock
from infrastructure_manager import InfrastructureManager
from utils import utils
try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase

class TestEucaAgent(TestCase):

  def test_euca_run_instances(self):
    i = InfrastructureManager(blocking=True)

    # first, validate that the run_instances call goes through successfully
    # and gives the user a reservation id
    full_params = {
      'credentials': {
        'a': 'b', 'EC2_URL': 'http://testing.appscale.com:8773/foo/bar',
        'EC2_ACCESS_KEY': 'access_key', 'EC2_SECRET_KEY': 'secret_key'},
      'group': 'boogroup',
      'image_id': 'booid',
      'infrastructure': 'euca',
      'instance_type': 'booinstance_type',
      'keyname': 'bookeyname',
      'num_vms': '2',
      'use_spot_instances': False,
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
    self.assertEquals(InfrastructureManager.STATE_RUNNING,
      i.reservations.get(id)['state'])
    vm_info = i.reservations.get(id)['vm_info']
    self.assertEquals(['ABC-public-ip1', 'DEF-public-ip2'],
      vm_info['public_ips'])
    self.assertEquals(['DEF-private-ip1', 'ABC-private-ip2'],
      vm_info['private_ips'])
    self.assertEquals(['i-id1', 'i-id2'], vm_info['instance_ids'])


  def setUp(self):
    (flexmock(EC2Connection)
      .should_receive('get_key_pair')
      .and_return(None))
    (flexmock(EC2Connection)
      .should_receive('create_key_pair')
      .with_args('bookeyname')
      .and_return(KeyPair()))
    (flexmock(EC2Connection)
      .should_receive('get_all_security_groups')
      .and_return([]))
    (flexmock(EC2Connection)
      .should_receive('create_security_group')
      .with_args('boogroup', 'AppScale security group')
      .and_return(SecurityGroup()))
    (flexmock(EC2Connection)
      .should_receive('authorize_security_group')
      .and_return())
    reservation = Reservation()

    # the old implementation had a regression where public and private IPs
    # were getting sorted, and thus public ip1 would point to private ip 2.
    # to prevent this regression from resurfacing, set up the dns names so
    # that a sort would mess them up again.
    instance1 = flexmock(name='instance1', private_dns_name='DEF-private-ip1',
      public_dns_name='ABC-public-ip1', id='i-id1', state='running',
      key_name='bookeyname')

    instance2 = flexmock(name='instance2', private_dns_name='ABC-private-ip2',
      public_dns_name='DEF-public-ip2', id='i-id2', state='running',
      key_name='bookeyname')

    reservation.instances = [instance1, instance2]
    (flexmock(EC2Connection)
      .should_receive('get_all_instances')
      .and_return([])
      .and_return([reservation]))
    (flexmock(EC2Connection)
     .should_receive('run_instances')
     .and_return())

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
