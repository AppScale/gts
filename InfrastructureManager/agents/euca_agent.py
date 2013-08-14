from agents.ec2_agent import EC2Agent
import boto
import glob
from urlparse import urlparse
from utils import utils

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


  def attach_disk(self, parameters, disk_name, instance_id):
    """ Attaches the Elastic Block Store volume specified in 'disk_name' to this
    virtual machine.

    This method differs from its EC2 counterpart because in EC2, we can ask the
    cloud to attach the disk to a certain location. In Euca, it determines where
    the disk gets placed, so we have to learn where it placed the disk and
    return that location instead.

    Args:
      parameters: A dict with keys for each parameter needed to connect to AWS.
      disk_name: A str naming the EBS mount to attach to this machine.
      instance_id: A str naming the id of the instance that the disk should be
        attached to. In practice, callers add disks to their own instances.
    Returns:
      The location on the local filesystem where the disk has been attached.
    """
    devices_before_attach = glob.glob('/dev/*')
    EC2Agent.attach_disk(self, parameters, disk_name, instance_id)
    while True:
      devices_after_attach = glob.glob('/dev/*')
      new_devices = utils.diff(devices_after_attach, devices_before_attach)
      if new_devices:
        utils.log("Found new attached devices: {0}".format(new_devices))
        if len(new_devices) == 1:
          utils.log("Found exactly one new attached device at {0}".format(
            new_devices[0]))
          return new_devices[0]
        else:
          self.handle_failure("Found too many new attached devices - not sure" \
            " which one is the device we attached. New devices are {0}".format(
            new_devices))
      else:
        utils.log("Still waiting for attached device to appear.")
        utils.sleep(1)


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
