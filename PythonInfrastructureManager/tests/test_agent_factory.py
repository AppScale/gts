from unittest.case import TestCase
from agents.ec2_agent import EC2Agent
from agents.factory import InfrastructureAgentFactory

__author__ = 'hiranya'

class TestAgentFactory(TestCase):
    def test_create_agent(self):
        factory = InfrastructureAgentFactory()
        agent = factory.create_agent('ec2')
        self.assertEquals(type(agent), type(EC2Agent()))

        try:
            agent = factory.create_agent('bogus')
            self.fail('No exception thrown for invalid infrastructure')
        except NameError:
            pass
        except Exception:
            self.fail('Unexpected exception thrown for invalid infrastructure')