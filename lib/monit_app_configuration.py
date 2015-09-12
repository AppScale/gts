import os
import subprocess
import sys
import random
import logging 

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import file_io

# Template used for monit configuration files.
TEMPLATE_LOCATION_SYSLOG = os.path.join(os.path.dirname(__file__)) +\
                    "/templates/monit_template_syslog.conf"
TEMPLATE_LOCATION = os.path.join(os.path.dirname(__file__)) +\
                    "/templates/monit_template.conf"

def create_config_file(watch, start_cmd, stop_cmd, ports, env_vars={},
  max_memory=500, syslog_server=None):
  """ Reads in a template file for monit and fills it with the 
      correct configuration. The caller is responsible for deleting 
      the created file.
  
  Args:
    watch: A string which identifies this process with monit
    start_cmd: The start command to start the process
    stop_cmd: The stop command to kill the process
    ports: A list of ports that are being watched
    env_vars: The environment variables used when starting the process
    max_memory: An int that names the maximum amount of memory that this process
      is allowed to use (in megabytes) before monit should restart it.
  Returns:
    The name of the created configuration file. 
  Raises: 
    TypeError with bad argument types
  """
  if not isinstance(watch, str): raise TypeError("Expected str")
  if not isinstance(start_cmd, str): raise TypeError("Expected str")
  if not isinstance(stop_cmd, str): raise TypeError("Expected str")
  if not isinstance(ports, list): raise TypeError("Expected list")
  if not isinstance(env_vars, dict): raise TypeError("Expected dict")

  env = ""
  for ii in env_vars:
    env += "export " + str(ii) + "=\"" + str(env_vars[ii]) + "\" && "

  # Convert ints to strings for template formatting
  for index, ii in enumerate(ports): ports[index] = str(ii) 

  # 'WATCH' and 'port' are substituted here as the last two arguments 
  # because the template script itself uses {}. If we do not sub for them 
  # a key error is raised by template.format().
  for port in ports:
    if syslog_server:
      template = file_io.read(TEMPLATE_LOCATION_SYSLOG)
      template = template.format(watch, start_cmd, stop_cmd, port, env,
        max_memory, syslog_server)
    else:
      template = file_io.read(TEMPLATE_LOCATION)
      template = template.format(watch, start_cmd, stop_cmd, port, env,
        max_memory)

    temp_file_name = "/etc/monit/conf.d/" + watch + '-' + \
                     str(port) + ".cfg"
    file_io.write(temp_file_name, template) 

  return
