# Programmer: Navraj Chohan
import os
import subprocess
import sys
import random
import logging 

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import file_io

# Template used for god configuration files 
TEMPLATE_LOCATION = os.path.join(os.path.dirname(__file__)) +\
                    "/templates/god_template.conf"

def create_config_file(watch, start_cmd, stop_cmd, ports, env_vars={}):
  """ Reads in a template file for god and fills it with the 
      correct configuration.
  
  Args:
    watch: The name of the watch
    start_cmd: The start command to start the process
    stop_cmd: The stop command to kill the process
    ports: A list of ports that are being watched
    env_vars: The environment variables used when starting the process
  Returns:
    The name of the created configuration file. 
  Raises: 
    TypeError with bad argument types
  Note: 
    The caller is responsible for deleting the created file.
  """
  
  if not isinstance(watch, str): raise TypeError
  if not isinstance(start_cmd, str): raise TypeError
  if not isinstance(stop_cmd, str): raise TypeError
  if not isinstance(ports, list): raise TypeError
  if not isinstance(env_vars, dict): raise TypeError

  template = file_io.read(TEMPLATE_LOCATION)

  env = ""
  for ii in env_vars:
    env += "          \""+ii+"\" => \""+env_vars[ii]+"\",\n" 
  if env: env = "w.env = {" + env + "}"

  # Convert ints to strings for template formatting
  for index, ii in enumerate(ports): ports[index] = str(ii) 

  # 'WATCH' and 'port' are substituted here as the last two arguments 
  # because the template script itself uses {}. If we do not sub for them 
  # a key error is raised by template.format()
  template = template.format(watch, 
                             start_cmd, 
                             stop_cmd, 
                             ', '.join(ports),
                             env,
                             "{WATCH}",
                             "{port}")

  temp_file_name = "/tmp/god-" + watch + '-' + \
                   str(random.randint(0, 9999999)) + ".conf"

  file_io.write(temp_file_name, template) 

  return temp_file_name

