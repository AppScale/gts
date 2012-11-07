# Programmer: Navraj Chohan
import SOAPpy
import sys

from M2Crypto import SSL

# Port used by this soap server
DEFAULT_PORT = 49934

# IP used for binding
DEFAULT_IP = '127.0.0.1'

# Required configuration fields for starting an application
REQUIRED_CONFIG_FIELDS = ['app_name', 
                          'app_port', 
                          'language', 
                          'load_balancer_ip', 
                          'load_balancer_port', 
                          'xmpp_ip']

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
  Returns:
    PID of process on success, -1 otherwise
  """

  print "Starting application"
  if not is_config_valid(configuration): return -1
  pid = -1 
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

def run_python_gae_app():
  """
  """
  return 

def run_java_gae_app():
  """
  """
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
  
  server = SOAPpy.SOAPServer((DEFAULT_IP, DEFAULT_PORT))
 
  server.registerFunction(start_app)
  server.registerFunction(stop_app)

  while 1:
    try: 
      server.serve_forever()
    except SSL.SSLError: 
      pass
 
