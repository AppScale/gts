from agents.ec2_agent import EC2Agent
from agents.euca_agent import EucalyptusAgent
from agents.factory import InfrastructureAgentFactory
from unittest import TestCase

__author__ = 'hiranya'
__email__ = 'hiranya@appscale.com'

class TestAgentFactory(TestCase):

  def test_create_agent(self):
    factory = InfrastructureAgentFactory()
    agent = factory.create_agent('ec2')
    self.assertEquals(type(agent), type(EC2Agent()))

    agent = factory.create_agent('euca')
    self.assertEquals(type(agent), type(EucalyptusAgent()))

    try:
      factory.create_agent('bogus')
      self.fail('No exception thrown for invalid infrastructure')
    except NameError:
      pass
    except Exception:
      self.fail('Unexpected exception thrown for invalid infrastructure')
