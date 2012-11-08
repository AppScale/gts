# Programmer: Navraj Chohan
import os
import random
import SOAPpy
import sys

from M2Crypto import SSL

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib/"))
import appscale_info
import constants

# IP used for binding app_manager SOAP service
DEFAULT_IP = '127.0.0.1'

# Required configuration fields for starting an application
REQUIRED_CONFIG_FIELDS = ['app_name', 
                          'app_port', 
                          'language', 
                          'load_balancer_ip', 
                          'load_balancer_port', 
                          'xmpp_ip',
                          'dblocations']

def start_app(configuration):
  """ Starts a Google App Engine application on this host machine. It 
      will start it up and then proceed to fetch the main page.
  
  Args:
    configuration: a dictionary that contains 
       app_name: Name of the application to start
       app_port: Port to start on 
       language: What language the app is written in
       load_balancer_ip: Public ip of load balancer
       load_balancer_port: Port of load balancer
       xmpp_ip: IP of XMPP service 
       dblocations: List of database locations 
  Returns:
    PID of process on success, -1 otherwise
  """

  print "Starting application"
  if not is_config_valid(configuration): return -1
  pid = 0
  return pid

def stop_app(app_name):
  """ Stops a Google App Engine application on this host machine.

  Args:
    app_name: Name of application to stop
  Returns:
    True on success, False otherwise
  """

  print "Stopping application"
  return True

def get_app_listing():
  """ Returns a dictionary on information applications
      running on this host.

  Returns:
    A dictionary of information on apps running on this host.
  """

  return {}

######################
# Private Functions
######################
def choose_db_location(db_locations):
  """ Given a string containing multiple datastore locations
  select one randomly.

  Args:
    db_locations: A list of datastore locations
  Returns:
    One IP location randomly selected from the string.
  Raise:
    ValueError if there are no locations given in the args.
  """
  if len(db_locations) == 0: raise ValueError("DB locations \
     were not correctly set")
  index = random.randint(0, len(db_locations) - 1)
  return db_locations[index]

def create_python_app_env(public_ip, port, app_name):
  """ Returns the environment variables used to start a python 
  application
  
  Args:
    public_ip: The public IP
    port: The port the application is using
    app_name: The name of the application to be run
  Returns:
    A dictionary containing the environment variables
  """

  env_vars = {}
  env_vars['MY_IP_ADDRESS'] = public_ip
  env_vars['MY_PORT'] = str(port)
  env_vars['APPNAME'] = app_name
  env_vars['GOMAXPROCS'] = appscale_info.get_num_cpus()

  return env_vars

def create_java_app_env():
  """ Returns the environment variables used to start a java 
  application
  
  Args: None
  Returns:
    A dictionary containing the environment variables  
  """

  return {}

def create_python_start_cmd(app_name,
                            login_ip, 
                            port, 
                            load_balancer_host, 
                            load_balancer_port,
                            xmpp_ip,
                            db_locations):
  """
  Creates the command line to run the python application server.
  
  Args:
    app_name: The name of the application to run
    login_ip: The public IP
    port: The local port the application server will bind to
    load_balancer_host: The host of the load balancer
    load_balancer_port: The port of the load balancer
    xmpp_ip: The IP of the XMPP service
  """
  # TODO pass all db locations to the AppServer so it can have 
  # multiple choices upon failure. 
  db_location = choose_db_location(db_locations)
  cmd = ["python2.5 ",
         constants.APPSCALE_HOME + "/AppServer/dev_appserver.py",
         "-p " + str(port),
         "--cookie_secret " + appscale_info.get_secret(),
         "--login_server " + login_ip,
         "--admin_console_server ''",
         "--nginx_port " + str(load_balancer_port),
         "--nginx_host " + str(load_balancer_host),
         "--require_indexes",
         "--enable_sendmail",
         "--xmpp_path " + xmpp_ip,
         "--uaserver_path " + db_location + ":"\
               + str(constants.UA_SERVER_PORT),
         "--datastore_path " + db_location + ":"\
               + str(constants.DB_SERVER_PORT),
         "--history_path /var/apps/" + app_name\
               + "/data/app.datastore.history",
         "/var/apps/" + app_name + "/app",
         "-a " + appscale_info.get_private_ip(),
         ]
  
  return ' '.join(cmd)

def create_java_start_cmd():
  """
  """

  return

def create_python_stop_cmd(port):
  """ This creates the stop command for an application which is 
  uniquely identified by a port number. Additional portions of the 
  start command are included to prevent the termination of other 
  processes. 
  
  Args: 
    port: The port which the application server is running
  Returns:
    A string of the stop command.
  """

  cmd = ["python2.5",
         constants.APPSCALE_HOME + "/AppServer/dev_appserver.py",
         "-p " + str(port),
         "--cookie_secret " + appscale_info.get_secret()]
  cmd = ' '.join(cmd)
  stop_cmd = "ps aux | grep '" + cmd +\
             "' | grep -v grep | awk '{ print $2 }' | xargs -d '\n' kill -9"
  return stop_cmd

def create_java_stop_cmd():
  """
  """

  return

def run_python_app():
  """
  """
  # validate that the app.yaml configuration file is there

  return 

def run_java_app():
  """
  """
  # validate that the xml configuration file is there
  return

def is_config_valid(config):
  """ Takes a configuration and checks to make sure all required properties 
    are present
 
  Args:
    config: The dictionary to validate
  Returns:
    True if valid, false otherwise
  """
  for ii in REQUIRED_CONFIG_FIELDS:
    if not ii in config:
      return False 
  return True

def usage():
  """ Prints usage of this program """
  print "args: --help or -h for this menu"

################################
# MAIN
################################
if __name__ == "__main__":
  for ii in range(1, len(sys.argv)):
    if sys.argv[ii] in ("-h", "--help"):
      usage()
      sys.exit()
  
  server = SOAPpy.SOAPServer((DEFAULT_IP, constants.APP_MANAGER_PORT))
 
  server.registerFunction(start_app)
  server.registerFunction(stop_app)

  while 1:
    try: 
      server.serve_forever()
    except SSL.SSLError: 
      pass
 
