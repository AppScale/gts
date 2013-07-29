from agents.ec2_agent import EC2Agent
import boto
from urlparse import urlparse

__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

class EucalyptusAgent(EC2Agent):
  """
  Eucalyptus infrastructure agent which can be used to spawn and terminate
  VMs in an Eucalyptus based environment.
  """

  # The version of Eucalyptus API used to interact with Euca clouds
  EUCA_API_VERSION = '2010-08-31'

  def open_connection(self, parameters):
    """
    Initialize a connection to the back-end Eucalyptus APIs.

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
    if result.port is not None:
      port = result.port
    elif result.scheme == 'http':
      port = 80
    elif result.scheme == 'https':
      port = 443
    else:
      self.handle_failure('Unknown scheme in EC2_URL: ' + result.scheme)
      return None

    return boto.connect_euca(host=result.hostname,
      aws_access_key_id=access_key,
      aws_secret_access_key=secret_key,
      port=port,
      path=result.path,
      is_secure=(result.scheme == 'https'),
      api_version=self.EUCA_API_VERSION, debug=2)

  def __get_instance_info(self, instances, status, keyname):
    """
    Filter out a list of instances by instance status and keyname.

    Args:
      instances: A list of instances as returned by __describe_instances.
      status: Status of the VMs (e.g., running, terminated).
      keyname: Keyname used to spawn instances.

    Returns:
      A tuple of the form (public ips, private ips, instance ids).
    """
    instance_ids = []
    public_ips = []
    private_ips = []
    for i in instances:
      if i.state == status and i.key_name == keyname:
        instance_ids.append(i.id)
        public_ips.append(i.ip_address)
        private_ips.append(i.private_ip_address)
    return public_ips, private_ips, instance_ids
