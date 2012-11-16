from agents.ec2_agent import EC2Agent

__author__ = 'hiranya'

class EucalyptusAgent(EC2Agent):
    """
    Eucalyptus infrastructure agent which can be used to spawn and terminate
    VMs in an Eucalyptus based environment.
    """

    def __init__(self):
        EC2Agent.__init__(self)
        self.prefix = 'euca'
