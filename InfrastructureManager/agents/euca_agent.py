from agents.ec2_agent import EC2Agent

__author__ = 'hiranya'

class EucalyptusAgent(EC2Agent):

    def __init__(self):
        EC2Agent.__init__(self)
        self.prefix = 'euca'
