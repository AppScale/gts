from unittest.case import TestCase
from flexmock import flexmock
from infrastructure_manager import InfrastructureManager
from utils import utils

__author__ = 'hiranya'

class TestEC2Agent(TestCase):

    def setUp(self):
        flexmock(utils, get_secret='secret')

    def test_ec2_run_instances(self):
        flexmock(utils, get_random_alphanumeric='0000000000')

        # mock out describe instances calls - the first time, there will be
        # no instances running, and the second time, the instance will have come
        # up
        first_time = ''
        second_time = """
        RESERVATION     r-55560977      admin   default
        INSTANCE        i-id      emi-721D0EBA    public-ip    private-ip  running  bookeyname   0       c1.medium       2010-05-07T07:17:48.23Z         myueccluster    eki-675412F5    eri-A1E113E0"""
        flexmock(utils).should_receive('shell').with_args(
            'ec2-describe-instances 2>&1').and_return(first_time).and_return(second_time)
        flexmock(utils).should_receive('shell').with_args(
            'ec2-run-instances -k bookeyname -n 1 --instance-type booinstance_type --group boogroup booid').and_return('')


        i = InfrastructureManager()

        # first, validate that the run_instances call goes through successfully
        # and gives the user a reservation id
        full_params = {
            # ASK_CHRIS: Why this wasn't an issue in Ruby?
            "credentials" : {'a' : 'b', 'CLOUD1_EC2_URL' : 'http://ec2.url.com'},
            "group" : "boogroup",
            "image_id" : "booid",
            "infrastructure" : "ec2",
            "instance_type" : "booinstance_type",
            "keyname" : "bookeyname",
            "num_vms" : "1",
            "spot" : "False",
            'cloud' : 1 # How on earth the Ruby test is passing without this?

        }

        id = '0000000000'  # no longer randomly generated
        full_result = {
            'success' : True,
            'reservation_id' : id,
            'reason' : 'none'
        }
        self.assertEquals(full_result, i.run_instances(full_params, "secret"))

