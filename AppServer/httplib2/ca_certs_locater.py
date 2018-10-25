"""Custom locater for CA_CERTS files for google3 code."""

__author__ = 'jcgregorio@google.com (Joe Gregorio)'

import os

from google3.pyglib import resources


# pylint: disable-msg=g-bad-name
def get():
  """Locate the ca_certs.txt file.

  The httplib2 library will look for local ca_certs_locater module to override
  the default location for the ca_certs.txt file. We override it here to first
  try loading via pyglib.resources, falling back to the traditional method if
  that fails.

  Returns:
    The file location returned as a string.
  """
  try:
    ca_certs = resources.GetResourceFilename(
        'google3/third_party/py/httplib2/cacerts.txt')
  except (IOError, AttributeError):
    # We're either running in an environment where we don't have access to
    # google3.pyglib.resources, or an environment where it won't work correctly
    # (e.g., //apphosting/tools:dev_appserver_internal_main). In either of these
    # cases, we fall back on the os.path.join approach.
    ca_certs = os.path.join(
        os.path.dirname(os.path.abspath(__file__)), 'cacerts.txt')
  return ca_certs
