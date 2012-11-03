from unittest import TestCase
from flexmock import flexmock
from utils import utils
from infrastructure_manager import *

__author__ = 'hiranya'

class TestInfrastructureManager(TestCase):

    def setUp(self):
        flexmock(utils, get_secret='secret')

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