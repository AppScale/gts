import logging
import struct

from appscale.agents.ec2_agent import EC2Agent
from appscale.agents.euca_agent import EucalyptusAgent
from appscale.agents.gce_agent import GCEAgent
from appscale.agents.openstack_agent import OpenStackAgent

logger = logging.getLogger(__name__)

try:
  from appscale.agents.azure_agent import AzureAgent
except (ImportError, struct.error):
  logger.exception('AzureAgent disabled')
  AzureAgent = None

__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

class InfrastructureAgentFactory:
  """
  Factory implementation which can be used to instantiate concrete infrastructure
  agents.
  """

  agents = {
    'ec2': EC2Agent,
    'euca': EucalyptusAgent,
    'gce': GCEAgent,
    'openstack': OpenStackAgent
  }
  if AzureAgent is not None:
    agents['azure'] = AzureAgent

  def create_agent(self, infrastructure):
    """
    Instantiate a new infrastructure agent.

    Args:
      infrastructure  A string indicating the type of infrastructure
                      agent to be initialized.

    Returns:
      An infrastructure agent instance that implements the BaseAgent API

    Raises:
      NameError       If the given input string does not map to any known
                      agent type.
    """
    if self.agents.has_key(infrastructure):
      return self.agents[infrastructure]()
    else:
      raise NameError('Unrecognized infrastructure: ' + infrastructure)
