from datetime import datetime
from os import environ
from os.path import abspath
from os.path import exists
import re
import sys
from time import sleep
from agents.agent import InfrastructureAgent
from utils.utils import shell, flatten, get_ip_addresses

__author__ = 'hiranya'

# A regular expression that matches fully qualified domain names, used to
# parse output from describe-instances to see the FQDNs for machines
# currently running.
FQDN_REGEX = '[\w\d\.\-]+'

class EC2Agent(InfrastructureAgent):

    def __init__(self):
        self.prefix = 'ec2'

    def set_environment_variables(self, variables, cloud_num):
        InfrastructureAgent.set_environment_variables(self, variables, cloud_num)
        if environ.has_key('EC2_JVM_ARGS'):
            del(environ['EC2_JVM_ARGS'])
        ec2_keys_dir = abspath('/etc/appscale/keys/cloud' + str(cloud_num))
        environ['EC2_PRIVATE_KEY'] = ec2_keys_dir + '/mykey.pem'
        environ['EC2_CERT'] = ec2_keys_dir + '/mycert.pem'
        print 'Setting private key to: {0} and certificate to: {1}'.format(
            environ['EC2_PRIVATE_KEY'], environ['EC2_CERT'])

    def spawn_vms(self, parameters):
        # TODO: make the interface more low level
        # TODO: describe_instances, run_instances, setup_login etc
        num_vms = parameters['num_vms']
        image_id = parameters['image_id']
        instance_type = parameters['instance_type']
        keyname = parameters['keyname']
        group = parameters['group']
        cloud = parameters['cloud']
        spot = False

        print '[{0}] [{1}] [{2}] [{3}] [ec2] [{4}] [{5}] [{6}]'.format(num_vms,
            image_id, instance_type, keyname, cloud, group, spot)

        start_time = datetime.now()

        public_ips = []
        private_ips = []
        instance_ids = []

        if num_vms < 0:
            return public_ips, private_ips, instance_ids

        ssh_key = abspath('/etc/appscale/keys/{0}/{1}.key'.format(cloud, keyname))
        print 'About to spawn EC2 instances - Expecting to find a key at', ssh_key

        #TODO: log obscured

        new_cloud = not exists(ssh_key)
        if new_cloud:
            print 'Creating keys/security group for', cloud
            #TODO: generate key
            #TODO: create appscale security group
        else:
            print 'Not creating keys/security group for', cloud

        instance_ids_up = []
        public_up_already = []
        private_up_already = []
        print 'EC2_URL = [{0}]'.format(environ['EC2_URL'])
        while True:
            describe_instances = shell(self.prefix + '-describe-instances 2>&1')
            print 'describe-instances says', describe_instances
            fqdn_regex = re.compile('\s+({0})\s+({0})\s+running\s+{1}\s'.format(FQDN_REGEX, keyname))
            instance_regex = re.compile('INSTANCE\s+(i-\w+)')
            vm_count_regex = re.compile('({0})\s+running\s+#{keyname}\s+'.format(FQDN_REGEX))
            all_ip_addresses = flatten(fqdn_regex.findall(describe_instances))
            instance_ids_up = flatten(instance_regex.findall(describe_instances))
            public_up_already, private_up_already = get_ip_addresses(all_ip_addresses)
            vms_up_already = len(vm_count_regex.findall(describe_instances))
            if vms_up_already > 0 or new_cloud:
                break

        args = '-k {0} -n {1} --instance-type {2} --group {3} {4}'.format(keyname,
            num_vms, instance_type, group, image_id)
        if spot:
            price = self.get_optimal_spot_price(instance_type)
            command_to_run = '{0}-request-spot-instances -p {1} {2}'.format(self.prefix, price, args)
        else:
            command_to_run = '{0}-run-instances {1}'.format(self.prefix, args)

        while True:
            print command_to_run
            run_instances = shell(command_to_run)
            print 'Run instances says', run_instances
            status, command_to_run = self.run_instances_response(command_to_run, run_instances)
            if status:
                break
            print 'sleepy time'
            sleep(5)

    def run_instances_response(self, command, output):
        if output.find('Please try again later') != -1:
            print 'Error with run instances: {0}. Will try again in a moment.'.format(output)
            return False, command
        elif output.find('try --addressing private') != -1:
            print 'Need to retry with addressing private. Will try again in a moment.'
            return False, command + ' --addressing private'
        elif output.find('PROBLEM') != -1:
            print 'Error:', output
            sys.exit('Saw the following error from EC2 tools: {0}'.format(output))
        else:
            print 'Run instances message sent successfully. Waiting for the image to start up.'
            return True, command

    def get_optimal_spot_price(self, instance_type):
        return None














