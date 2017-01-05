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

TEMPLATE_LOCATION_FOR_UPGRADE = os.path.join(os.path.dirname(__file__)) + \
                    "/templates/monit_template_for_upgrade.conf"
# The directory used when storing a service's config file.
MONIT_CONFIG_DIR = '/etc/monit/conf.d'

def create_config_file(watch, start_cmd, stop_cmd, ports, env_vars={},
  max_memory=500, syslog_server="", host=None, upgrade_flag=False, match_cmd=""):
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
    syslog_server: The IP of the remote syslog server to use.
    host: The private IP of a server that runs the appengine role; used for 
      reliably detecting a running app server process.
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
  template = ""

  # If the match is not specified, we will match the starting commands.
  if not match_cmd:
    match_cmd = start_cmd

  # During upgrade we need to disable the memory usage rule.
  if upgrade_flag:
    max_memory = 0

  for port in ports:
    if syslog_server:
      template = file_io.read(TEMPLATE_LOCATION_SYSLOG)
      template = template.format(watch=watch, start=start_cmd, stop=stop_cmd,
        port=port, env=env, syslog_server=syslog_server, match=match_cmd)
    else:
        template = file_io.read(TEMPLATE_LOCATION)
        template = template.format(watch=watch, start=start_cmd, stop=stop_cmd,
          port=port, match=match_cmd, env=env)

    if max_memory > 0:
      template += "  if totalmem > {} MB for 10 cycles then restart\n".\
        format(max_memory)

    if host:
      template += "  if failed host {} port {} then restart\n".\
        format(host, port)

    config_file = '{}/appscale-{}-{}.cfg'.\
      format(MONIT_CONFIG_DIR, watch, port)
    file_io.write(config_file, template)

  return
