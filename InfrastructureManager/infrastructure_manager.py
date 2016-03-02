import json
import thread

from agents.base_agent import AgentConfigurationException
from agents.base_agent import AgentRuntimeException
from agents.base_agent import BaseAgent
from agents.factory import InfrastructureAgentFactory

from utils import utils
from utils.persistent_dictionary import PersistentDictionary
from utils.persistent_dictionary import PersistentStoreFactory

class InfrastructureManager:
  """
  InfrastructureManager class is the main entry point to the AppScale
  Infrastructure Manager implementation. An instance of this class can
  be used to start new virtual machines in a specified cloud environment
  and terminate virtual machines when they are no longer required. Instances
  of this class also keep track of the virtual machines spawned by them
  and hence each InfrastructureManager instance can be queried to obtain
  information about any virtual machines spawned by each of them in the
  past.

  This implementation is completely cloud infrastructure agnostic
  and hence can be used to spawn/terminate instances on a wide range of
  cloud (IaaS) environments. All the cloud environment specific operations
  are delegated to a separate cloud agent and the InfrastructureManager
  initializes cloud agents on demand by looking at the 'infrastructure'
  parameter passed into the methods of this class.
  """

  # Default reasons which might be returned by this module
  REASON_BAD_SECRET = 'bad secret'
  REASON_BAD_VM_COUNT = 'bad vm count'
  REASON_BAD_ARGUMENTS = 'bad arguments'
  REASON_RESERVATION_NOT_FOUND = 'reservation_id not found'
  REASON_NONE = 'none'

  # Parameters required by InfrastructureManager
  PARAM_RESERVATION_ID = 'reservation_id'
  PARAM_INFRASTRUCTURE = 'infrastructure'
  PARAM_NUM_VMS = 'num_vms'

  # States a particular VM deployment could be in
  STATE_PENDING = 'pending'
  STATE_RUNNING = 'running'
  STATE_FAILED  = 'failed'

  # A list of parameters required to query the InfrastructureManager about
  # the state of a run_instances request.
  DESCRIBE_INSTANCES_REQUIRED_PARAMS = ( PARAM_RESERVATION_ID, )

  # A list of parameters required to initiate a VM deployment process
  RUN_INSTANCES_REQUIRED_PARAMS = (
    PARAM_INFRASTRUCTURE,
    PARAM_NUM_VMS
  )

  # A list of parameters required to initiate a VM termination process
  TERMINATE_INSTANCES_REQUIRED_PARAMS = ( PARAM_INFRASTRUCTURE, )

  def __init__(self, params=None, blocking=False):
    """
    Create a new InfrastructureManager instance. This constructor
    accepts an optional boolean parameter which decides whether the
    InfrastructureManager instance should operate in blocking mode
    or not. A blocking InfrastructureManager does not return until
    each requested run/terminate operation is complete. This mode
    is useful for testing and verification purposes. In a real-world
    deployment it's advisable to instantiate the InfrastructureManager
    in the non-blocking mode as run/terminate operations could take
    a rather long time to complete. By default InfrastructureManager
    instances are created in the non-blocking mode.

    Args
      params    A dictionary of parameters. Optional parameter. If
                specified it must at least include the 'store_type' parameter.
      blocking  Whether to operate in blocking mode or not. Optional
                and defaults to false.
    """
    self.blocking = blocking
    self.secret = utils.get_secret()
    self.agent_factory = InfrastructureAgentFactory()
    if params is not None:
      store_factory = PersistentStoreFactory()
      store = store_factory.create_store(params)
      self.reservations = PersistentDictionary(store)
    else:
      self.reservations = PersistentDictionary()

  def describe_instances(self, parameters, secret):
    """
    Query the InfrastructureManager instance for details regarding
    a set of virtual machines spawned in the past. This method accepts
    a dictionary of parameters and a secret for authentication purposes.
    The dictionary of parameters must include a 'reservation_id' parameter
    which is used to reference past virtual machine deployments.

    Args:
      parameters  A dictionary of parameters which contains a valid
                  'reservation_id' parameter. A valid 'reservation_id'
                  is an ID issued by the run_instances method of the
                  same InfrastructureManager object. Alternatively one
                  may provide a valid JSON string instead of a dictionary
                  object.
      secret      A previously established secret

    Returns:
      If the provided secret key is valid and the parameters map contains
      a valid 'reservation_id' parameter, this method will return a
      dictionary containing information regarding the requested past
      virtual machine deployment. This returned map contains several
      keys including 'success', 'state', 'reason' and 'vm_info'. The value
      of 'success' could be True of False depending on the outcome of the
      virtual machine deployment process. If the value of 'success' happens
      to be False, the 'reason' key would contain more details as to what
      caused the deployment to fail. The 'state' key could contain a 'pending'
      value or a 'running' value depending on the current state of the
      virtual machine deployment. And finally the 'vm_info' key would point
      to a another dictionary containing the IP addresses of the spawned virtual
      machines. If the virtual machine deployment had failed or still in the
      'pending' state, this key would contain the value None.

      If this method receives an invalid key or an invalid 'reservation_id'
      parameter, it will return a dictionary containing the keys 'success'
      and 'reason' where 'success' would be set to False, and 'reason' is
      set to a simple error message describing the cause of the error.

    Raises:
      TypeError   If the inputs are not of the expected types
      ValueError  If the input JSON string (parameters) cannot be parsed properly
    """
    parameters, secret = self.__validate_args(parameters, secret)

    if self.secret != secret:
      return self.__generate_response(False, self.REASON_BAD_SECRET)

    for param in self.DESCRIBE_INSTANCES_REQUIRED_PARAMS:
      if not utils.has_parameter(param, parameters):
        return self.__generate_response(False, 'no ' + param)

    reservation_id = parameters[self.PARAM_RESERVATION_ID]
    if self.reservations.has_key(reservation_id):
      return self.reservations.get(reservation_id)
    else:
      return self.__generate_response(False, self.REASON_RESERVATION_NOT_FOUND)

  def run_instances(self, parameters, secret):
    """
    Start a new virtual machine deployment using the provided parameters. The
    input parameter set must include an 'infrastructure' parameter which indicates
    the exact cloud environment to use. Value of this parameter will be used to
    instantiate a cloud environment specific agent which knows how to interact
    with the specified cloud platform. The parameters map must also contain a
    'num_vms' parameter which indicates the number of virtual machines that should
    be spawned. In addition to that any parameters required to spawn VMs in the
    specified cloud environment must be included in the parameters map.

    If this InfrastructureManager instance has been created in the blocking mode,
    this method will not return until the VM deployment is complete. Otherwise
    this method will simply kick off the VM deployment process and return
    immediately.

    Args:
      parameters  A parameter map containing the keys 'infrastructure',
                  'num_vms' and any other cloud platform specific
                  parameters. Alternatively one may provide a valid
                  JSON string instead of a dictionary object.
      secret      A previously established secret

    Returns:
      If the secret is valid and all the required parameters are available in
      the input parameter map, this method will return a dictionary containing
      a special 'reservation_id' key. If the secret is invalid or a required
      parameter is missing, this method will return a different map with the
      key 'success' set to False and 'reason' set to a simple error message.

    Raises:
      TypeError   If the inputs are not of the expected types
      ValueError  If the input JSON string (parameters) cannot be parsed properly
    """
    parameters, secret = self.__validate_args(parameters, secret)

    utils.log('Received a request to run instances.')

    if self.secret != secret:
      utils.log('Incoming secret {0} does not match the current secret {1} - '\
                'Rejecting request.'.format(secret, self.secret))
      return self.__generate_response(False, self.REASON_BAD_SECRET)

    for param in self.RUN_INSTANCES_REQUIRED_PARAMS:
      if not utils.has_parameter(param, parameters):
        return self.__generate_response(False, 'no ' + param)

    num_vms = int(parameters[self.PARAM_NUM_VMS])
    if num_vms <= 0:
      utils.log('Invalid VM count: {0}'.format(num_vms))
      return self.__generate_response(False, self.REASON_BAD_VM_COUNT)

    infrastructure = parameters[self.PARAM_INFRASTRUCTURE]
    agent = self.agent_factory.create_agent(infrastructure)
    try:
      agent.assert_required_parameters(parameters, BaseAgent.OPERATION_RUN)
    except AgentConfigurationException as exception:
      return self.__generate_response(False, str(exception))

    reservation_id = utils.get_random_alphanumeric()
    status_info = {
      'success': True,
      'reason': 'received run request',
      'state': self.STATE_PENDING,
      'vm_info': None
    }
    self.reservations.put(reservation_id, status_info)
    utils.log('Generated reservation id {0} for this request.'.format(
      reservation_id))
    try:
      if self.blocking:
        self.__spawn_vms(agent, num_vms, parameters, reservation_id)
      else:
        thread.start_new_thread(self.__spawn_vms,
          (agent, num_vms, parameters, reservation_id))
    except AgentConfigurationException as exception:
      status_info = {
        'success' : False,
        'reason' : str(exception),
        'state' : self.STATE_FAILED,
        'vm_info' : None
      }
      self.reservations.put(reservation_id, status_info)
      utils.log('Updated reservation id {0} with failed status because: {1}' \
        .format(reservation_id, str(exception)))

    utils.log('Successfully started request {0}.'.format(reservation_id))
    return self.__generate_response(True,
      self.REASON_NONE, {'reservation_id': reservation_id})

  def terminate_instances(self, parameters, secret):
    """
    Terminate a group of virtual machines using the provided parameters.
    The input parameter map must contain an 'infrastructure' parameter which
    will be used to instantiate a suitable cloud agent. Any additional
    environment specific parameters should also be available in the same
    map.

    If this InfrastructureManager instance has been created in the blocking mode,
    this method will not return until the VM deployment is complete. Otherwise
    this method simply starts the VM termination process and returns immediately.

    Args:
      parameters  A dictionary of parameters containing the required
                  'infrastructure' parameter and any other platform
                  dependent required parameters. Alternatively one
                  may provide a valid JSON string instead of a dictionary
                  object.
      secret      A previously established secret

    Returns:
      If the secret is valid and all the parameters required to successfully
      start a termination process are present in the parameters dictionary,
      this method will return a dictionary with the key 'success' set to
      True. Otherwise it returns a dictionary with 'success' set to False
      and 'reason' set to a simple error message.

    Raises:
      TypeError   If the inputs are not of the expected types
      ValueError  If the input JSON string (parameters) cannot be parsed properly
    """
    parameters, secret = self.__validate_args(parameters, secret)

    if self.secret != secret:
      return self.__generate_response(False, self.REASON_BAD_SECRET)

    for param in self.TERMINATE_INSTANCES_REQUIRED_PARAMS:
      if not utils.has_parameter(param, parameters):
        return self.__generate_response(False, 'no ' + param)

    infrastructure = parameters[self.PARAM_INFRASTRUCTURE]
    agent = self.agent_factory.create_agent(infrastructure)
    try:
      agent.assert_required_parameters(parameters,
        BaseAgent.OPERATION_TERMINATE)
    except AgentConfigurationException as exception:
      return self.__generate_response(False, str(exception))

    if self.blocking:
      self.__kill_vms(agent, parameters)
    else:
      thread.start_new_thread(self.__kill_vms, (agent, parameters))
    return self.__generate_response(True, self.REASON_NONE)

  def attach_disk(self, parameters, disk_name, instance_id, secret):
    """ Contacts the infrastructure named in 'parameters' and tells it to
    attach a persistent disk to this machine.

    Args:
      parameters: A dict containing the credentials necessary to send requests
        to the underlying cloud infrastructure.
      disk_name: A str corresponding to the name of the persistent disk that
        should be attached to this machine.
      instance_id: A str naming the instance id that the disk should be attached
        to (typically this machine).
      secret: A str that authenticates the caller.
    """
    parameters, secret = self.__validate_args(parameters, secret)

    if self.secret != secret:
      return self.__generate_response(False, self.REASON_BAD_SECRET)

    infrastructure = parameters[self.PARAM_INFRASTRUCTURE]
    agent = self.agent_factory.create_agent(infrastructure)
    disk_location = agent.attach_disk(parameters, disk_name, instance_id)
    return self.__generate_response(True, self.REASON_NONE,
      {'location' : disk_location})


  def __spawn_vms(self, agent, num_vms, parameters, reservation_id):
    """
    Private method for starting a set of VMs

    Args:
      agent           Infrastructure agent in charge of current operation
      num_vms         No. of VMs to be spawned
      parameters      A dictionary of parameters
      reservation_id  Reservation ID of the current run request
    """
    status_info = self.reservations.get(reservation_id)
    try:
      security_configured = agent.configure_instance_security(parameters)
      instance_info = agent.run_instances(num_vms, parameters,
        security_configured)
      ids = instance_info[0]
      public_ips = instance_info[1]
      private_ips = instance_info[2]
      status_info['state'] = self.STATE_RUNNING
      status_info['vm_info'] = {
        'public_ips': public_ips,
        'private_ips': private_ips,
        'instance_ids': ids
      }
      utils.log('Successfully finished request {0}.'.format(reservation_id))
    except AgentRuntimeException as exception:
      status_info['state'] = self.STATE_FAILED
      status_info['reason'] = str(exception)
    self.reservations.put(reservation_id, status_info)


  def __kill_vms(self, agent, parameters):
    """
    Private method for stopping a set of VMs

    Args:
      agent       Infrastructure agent in charge of current operation
      parameters  A dictionary of parameters
    """
    agent.terminate_instances(parameters)

  def __generate_response(self, status, msg, extra=None):
    """
    Generate an infrastructure manager service response

    Args:
      status  A boolean value indicating the status
      msg     A reason message (useful if this a failed operation)
      extra   Any extra fields to be included in the response (Optional)

    Returns:
      A dictionary containing the operation response
    """
    utils.log("Sending success = {0}, reason = {1}".format(status, msg))
    response = {'success': status, 'reason': msg}
    if extra is not None:
      for key, value in extra.items():
        response[key] = value
    return response

  def __validate_args(self, parameters, secret):
    """
    Validate the arguments provided by user.

    Args:
      parameters  A dictionary (or a JSON string) provided by the client
      secret      Secret sent by the client

    Returns:
      Processed user arguments

    Raises
      TypeError If at least one user argument is not of the current type
    """
    if type(parameters) != type('') and type(parameters) != type({}):
      raise TypeError('Invalid data type for parameters. Must be a '
                      'JSON string or a dictionary.')
    elif type(secret) != type(''):
      raise TypeError('Invalid data type for secret. Must be a string.')

    if type(parameters) == type(''):
      parameters = json.loads(parameters)
    return parameters, secret
