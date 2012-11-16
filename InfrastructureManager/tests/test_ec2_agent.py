from agents.factory import InfrastructureAgentFactory
from flexmock import flexmock
from infrastructure_manager import InfrastructureManager
from os import environ
from StringIO import StringIO
import sys
import time
from unittest.case import TestCase
from utils import utils

__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

class TestEC2Agent(TestCase):

    def test_ec2_run_instances(self):
        self.do_set_up('ec2')
        self.run_instances('ec2', True)
        self.run_instances('ec2', False)
        self.do_tear_down('ec2')

    def test_ec2_terminate_instances(self):
        self.do_set_up('ec2')
        self.terminate_instances('ec2', True)
        self.terminate_instances('ec2', False)
        self.do_tear_down('ec2')

    def test_euca_run_instances(self):
        self.do_set_up('euca')
        self.run_instances('euca', False)
        self.do_tear_down('euca')

    def test_euca_terminate_instances(self):
        self.do_set_up('euca')
        self.terminate_instances('euca', False)
        self.do_tear_down('euca')

    def test_environment_variables(self):
        """
        Make sure all the provided environment variables are
        set in the runtime. Failure to do so had caused issues
        in Euca3 in the past. Also make sure all sensitive
        information are obscured in the log.
        """
        factory = InfrastructureAgentFactory()
        agent = factory.create_agent('ec2')
        credentials = {
            'TEST1' : 'TEST1_VALUE',
            'TEST2' : 'TEST2_VALUE',
            'TEST_KEY' : 'TEST_KEY_VALUE',
            'NONE_VALUE_KEY' : None
        }
        params = {
            'credentials' : credentials,
        }

        old_std_out = sys.stdout
        sys.stdout = my_std_out = StringIO()
        agent.set_environment_variables(params)
        self.assertEquals(environ['TEST1'], 'TEST1_VALUE')
        self.assertEquals(environ['TEST2'], 'TEST2_VALUE')
        self.assertEquals(environ['TEST_KEY'], 'TEST_KEY_VALUE')
        sys.stdout = old_std_out

        output = my_std_out.getvalue()
        print output
        self.assertTrue(output.find('**********ALUE') != -1)
        self.assertTrue(output.find('TEST_KEY_VALUE') == -1)
        self.assertTrue(output.find('None value detected for the credential: NONE_VALUE_KEY') != -1)

    def test_spot_price_estimation(self):
        spot_prices = """0.1
0.1
0.2
0.3
0.2
0.3"""
        (flexmock(utils)
             .should_receive('shell')
             .with_args('ec2-describe-spot-price-history -t m1.large | grep \'Linux/UNIX\' | awk \'{print $2}\'')
             .and_return(spot_prices))
        factory = InfrastructureAgentFactory()
        agent = factory.create_agent('ec2')
        self.assertEqual('{0:.2f}'.format(0.2 * 1.2),
            '{0:.2f}'.format(agent.get_optimal_spot_price('m1.large')))

    def run_instances(self, prefix, blocking):
        i = InfrastructureManager(blocking)

        # first, validate that the run_instances call goes through successfully
        # and gives the user a reservation id
        full_params = {
            'credentials' : {'a' : 'b', 'CLOUD1_EC2_URL' : 'http://ec2.url.com'},
            'group' : 'boogroup',
            'image_id' : 'booid',
            'infrastructure' : prefix,
            'instance_type' : 'booinstance_type',
            'keyname' : 'bookeyname',
            'num_vms' : '1',
            'spot' : 'False',
        }

        id = '0000000000'  # no longer randomly generated
        full_result = {
            'success' : True,
            'reservation_id' : id,
            'reason' : 'none'
        }
        self.assertEquals(full_result, i.run_instances(full_params, 'secret'))

        # next, look at run_instances internally to make sure it actually is
        # updating its reservation info
        if not blocking:
            time.sleep(2)
        self.assertEquals(InfrastructureManager.STATE_RUNNING, i.reservations[id]['state'])

        vm_info = i.reservations[id]['vm_info']
        self.assertEquals(['public-ip'], vm_info['public_ips'])
        self.assertEquals(['private-ip'], vm_info['private_ips'])
        self.assertEquals(['i-id'], vm_info['instance_ids'])

    def terminate_instances(self, prefix, blocking):
        i = InfrastructureManager(blocking)

        params1 = { 'infrastructure' : prefix }
        result1 = i.terminate_instances(params1, 'secret')
        self.assertFalse(result1['success'])
        self.assertEquals(result1['reason'], 'no credentials')

        params2 = {
            'credentials' : {'a' : 'b', 'CLOUD1_EC2_URL' : 'http://ec2.url.com'},
            'infrastructure' : prefix,
            'instance_ids' : [ 'i-12345' ]
        }
        result2 = i.terminate_instances(params2, 'secret')
        if not blocking:
            time.sleep(2)
        self.assertTrue(result2['success'])

    def do_set_up(self, prefix):
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
             .with_args('{0}-terminate-instances i-12345 2>&1'.format(prefix))
             .and_return('i-12345'))

        first_time = ''
        second_time = """
        RESERVATION     r-55560977      admin   default
        INSTANCE        i-id      emi-721D0EBA    public-ip    private-ip  running  bookeyname   0       c1.medium       2010-05-07T07:17:48.23Z         myueccluster    eki-675412F5    eri-A1E113E0"""
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-describe-instances 2>&1'.format(prefix))
             .and_return(first_time)
             .and_return(second_time))
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-run-instances -k bookeyname -n 1 --instance-type booinstance_type --group boogroup booid'.format(prefix))
             .and_return(''))
        (flexmock(utils)
             .should_receive('shell')
             .with_args('dig private-ip +short')
             .and_return('private-ip\n'))
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-add-keypair bookeyname 2>&1'.format(prefix))
             .and_return('BEGIN RSA PRIVATE KEY'))
        (flexmock(utils)
             .should_receive('write_key_file')
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-add-group boogroup -d appscale 2>&1'.format(prefix))
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-authorize boogroup -p 1-65535 -P udp 2>&1'.format(prefix))
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-authorize boogroup -p 1-65535 -P tcp 2>&1'.format(prefix))
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-authorize boogroup -s 0.0.0.0/0 -P icmp -t -1:-1 2>&1'.format(prefix))
             .and_return())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('env')
             .and_return(''))

    def do_tear_down(self, prefix):
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
             .with_args('{0}-terminate-instances i-12345 2>&1'.format(prefix))
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-describe-instances 2>&1'.format(prefix))
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-run-instances -k bookeyname -n 1 --instance-type booinstance_type --group boogroup booid'.format(prefix))
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('dig private-ip +short')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-add-keypair bookeyname 2>&1'.format(prefix))
             .reset())
        (flexmock(utils)
             .should_receive('write_key_file')
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-add-group boogroup -d appscale 2>&1'.format(prefix))
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-authorize boogroup -p 1-65535 -P udp 2>&1'.format(prefix))
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-authorize boogroup -p 1-65535 -P tcp 2>&1'.format(prefix))
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('{0}-authorize boogroup -s 0.0.0.0/0 -P icmp -t -1:-1 2>&1'.format(prefix))
             .reset())
        (flexmock(utils)
             .should_receive('shell')
             .with_args('env')
             .reset())

