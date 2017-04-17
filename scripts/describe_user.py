""" This script dumps AppScale attributes on a user. """

import SOAPpy
import sys

from appscale.common import appscale_info
from appscale.common import constants


def get_soap_accessor():
  """ Returns the SOAP server accessor to deal with application and users.

  Returns:
    A soap server accessor.
  """
  db_ip = appscale_info.get_db_master_ip()
  bindport = constants.UA_SERVER_PORT
  return SOAPpy.SOAPProxy("https://{0}:{1}".format(db_ip, bindport))

if __name__ == "__main__":

  email = sys.argv[1]
  secret = appscale_info.get_secret()
  server = get_soap_accessor()
  if server.does_user_exist(email, secret) != "true":
    print "User does not exist."
    sys.exit(1)

  print server.get_user_data(email, secret)
