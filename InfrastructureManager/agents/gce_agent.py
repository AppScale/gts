#!/usr/bin/env python
"""
This file provides a single class, GCEAgent, that the AppScale Tools can use to
interact with Google Compute Engine.
"""

# General-purpose Python library imports
import datetime
import os.path
import time
import uuid


# Third-party imports
from apiclient import discovery
import httplib2
import oauth2client.client
import oauth2client.file
import oauth2client.tools


# AppScale-specific imports
from agents.base_agent import AgentConfigurationException
from agents.base_agent import AgentRuntimeException
from agents.base_agent import BaseAgent 
from utils import utils


class GCEAgent(BaseAgent):
  """ GCEAgent defines a specialized BaseAgent that allows for interaction with
  Google Compute Engine.

  It authenticates via OAuth2 and interacts with GCE via the Google Client
  Library.
  """


  # The maximum amount of time, in seconds, that we are willing to wait for a
  # virtual machine to start up, after calling instances().add(). GCE is pretty
  # fast at starting up images, and in practice, we haven't seen it take longer
  # than 200 seconds, but this upper bound is set just to be safe.
  MAX_VM_CREATION_TIME = 600


  # The amount of time that run_instances waits between each instances().list()
  # request. Setting this value lower results in more requests made to Google,
  # but is more responsive to when machines become ready to use.
  SLEEP_TIME = 20
  

  PARAM_GROUP = 'group'


  PARAM_IMAGE_ID = 'image_id'


  PARAM_INSTANCE_IDS = 'instance_ids'


  PARAM_INSTANCE_TYPE = 'instance_type'


  PARAM_KEYNAME = 'keyname'


  PARAM_PROJECT = 'project'

  
  PARAM_SECRETS = 'client_secrets'


  PARAM_VERBOSE = 'is_verbose'


  PARAM_ZONE = 'zone'


  # A set that contains all of the items necessary to run AppScale in Google
  # Compute Engine.
  REQUIRED_CREDENTIALS = (
    PARAM_GROUP,
    PARAM_IMAGE_ID,
    PARAM_KEYNAME,
    PARAM_PROJECT,
    PARAM_ZONE
  )


  # The OAuth 2.0 scope used to interact with Google Compute Engine.
  GCE_SCOPE = 'https://www.googleapis.com/auth/compute'


  # The version of the Google Compute Engine API that we support.
  API_VERSION = 'v1'


  # The URL endpoint that receives Google Compute Engine API requests.
  GCE_URL = 'https://www.googleapis.com/compute/{0}/projects/'.format(API_VERSION)


  # The person to contact if there is a problem with the instance. We set this
  # to 'default' to not have to actually put anyone's personal information in.
  DEFAULT_SERVICE_EMAIL = 'default'


  # The location on the local filesystem where SSH private keys used with
  # Google Compute Engine are stored, by default.
  GCE_PRIVATE_SSH_KEY = os.path.expanduser("~/.ssh/google_compute_engine")


  # The location on the local filesystem where SSH public keys uploaded to
  # Google Compute Engine are stored, by default.
  GCE_PUBLIC_SSH_KEY = GCE_PRIVATE_SSH_KEY + ".pub"


  CLIENT_SECRETS_LOCATION = '/etc/appscale/client_secrets.json'


  OAUTH2_STORAGE_LOCATION = '/etc/appscale/oauth2.dat'


  def configure_instance_security(self, parameters):
    """ Creates a GCE network and firewall with the specified name, and opens
    the ports on that firewall as needed for AppScale.

    We expect both the network and the firewall to not exist before this point,
    to avoid accidentally placing AppScale instances from different deployments
    in the same network and firewall (thus enabling them to see each other's web
    traffic).

    Args:
      parameters: A dict with keys for each parameter needed to connect to
        Google Compute Engine, and an additional key indicating the name of the
        network and firewall that we should create in GCE.
    Returns:
      True, if the named network and firewall was created successfully.
    Raises:
      AgentRuntimeException: If the named network or firewall already exist in
      GCE.
    """
    return True


  def assert_required_parameters(self, parameters, operation):
    """ Checks the given parameters to make sure that they can be used to
    interact with Google Compute Engine.

    Args:
      parameters: A dict that maps the name of each credential to be used in GCE
        with the value we should use.
      operation: A BaseAgent.OPERATION that indicates if we wish to add or
        delete instances. Unused here, as all operations require the same
        credentials.
    Raises:
      AgentConfigurationException: If any of the required credentials are not
        present, or if the client_secrets parameter refers to a file that is not
        present on the local filesystem.
    """
    # Make sure the user has set each parameter.
    for param in self.REQUIRED_CREDENTIALS:
      if param not in parameters:
        raise AgentConfigurationException('The required parameter, {0}, was' \
          ' not specified.'.format(param))

    # Next, make sure that the oauth2 file exists
    if not os.path.exists(self.OAUTH2_STORAGE_LOCATION):
      raise AgentConfigurationException('Could not find your signed OAuth2' \
        'file at {0}'.format(self.OAUTH2_STORAGE_LOCATION))


  def describe_instances(self, parameters):
    """ Queries Google Compute Engine to see which instances are currently
    running, and retrieve information about their public and private IPs.

    Args:
      parameters: A dict with keys for each parameter needed to connect to
        Google Compute Engine.
    Returns:
      A tuple of the form (public_ips, private_ips, instance_ids), where each
        member is a list. Items correspond to each other across these lists,
        so a caller is guaranteed that item X in each list belongs to the same
        virtual machine.
    """
    gce_service, credentials = self.open_connection(parameters)
    http = httplib2.Http()
    auth_http = credentials.authorize(http)
    request = gce_service.instances().list(
      project=parameters[self.PARAM_PROJECT],
      filter="name eq appscale-{0}-.*".format(parameters[self.PARAM_GROUP]),
      zone=parameters[self.PARAM_ZONE]
    )
    response = request.execute(auth_http)
    utils.log(str(response))

    instance_ids = []
    public_ips = []
    private_ips = []

    if response and 'items' in response:
      instances = response['items']
      for instance in instances:
        if instance['status'] == "RUNNING":
          instance_ids.append(instance['name'])
          public_ips.append(instance['networkInterfaces'][0]['accessConfigs'][0]['natIP'])
          private_ips.append(instance['networkInterfaces'][0]['networkIP'])

    return public_ips, private_ips, instance_ids


  def generate_disk_name(self, parameters):
    """ Creates a temporary name for a disk.

    Args:
      parameters: A dict with keys for each parameter needed to connect to
        Google Compute Engine.
    Returns:
      A str, a disk name associated with the root disk of AppScale on GCE.
    """
    return "appscale{0}{1}".format(parameters[self.PARAM_GROUP], 
      str(int(time.time() * 1000)))

  def create_scratch_disk(self, parameters):
    """ Creates a disk from a given machine image.

    GCE does not support scratch disks on API version v1 and higher. We create
    a persistent disk upon creation to act like one to keep the abstraction used
    in other infrastructures.

    Args:
      parameters: A dict with keys for each parameter needed to connect to
        Google Compute Engine.
    Returns:
      A str, the url to the disk to use.
    """
    gce_service, credentials = self.open_connection(parameters)
    http = httplib2.Http()
    auth_http = credentials.authorize(http)
    disk_name = self.generate_disk_name(parameters)
    project_name = parameters[self.PARAM_PROJECT]
    project_url = '{0}{1}'.format(self.GCE_URL, 
      parameters[self.PARAM_PROJECT])
    source_image_url = '{0}{1}/global/images/{2}'.format(self.GCE_URL,
      project_name, parameters[self.PARAM_IMAGE_ID])
    request = gce_service.disks().insert(
      project=project_name,
      zone=parameters[self.PARAM_ZONE],
      body={
        'name':disk_name 
      },
      sourceImage=source_image_url
    )
    response = request.execute(http=auth_http)
    utils.log(str(response))
    self.ensure_operation_succeeds(gce_service, auth_http, response,
      parameters[self.PARAM_PROJECT])

    disk_url = "{0}/zones/{1}/disks/{2}".format(
      project_url, parameters[self.PARAM_ZONE], disk_name)
    return disk_url

  def run_instances(self, count, parameters, security_configured):
    """ Starts 'count' instances in Google Compute Engine, and returns once they
    have been started.

    Callers should create a network and attach a firewall to it before using
    this method, or the newly created instances will not have a network and
    firewall to attach to (and thus this method will fail).

    Args:
      count: An int that specifies how many virtual machines should be started.
      parameters: A dict with keys for each parameter needed to connect to
        Google Compute Engine.
      security_configured: Unused, as we assume that the network and firewall
        has already been set up.
    """
    project_id = parameters[self.PARAM_PROJECT]
    image_id = parameters[self.PARAM_IMAGE_ID]
    instance_type = parameters[self.PARAM_INSTANCE_TYPE]
    keyname = parameters[self.PARAM_KEYNAME]
    group = parameters[self.PARAM_GROUP]
    zone = parameters[self.PARAM_ZONE]

    utils.log("Starting {0} machines with machine id {1}, with " \
      "instance type {2}, keyname {3}, in security group {4}, in zone {5}" \
      .format(count, image_id, instance_type, keyname, group, zone))

    # First, see how many instances are running and what their info is.
    start_time = datetime.datetime.now()
    active_public_ips, active_private_ips, active_instances = \
      self.describe_instances(parameters)

    # Construct URLs
    image_url = '{0}{1}/global/images/{2}'.format(self.GCE_URL, project_id, image_id)
    project_url = '{0}{1}'.format(self.GCE_URL, project_id)
    machine_type_url = '{0}/zones/{1}/machineTypes/{2}'.format(project_url,
      zone, instance_type)
    zone_url = '{0}/zones/{1}'.format(project_url, zone)
    network_url = '{0}/global/networks/{1}'.format(project_url, group)

    public_key = utils.get_public_key(keyname)

    # Construct the request body
    for index in range(count):
      disk_url = self.create_scratch_disk(parameters)
      instances = {
        # Truncate the name down to the first 62 characters, since GCE doesn't
        # let us use arbitrarily long instance names.
        'name': "appscale-{0}-{1}".format(group, uuid.uuid4())[:62],
        'machineType': machine_type_url,
        'disks':[{
          'source': disk_url,
          'boot': 'true',
          'type': 'PERSISTENT'
        }],
        'image': image_url,
        'networkInterfaces': [{
          'accessConfigs': [{
            'type': 'ONE_TO_ONE_NAT',
            'name': 'External NAT'
          }],
          'network': network_url
        }],
        'serviceAccounts': [{
          'email': self.DEFAULT_SERVICE_EMAIL,
          'scopes': [self.GCE_SCOPE]
        }],
        'metadata': {
          'items': [{
            'key': 'ssh-keys',
            'value': 'root:{} root@localhost'.format(public_key)
          }]
        }
      }

      # Create the instance
      gce_service, credentials = self.open_connection(parameters)
      http = httplib2.Http()
      auth_http = credentials.authorize(http)
      request = gce_service.instances().insert(
           project=project_id, body=instances, zone=zone)
      response = request.execute(auth_http)
      utils.log(str(response))
      self.ensure_operation_succeeds(gce_service, auth_http, response, 
        parameters[self.PARAM_PROJECT])
    
    instance_ids = []
    public_ips = []
    private_ips = []
    end_time = datetime.datetime.now() + datetime.timedelta(0,
      self.MAX_VM_CREATION_TIME)
    now = datetime.datetime.now()

    while now < end_time:
      time_left = (end_time - now).seconds
      utils.log("Waiting for your instances to start...")
      instance_info = self.describe_instances(parameters)
      public_ips = instance_info[0]
      private_ips = instance_info[1]
      instance_ids = instance_info[2]
      public_ips = utils.diff(public_ips, active_public_ips)
      private_ips = utils.diff(private_ips, active_private_ips)
      instance_ids = utils.diff(instance_ids, active_instances)
      if count == len(public_ips):
        break
      time.sleep(self.SLEEP_TIME)
      now = datetime.datetime.now()

    if not public_ips:
      self.handle_failure('No public IPs were able to be procured '
                          'within the time limit')

    if len(public_ips) != count:
      for index in range(0, len(public_ips)):
        if public_ips[index] == '0.0.0.0':
          instance_to_term = instance_ids[index]
          utils.log('Instance {0} failed to get a public IP address'\
                  'and is being terminated'.format(instance_to_term))
          self.terminate_instances([instance_to_term])

    end_time = datetime.datetime.now()
    total_time = end_time - start_time
    utils.log("Started {0} on-demand instances in {1} seconds" \
      .format(count, total_time.seconds))
    return instance_ids, public_ips, private_ips


  def open_connection(self, parameters):
    """ Connects to Google Compute Engine with the given credentials.

    Args:
      parameters: A dict that contains all the parameters necessary to
        authenticate this user with Google Compute Engine. We assume that the
        user has already authorized this account for use with GCE.
    Returns:
      An apiclient.discovery.Resource that is a connection valid for requests
      to Google Compute Engine for the given user, and a Credentials object that
      can be used to sign requests performed with that connection.
    """
    # Perform OAuth 2.0 authorization.
    storage = oauth2client.file.Storage(self.OAUTH2_STORAGE_LOCATION)
    credentials = storage.get()

    # Build the service
    return discovery.build('compute', self.API_VERSION), credentials


  def terminate_instances(self, parameters):
    """ Deletes the instances specified in 'parameters' running in Google
    Compute Engine.

    Args:
      parameters: A dict with keys for each parameter needed to connect to
        Google Compute Engine, and an additional key mapping to a list of
        instance names that should be deleted.
    """
    instance_ids = parameters[self.PARAM_INSTANCE_IDS]
    for instance_id in instance_ids:
      gce_service, credentials = self.open_connection(parameters)
      http = httplib2.Http()
      auth_http = credentials.authorize(http)
      request = gce_service.instances().delete(
        project=parameters[self.PARAM_PROJECT],
        zone=parameters[self.PARAM_ZONE],
        instance=instance_id
      )
      response = request.execute(auth_http)
      utils.log(str(response))
      self.ensure_operation_succeeds(gce_service, auth_http, response,
        parameters[self.PARAM_PROJECT])


  def attach_disk(self, parameters, disk_name, instance_id):
    """ Attaches the persistent disk specified in 'disk_name' to this virtual
    machine.

    Args:
      parameters: A dict with keys for each parameter needed to connect to
        Google Compute Engine.
      disk_name: A str naming the persistent disk to attach to this machine.
      instance_id: A str naming the id of the instance that the disk should be
        attached to. In practice, callers add disks to their own instance.
    Returns:
      A str indicating where the persistent disk has been attached to.
    """
    gce_service, credentials = self.open_connection(parameters)
    http = httplib2.Http()
    auth_http = credentials.authorize(http)
    project = parameters[self.PARAM_PROJECT]
    zone = parameters[self.PARAM_ZONE]
    request = gce_service.instances().attachDisk(
      project=project,
      zone=zone,
      instance=instance_id,
      body={
        'kind' : 'compute#attachedDisk',
        'type' : 'PERSISTENT',
        'mode' : 'READ_WRITE',
        'source' : "https://www.googleapis.com/compute/{0}/projects/{1}" \
          "/zones/{2}/disks/{3}".format(self.API_VERSION, project, 
          zone, disk_name),
        'deviceName' : 'sdb'
      }
    )
    response = request.execute(auth_http)
    utils.log(str(response))
    self.ensure_operation_succeeds(gce_service, auth_http, response,
      parameters[self.PARAM_PROJECT])

    return '/dev/sdb'


  def ensure_operation_succeeds(self, gce_service, auth_http, response, project_id):
    """ Waits for the given GCE operation to finish successfully.

    Callers should use this function whenever they perform a destructive
    operation in Google Compute Engine. For example, it is not necessary to use
    this function when seeing if a resource exists (e.g., a network, firewall,
    or instance), but it is useful to use this method when creating or deleting
    a resource. One example is when we create a network. As we are only allowed
    to have five networks, it is useful to make sure that the network was
    successfully created before trying to create a firewall attached to that
    network.

    Args:
      gce_service: An apiclient.discovery.Resource that is a connection valid
        for requests to Google Compute Engine for the given user.
      auth_http: A HTTP connection that has been signed with the given user's
        Credentials, and is authorized with the GCE scope.
      response: A dict that contains the operation that we want to ensure has
        succeeded, referenced by a unique ID (the 'name' field).
      project_id: A str that identifies the GCE project that requests should
        be billed to.
    """
    status = response['status']
    while status != 'DONE' and response:
      operation_id = response['name']

      # Identify if this is a per-zone resource
      if 'zone' in response:
        zone_name = response['zone'].split('/')[-1]
        request = gce_service.zoneOperations().get(
            project=project_id,
            operation=operation_id,
            zone=zone_name)
      else:
        request = gce_service.globalOperations().get(
             project=project_id, operation=operation_id)

      response = request.execute(auth_http)
      if response:
        status = response['status']

        if 'error' in response:
          message = "\n".join([errors['message'] for errors in
            response['error']['errors']])
          raise AgentRuntimeException(str(message))
