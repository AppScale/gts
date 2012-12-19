__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

class BaseAgent:
  """
  BaseAgent class defines the interface that must be implemented by
  each and every cloud agent implementation. This interface defines
  the basic operations such as run_instances and terminate_instances,
  which must be supported by every agent. The InfrastructureManager
  assumes that all agent implementations are based on this interface
  and uses that knowledge to interact with different cloud platforms.
  """

  # Basic operations supported by agents
  OPERATION_RUN = 'run'
  OPERATION_TERMINATE = 'terminate'

  def set_environment_variables(self, parameters):
    """
    Set any cloud platform specific environment variables
    in the current process.

    Args:
      parameters  A dictionary of parameters that may include parameters
                  that should not be actually set in  in the current process
                  as environment variables. Agent implementations may decide
                  which subset of parameters should be set as environment
                  variables.
    """
    raise NotImplementedError

  def configure_instance_security(self, parameters):
    """
    Configure and setup security features for the VMs spawned via this
    agent. This method is called whenever InfrastructureManager is about
    start a set of VMs using this agent. Implementations may configure
    security features such as VM login and firewalls in this method.
    Implementations also have the option of not taking any action upon
    this method call.

    Args:
      parameters    A dictionary containing the required security parameters

    Returns:
      True if some action was taken to configure security for the VMs
      and False otherwise.
    """
    raise NotImplementedError

  def describe_instances(self, parameters):
    """
    Query the underlying cloud platform regarding VMs that are already
    up and running.

    Args:
      parameters  A dictionary containing the parameters required by the
                  infrastructure agent.

    Returns:
      A tuple of the form (public, private, id) where public is a list
      of private IP addresses, private is a list of private IP addresses
      and id is a list of platform specific VM identifiers.
    """
    raise NotImplementedError

  def run_instances(self, count, parameters, security_configured):
    """
    Start a set of virtual machines using the parameters provided.

    Args:
      count                 An integer that indicates the number of
                            VMs to be spawned
      parameters            A dictionary of parameters required by
                            the agent implementation to create the VMs
      security_configured   True if security has been configured for the VMs
                            by this agent, or False otherwise. This is
                            usually the value that was returned by a call
                            to the configure_instance_security method
    Returns:
      A tuple consisting of information related to the spawned VMs. The
      tuple should contain a list of instance IDs, a list of public IP
      addresses and a list of private IP addresses.
    """
    raise NotImplementedError

  def terminate_instances(self, parameters):
    """
    Terminate a set of virtual machines using the parameters given.

    Args:
      parameters  A dictionary of parameters
    """
    raise NotImplementedError

  def assert_required_parameters(self, parameters, operation):
    """
    Check whether all the platform specific parameters are present in the
    provided dictionary. If all the parameters required to perform the
    given operation is available this method simply returns. Otherwise
    it throws an AgentConfigurationException.

    Args:
      parameters  A dictionary of parameters (as provided by the client)
      operation   Operation for which the parameters should be checked

    Raises:
      AgentConfigurationException If a required parameter is absent
    """
    raise NotImplementedError


class AgentConfigurationException(Exception):
  """
  An agent implementation may throw this exception when it detects that a
  given cloud configuration is missing some required parameters or contains
  invalid values.
  """

  def __init__(self, msg):
    Exception.__init__(self, msg)