""" This script dumps all users. """

import M2Crypto
import os
import SOAPpy
import string
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), "../lib"))
import appscale_info
import constants

def get_soap_accessor():
  """ Returns the SOAP server accessor to deal with application and users.

  Returns:
    A soap server accessor.
  """
  db_ip = appscale_info.get_db_master_ip()
  bindport = constants.UA_SERVER_PORT
  return SOAPpy.SOAPProxy("https://{0}:{1}".format(db_ip, bindport))

if __name__ == "__main__":

  server = get_soap_accessor()
  users = server.get_all_users(appscale_info.get_secret())
  users = users.split(':')
  for user in users:
    print user
