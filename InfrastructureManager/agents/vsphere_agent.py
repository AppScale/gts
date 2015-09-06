"""
[TESTING]
Agent class for vSphere.

You need setup your vCenter:
	you need create a AppScale template with VMWare tools installed and to be powered on.
  	you need create a head node in vSphere
"""

from agents.base_agent import BaseAgent, AgentConfigurationException, AgentRuntimeException
from pysphere import VIServer
import datetime
import os
import time
import random


__author__ = 'Marco Maria Di Nicola'
__email__ = 'marticus@hotmail.it'
__email2__ = 'dinicola.1210022@studenti.uniroma1.it'

PARAM_USERNAME = 'vusername'
PARAM_PASSWORD = 'vpassword'
PARAM_HOST = 'vhost'
PARAM_IMAGE_ID = 'vimage_id'                 #name of AppScale Template create in vSphere some like appscale-template
PARAM_INSTANCE_IDS = 'instance_ids'         #name of vm (ex: appscale1)

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
							  'credentials', 'image_id'.
	      security_configured Uses this boolean value as an heuristic to
	                          detect brand new AppScale deployments.

	    Returns:
	      A tuple of the form (instances, private_ips)
		"""
		conn = self.open_connection(parameters)
		if conn is not None:
			template = conn.get_vm_by_name(parameters[PARAM_IMAGE_ID])
			nvm = len(conn.get_registered_vms())
			nvm += random.randint(0, 1000)
			public_ips = []
			private_ips = []
			instance_ids = []
			for i in range(count):
				name = "appscale{0}".format(nvm)
				newVM = template.clone(name)                                    #valutare se inserire una wait di 1 min
				ip = newVM.get_property('ip_address')							#modificato
				time.sleep(180)
				instance_ids.append(name)
				private_ips.append(ip)
				nvm += 1
			public_ips = private_ips
			print public_ips
			print private_ips
			print instance_id
			return instance_ids, public_ips, private_ips
		return None
