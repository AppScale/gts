""" This script dumps all users. """

import SOAPpy

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

  server = get_soap_accessor()
  users = server.get_all_users(appscale_info.get_secret())
  users = users.split(':')
  for user in users:
    print user
