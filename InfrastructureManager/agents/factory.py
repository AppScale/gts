from agents.ec2_agent import EC2Agent
from agents.euca_agent import EucalyptusAgent

__author__ = 'hiranya'

class InfrastructureAgentFactory:
    """
    Factory implementation which can be used to instantiate concrete infrastructure
    agents.
    """

    def create_agent(self, infrastructure):
        """
        Instantiate a new infrastructure agent.

        Args:
            - infrastructure    A string indicating the type of infrastructure
                                agent to be initialized.

        Returns:
            An infrastructure agent instance that implements the BaseAgent API

        Raises:
            - NameError     If the given input string does not map to any known
                            agent type.
        """
        if infrastructure == 'ec2':
            return EC2Agent()
        elif infrastructure == 'euca':
            return EucalyptusAgent()
        else:
            raise NameError('Unrecognized infrastructure: ' +   infrastructure)