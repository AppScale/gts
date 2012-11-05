from datetime import datetime
from os import environ
from os.path import abspath
from os.path import exists
import re
import sys
from time import sleep
from agents.base_agent import BaseAgent
from utils.utils import shell, flatten, get_ip_addresses, has_parameter

__author__ = 'hiranya'

# A regular expression that matches fully qualified domain names, used to
# parse output from describe-instances to see the FQDNs for machines
# currently running.
FQDN_REGEX = '[\w\d\.\-]+'

# The maximum amount of time, in seconds, that we are willing to wait for
# a virtual machine to start up, from the initial run-instances request.
# Setting this value is a bit of an art, but we choose the value below
# because our image is roughly 10GB in size, and if Eucalyptus doesn't
# have the image cached, it could take half an hour to get our image
# started.
MAX_VM_CREATION_TIME = 1800

# The amount of time that run_instances waits between each describe-instances
# request. Setting this value too low can cause Eucalyptus to interpret
# requests as replay attacks.
SLEEP_TIME = 20

PARAM_CREDENTIALS       = 'credentials'
PARAM_GROUP             = 'group'
PARAM_IMAGE_ID          = 'image_id'
PARAM_INSTANCE_TYPE     = 'instance_type'
PARAM_KEYNAME           = 'keyname'

REQUIRED_EC2_RUN_INSTANCES_PARAMS = (
    PARAM_CREDENTIALS,
    PARAM_GROUP,
    PARAM_IMAGE_ID,
    PARAM_INSTANCE_TYPE,
    PARAM_KEYNAME
)

class EC2Agent(BaseAgent):

    def __init__(self):
        self.prefix = 'ec2'
        self.new_cloud = True

    def set_environment_variables(self, variables, cloud_num):
        BaseAgent.set_environment_variables(self, variables, cloud_num)
        if environ.has_key('EC2_JVM_ARGS'):
            del(environ['EC2_JVM_ARGS'])
        ec2_keys_dir = abspath('/etc/appscale/keys/cloud' + str(cloud_num))
        environ['EC2_PRIVATE_KEY'] = ec2_keys_dir + '/mykey.pem'
        environ['EC2_CERT'] = ec2_keys_dir + '/mycert.pem'
        print 'Setting private key to: {0} and certificate to: {1}'.format(
            environ['EC2_PRIVATE_KEY'], environ['EC2_CERT'])

    def configure_instance_security(self, parameters):
        keyname = parameters[PARAM_KEYNAME]
        cloud = parameters['cloud']
        ssh_key = abspath('/etc/appscale/keys/{0}/{1}.key'.format(cloud, keyname))
        print 'About to spawn EC2 instances - Expecting to find a key at', ssh_key
        #TODO: log obscured
        self.new_cloud = not exists(ssh_key)
        if self.new_cloud:
            print 'Creating keys/security group for', cloud
            #TODO: generate key
            #TODO: create appscale security group
        else:
            print 'Not creating keys/security group for', cloud

    def has_required_parameters(self, parameters):
        for param in REQUIRED_EC2_RUN_INSTANCES_PARAMS:
            if not has_parameter(param, parameters):
                return False, 'no ' + param
        return True, 'none'

    def describe_instances(self, parameters):
        keyname = parameters[PARAM_KEYNAME]
        instances = []
        public_ips = []
        private_ips = []
        print 'EC2_URL = [{0}]'.format(environ['EC2_URL'])
        while True:
            describe_instances = shell(self.prefix + '-describe-instances 2>&1')
            print 'describe-instances says', describe_instances
            fqdn_regex = re.compile('\s+({0})\s+({0})\s+running\s+{1}\s'.format(FQDN_REGEX, keyname))
            instance_regex = re.compile('INSTANCE\s+(i-\w+)')
            vm_count_regex = re.compile('({0})\s+running\s+#{keyname}\s+'.format(FQDN_REGEX))
            all_ip_addresses = flatten(fqdn_regex.findall(describe_instances))
            instances = flatten(instance_regex.findall(describe_instances))
            public_ips, private_ips = get_ip_addresses(all_ip_addresses)
            vms_up_already = len(vm_count_regex.findall(describe_instances))
            if vms_up_already > 0 or self.new_cloud:
                break
        return public_ips, private_ips, instances

    def run_instances(self, count, parameters):
        image_id = parameters[PARAM_IMAGE_ID]
        instance_type = parameters[PARAM_INSTANCE_TYPE]
        keyname = parameters[PARAM_KEYNAME]
        group = parameters[PARAM_GROUP]
        cloud = parameters['cloud']
        spot = False

        print '[{0}] [{1}] [{2}] [{3}] [ec2] [{4}] [{5}] [{6}]'.format(count,
            image_id, instance_type, keyname, cloud, group, spot)

        start_time = datetime.now()
        active_public_ips, active_private_ips, active_instances = self.describe_instances(
            parameters)
        args = '-k {0} -n {1} --instance-type {2} --group {3} {4}'.format(keyname,
            count, instance_type, group, image_id)
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

        instances = []
        public_ips = []
        private_ips = []
        sleep(10)

        end_time = datetime.now() + datetime.timedelta(0, MAX_VM_CREATION_TIME)
        now = datetime.now()
        while now < end_time:
            describe_instances = shell(self.prefix + '-describe-instances 2>&1')
            print '[{0}] {1} seconds left...'.format(now, (end_time - now).seconds)
            print describe_instances

            #TODO: regex stuff
            sleep(SLEEP_TIME)
            now = datetime.now()

        if not public_ips:
            sys.exit('No public IPs were able to be procured within the time limit')

        if len(public_ips) != count:
            pass
            #TODO: More regex stuff

        end_time = datetime.now()
        total_time = end_time - start_time
        if spot:
            print 'TIMING: It took {0} seconds to spawn {1} spot instances'.format(
                total_time.seconds, count)
        else:
            print 'TIMING: It took {0} seconds to spawn {1} regular instances'.format(
                total_time.seconds, count)
        return instances, public_ips, private_ips

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














