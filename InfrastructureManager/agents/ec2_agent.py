from agents.base_agent import BaseAgent, AgentConfigurationException, AgentRuntimeException
import datetime
import os
import re
import time
from utils import utils

__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

class EC2Agent(BaseAgent):
  """
  EC2 infrastructure agent class which can be used to spawn and terminate
  VMs in an EC2 based environment.
  """

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

  PARAM_CREDENTIALS = 'credentials'
  PARAM_GROUP = 'group'
  PARAM_IMAGE_ID = 'image_id'
  PARAM_INSTANCE_TYPE = 'instance_type'
  PARAM_KEYNAME = 'keyname'
  PARAM_INSTANCE_IDS = 'instance_ids'

  REQUIRED_EC2_RUN_INSTANCES_PARAMS = (
    PARAM_CREDENTIALS,
    PARAM_GROUP,
    PARAM_IMAGE_ID,
    PARAM_INSTANCE_TYPE,
    PARAM_KEYNAME
    )

  REQUIRED_EC2_TERMINATE_INSTANCES_PARAMS = (
    PARAM_CREDENTIALS,
    PARAM_INSTANCE_IDS
  )

  RUN_INSTANCES_RETRY_COUNT = 3
  ADD_KEY_PAIR_RETRY_COUNT = 3
  DESCRIBE_INSTANCES_RETRY_COUNT = 3

  def __init__(self):
    self.prefix = 'ec2'

  def set_environment_variables(self, parameters):
    """
    Set the EC2 specific environment variables. Required values for the
    environment variables are read from the 'credentials' parameter of
    the parameters map. (Also see documentation for the BaseAgent class)

    Args:
      parameters  A dictionary containing the 'credentials' key
    """
    if os.environ.has_key('EC2_JVM_ARGS'):
      del(os.environ['EC2_JVM_ARGS'])

    variables = parameters[self.PARAM_CREDENTIALS]
    for key, value in variables.items():
      if value is None:
        utils.log('None value detected for the credential: {0}.'.format(key))
        continue

      if key.find('KEY') != -1:
        utils.log('Setting {0} to {1} in our environment.'.format(
          key, utils.obscure_string(value)))
      else:
        utils.log('Setting {0} to {1} in our environment.'.format(key, value))
      os.environ[key] = value

    ec2_keys_dir = os.path.abspath('/etc/appscale/keys/cloud1')
    os.environ['EC2_PRIVATE_KEY'] = ec2_keys_dir + '/mykey.pem'
    os.environ['EC2_CERT'] = ec2_keys_dir + '/mycert.pem'
    utils.log('Setting private key to: {0} and certificate to: {1}'.format(
      os.environ['EC2_PRIVATE_KEY'], os.environ['EC2_CERT']))

  def configure_instance_security(self, parameters):
    """
    Setup EC2 security keys and groups. Required input values are read from
    the parameters dictionary. More specifically, this method expects to
    find a 'keyname' parameter and a 'group' parameter in the parameters
    dictionary. Using these provided values, this method will create a new
    EC2 key-pair and a security group. Security group will be granted permissions
    to access any port on the instantiated VMs. (Also see documentation for the
    BaseAgent class)

    Args:
      parameters  A dictionary of parameters
    """
    keyname = parameters[self.PARAM_KEYNAME]
    group = parameters[self.PARAM_GROUP]
    ssh_key = os.path.abspath('/etc/appscale/keys/cloud1/{0}.key'.format(keyname))
    utils.log('About to spawn EC2 instances - Expecting to find a key at {0}'.format(ssh_key))
    utils.log(utils.get_obscured_env(['EC2_ACCESS_KEY', 'EC2_SECRET_KEY']))
    if not os.path.exists(ssh_key):
      utils.log('Creating keys/security group')
      ec2_output = ''
      attempts = 1
      while True:
        ec2_output = utils.shell('{0}-add-keypair {1} 2>&1'.format(self.prefix, keyname))
        if ec2_output.find('BEGIN RSA PRIVATE KEY') != -1:
          break
        elif attempts == self.ADD_KEY_PAIR_RETRY_COUNT:
          raise AgentRuntimeException('Failed to invoke add_keypair')
        utils.log('Trying again. Saw this from {0}-add-keypair: {1}'.format(
          self.prefix, ec2_output))
        utils.shell('{0}-delete-keypair {1} 2>&1'.format(self.prefix, keyname))
      utils.write_key_file(ssh_key, ec2_output)
      utils.shell('{0}-add-group {1} -d appscale 2>&1'.format(self.prefix, group))
      utils.shell('{0}-authorize {1} -p 1-65535 -P udp 2>&1'.format(self.prefix, group))
      utils.shell('{0}-authorize {1} -p 1-65535 -P tcp 2>&1'.format(self.prefix, group))
      utils.shell('{0}-authorize {1} -s 0.0.0.0/0 -P icmp -t -1:-1 2>&1'.format(self.prefix, group))
      return True
    else:
      utils.log('Not creating keys/security group')
      return False

  def assert_required_parameters(self, parameters, operation):
    """
    Assert that all the parameters required for the EC2 agent are in place.
    (Also see documentation for the BaseAgent class)

    Args:
      parameters  A dictionary of parameters
      operation   Operations to be invoked using the above parameters
    """
    required_params = ()
    if operation == BaseAgent.OPERATION_RUN:
      required_params = self.REQUIRED_EC2_RUN_INSTANCES_PARAMS
    elif operation == BaseAgent.OPERATION_TERMINATE:
      required_params = self.REQUIRED_EC2_TERMINATE_INSTANCES_PARAMS

    for param in required_params:
      if not utils.has_parameter(param, parameters):
        raise AgentConfigurationException('no ' + param)

  def describe_instances(self, parameters):
    """
    Execute the ec2-describe-instances command and returns a summary of the
    already running EC2 instances. (Also see documentation for the BaseAgent
    class)

    Args:
      parameters  A dictionary containing the 'keyname' parameter

    Returns:
      A tuple of the form (public_ips, private_ips, instances) where each
      member is a list.
    """
    keyname = parameters[self.PARAM_KEYNAME]
    describe_instances = utils.shell(self.prefix + '-describe-instances 2>&1')
    utils.log('describe-instances says {0}'.format(describe_instances))
    fqdn_regex = re.compile('\s+({0})\s+({0})\s+running\s+{1}\s'.format(self.FQDN_REGEX, keyname))
    instance_regex = re.compile('INSTANCE\s+(i-\w+)')
    all_ip_addresses = utils.flatten(fqdn_regex.findall(describe_instances))
    instances = utils.flatten(instance_regex.findall(describe_instances))
    public_ips, private_ips = self.get_ip_addresses(all_ip_addresses)
    return public_ips, private_ips, instances

  def run_instances(self, count, parameters, security_configured):
    """
    Spawn the specified number of EC2 instances using the parameters
    provided. This method relies on the ec2-run-instances command to
    spawn the actual VMs in the cloud. This method is blocking in that
    it waits until the requested VMs are properly booted up. However
    if the requested VMs cannot be procured within 1800 seconds, this
    method will treat it as an error and return. (Also see documentation
    for the BaseAgent class)

    Args:
      count               No. of VMs to spawned
      parameters          A dictionary of parameters. This must contain 'keyname',
                          'group', 'image_id' and 'instance_type' parameters.
      security_configured Uses this boolean value as an heuristic to
                          detect brand new AppScale deployments.

    Returns:
      A tuple of the form (instances, public_ips, private_ips)
    """
    image_id = parameters[self.PARAM_IMAGE_ID]
    instance_type = parameters[self.PARAM_INSTANCE_TYPE]
    keyname = parameters[self.PARAM_KEYNAME]
    group = parameters[self.PARAM_GROUP]
    spot = False

    utils.log('[{0}] [{1}] [{2}] [{3}] [ec2] [{4}] [{5}]'.format(count,
      image_id, instance_type, keyname, group, spot))

    start_time = datetime.datetime.now()
    active_public_ips = []
    active_private_ips = []
    active_instances = []
    if os.environ.has_key('EC2_URL'):
      utils.log('EC2_URL = [{0}]'.format(os.environ['EC2_URL']))
    else:
      utils.log('Warning: EC2_URL environment not found in the process runtime!')

    attempts = 1
    while True:
      active_public_ips, active_private_ips, active_instances =\
      self.describe_instances(parameters)
      # If security has been configured on this agent just now,
      # that's an indication that this is a fresh cloud deployment.
      # As such it's not expected to have any running VMs.
      if len(active_instances) > 0 or security_configured:
        break
      elif attempts == self.DESCRIBE_INSTANCES_RETRY_COUNT:
        raise AgentRuntimeException('Failed to invoke describe_instances')
      attempts += 1

    args = '-k {0} -n {1} --instance-type {2} --group {3} {4}'.format(keyname,
      count, instance_type, group, image_id)
    if spot:
      price = self.get_optimal_spot_price(instance_type)
      command_to_run = '{0}-request-spot-instances -p {1} {2}'.format(self.prefix, price, args)
    else:
      command_to_run = '{0}-run-instances {1}'.format(self.prefix, args)

    attempts = 1
    while True:
      run_instances = utils.shell(command_to_run)
      utils.log('Run instances says {0}'.format(run_instances))
      status, command_to_run = self.run_instances_response(command_to_run, run_instances)
      if status:
        break
      elif attempts == self.RUN_INSTANCES_RETRY_COUNT:
        raise AgentRuntimeException('Failed to invoke run_instances')
      attempts += 1
      utils.log('sleepy time')
      utils.sleep(5)

    instances = []
    public_ips = []
    private_ips = []
    utils.sleep(10)

    end_time = datetime.datetime.now() + datetime.timedelta(0, self.MAX_VM_CREATION_TIME)
    now = datetime.datetime.now()
    while now < end_time:
      describe_instances = utils.shell(self.prefix + '-describe-instances 2>&1')
      utils.log('[{0}] {1} seconds left...'.format(now, (end_time - now).seconds))
      utils.log(describe_instances)
      fqdn_regex = re.compile('\s+({0})\s+({0})\s+running\s+{1}\s'.format(self.FQDN_REGEX, keyname))
      instance_regex = re.compile('INSTANCE\s+(i-\w+)')
      all_ip_addresses = utils.flatten(fqdn_regex.findall(describe_instances))
      instances = utils.flatten(instance_regex.findall(describe_instances))
      public_ips, private_ips = self.get_ip_addresses(all_ip_addresses)
      public_ips = utils.diff(public_ips, active_public_ips)
      private_ips = utils.diff(private_ips, active_private_ips)
      instances = utils.diff(instances, active_instances)
      if count == len(public_ips):
        break
      time.sleep(self.SLEEP_TIME)
      now = datetime.datetime.now()

    if not public_ips:
      raise AgentRuntimeException('No public IPs were able to be procured within the time limit')

    if len(public_ips) != count:
      for index in range(0, len(public_ips)):
        if public_ips[index] == '0.0.0.0':
          instance_to_term = instances[index]
          utils.log('Instance {0} failed to get a public IP address and is being terminated'.\
          format(instance_to_term))
          utils.shell(self.prefix + '-terminate-instances ' + instance_to_term)
      pass

    end_time = datetime.datetime.now()
    total_time = end_time - start_time
    if spot:
      utils.log('TIMING: It took {0} seconds to spawn {1} spot instances'.format(
        total_time.seconds, count))
    else:
      utils.log('TIMING: It took {0} seconds to spawn {1} regular instances'.format(
        total_time.seconds, count))
    return instances, public_ips, private_ips

  def terminate_instances(self, parameters):
    """
    Stop one of more EC2 instances using the ec2-terminate-instance command.
    The input instance IDs are fetched from the 'instance_ids' parameters
    in the input map. (Also see documentation for the BaseAgent class)

    Args:
      parameters  A dictionary of parameters
    """
    instance_ids = parameters[self.PARAM_INSTANCE_IDS]
    arg = ' '.join(instance_ids)
    utils.shell('{0}-terminate-instances {1} 2>&1'.format(self.prefix, arg))

  def run_instances_response(self, command, output):
    """
    Local utility method to parse the validate the output of ec2-run-instances
    command.

    Args:
      command Exact command executed
      output Output of the command

    Returns:
      A tuple of the form (status,command) where status is a boolean value
      indicating the success/failure status of the output and command is
      the modified command to be retried in case the previous attempt had
      failed.
    """
    if output.find('Please try again later') != -1:
      utils.log('Error with run instances: {0}. Will try again in a moment.'.format(output))
      return False, command
    elif output.find('try --addressing private') != -1:
      utils.log('Need to retry with addressing private. Will try again in a moment.')
      return False, command + ' --addressing private'
    elif output.find('PROBLEM') != -1:
      utils.log('Error: {0}'.format(output))
      raise AgentRuntimeException('Saw the following error from EC2 tools: {0}'.format(output))
    else:
      utils.log('Run instances message sent successfully. Waiting for the image to start up.')
      return True, command

  def get_optimal_spot_price(self, instance_type):
    """
    Returns the spot price for an EC2 instance of the specified instance type.
    ec2-describe-spot-price-history command is used to obtain a set of spot
    prices from EC2 and the returned value is computed by averaging all the
    returned values and incrementing it by extra 20%.

    Args:
      instance_type An EC2 instance type

    Returns:
      The estimated spot price for the specified instance type
    """
    command = 'ec2-describe-spot-price-history -t {0} | grep \'Linux/UNIX\' | '\
              'awk \'{{print $2}}\''.format(instance_type)
    prices = utils.shell(command).split('\n')
    sum = 0.0
    for price in prices:
      sum += float(price)
    average = sum / len(prices)
    plus_twenty = average * 1.20
    utils.log('The average spot instance price for a {0} machine is {1}, '\
              'and 20% more is {2}'.format(instance_type, average, plus_twenty))
    return plus_twenty

  def get_ip_addresses(self, all_addresses):
    """
    Extract public IPs and private IPs from a list of IP addresses.
    This method is used to extract the IP addresses from the EC2
    command outputs.

    Args:
      all_addresses A list of IP addresses

    Returns:
      A tuple of the form (public_ips, private_ips)
    """
    if len(all_addresses) % 2 != 0:
      raise AgentRuntimeException('IP address list is not of even length')
    reported_public = []
    reported_private = []
    for index in range(0, len(all_addresses)):
      if index % 2 == 0:
        reported_public.append(all_addresses[index])
      else:
        reported_private.append(all_addresses[index])
    utils.log('Reported public IPs: {0}'.format(reported_public))
    utils.log('Reported private IPs: {0}'.format(reported_private))

    actual_public = []
    actual_private = []
    for index in range(0, len(reported_public)):
      public = reported_public[index]
      private = reported_private[index]
      if public != '0.0.0.0' and private != '0.0.0.0':
        actual_public.append(public)
        actual_private.append(private)

    for index in range(0, len(actual_private)):
      ip = utils.convert_fqdn_to_ip(actual_private[index])
      if ip is not None:
        actual_private[index] = ip
      else:
        utils.log('Failed to convert {0} into an IP'.format(actual_private[index]))

    return actual_public, actual_private