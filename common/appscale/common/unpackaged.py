""" This module refers to unpackaged directories needed by this package. """
import os

# The location of the AppScale git repository.
APPSCALE_HOME = os.path.join('/root', 'appscale')

# The location of the Python AppServer.
APPSCALE_PYTHON_APPSERVER = os.path.join(APPSCALE_HOME, 'AppServer')

# The location of the dashboard.
DASHBOARD_DIR = os.path.join(APPSCALE_HOME, 'AppDashboard')
