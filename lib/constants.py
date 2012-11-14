"""
This file contains constants used throughput AppScale
"""
import os 

# The current version of AppScale
APPSCALE_VERSION = "1.6.4"

# AppScale home directory
APPSCALE_HOME = os.environ.get("APPSCALE_HOME")

# For unit testing 
if not APPSCALE_HOME: APPSCALE_HOME = '/root/appscale'

# Location of pid files for processes and applications
APP_PID_DIR = APPSCALE_HOME + '/.appscale/'

# Location of Java Server
JAVA_APPSERVER = APPSCALE_HOME + '/AppServer_Java'

# The location of the file which specifies the current private IP
PRIVATE_IP_LOC = '/etc/appscale/my_private_ip'

# The location of the file which specifies the current public IP
PUBLIC_IP_LOC = '/etc/appscale/my_public_ip'

# The location of the file which holds the AppScale secret key
SECRET_LOC = '/etc/appscale/secret.key'

# The location of the file which contains information on the current db
DB_INFO_LOC = '/etc/appscale/database_info.yaml'

# The port of the datastore server
DB_SERVER_PORT = 8888

# The port of the users/apps SOAP server
UA_SERVER_PORT = 4343

# The port of the application manager soap server
APP_MANAGER_PORT = 49934

# Python programs
PYTHON = "python"

# Python programs
PYTHON27 = "python27"

# Java programs
JAVA = "java"


