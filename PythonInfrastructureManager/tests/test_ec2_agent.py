from unittest.case import TestCase
from flexmock import flexmock
import time
from infrastructure_manager import InfrastructureManager
from utils import utils

__author__ = 'hiranya'

class TestEC2Agent(TestCase):

    def test_ec2_run_instances(self):
        # mock out describe instances calls - the first time, there will be
        # no instances running, and the second time, the instance will have come
        # up

        i = InfrastructureManager()

        # first, validate that the run_instances call goes through successfully
        # and gives the user a reservation id
        full_params = {
            # Chris: Why this wasn't an issue in Ruby?
            "credentials" : {'a' : 'b', 'CLOUD1_EC2_URL' : 'http://ec2.url.com'},
            "group" : "boogroup",
            "image_id" : "booid",
            "infrastructure" : "ec2",
            "instance_type" : "booinstance_type",
            "keyname" : "bookeyname",
            "num_vms" : "1",
            "spot" : "False",
            'cloud' : 1 # Chris: How on earth the Ruby test is passing without this?
        }

        id = '0000000000'  # no longer randomly generated
        full_result = {
            'success' : True,
            'reservation_id' : id,
            'reason' : 'none'
        }
        self.assertEquals(full_result, i.run_instances(full_params, "secret"))

        # next, look at run_instances internally to make sure it actually is
        # updating its reservation info
        # Chris: How was this race condition addressed by the Ruby test?
        time.sleep(2)
        self.assertEquals("running", i.reservations[id]["state"])

        vm_info = i.reservations[id]["vm_info"]
        self.assertEquals(["public-ip"], vm_info["public_ips"])
        self.assertEquals(["private-ip"], vm_info["private_ips"])
        self.assertEquals(["i-id"], vm_info["instance_ids"])

    def test_ec2_terminate_instances(self):
        i = InfrastructureManager()

        params1 = { 'infrastructure' : 'ec2' }
        result1 = i.terminate_instances(params1, 'secret')
        self.assertFalse(result1['success'])
        self.assertEquals(result1['reason'], 'no credentials')

        params2 = {
            "credentials" : {'a' : 'b', 'CLOUD1_EC2_URL' : 'http://ec2.url.com'},
            'infrastructure' : 'ec2',
            'instance_ids' : [ 'i-12345' ]
        }
        result2 = i.terminate_instances(params2, 'secret')
        self.assertTrue(result2['success'])
        time.sleep(2)

    def setUp(self):
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
             .should_receive('shell')
             .with_args('ec2-terminate-instances i-12345 2>&1')
             .and_return('i-12345'))

        first_time = ''
        second_time = """
        RESERVATION     r-55560977      admin   default
        INSTANCE        i-id      emi-721D0EBA    public-ip    private-ip  running  bookeyname   0       c1.medium       2010-05-07T07:17:48.23Z         myueccluster    eki-675412F5    eri-A1E113E0"""
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-describe-instances 2>&1')
             .and_return(first_time)
             .and_return(second_time))
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-run-instances -k bookeyname -n 1 --instance-type booinstance_type --group boogroup booid')
             .and_return(''))
        (flexmock(utils)
             .should_receive('shell')
             .with_args('dig private-ip +short')
             .and_return('private-ip\n'))
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-add-keypair bookeyname 2>&1')
             .and_return('BEGIN RSA PRIVATE KEY'))
        (flexmock(utils)
             .should_receive('write_key_file')
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-add-group boogroup -d appscale 2>&1')
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-authorize boogroup -p 1-65535 -P udp 2>&1')
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-authorize boogroup -p 1-65535 -P tcp 2>&1')
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-authorize boogroup -s 0.0.0.0/0 -P icmp -t -1:-1 2>&1')
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('env')
             .and_return(''))

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
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-terminate-instances i-12345 2>&1')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-describe-instances 2>&1')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-run-instances -k bookeyname -n 1 --instance-type booinstance_type --group boogroup booid')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('dig private-ip +short')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-add-keypair bookeyname 2>&1')
             .reset())
        (flexmock(utils)
             .should_receive('write_key_file')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-add-group boogroup -d appscale 2>&1')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-authorize boogroup -p 1-65535 -P udp 2>&1')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-authorize boogroup -p 1-65535 -P tcp 2>&1')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-authorize boogroup -s 0.0.0.0/0 -P icmp -t -1:-1 2>&1')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('env')
             .reset())

