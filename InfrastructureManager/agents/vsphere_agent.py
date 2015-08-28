"""
[TESTING]
Agent class for vSphere.
The agent need pysphere 0.1.8 you can install from pip or from esayinstall tools

You need setup your vCenter:
    you need create a AppScale template with VMWare tools installed and to be
    powered on.
      you need create a head node in vSphere
"""

from agents.base_agent import BaseAgent, AgentConfigurationException, AgentRuntimeException
import datetime
from pysphere import VIServer
import time
from utils import utils

__author__ = 'Marco Maria Di Nicola'
__email__ = 'marticus@hotmail.it'
__email2__ = 'dinicola.1210022@studenti.uniroma1.it'

PARAM_USERNAME = 'vusername'
PARAM_PASSWORD = 'vpassword'
PARAM_HOST = 'vhost'
PARAM_RESOURCE_POOL = 'vresource_pool'       #name of Resouce Pool in vSphere (reservate for AppScale) some like appscale-pool
PARAM_IMAGE_ID = 'vimage_id'                 #name of AppScale Template create in vSphere some like appscale-template
#PARAM_INSTANCE_IDS = 'instance_ids'         #name of vm (ex: appscale1)

class vSphereAgent(BaseAgent):


	"""
	vSphere infrastructure agent class which can be used to spawn and terminate
  	VMs in an vSphere based environment.
	"""
	def configure_instance_security(self, parameters):
		"""
		Prepare AppScale head node in vCenter and AppScale template for cloning
		a new virtual machines
		"""
		return True

	def open_connection(self, parameters):
		"""
		Initialize a connection to the back-end vSphere.

	    Args:
	      parameters  A dictionary containing the 'credentials' parameter.

	    Returns:
	      An instance of pysphere connection
		"""

		try:
			server = VIServer()
			server.connect(parameters[PARAM_HOST], parameters[PARAM_USERNAME], parameters[PARAM_PASSWORD])
		except StandardError, e:
			print ('Connection problem with the host {0}'.format(parameters[PARAM_HOST]))
			print e
			return None
		return server

	def terminate_instances(self, parameters):
		"""
		Stop one of more vSphere instances using. The input instance IDs are
	    fetched from the 'instance_ids' parameters in the input map. (Also
	    see documentation for the BaseAgent class)

	    Args:
	      parameters  A dictionary of parameters
		"""
		instance_ids = parameters[PARAM_INSTANCE_IDS]
		conn = self.open_connection(parameters)
		if conn is not None:
			for instance_id in instance_ids:
				vm = conn.get_vm_by_name(instance_id)
				vm.power_off()
				vm.destroy()

	def run_instances(self, count, parameters, security_configured):
		"""
		Spawns the specified number of vSphere instances using the parameters
	    provided.

	    Args:
	      count               No. of VMs to spawned
	      parameters          A dictionary of parameters. This must contain
							  'credentials', 'resource_pool', 'image_id'.
	      security_configured Uses this boolean value as an heuristic to
	                          detect brand new AppScale deployments.

	    Returns:
	      A tuple of the form (instances, private_ips)
		"""
		#valutare se fare una creazione asincrona delle macchine
		conn = self.open_connection(parameters)
		if conn is not None:
			template = conn.get_vm_by_name(parameters[PARAM_IMAGE_ID])
			nvm = len(conn.get_registered_vms(resource_pool=parameters[PARAM_RESOURCE_POOL], advanced_filters={'config.template':False}))
			nvm += 1
			private_ips = []
			instance_ids = []
			for i in range(count):
				name = "appscale{0}".format(nvm)
				newVM = template.clone(name,resourcepool=parameters[PARAM_RESOURCE_POOL])
				ip = get_property('ip_address')
				instance_ids.append(name)
				private_ips.append(ip)
				nvm += 1
			return instance_ids, private_ips
		return None
