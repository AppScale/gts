"""
[TESTING]
Agent class for vSphere. 
The agent need pysphere 0.1.8 you can install from pip on from esayinstall tools

You need setup your vCenter:
	you need create a template with AppScale, follow the AppScale guide.
  you need create a head node in vSphere
"""

from agents.base_agent import BaseAgent, AgentConfigurationException, AgentRuntimeException
from pysphere import VIServer
import datetime
import glob
import os
import time
from utils import utils

__author__ = 'Marco M. Di Nicola'
__email__ = 'marticus@hotmail.it'

PARAM_CREDENTIALS = 'credentials'           #HOST(vCenter ip), USERNAME, PASSWORD
PARAM_IMAGE_ID = 'image_id'                 #name of AppScale Template in vSphere some like appscale-template
PARAM_RESOURCE_POOL = 'resouce_pool'        #name of Resouce Pool in vSphere some like appscale-pool
PARAM_INSTANCE_IDS = 'instance_ids'         #path of vm

class vSphereAgent(BaseAgent):
  """
  	vSphere infrastructure agent class which can be used to spawn and terminate
  	VMs in an vSphere based environment.
 	"""
  def configure_instance_security(self, parameters):
    """
      prepare AppScale head node in vCenter and AppScale template for cloning a new virtual machines
    """
    return True

  #TERMINATED
  def open_connection(self, parameters):
  	"""
  	Initialize a connection to the back-end vSphere.

  	Args:
  		parameters  A dictionary containing the 'credentials' parameter.

  	Returns:
    		An instance of pysphere connection
  	"""
  	credentials = parameters[self.PARAM_CREDENTIALS]
  	server=VIServer()
  	return server.connect(credentials['HOST'], credentials['USERNAME'], credentials['PASSWORD'])

  #TERMINATED
  def terminate_instances(self, parameters):
    """ 
    Deletes the instances specified in 'parameters' in running vSphere.

    Args:
      parameters: list of vm to be destroyed.
    """
    instance_ids = parameters[self.PARAM_INSTANCE_IDS]
    conn = self.open_connection(parameters)
    for instance_id in instance_ids:
      vm = conn.get_vm_by_path(instance_id)
      vm.power_off()
      vm.destroy()



  #time problem
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
    conn = self.open_connection(parameters)
    template = conn.get_vm_by_name(parameters[PARAM_IMAGE_ID])
    nvm = len(server.get_registered_vms(resource_pool=parameters[PARAM_RESOURCE_POOL], advanced_filters={'config.template':False}))
    nvm += 1
    for i in count:
      name = "appscale-{0}".format(nvm)
      template.clone(name,resourcepool=parameters[PARAM_RESOURCE_POOL])
      nvm += 1
    
    vmlist = server.get_registered_vms(resource_pool=parameters[PARAM_RESOURCE_POOL], advanced_filters={'config.template':False})










    
