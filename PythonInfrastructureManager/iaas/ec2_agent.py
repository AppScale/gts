from os import environ
from os.path import abspath
from infrastructure_manager import IaaSAgent

__author__ = 'hiranya'

class EC2Agent(IaaSAgent):

    def set_environment_variables(self, variables, cloud_num):
        IaaSAgent.set_environment_variables(self, variables, cloud_num)
        if environ.has_key('EC2_JVM_ARGS'):
            del(environ['EC2_JVM_ARGS'])
        ec2_keys_dir = abspath('/etc/appscale/keys/cloud' + str(cloud_num))
        environ['EC2_PRIVATE_KEY'] = ec2_keys_dir + '/mykey.pem'
        environ['EC2_CERT'] = ec2_keys_dir + '/mycert.pem'
        print 'Setting private key to:', environ['EC2_PRIVATE_KEY'], \
            'and certificate to: ', environ['EC2_CERT']