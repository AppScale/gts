#!/usr/bin/env python
"""
This file provides a single class, AzureAgent, that the AppScale Tools can use to
interact with Microsoft Azure.
"""

# General-purpose Python library imports
import adal
import json
import os.path
import shutil
import time

# Azure specific imports
from azure.batch.models import OSType
from azure.common.credentials import ServicePrincipalCredentials
from azure.mgmt.authorization import AuthorizationManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.compute.models import HardwareProfile
from azure.mgmt.compute.models import OSProfile
from azure.mgmt.compute.models import CachingTypes
from azure.mgmt.compute.models import DiskCreateOptionTypes
from azure.mgmt.compute.models import ImageReference
from azure.mgmt.compute.models import LinuxConfiguration
from azure.mgmt.compute.models import NetworkProfile
from azure.mgmt.compute.models import NetworkInterfaceReference
from azure.mgmt.compute.models import OSDisk
from azure.mgmt.compute.models import SshConfiguration
from azure.mgmt.compute.models import SshPublicKey
from azure.mgmt.compute.models import StorageProfile
from azure.mgmt.compute.models import LinuxConfiguration
from azure.mgmt.compute.models import VirtualHardDisk
from azure.mgmt.compute.models import VirtualMachine
from azure.mgmt.compute.models import VirtualMachineSizeTypes

from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkInterfaceIPConfiguration
from azure.mgmt.network.models import AddressSpace
from azure.mgmt.network.models import IPAllocationMethod
from azure.mgmt.network.models import NetworkInterface
from azure.mgmt.network.models import PublicIPAddress
from azure.mgmt.network.models import Subnet
from azure.mgmt.network.models import VirtualNetwork

from azure.mgmt.resource.resources import ResourceManagementClient
from azure.mgmt.resource.resources.models import ResourceGroup
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.storage.models import StorageAccountCreateParameters, Sku, SkuName, Kind
from msrestazure.azure_exceptions import CloudError

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

  # Default Storage Account name to use for Azure.
  DEFAULT_STORAGE_ACCT = 'appscalestorage'

  # Default resource group name to use for Azure.
  DEFAULT_RESOURCE_GROUP = 'appscale-group'

  # The following constants are string literals that can be used by callers to
  # index into the parameters that the user passes in, as opposed to having to
  # type out the strings each time we need them.
  PARAM_APP_ID = "app_id"
  PARAM_APP_SECRET = "app_secret_key"
  PARAM_CREDENTIALS = 'credentials'
  PARAM_EXISTING_RG = 'does_exist'
  PARAM_GROUP = 'group'
  PARAM_INSTANCE_IDS = 'instance_ids'
  PARAM_KEYNAME = 'keyname'
  PARAM_REGION = 'region'
  PARAM_RESOURCE_GROUP = 'resource_group'
  PARAM_STORAGE_ACCOUNT = 'storage_account'
  PARAM_SUBCR_ID = "subscription_id"
  PARAM_TENANT_ID = "tenant_id"
  PARAM_TEST = 'test'
  PARAM_TAG = 'group_tag'
  PARAM_VERBOSE = 'is_verbose'
  PARAM_ZONE = 'zone'

  # A set that contains all of the items necessary to run AppScale in Azure.
  REQUIRED_CREDENTIALS = (
    PARAM_APP_SECRET,
    PARAM_APP_ID,
    PARAM_KEYNAME,
    PARAM_SUBCR_ID,
    PARAM_TENANT_ID,
    PARAM_ZONE
  )

  # The following constants are the strings needed to start an Azure VM instance.
  BASE_NAME = 'azure-appscale'

  VIRTUAL_NETWORK_NAME = BASE_NAME

  SUBNET_NAME = BASE_NAME

  NETWORK_INTERFACE_NAME = BASE_NAME

  VM_NAME = BASE_NAME

  OS_DISK_NAME = BASE_NAME

  PUBLIC_IP_NAME = BASE_NAME

  COMPUTER_NAME = BASE_NAME

  ADMIN_USERNAME = 'azureuser'

  IMAGE_PUBLISHER = 'Canonical'

  IMAGE_OFFER = 'UbuntuServer'

  IMAGE_SKU = '14.04.0-LTS'

  IMAGE_VERSION = 'latest'

  # The location on the local filesystem where SSH private keys used with
  # Google Compute Engine are stored, by default.
  AZURE_PRIVATE_SSH_KEY = os.path.expanduser("~/root/.ssh/")

  # The location on the local filesystem where SSH public keys uploaded to
  # Google Compute Engine are stored, by default.
  AZURE_PUBLIC_SSH_KEY = AZURE_PRIVATE_SSH_KEY + ".pub"

  # The mininum number of time to sleep for Azure resources to get created.
  SLEEP_TIME = 10

  def configure_instance_security(self, parameters):
    """Configure and setup security features for the VMs spawned via this
    agent. This method is called before starting virtual machines. Implementations
    may configure security features such as VM login and firewalls in this method.
    Args:
      parameters: A dict containing values necessary to authenticate with the
        underlying cloud.
    Returns:
      True if some action was taken to configure security for the VMs
      and False otherwise.
    Raises:
      AgentRuntimeException: If security features could not be successfully
        configured in the underlying cloud.
    """
    return True

  def assert_required_parameters(self, parameters, operation):
    """Check whether all the platform specific parameters are present in the
    provided dict. If all the parameters required to perform the given operation
    is available this method simply returns. Otherwise it throws an
    AgentConfigurationException.

    Args:
      parameters: A dict containing values necessary to authenticate with the
        underlying cloud.
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

  def describe_instances(self, parameters, pending=False):
    """Query the underlying cloud platform regarding VMs that are running.

    Args:
      parameters: A dict containing values necessary to authenticate with the
        underlying cloud.
      pending: If we should show pending instances.
    Returns:
      A tuple of the form (public, private, id) where public is a list
      of private IP addresses, private is a list of private IP addresses,
      and id is a list of platform specific VM identifiers.
    """
    credentials = self.open_connection(parameters)
    subscription_id = parameters[self.PARAM_SUBCR_ID]
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
    """
    credentials = self.open_connection(parameters)
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    subscription_id = parameters[self.PARAM_SUBCR_ID]
    network_client = NetworkManagementClient(credentials, subscription_id)
    zone = parameters[self.PARAM_ZONE]

    for _ in range(count):
      vm_network_name = Haikunator().haikunate()
      self.create_network_interface(network_client, zone, resource_group,
        vm_network_name, vm_network_name, vm_network_name, vm_network_name)
      network_interface = network_client.network_interfaces.get(
        resource_group, vm_network_name)
      self.create_virtual_machine(credentials, network_client,
        network_interface.id, parameters, vm_network_name)

    public_ips, private_ips, instance_ids = self.describe_instances(parameters)

    return instance_ids, public_ips, private_ips

  def create_virtual_machine(self, credentials, network_client, network_id, parameters,
    vm_network_name):
    """ Creates an Azure virtual machine using the network interface created.

    Args:
      credentials: A ServicePrincipalCredentials instance, that can be used to access or
        create any resources.
      network_client: A NetworkManagementClient instance.
      network_id: The network id of the network interface created.
      parameters: A dict, containing all the parameters necessary to
        authenticate this user with Azure.
    """
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    storage_account = parameters[self.PARAM_STORAGE_ACCOUNT]
    zone = parameters[self.PARAM_ZONE]
    verbose = parameters[self.PARAM_VERBOSE]
    utils.log("Creating a Virtual Machine '{}'".format(vm_network_name))
    subscription_id = parameters[self.PARAM_SUBCR_ID]
    compute_client = ComputeManagementClient(credentials, subscription_id)

    keyname = parameters[self.PARAM_KEYNAME]
    private_key_path = LocalState.LOCAL_APPSCALE_PATH + keyname
    public_key_path = private_key_path + ".pub"

    with open(public_key_path, 'r') as pub_ssh_key_fd:
      pub_ssh_key = pub_ssh_key_fd.read()

    key_path = "/home/{}/.ssh/authorized_keys".format(self.ADMIN_USERNAME)
    public_keys = [SshPublicKey(path=key_path, key_data=pub_ssh_key)]
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

    os_disk = OSDisk(caching=CachingTypes.none,
                     create_option=DiskCreateOptionTypes.from_image,
                     name=vm_network_name, vhd=virtual_hd)

    image_reference = ImageReference(publisher=self.IMAGE_PUBLISHER,
                                     offer=self.IMAGE_OFFER,
                                     sku=self.IMAGE_SKU,
                                     version=self.IMAGE_VERSION)

    compute_client.virtual_machines.create_or_update(
      resource_group, vm_network_name, VirtualMachine(location=zone,
                                                   os_profile=os_profile,
                                                   hardware_profile=hardware_profile,
                                                   network_profile=network_profile,
                                                   storage_profile=StorageProfile(
                                                     os_disk=os_disk,
                                                     image_reference=image_reference)))

    # Sleep until an IP address gets associated with the VM.
    sleep_time = 1
    while True:
      public_ip_address = network_client.public_ip_addresses.get(resource_group,
                                                                 vm_network_name)
      if public_ip_address.ip_address:
        print('Azure VM is available at {}'.format(public_ip_address.ip_address))
        break
      AppScaleLogger.verbose("Waiting {} second(s) for IP address to be "
        "available".format(sleep_time), verbose)
      time.sleep(sleep_time)
      sleep_time = min(sleep_time * 2, 20)

  def terminate_instances(self, parameters):
    """Terminate a set of virtual machines using the parameters given.

    Args:
      parameters: A dict containing values necessary to authenticate with the
        underlying cloud.
    """
    credentials = self.open_connection(parameters)
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    subscription_id = parameters[self.PARAM_SUBCR_ID]
    public_ips, private_ips, instance_ids = self.describe_instances(parameters)

    utils.log("Terminating the vm instance/s '{}'".format(instance_ids))
    compute_client = ComputeManagementClient(credentials, subscription_id)
    for vm_name in instance_ids:
      compute_client.virtual_machines.delete(resource_group, vm_name)

  def cleanup_state(self, parameters):
    """Removes any remote state that was created to run AppScale instances
    during this deployment.
    Args:
      parameters: A dict that includes keys indicating the remote state
        that should be deleted.
    """
    subscription_id = parameters[self.PARAM_SUBCR_ID]
    resource_group = parameters[self.PARAM_RESOURCE_GROUP]
    credentials = self.open_connection(parameters)
    verbose = parameters[self.PARAM_VERBOSE]
    network_client = NetworkManagementClient(credentials, subscription_id)

    time.sleep(60)
    utils.log("Deleting the Virtual Network, Public IP Address "
      "and Network Interface created for this deployment.")

    virtual_networks = network_client.virtual_networks.list(resource_group)
    for network in virtual_networks:
      network_client.virtual_networks.delete(resource_group, network.name)

    public_ip_addresses = network_client.public_ip_addresses.list(resource_group)
    for public_ip in public_ip_addresses:
      network_client.public_ip_addresses.delete(resource_group, public_ip.name)

    network_interfaces = network_client.network_interfaces.list(resource_group)
    for interface in network_interfaces:
      network_client.network_interfaces.delete(resource_group, interface.name)


  def get_params_from_args(self, args):
    """ Constructs a dict with only the parameters necessary to interact with
    Microsoft Azure (mainly the Azure credentials JSON file).

    Args:
      args: A Namespace or dict, that maps all of the arguments the user has
        invoked an AppScale command with their associated value.
    Returns:
      A dict, that maps each argument given to the value that was associated with
      it.
    Raises:
      AgentConfigurationException: If the caller fails to specify an Azure
      credentials JSON file, or if it doesn't exist on the local filesystem.
    """
    if not isinstance(args, dict):
      args = vars(args)

    params = {
      self.PARAM_CREDENTIALS: {},
      self.PARAM_APP_ID: args[self.PARAM_APP_ID],
      self.PARAM_APP_SECRET: args[self.PARAM_APP_SECRET],
      self.PARAM_KEYNAME: args[self.PARAM_KEYNAME],
      self.PARAM_RESOURCE_GROUP: args[self.PARAM_RESOURCE_GROUP],
      self.PARAM_REGION: args[self.PARAM_ZONE],
      self.PARAM_STORAGE_ACCOUNT: args[self.PARAM_STORAGE_ACCOUNT],
      self.PARAM_SUBCR_ID: args[self.PARAM_SUBCR_ID],
      self.PARAM_TAG: args[self.PARAM_TAG],
      self.PARAM_TENANT_ID: args[self.PARAM_TENANT_ID],
      self.PARAM_TEST: args[self.PARAM_TEST],
      self.PARAM_VERBOSE : args.get('verbose', False),
      self.PARAM_ZONE : args[self.PARAM_ZONE]
    }
    is_valid, rg_names = self.assert_credentials_are_valid(params)
    if not is_valid:
      raise AgentConfigurationException("Unable to authenticate using the "
                                        "credentials provided.")

    # Check if the resource group passed in exists already, if it does, then
    # pass an existing group flag so that it is not created again.
    # In case no resource group is passed, pass a default appscale-group.
    params[self.PARAM_EXISTING_RG] = False
    if not args[self.PARAM_RESOURCE_GROUP]:
      params[self.PARAM_RESOURCE_GROUP] = self.DEFAULT_RESOURCE_GROUP

    if args[self.PARAM_RESOURCE_GROUP] in rg_names:
      params[self.PARAM_EXISTING_RG] = True

    if not args[self.PARAM_STORAGE_ACCOUNT]:
      params[self.PARAM_STORAGE_ACCOUNT] = self.DEFAULT_STORAGE_ACCT
    return params

  def open_connection(self, parameters):
    """ Connects to Microsoft Azure with the given credentials, creates a
    an authentication token and uses that to get the ServicePrincipalCredentials
    which is needed to access any resources.

    Args:
      parameters: A dict, containing all the parameters necessary to authenticate
      this user with Azure. We assume that the user has already authorized this
      account by creating a Service Principal with the appropriate (Contributor)
      role.
    Returns:
      A dict, created from the path specified for credentials JSON file.
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
    # which contains a role assignment. It can be created using the Azure CLI.
    credentials = ServicePrincipalCredentials(client_id=app_id,
                                              secret=app_secret_key,
                                              tenant=tenant_id)
    return credentials


  def create_network_interface(self, network_client, region, group_name,
    interface_name, network_name, subnet_name, ip_name):
    """ A helper function that creates the network resources, such as virtual
    network, public ip and network interface.

    Args:
      network_client: A NetworkManagementClient instance
      region: The location specified in the AppScalefile
      group_name: The Azure resource group name under which the VM is created.
      interface_name: The name to use for the Network Interface resource.
      network_name: The name to use for the Virtual Network resource.
      subnet_name: The name to use for the Subnet resource.
      ip_name: The name to use for the Public IP Address resource.
    """
    utils.log("Creating/Updating the Virtual Network '{}'".
      format(network_name))
    address_space = AddressSpace(address_prefixes=['10.1.0.0/16'])
    subnet1 = Subnet(name=subnet_name, address_prefix='10.1.0.0/24')
    network_client.virtual_networks.create_or_update(group_name, network_name,
      VirtualNetwork(location=region, address_space=address_space,
                     subnets=[subnet1]))

    time.sleep(self.SLEEP_TIME)
    subnet = network_client.subnets.get(group_name, network_name, subnet_name)

    utils.log("Creating/Updating the Public IP Address '{}'".
      format(ip_name))
    ip_address = PublicIPAddress(
      location=region, public_ip_allocation_method=IPAllocationMethod.dynamic,
      idle_timeout_in_minutes=4)
    network_client.public_ip_addresses.create_or_update(group_name, ip_name, ip_address)

    time.sleep(self.SLEEP_TIME)
    public_ip_address = network_client.public_ip_addresses.get(group_name, ip_name)
    utils.log("Creating/Updating the Network Interface '{}'".format(interface_name))
    network_interface_ip_conf = NetworkInterfaceIPConfiguration(
      name='default', private_ip_allocation_method=IPAllocationMethod.dynamic,
      subnet=subnet, public_ip_address=PublicIPAddress(id=(public_ip_address.id)))

    network_client.network_interfaces.create_or_update(
      group_name, interface_name, NetworkInterface(
        location=region, ip_configurations=[network_interface_ip_conf]))
    time.sleep(self.SLEEP_TIME)

  def create_resource_group(self, parameters, credentials):
    """ Creates a Resource Group for the application using the Service Principal
    Credentials, if it does not already exist. In the case where no resource
    group is specified, a default 'appscale-group' is created.

    Args:
      parameters: A dict, containing all the parameters necessary to
        authenticate this user with Azure.
      credentials: A ServicePrincipalCredentials instance, that can be used to
      access or create any resources.
    Raises:
      AgentConfigurationException: If there was a problem creating or accessing
        a resource group with the given subscription.
    """
    subscription_id = parameters[self.PARAM_SUBCR_ID]
    resource_client = ResourceManagementClient(credentials, subscription_id)
    rg_name = parameters[self.PARAM_RESOURCE_GROUP]

    tag_name = 'default-tag'
    if parameters[self.PARAM_TAG]:
      tag_name = parameters[self.PARAM_TAG]

    storage_client = StorageManagementClient(credentials, subscription_id)
    resource_client.providers.register('Microsoft.Storage')
    try:
      # If the resource group does not already exist, create a new one with the
      # specified storage account.
      if not parameters[self.PARAM_EXISTING_RG]:
        utils.log("Creating a new resource group '{0}' with the tag "
          "'{1}'.".format(rg_name, tag_name))
        resource_client.resource_groups.create_or_update(
          rg_name, ResourceGroup(location=parameters[self.PARAM_ZONE],
                                 tags={'tag': tag_name}))
        self.create_storage_account(parameters, storage_client)
      else:
        # If it already exists, check if the specified storage account exists
        # under it and if not, create a new account.
        storage_accounts = storage_client.storage_accounts.\
          list_by_resource_group(rg_name)
        acct_names = []
        for account in storage_accounts:
          acct_names.append(account.name)

        if parameters[self.PARAM_STORAGE_ACCOUNT] in acct_names:
            utils.log("Storage account '{0}' under '{1}' resource group "
              "already exists. So not creating it again.".format(
              parameters[self.PARAM_STORAGE_ACCOUNT], rg_name))
        else:
          self.create_storage_account(parameters, storage_client)
    except CloudError as error:
      raise AgentConfigurationException("Unable to create a resource group "
        "using the credentials provided: {}".format(error.message))

  def create_storage_account(self, parameters, storage_client):
    """ Creates a Storage Account under the Resource Group, if it does not
    already exist. In the case where no resource group is specified, a default
    'appscalestorage' account is created.

    Args:
      parameters: A dict, containing all the parameters necessary to authenticate
        this user with Azure.
      credentials: A ServicePrincipalCredentials instance, that can be used to access or
      create any resources.
    Raises:
      AgentConfigurationException: If there was a problem creating or accessing
        a storage account with the given subscription.
    """
    storage_account = parameters[self.PARAM_STORAGE_ACCOUNT]
    rg_name = parameters[self.PARAM_RESOURCE_GROUP]

    try:
      utils.log("Creating a new storage account '{0}' under the "
        "resource group '{1}'.".format(storage_account, rg_name))
      result = storage_client.storage_accounts.create(
        rg_name, storage_account,StorageAccountCreateParameters(
          sku=Sku(SkuName.standard_lrs), kind=Kind.storage,
          location=parameters[self.PARAM_ZONE]))
      # result is a msrestazure.azure_operation.AzureOperationPoller instance
      # wait insure polling the underlying async operation until it's done.
      result.wait()
    except CloudError as error:
      raise AgentConfigurationException("Unable to create a storage account "
        "using the credentials provided: {}".format(error.message))
