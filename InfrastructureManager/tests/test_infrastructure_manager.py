from flexmock import flexmock
from utils import utils
from infrastructure_manager import *
try:
  from unittest import TestCase
except ImportError:
  from unittest.case import TestCase

class TestInfrastructureManager(TestCase):
  def setUp(self):
    flexmock(utils).should_receive('get_secret').and_return('secret')

  def tearDown(self):
    flexmock(utils).should_receive('get_secret').reset()

  def test_initialize(self):
    i = InfrastructureManager()
    self.assertEquals('secret', i.secret)

  def test_describe_instances(self):
    i = InfrastructureManager()
    params1 = {}
    result1 = i.describe_instances(params1, 'secret1')
    self.assertFalse(result1['success'])
    self.assertEquals(result1['reason'],
      InfrastructureManager.REASON_BAD_SECRET)

    # test the scenario where we fail to give describe_instances a
    # reservation id
    params2 = {}
    result2 = i.describe_instances(params2, 'secret')
    self.assertFalse(result2['success'])
    self.assertEquals(result2['reason'],
      'no ' + InfrastructureManager.PARAM_RESERVATION_ID)

    # test what happens when a caller fails to give describe instances
    # a reservation id that's in the system
    params3 = {InfrastructureManager.PARAM_RESERVATION_ID: 'boo'}
    result3 = i.describe_instances(params3, 'secret')
    self.assertFalse(result3['success'])
    self.assertEquals(result3['reason'],
      InfrastructureManager.REASON_RESERVATION_NOT_FOUND)

    # test what happens when a caller gives describe_instances a reservation
    # id that is in the system
    id = '0000000000'
    params4 = {InfrastructureManager.PARAM_RESERVATION_ID: id}
    vm_info = {
      'public_ips': ['public-ip'],
      'private_ips': ['private-ip'],
      'instance_ids': ['i-id']
    }
    status_info = {
      'success': True,
      'reason': 'received run request',
      'state': InfrastructureManager.STATE_RUNNING,
      'vm_info': vm_info
    }
    i.reservations.put(id, status_info)
    result4 = i.reservations.get(id)
    self.assertEquals(result4, i.describe_instances(params4, "secret"))

    params5 = json.dumps(params4)
    self.assertEquals(result4, i.describe_instances(params5, "secret"))

    try:
      i.describe_instances('foo', 'bar')
      self.fail('Must throw an exception')
    except Exception:
      pass

    try:
      i.describe_instances({'reservation_id': 'foo'}, {})
      self.fail('Must throw an exception')
    except TypeError:
      pass

  def test_run_instances(self):
    i = InfrastructureManager()

    params1 = {}
    result1 = i.run_instances(params1, 'secret1')
    self.assertFalse(result1['success'])
    self.assertEquals(result1['reason'],
      InfrastructureManager.REASON_BAD_SECRET)

    params2 = {}
    result2 = i.run_instances(params2, 'secret')
    self.assertFalse(result2['success'])
    self.assertEquals(result2['reason'], 'no infrastructure')

    params3 = {'infrastructure': 'ec2'}
    result3 = i.run_instances(params3, 'secret')
    self.assertFalse(result3['success'])
    self.assertEquals(result3['reason'], 'no num_vms')

    params4 = {'infrastructure': 'ec2', 'num_vms': 0}
    result4 = i.run_instances(params4, 'secret')
    self.assertFalse(result4['success'])
    self.assertEquals(result4['reason'],
      InfrastructureManager.REASON_BAD_VM_COUNT)

    try:
      result5 = i.run_instances('foo', 'bar')
      self.fail('Must throw an exception')
    except Exception:
      pass

  def test_terminate_instances(self):
    i = InfrastructureManager()

    params1 = {}
    result1 = i.terminate_instances(params1, 'secret1')
    self.assertFalse(result1['success'])
    self.assertEquals(result1['reason'],
      InfrastructureManager.REASON_BAD_SECRET)

    params2 = {}
    result2 = i.terminate_instances(params2, 'secret')
    self.assertFalse(result2['success'])
    self.assertEquals(result2['reason'], 'no infrastructure')

    try:
      result3 = i.terminate_instances('foo', 'bar')
      self.fail('Must throw an exception')
    except Exception:
      pass
