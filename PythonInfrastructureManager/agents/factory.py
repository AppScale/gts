from agents.ec2_agent import EC2Agent

__author__ = 'hiranya'

class InfrastructureAgentFactory:
    def create_agent(self, infrastructure):
        if infrastructure == 'ec2':
            return EC2Agent()
        else:
            raise NameError('Unrecognized infrastructure: ' +   infrastructure)