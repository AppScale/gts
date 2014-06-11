from agents.ec2_agent import EC2Agent
import boto
import glob
from urlparse import urlparse
from utils import utils

__author__ = 'dario nascimento'
__email__ = 'dario.nascimento@tecnico.ulisboa.pt'

class OpenStackAgent(EC2Agent):
  """
  OpenStack infrastructure agent which can be used to spawn and terminate
  VMs in an OpenStack based environment.
  """

  # The version of OpenStack API used to interact with Boto 
  # OpenStack_API_VERSION = 'ICE-HOUSE-2014.1'

  def configure_instance_security(self, parameters):
    """
    Setup EC2 security keys and groups. Required input values are read from
    the parameters dictionary. More specifically, this method expects to
    find a 'keyname' parameter and a 'group' parameter in the parameters
    dictionary. Using these provided values, this method will create a new
    EC2 key-pair and a security group. Security group will be granted permissions
    to access any port on the instantiated VMs. (Also see documentation for the
    BaseAgent class)

    This method differs from its EC2 counterpart because in OpenStack the security group
    definition for icmp must include the port range.

    Args:
      parameters  A dictionary of parameters
    """
    keyname = parameters[self.PARAM_KEYNAME]
    group = parameters[self.PARAM_GROUP]

    key_path = '/etc/appscale/keys/cloud1/{0}.key'.format(keyname)
    ssh_key = os.path.abspath(key_path)
    utils.log('About to spawn EC2 instances - ' \
              'Expecting to find a key at {0}'.format(ssh_key))
    if os.path.exists(ssh_key):
      utils.log('SSH keys found in the local system - '
                'Not initializing EC2 security')
      return False

    try:
      conn = self.open_connection(parameters)
      key_pair = conn.get_key_pair(keyname)
      if key_pair is None:
        utils.log('Creating key pair: ' + keyname)
        key_pair = conn.create_key_pair(keyname)
      utils.write_key_file(ssh_key, key_pair.material)

      security_groups = conn.get_all_security_groups()
      group_exists = False
      for security_group in security_groups:
        if security_group.name == group:
          group_exists = True
          break

      if not group_exists:
        utils.log('Creating security group: ' + group)
        conn.create_security_group(group, 'AppScale security group')
        conn.authorize_security_group(group, from_port=1,
          to_port=65535, ip_protocol='udp')
        conn.authorize_security_group(group, from_port=1,
          to_port=65535, ip_protocol='tcp')
        #TODO: test if compatible with EC2 too, then change EC2_agent and remove this method
        conn.authorize_security_group(group, from_port=-1, to_port=-1, 
                              ip_protocol='icmp', cidr_ip='0.0.0.0/0')

      return True
    except EC2ResponseError as exception:
      self.handle_failure('EC2 response error while initializing '
                          'security: ' + exception.error_message)
    except Exception as exception:
      self.handle_failure('Error while initializing EC2 '
                          'security: ' + exception.message)




  def run_instances(self, count, parameters, security_configured):
    """
    Spawns the specified number of EC2 instances using the parameters
    provided. This method is blocking in that it waits until the
    requested VMs are properly booted up. However if the requested
    VMs cannot be procured within 1800 seconds, this method will treat
    it as an error and return. (Also see documentation for the BaseAgent
    class)


    This method differs from its EC2 counterpart because OpenStack does not
    support spot instances.
    Args:
      count               No. of VMs to spawned
      parameters          A dictionary of parameters. This must contain 'keyname',
                          'group', 'image_id' and 'instance_type' parameters.
      security_configured Uses this boolean value as an heuristic to
                          detect brand new AppScale deployments.

    Returns:
      A tuple of the form (instances, public_ips, private_ips)
    """
    if  parameters[self.PARAM_SPOT] == "True":
        parameters[self.PARAM_SPOT] = 'False'
        utils.log("OpenStack does not support spot instances")

    super.run_instances(self,count,parameters,security_configured)


  #expected url: http://192.168.2.12:8773/services/Cloud
  def open_connection(self, parameters):
    """
    Initialize a connection to the back-end OpenStack APIs.

    Args:
      parameters  A dictionary containing the 'credentials' parameter

    Returns:
      An instance of Boto EC2Connection
    """
    credentials = parameters[self.PARAM_CREDENTIALS]
    access_key = str(credentials['EC2_ACCESS_KEY'])
    secret_key = str(credentials['EC2_SECRET_KEY'])
    ec2_url = str(credentials['EC2_URL'])

    result = urlparse(ec2_url)

    if result.port is not None and result.hostname is not None and result.path is not None:
      port = result.port
    else:
      self.handle_failure('Unknown scheme in Openstack_URL: ' + result.scheme+ ' : expected like http://<controller>:8773/services/Cloud')
      return None


    #TODO: region may not be "nova"
    region = boto.ec2.regioninfo.RegionInfo(name="nova", endpoint="192.168.2.12") 
    return boto.connect_ec2(aws_access_key_id=access_key, aws_secret_access_key=secret_key, 
                                        is_secure=(result.scheme == 'https'), 
                                        region=region, 
                                        port=result.port, 
                                        path=result.path,debug=2) 
