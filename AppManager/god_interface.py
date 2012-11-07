# Programmer: Navraj Chohan
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import file_io

# Template used for god configuration files 
TEMPLATE_LOCATION = "./templates/god_template.conf"

def start(watch, start_cmd, stop_cmd, ports, env_vars=[]):
  """ Starts a watch on God
  
  Args:
    watch: The name of the watch
    start_cmd: The start command to start the process
    stop_cmd: The stop command to kill the process
    ports: The ports that are being watched
    env_vars: The environment variables used when starting the process
  Returns:
    True on success, False otherwise
  """

  create_config_file(watch, start_cmd, stop_cmd, ports, env_vars)
  
def create_config_file(watch, start_cmd, stop_cmd, ports, env_vars=[]):
  """ Reads in a template file for god and fills it with the 
      correct configuration.
  
  Args:
    watch: The name of the watch
    start_cmd: The start command to start the process
    stop_cmd: The stop command to kill the process
    ports: The ports that are being watched
    env_vars: The environment variables used when starting the process
  """

  template = file_io.read(TEMPLATE_LOCATION)

  env = ""
  for ii in env_vars:
    env += "          \""+ii+"\" => \""+env_vars[ii]+"\",\n" 

  template = template.format(watch, 
                             start_cmd, 
                             stop_cmd, 
                             ', '.joing(ports),
                             env)
  file_name = "SOME FILE" 
  file_io.write(file_name, template) 
