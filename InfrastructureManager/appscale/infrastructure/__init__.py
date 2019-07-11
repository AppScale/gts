import argparse
import logging
import uuid

from tornado import gen, web
from tornado.escape import json_decode, json_encode
from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.options import options

from appscale.common import appscale_info
from appscale.common.constants import (
  HTTPCodes,
  LOG_FORMAT
)
from appscale.agents.base_agent import (
  AgentConfigurationException,
  AgentRuntimeException,
  BaseAgent
)
from appscale.agents.factory import InfrastructureAgentFactory

from .operation_ids_cache import OperationIdsCache

logger = logging.getLogger(__name__)

DEFAULT_PORT = 17444

# Parameters required by InfrastructureManager
PARAM_OPERATION_ID = 'operation_id'

# Parameters expected in request bodies for certain agent calls.
PARAM_DISK_NAME = 'disk_name'
PARAM_INFRASTRUCTURE = 'infrastructure'
PARAM_INSTANCE_ID = 'instance_id'
PARAM_NUM_VMS = 'num_vms'

# The state of each operation.
operation_ids = OperationIdsCache()


class CustomHTTPError(web.HTTPError):
  """ An HTTPError that keeps track of keyword arguments. """

  def __init__(self, status_code=500, **kwargs):
    # Pass standard HTTPError arguments along.
    log_message = kwargs.get('log_message', None)
    reason = kwargs.get('reason', None)
    super(CustomHTTPError, self).__init__(status_code,
                                          log_message=log_message,
                                          reason=reason)
    self.kwargs = kwargs

class NoPublicIpsFoundException(Exception):
  """ An exception indicating no "new" public ips were found."""
  pass

def get_agent(agent_factory, operation, args, scaling_params=None):
    """ Returns an agent and the parameters reformatted from the given
    parameters. The point of this is so the controller doesn't have to
    rearrange the dictionary and it can all be done by the agent.

    Args:
      agent_factory: The Agent Factory to use.
      infrastructure: The infrastructure agent to create.
      operation: The agent operation that we are going to run.
      args: The original dictionary received from the AppController.
      scaling_params: A dictionary containing additional keys to be added
        for an agent operation. Ex: 'instance_ids' required for
        terminate_instances so needs to be added before asserting required
        parameters.
    Returns:
      A tuple containing the Agent instance and the dictionary of parameters
        that have been verified.
    Raises:
      AgentConfigurationException if we are missing required parameters.
    """
    agent = agent_factory.create_agent(args[PARAM_INFRASTRUCTURE])
    parameters = agent.get_params_from_args(args)
    parameters[BaseAgent.PARAM_AUTOSCALE_AGENT] = True
    if scaling_params:
      parameters.update(scaling_params)
    agent.assert_required_parameters(parameters, operation)
    return (agent, parameters)

class InstancesHandler(web.RequestHandler):
  """InstancesHandler is used to start and stop instances in a supported
  infrastructure by making calls to the agents available in the tools. It
  keeps track of these operations in the OperationsCache that will be updated
  when the agent request is completed.
  """

  # States a particular VM deployment could be in
  STATE_PENDING = 'pending'
  STATE_SUCCESS = 'success'
  STATE_FAILED  = 'failed'

  def initialize(self, agent_factory):
    """ Defines required resources to handle requests.

    Args:
      agent_factory: An Agent Factory.
    """
    self.agent_factory = agent_factory

  @gen.coroutine
  def get(self):
    """
    Query the InfrastructureManager instance for details regarding
    an operation id for running or terminating instances.

    Args:
      AppScale-Secret: Required in header. Authentication to deployment.
      operation_id: Required in body. A valid 'operation_id' is an ID issued
        by InfrastructureManager during the initial request.
    Returns:
      A dictionary containing the following keys for the specified cases.

      For a run_instances operation_id:
        'success': True or False depending on the outcome of the virtual
          machine deployment process.
        'state': pending, failed, or success
        'reason': None if success, otherwise a string containing the Exception.
        'vm_info': None if a terminate request or a run operation is pending,
          otherwise should be a dictionary containing the following keys:
            'public_ips': The list of public ips to add to the deployment.
            'private_ips': The list of private ips to add to the deployment.
            'instance_ids': The list of instance ids to add to the deployment.
      For a terminate_instances operation_id:
        'success': True or False depending on the outcome of the virtual
          machine deployment process.
        'state': pending, failed, or success
        'reason': None if success, otherwise a string containing the Exception.
        * note that this dictionary does not contain 'vm_info'.

    Raises:
      CustomHTTPError if an invalid Operation ID is given.

    """
    if 'AppScale-Secret' not in self.request.headers \
        or self.request.headers['AppScale-Secret'] != options.secret:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid secret')

    parameters = json_decode(self.request.body)
    logger.info('Operation id received: {}'.format(parameters))
    if not parameters or 'operation_id' not in parameters:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST, message='operation_id is a'
                                                           'required parameter')

    operation_id = parameters['operation_id']
    if operation_ids.has_key(operation_id):
      operation_id_content = operation_ids.get(operation_id)
      logger.debug('Operation contents: {}'.format(operation_id_content))
      self.write(json_encode(operation_id_content))
    else:
      logger.error('Operation id not found')
      raise CustomHTTPError(HTTPCodes.NOT_FOUND, message='Operation id not '
                                                         'found')
  @gen.coroutine
  def post(self):
    """
    Spawn new instances using the provided parameters. The request must also
    contain a 'num_vms' parameter which indicates the number of virtual
    machines that should be spawned.

    Args:
      AppScale-Secret: Required in header. Authentication to deployment.
      args: The request body, a dictionary of values needed to start
        instances in the specified infrastructure. Infrastructure specific
        checks are made in  'get_agent', but the following parameters will be
        verified here:
          num_vms: Required in body. Number of VMs to start.
          infrastructure: Required in body, infrastructure to construct an agent
            for.
    Returns:
      If the secret is valid and all the required parameters are available in
      the input parameter map, this method will return a dictionary containing
      an 'operation_id' key.

    Raises:
      CustomHTTPError if the necessary parameters are not filled.
    """
    if 'AppScale-Secret' not in self.request.headers \
        or self.request.headers['AppScale-Secret'] != options.secret:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid secret')

    args = json_decode(self.request.body)

    logger.info('Received a request to run instances.')
    for arg in [PARAM_INFRASTRUCTURE, PARAM_NUM_VMS]:
      if arg not in args:
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
              message='{} is a required parameter'.format(arg))

    num_vms = int(args[PARAM_NUM_VMS])
    if num_vms <= 0:
      logger.warn('Invalid VM count: {0}'.format(num_vms))
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Invalid VM count: {0}'.format(num_vms))

    try:
      agent, run_params = get_agent(self.agent_factory,
                                    BaseAgent.OPERATION_RUN, args)
    except AgentConfigurationException as exception:
      logger.exception("Error creating agent!")
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
        message='Invalid agent configuration: {0}'.format(exception))

    operation_id = str(uuid.uuid4())
    status_info = {
      'success': False,
      'reason': 'received run request',
      'state': self.STATE_PENDING,
      'vm_info': None
    }
    operation_ids[operation_id] = status_info
    logger.debug('Generated operation id {0} for this request.'.format(
        operation_id))
    IOLoop.current().spawn_callback(InstancesHandler._spawn_vms, agent=agent,
                                    parameters=run_params,
                                    num_vms=num_vms,
                                    operation_id=operation_id)
    logger.info('Successfully started operation {0}.'.format(operation_id))
    self.write(json_encode({PARAM_OPERATION_ID: operation_id}))

  @gen.coroutine
  def delete(self):
    """
    Terminate a virtual machine.
    Args:
      AppScale-Secret: Required in header. Authentication to deployment.
      args: The request body, a dictionary of values needed to start
        instances in the specified infrastructure. Infrastructure specific
        checks are made in  'get_agent', but the following parameters will be
        verified here:
          instance_id: Required in body. Instance id to terminate.
          infrastructure: Required in body, infrastructure to construct an agent
            for.
    Returns:
      If the secret is valid and all the required parameters are available in
      the input parameter map, this method will return a dictionary containing
      an 'operation_id' key.

    Raises:
      CustomHTTPError if the necessary parameters are not filled.
    """
    if 'AppScale-Secret' not in self.request.headers \
        or self.request.headers['AppScale-Secret'] != options.secret:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid secret')

    args = json_decode(self.request.body)
    for arg in [PARAM_INFRASTRUCTURE, BaseAgent.PARAM_INSTANCE_IDS]:
      if arg not in args:
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                                message='{} is required'.format(arg))

    # Dictionary containing the keys and values that need to be added to the
    # parameters in order to perform a terminate_instances request.
    scaling_params = {BaseAgent.PARAM_INSTANCE_IDS: args[BaseAgent.PARAM_INSTANCE_IDS]}
    try:
      agent, terminate_params = get_agent(self.agent_factory,
                                          BaseAgent.OPERATION_TERMINATE,
                                          args, scaling_params)
    except AgentConfigurationException as exception:
      logger.exception("Error creating agent!")
      raise CustomHTTPError(HTTPCodes.INTERNAL_ERROR,
        message='Invalid agent configuration: {0}'.format(exception))

    operation_id = str(uuid.uuid4())
    status_info = {
      'success': False,
      'reason': 'received kill request',
      'state': self.STATE_PENDING,
      'vm_info': None
    }
    operation_ids[operation_id] = status_info
    logger.debug('Generated operation id {0} for this request.'.format(
        operation_id))
    IOLoop.current().spawn_callback(InstancesHandler._kill_vms, agent, terminate_params,
                                    operation_id)
    logger.info('Successfully started operation {0}.'.format(operation_id))
    self.write(json_encode({PARAM_OPERATION_ID: operation_id}))


  @classmethod
  def _describe_vms(cls, agent, parameters):
    """
    Private method for calling the agent to describe VMs.

    Args:
      agent: Infrastructure agent in charge of current operation
      parameters: A dictionary of values needed to describe instances in the
        specified infrastructure.
    Returns:
      If the agent is able to describe instances, returns lists in the form
      ([public_ips], [private_ips], [instance_ids])
    Raises:
      AgentConfigurationException if there was a problem contacting the
        infrastructure.
      AgentRuntimeException if there was a problem describing instances.
    """
    return agent.describe_instances(parameters)

  @classmethod
  def _spawn_vms(cls, agent, num_vms, parameters, operation_id):
    """
    Private method for starting a set of VMs

    Args:
      agent: Infrastructure agent in charge of current operation
      num_vms: No. of VMs to be spawned
      parameters: A dictionary of values needed to start instances in the
        specified infrastructure.
      operation_id: Operation ID of the current run request
    """
    status_info = operation_ids[operation_id]
    try:
      active_public_ips, active_private_ips, active_instances = \
        cls._describe_vms(agent, parameters)
    except (AgentConfigurationException, AgentRuntimeException) as exception:
      status_info['state'] = cls.STATE_FAILED
      status_info['success'] = False
      status_info['reason'] = str(exception)
      logger.info('Updating run instances request with operation id {0} to '
                  'failed status because: {1}' \
                  .format(operation_id, str(exception)))
      return

    try:
      security_configured = agent.configure_instance_security(parameters)
      instance_ids, public_ips, private_ips = \
        agent.run_instances(num_vms, parameters, security_configured,
                            public_ip_needed=False)
      status_info['success'] = True
      status_info['state'] = cls.STATE_SUCCESS
      status_info['vm_info'] = {
        'public_ips': public_ips,
        'private_ips': private_ips,
        'instance_ids': instance_ids
      }
      logger.info('Successfully finished operation {0}.'.format(
          operation_id))
    except (AgentConfigurationException, AgentRuntimeException) as exception:
      # Check if we have had partial success starting instances.
      try:
        public_ips, private_ips, instance_ids = \
          cls._describe_vms(agent, parameters)

        public_ips = agent.diff(public_ips, active_public_ips)
        if not public_ips:
          raise NoPublicIpsFoundException

        private_ips = agent.diff(private_ips, active_private_ips)
        instance_ids = agent.diff(instance_ids, active_instances)
        status_info['state'] = cls.STATE_SUCCESS
        status_info['vm_info'] = {
          'public_ips': public_ips,
          'private_ips': private_ips,
          'instance_ids': instance_ids
        }
      except (AgentConfigurationException, AgentRuntimeException,
              NoPublicIpsFoundException):
        status_info['state'] = cls.STATE_FAILED

      # Mark it as failed either way since the AppController never checks
      # 'success' and it technically failed.
      status_info['success'] = False
      status_info['reason'] = str(exception)
      logger.info('Updating run instances request with operation id {0} to '
                  'failed status because: {1}' \
                  .format(operation_id, str(exception)))

  @classmethod
  def _kill_vms(cls, agent, parameters, operation_id):
    """
    Private method for stopping a VM. This method assumes it has only been
    told to stop one VM.

    Args:
      agent: Infrastructure agent in charge of current operation
      parameters: A dictionary of values needed to terminate instances in the
        specified infrastructure.
      operation_id: Operation ID of the current terminate request
    """
    status_info = operation_ids[operation_id]
    try:
      agent.terminate_instances(parameters)
      status_info['success'] = True
      status_info['state'] = cls.STATE_SUCCESS
      logger.info('Successfully finished operation {0}.'.format(
          operation_id))
    except (AgentRuntimeException, AgentConfigurationException) as exception:
      status_info['state'] = cls.STATE_FAILED
      status_info['reason'] = str(exception)
      logger.info('Updating operation {0} to {1}.'.format(
          operation_id, cls.STATE_FAILED))


class InstanceHandler(web.RequestHandler):
  """  Instance Handler is used to modify (adding a disk) or get statistics
  (system manager stats) from existing instances. InstanceHandler should be
  ran on every machine.
    """
  def initialize(self, agent_factory):
    """ Defines required resources to handle requests.

    Args:
      agent_factory: An Agent Factory.
    """
    self.agent_factory = agent_factory

  @gen.coroutine
  def post(self):
    """ Contacts the infrastructure named in 'parameters' and tells it to
    attach a persistent disk to this machine.

    Args:
      AppScale-Secret: Required in header. Authentication to deployment.
      args: the request body, a dictionary of values needed to start
        instances in the specified infrastructure. Infrastructure specific
        checks are made in  'get_agent', but the following parameters will be
        verified here:
          disk_name: A str corresponding to the name of the persistent disk that
            should be attached to this machine.
          instance_id: A str naming the instance id that the disk should be
            attached to (typically this machine).
          infrastructure: Required in body, infrastructure to construct an agent
            for.
    """
    if 'AppScale-Secret' not in self.request.headers \
        or self.request.headers['AppScale-Secret'] != options.secret:
      raise CustomHTTPError(HTTPCodes.UNAUTHORIZED, message='Invalid secret')

    args = json_decode(self.request.body)
    for arg in [PARAM_DISK_NAME, PARAM_INFRASTRUCTURE, PARAM_INSTANCE_ID]:
      if arg not in args:
        raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
            message='{} is a required parameter'.format(arg))

    # There is no "operation_attach_disk" so send None for operation and no
    # additional parameters are required.
    agent, attach_params = get_agent(self.agent_factory, None, args)
    try:
      disk_location = agent.attach_disk(attach_params,
                                        args[PARAM_DISK_NAME],
                                        args[PARAM_INSTANCE_ID])
    except (AgentRuntimeException, AgentConfigurationException) as e:
      raise CustomHTTPError(HTTPCodes.BAD_REQUEST,
                            message='Error attaching disk! {}'.format(e))
    self.write(json_encode({'location': disk_location}))

class Respond404Handler(web.RequestHandler):
  """
  This class is aimed to stub unavailable route.
  The autoscaler is not available on all nodes.
    """

  def initialize(self, reason):
    self.reason = reason

  def get(self):
    self.set_status(404, self.reason)

def make_app(secret, is_autoscaler):
  options.__dict__['_options'].clear()
  options.define('secret', secret)
  agent_factory = InfrastructureAgentFactory()

  if is_autoscaler:
    scaler_route = ('/instances', InstancesHandler,
                    {'agent_factory': agent_factory})
  else:
    scaler_route = ('/instances', Respond404Handler,
                    dict(reason='This node was not started as an autoscaler.'))
  app = web.Application([
    ('/instance', InstanceHandler, {'agent_factory': agent_factory}),
    scaler_route,
  ])
  return app


def main():
  """ Starts the AdminServer. """
  logging.basicConfig(format=LOG_FORMAT, level=logging.INFO)
  parser = argparse.ArgumentParser()
  parser.add_argument('--autoscaler', action='store_true',
                      help='Ability to start/terminate instances.')
  parser.add_argument('-p', '--port', type=int, default=DEFAULT_PORT,
                      help='The port to listen on')
  parser.add_argument('-v', '--verbose', action='store_true',
                      help='Output debug-level logging')
  args = parser.parse_args()
  if args.verbose:
    logger.setLevel(logging.DEBUG)

  app = make_app(appscale_info.get_secret(), args.autoscaler)

  logger.info('Starting InfrastructureManager')
  app.listen(args.port)
  io_loop = IOLoop.current()
  io_loop.start()
