""" This module refers to unpackaged directories needed by this package. """
import os

# The location of the AppScale git repository.
APPSCALE_HOME = os.path.join('/root', 'appscale')

# The location of the lib directory.
APPSCALE_LIB_DIR = os.path.join(APPSCALE_HOME, 'lib')

# The location of the Python AppServer.
APPSCALE_PYTHON_APPSERVER = os.path.join(APPSCALE_HOME, 'AppServer')
