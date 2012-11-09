from unittest import TestCase
from flexmock import flexmock
from utils import utils
from infrastructure_manager import *

__author__ = 'hiranya'

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
        self.assertEquals(result1['reason'], REASON_BAD_SECRET)

        # test the scenario where we fail to give describe_instances a
        # reservation id
        params2 = {}
        result2 = i.describe_instances(params2, 'secret')
        self.assertFalse(result2['success'])
        self.assertEquals(result2['reason'], 'no ' + PARAM_RESERVATION_ID)

        # test what happens when a caller fails to give describe instances
        # a reservation id that's in the system
        params3 = { 'reservation_id' : 'boo' }
        result3 = i.describe_instances(params3, 'secret')
        self.assertFalse(result3['success'])
        self.assertEquals(result3['reason'], REASON_RESERVATION_NOT_FOUND)

        # test what happens when a caller gives describe_instances a reservation
        # id that is in the system
        id = '0000000000'
        params4 = { "reservation_id" : id }
        vm_info = {
            "public_ips" : ["public-ip"],
            "private_ips" : ["private-ip"],
            "instance_ids" : ["i-id"]
        }
        i.reservations[id] = {
            "success" : True,
            "reason" : "received run request",
            "state" : "running",
            "vm_info" : vm_info
        }
        result4 = i.reservations[id]
        self.assertEquals(result4, i.describe_instances(params4, "secret"))

    def test_run_instances(self):
        i = InfrastructureManager()

        params1 = {}
        result1 = i.run_instances(params1, 'secret1')
        self.assertFalse(result1['success'])
        self.assertEquals(result1['reason'], REASON_BAD_SECRET)

        params2 = {}
        result2 = i.run_instances(params2, 'secret')
        self.assertFalse(result2['success'])
        self.assertEquals(result2['reason'], 'no infrastructure')

        params3 = { 'infrastructure' : 'ec2' }
        result3 = i.run_instances(params3, 'secret')
        self.assertFalse(result3['success'])
        self.assertEquals(result3['reason'], 'no num_vms')

    def test_terminate_instances(self):
        i = InfrastructureManager()

        params1 = {}
        result1 = i.terminate_instances(params1, 'secret1')
        self.assertFalse(result1['success'])
        self.assertEquals(result1['reason'], REASON_BAD_SECRET)

        params2 = {}
        result2 = i.terminate_instances(params2, 'secret')
        self.assertFalse(result2['success'])
        self.assertEquals(result2['reason'], 'no infrastructure')

