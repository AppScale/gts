# Programmer: Navraj Chohan <nlake44@gmail.com>
"""
This file contains constants used throughout AppScale.
"""
import os 

# The current version of AppScale
APPSCALE_VERSION = "1.6.6"

# AppScale home directory
APPSCALE_HOME = os.environ.get("APPSCALE_HOME")

# For unit testing 
if not APPSCALE_HOME: APPSCALE_HOME = '/root/appscale'

# Location of PID files for processes and applications
APP_PID_DIR = '/etc/appscale/'

# Location of Java Server
JAVA_APPSERVER = APPSCALE_HOME + '/AppServer_Java'

# The location of the file which specifies the current private IP
PRIVATE_IP_LOC = '/etc/appscale/my_private_ip'

# The location of the file which specifies the current public IP
PUBLIC_IP_LOC = '/etc/appscale/my_public_ip'

# The location of the file which holds the AppScale secret key
SECRET_LOC = '/etc/appscale/secret.key'

# The location of the file which contains information on the current DB
DB_INFO_LOC = '/etc/appscale/database_info.yaml'

# The file location which has all taskqueue nodes listed.
TASKQUEUE_NODE_FILE = "/etc/appscale/taskqueue_nodes"

# The port of the datastore server
DB_SERVER_PORT = 8888

# The port of the UserAppServer SOAP server
UA_SERVER_PORT = 4343

# The port of the application manager soap server
APP_MANAGER_PORT = 49934

# Python programs
PYTHON = "python"

# Python2.7 programs
PYTHON27 = "python27"

# Java programs
JAVA = "java"

# Go programs
GO = "go"

# Location where applications are stored
APPS_PATH = "/var/apps/"
