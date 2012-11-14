from agents.ec2_agent import EC2Agent
from agents.euca_agent import EucalyptusAgent

__author__ = 'hiranya'

class InfrastructureAgentFactory:
    def create_agent(self, infrastructure):
        if infrastructure == 'ec2':
            return EC2Agent()
        elif infrastructure == 'euca':
            return EucalyptusAgent()
        else:
            raise NameError('Unrecognized infrastructure: ' +   infrastructure)