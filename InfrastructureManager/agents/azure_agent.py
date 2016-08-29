#!/usr/bin/env python
"""
This file provides a single class, AzureAgent, that the AppScale Tools can use to
interact with Microsoft Azure.
"""

# General-purpose Python library imports
import adal
import os.path
import time

# Azure specific imports
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import CachingTypes
from azure.mgmt.compute.models import DiskCreateOptionTypes
from azure.mgmt.compute.models import HardwareProfile
from azure.mgmt.compute.models import LinuxConfiguration
from azure.mgmt.compute.models import NetworkProfile
from azure.mgmt.compute.models import NetworkInterfaceReference
from azure.mgmt.compute.models import OperatingSystemTypes
from azure.mgmt.compute.models import OSDisk
from azure.mgmt.compute.models import OSProfile
from azure.mgmt.compute.models import SshConfiguration
from azure.mgmt.compute.models import SshPublicKey
from azure.mgmt.compute.models import StorageProfile
from azure.mgmt.compute.models import VirtualHardDisk
from azure.mgmt.compute.models import VirtualMachine
from azure.mgmt.compute.models import VirtualMachineSizeTypes

from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import AddressSpace
from azure.mgmt.network.models import IPAllocationMethod
from azure.mgmt.network.models import NetworkInterfaceIPConfiguration
from azure.mgmt.network.models import NetworkInterface
from azure.mgmt.network.models import PublicIPAddress
from azure.mgmt.network.models import Subnet
from azure.mgmt.network.models import VirtualNetwork

from haikunator import Haikunator

# AppScale-specific imports
from agents.base_agent import AgentConfigurationException
from agents.base_agent import AgentRuntimeException
from agents.base_agent import BaseAgent
from utils import utils

class AzureAgent(BaseAgent):
  """ AzureAgent defines a specialized BaseAgent that allows for interaction
  with Microsoft Azure. It authenticates using the ADAL (Active Directory
  Authentication Library).
  """
  # The Azure URL endpoint that receives all the authentication requests.
  AZURE_AUTH_ENDPOINT = 'https://login.microsoftonline.com/'

  # The Azure Resource URL to get the authentication token using client credentials.
  AZURE_RESOURCE_URL = 'https://management.core.windows.net/'

  # The default Storage Account name to use for Azure.
  DEFAULT_STORAGE_ACCT = 'appscalestorage'

  # The default resource group name to use for Azure.
  DEFAULT_RESOURCE_GROUP = 'appscalegroup'

  # The following constants are string literals that can be used by callers to
  # index into the parameters that the user passes in, as opposed to having to
  # type out the strings each time we need them.
  PARAM_APP_ID = 'app_id'
  PARAM_APP_SECRET = 'app_secret_key'
  PARAM_CREDENTIALS = 'credentials'
  PARAM_EXISTING_RG = 'does_exist'
  PARAM_GROUP = 'group'
  PARAM_INSTANCE_IDS = 'instance_ids'
  PARAM_KEYNAME = 'keyname'
  PARAM_IMAGE_ID = 'image_id'
  PARAM_REGION = 'region'
  PARAM_RESOURCE_GROUP = 'resource_group'
  PARAM_STORAGE_ACCOUNT = 'storage_account'
  PARAM_SUBCR_ID = 'subscription_id'
  PARAM_TENANT_ID = 'tenant_id'
  PARAM_TEST = 'test'
  PARAM_TAG = 'group_tag'
  PARAM_VERBOSE = 'is_verbose'
  PARAM_ZONE = 'zone'

  # A set that contains all of the items necessary to run AppScale in Azure.
  REQUIRED_CREDENTIALS = (
    PARAM_APP_SECRET,
    PARAM_APP_ID,
    PARAM_IMAGE_ID,
    PARAM_KEYNAME,
    PARAM_SUBCR_ID,
    PARAM_TENANT_ID,
    PARAM_ZONE
  )

  # The admin username needed to create an Azure VM instance.
  ADMIN_USERNAME = 'azureuser'

  # The file path for the authorized keys on the head node
  # for an Azure VM.
  AUTHORIZED_KEYS_FILE = "/home/{}/.ssh/authorized_keys"

  # The maximum number of seconds to sleep while waiting for
  # Azure resources to get created.
  SLEEP_TIME = 10

  def configure_instance_security(self, parameters):
    """ Configure and setup groups and storage accounts for the VMs spawned.
    This method is called before starting virtual machines.
    Args:
      parameters: A dict containing values necessary to authenticate with the
        underlying cloud.
    Returns:
      True, if the group and account were created successfully.
      False, otherwise.
    Raises:
      AgentRuntimeException: If security features could not be successfully
        configured in the underlying cloud.
    """
    return True

  def describe_instances(self, parameters, pending=False):
    """ Queries Microsoft Azure to see which instances are currently
    running, and retrieves information about their public and private IPs.
    Args:
      parameters: A dict containing values necessary to authenticate with the
        underlying cloud.
      pending: If we should show pending instances.
    Returns:
      public_ips: A list of public IP addresses.
      private_ips: A list of private IP addresses.
      instance_ids: A list of unique Azure VM names.
    """
    credentials = self.open_connection(parameters)
    subscription_id = str(parameters[self.PARAM_SUBCR_ID])
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    network_client = NetworkManagementClient(credentials, subscription_id)
    compute_client = ComputeManagementClient(credentials, subscription_id)
    public_ips = []
    private_ips = []
    instance_ids = []

    public_ip_addresses = network_client.public_ip_addresses.list(resource_group)
    for public_ip in public_ip_addresses:
      public_ips.append(public_ip.ip_address)

    network_interfaces = network_client.network_interfaces.list(resource_group)
    for network_interface in network_interfaces:
      for ip_config in network_interface.ip_configurations:
        private_ips.append(ip_config.private_ip_address)

    virtual_machines = compute_client.virtual_machines.list(resource_group)
    for vm in virtual_machines:
      instance_ids.append(vm.name)
    return public_ips, private_ips, instance_ids

  def run_instances(self, count, parameters, security_configured):
    """ Starts 'count' instances in Microsoft Azure, and returns once they
    have been started. Callers should create a network and attach a firewall
    to it before using this method, or the newly created instances will not
    have a network and firewall to attach to (and thus this method will fail).
    Args:
      count: An int, that specifies how many virtual machines should be started.
      parameters: A dict, containing all the parameters necessary to
        authenticate this user with Azure.
      security_configured: Unused, as we assume that the network and firewall
        has already been set up.
    Returns:
      instance_ids: A list of unique Azure VM names.
      public_ips: A list of public IP addresses.
      private_ips: A list of private IP addresses.
    """
    credentials = self.open_connection(parameters)
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    subscription_id = str(parameters[self.PARAM_SUBCR_ID])
    network_client = NetworkManagementClient(credentials, subscription_id)

    for _ in range(count):
      vm_network_name = Haikunator().haikunate()
      self.create_network_interface(network_client, parameters,
        vm_network_name, vm_network_name, vm_network_name, vm_network_name)
      network_interface = network_client.network_interfaces.get(
        resource_group, vm_network_name)
      self.create_virtual_machine(credentials, network_client,
                                  network_interface.id, parameters,
                                  vm_network_name)
    public_ips, private_ips, instance_ids = self.describe_instances(parameters)
    return instance_ids, public_ips, private_ips

  def create_virtual_machine(self, credentials, network_client, network_id,
                             parameters, vm_network_name):
    """ Creates an Azure virtual machine using the network interface created.
    Args:
      credentials: A ServicePrincipalCredentials instance, that can be used to
        access or create any resources.
      network_client: A NetworkManagementClient instance.
      network_id: The network id of the network interface created.
      parameters: A dict, containing all the parameters necessary to
        authenticate this user with Azure.
    """
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    storage_account = parameters[self.PARAM_STORAGE_ACCOUNT]
    zone = parameters[self.PARAM_ZONE]
    utils.log("Creating a Virtual Machine '{}'".format(vm_network_name))
    subscription_id = str(parameters[self.PARAM_SUBCR_ID])
    compute_client = ComputeManagementClient(credentials, subscription_id)

    auth_keys_path =  self.AUTHORIZED_KEYS_FILE.format(self.ADMIN_USERNAME)

    with open(auth_keys_path, 'r') as pub_ssh_key_fd:
      pub_ssh_key = pub_ssh_key_fd.read()

    public_keys = [SshPublicKey(path=auth_keys_path, key_data=pub_ssh_key)]
    ssh_config = SshConfiguration(public_keys=public_keys)
    linux_config = LinuxConfiguration(disable_password_authentication=True,
                                      ssh=ssh_config)
    os_profile = OSProfile(admin_username=self.ADMIN_USERNAME,
                           computer_name=vm_network_name,
                           linux_configuration=linux_config)

    hardware_profile = HardwareProfile(
      vm_size=VirtualMachineSizeTypes.standard_a3)

    network_profile = NetworkProfile(
      network_interfaces=[NetworkInterfaceReference(id=network_id)])

    virtual_hd = VirtualHardDisk(
      uri='https://{0}.blob.core.windows.net/vhds/{1}.vhd'.
        format(storage_account, vm_network_name))

    image_hd = VirtualHardDisk(uri=parameters[self.PARAM_IMAGE_ID])
    os_type = OperatingSystemTypes.linux
    os_disk = OSDisk(os_type=os_type, caching=CachingTypes.read_write,
                     create_option=DiskCreateOptionTypes.from_image,
                     name=vm_network_name, vhd=virtual_hd, image=image_hd)

    compute_client.virtual_machines.create_or_update(
      resource_group, vm_network_name, VirtualMachine(location=zone,
        os_profile=os_profile, hardware_profile=hardware_profile,
        network_profile=network_profile,
        storage_profile=StorageProfile(os_disk=os_disk)))

    # Sleep until an IP address gets associated with the VM.
    while True:
      public_ip_address = network_client.public_ip_addresses.get(resource_group,
                                                                 vm_network_name)
      if public_ip_address.ip_address:
        utils.log('Azure VM is available at {}'.
                  format(public_ip_address.ip_address))
        break
      utils.log("Waiting {} second(s) for IP address to be available".
                format(self.SLEEP_TIME))
      time.sleep(self.SLEEP_TIME)

  def associate_static_ip(self, instance_id, static_ip):
    """Associates the given static IP address with the given instance ID.
    Args:
      instance_id: A str that names the instance that the static IP should be
        bound to.
      static_ip: A str naming the static IP to bind to the given instance.
    """

  def terminate_instances(self, parameters):
    """ Deletes the instances specified in 'parameters' running in Azure.
    Args:
      parameters: A dict, containing all the parameters necessary to
        authenticate this user with Azure.
    """
    credentials = self.open_connection(parameters)
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    subscription_id = str(parameters[self.PARAM_SUBCR_ID])
    public_ips, private_ips, instance_ids = self.describe_instances(parameters)

    utils.log("Terminating the vm instance/s '{}'".format(instance_ids))
    compute_client = ComputeManagementClient(credentials, subscription_id)
    for vm_name in instance_ids:
      result = compute_client.virtual_machines.delete(resource_group, vm_name)
      resource_name  = 'Virtual Machine' + ':' + vm_name
      self.sleep_until_delete_operation_done(result, resource_name)

  def sleep_until_delete_operation_done(self, result, resource_name):
    """ Sleeps until the delete operation for the resource is completed
    successfully.
    Args:
      result: An instance, of the AzureOperationPoller to poll for the status
        of the operation being performed.
      resource_name: The name of the resource being deleted.
    """
    while not result.done():
      utils.log("Waiting {0} second(s) for '{1}' to be "
                "deleted".format(self.SLEEP_TIME, resource_name))
      time.sleep(self.SLEEP_TIME)

  def cleanup_state(self, parameters):
    """ Removes any remote state that was created to run AppScale instances
    during this deployment.
    Args:
      parameters: A dict that includes keys indicating the remote state
        that should be deleted.
    """
    subscription_id = str(parameters[self.PARAM_SUBCR_ID])
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    credentials = self.open_connection(parameters)
    network_client = NetworkManagementClient(credentials, subscription_id)

    utils.log("Deleting the Virtual Network, Public IP Address "
                       "and Network Interface created for this deployment.")
    network_interfaces = network_client.network_interfaces.list(resource_group)
    for interface in network_interfaces:
      result = network_client.network_interfaces.delete(resource_group,
                                                        interface.name)
      resource_name = 'Network Interface' + ':' + interface.name
      self.sleep_until_delete_operation_done(result, resource_name)

    public_ip_addresses = network_client.public_ip_addresses.list(resource_group)
    for public_ip in public_ip_addresses:
      result = network_client.public_ip_addresses.delete(resource_group,
                                                         public_ip.name)
      resource_name = 'Public IP Address' + ':' + public_ip.name
      self.sleep_until_delete_operation_done(result, resource_name)

    virtual_networks = network_client.virtual_networks.list(resource_group)
    for network in virtual_networks:
      result = network_client.virtual_networks.delete(resource_group,
                                                      network.name)
      resource_name = 'Virtual Network' + ':' + network.name
      self.sleep_until_delete_operation_done(result, resource_name)

  def assert_required_parameters(self, parameters, operation):
    """ Check whether all the parameters required to interact with Azure are
    present in the provided dict.
    Args:
      parameters: A dict containing values necessary to authenticate with the
        Azure.
      operation: A str representing the operation for which the parameters
        should be checked.
    Raises:
      AgentConfigurationException: If a required parameter is absent.
    """
    # Make sure that the user has set each parameter.
    for param in self.REQUIRED_CREDENTIALS:
      if param not in parameters:
        raise AgentConfigurationException('The required parameter, {0}, was not'
          ' specified.'.format(param))

  def open_connection(self, parameters):
    """ Connects to Microsoft Azure with the given credentials, creates an
    authentication token and uses that to get the ServicePrincipalCredentials
    which is needed to access any resources.
    Args:
      parameters: A dict, containing all the parameters necessary to authenticate
        this user with Azure. We assume that the user has already authorized this
        account by creating a Service Principal with the appropriate (Contributor)
        role.
    Returns:
      A ServicePrincipalCredentials instance, that can be used to access or
        create any resources.
    """
    app_id = parameters[self.PARAM_APP_ID]
    app_secret_key = parameters[self.PARAM_APP_SECRET]
    tenant_id = parameters[self.PARAM_TENANT_ID]

    # Get an Authentication token using ADAL.
    context = adal.AuthenticationContext(self.AZURE_AUTH_ENDPOINT + tenant_id)
    token_response = context.acquire_token_with_client_credentials(
      self.AZURE_RESOURCE_URL, app_id, app_secret_key)
    token_response.get('accessToken')

    # To access Azure resources for an application, we need a Service Principal
    # with the accurate role assignment. It can be created using the Azure CLI.
    credentials = ServicePrincipalCredentials(client_id=app_id,
                                              secret=app_secret_key,
                                              tenant=tenant_id)
    return credentials

  def create_network_interface(self, network_client, parameters, interface_name,
                               network_name, subnet_name, ip_name):
    """ A helper function that creates the network resources, such as virtual
    network, public ip and network interface.
    Args:
      network_client: A NetworkManagementClient instance.
      parameters:  A dict, containing all the parameters necessary to
        authenticate this user with Azure.
      interface_name: The name to use for the Network Interface resource.
      network_name: The name to use for the Virtual Network resource.
      subnet_name: The name to use for the Subnet resource.
      ip_name: The name to use for the Public IP Address resource.
    """
    group_name = parameters[self.PARAM_RESOURCE_GROUP]
    region = parameters[self.PARAM_ZONE]
    utils.log("Creating/Updating the Virtual Network '{}'".format(network_name))
    address_space = AddressSpace(address_prefixes=['10.1.0.0/16'])
    subnet1 = Subnet(name=subnet_name, address_prefix='10.1.0.0/24')
    result = network_client.virtual_networks.create_or_update(group_name, network_name,
      VirtualNetwork(location=region, address_space=address_space, subnets=[subnet1]))
    self.sleep_until_update_operation_done(result, network_name)
    subnet = network_client.subnets.get(group_name, network_name, subnet_name)

    utils.log("Creating/Updating the Public IP Address '{}'".format(ip_name))
    ip_address = PublicIPAddress(
      location=region, public_ip_allocation_method=IPAllocationMethod.dynamic,
      idle_timeout_in_minutes=4)
    result = network_client.public_ip_addresses.create_or_update(group_name,
                                                                 ip_name, ip_address)
    self.sleep_until_update_operation_done(result, ip_name)
    public_ip_address = network_client.public_ip_addresses.get(group_name, ip_name)

    utils.log("Creating/Updating the Network Interface '{}'".format(interface_name))
    network_interface_ip_conf = NetworkInterfaceIPConfiguration(
      name='default', private_ip_allocation_method=IPAllocationMethod.dynamic,
      subnet=subnet, public_ip_address=PublicIPAddress(id=(public_ip_address.id)))

    result = network_client.network_interfaces.create_or_update(group_name,
      interface_name, NetworkInterface(location=region,
                                       ip_configurations=[network_interface_ip_conf]))
    self.sleep_until_update_operation_done(result, interface_name)

  def sleep_until_update_operation_done(self, result, resource_name):
    """ Sleeps until the create/update operation for the resource is completed
      successfully.
      Args:
        result: An instance, of the AzureOperationPoller to poll for the status
          of the operation being performed.
        resource_name: The name of the resource being updated.
    """
    while not result.done():
      utils.log("Waiting {0} second(s) for {1} to be created/updated.".
                format(self.SLEEP_TIME, resource_name))
      time.sleep(self.SLEEP_TIME)
