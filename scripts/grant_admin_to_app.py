""" Grants admin access to a user. """

import os
import SOAPpy
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

def usage():
  """ Prints the usage of this script. """
  print ""
  print "Grants admin access to user for a given application."
  print "Args:  email address"
  print "       an application ID."
  print ""
  print "Example:"
  print "  python add_admin_to_app.py bob@appscale.com guestbook"
  print ""

if __name__ == "__main__":
  total = len(sys.argv)
  if total < 3:
    usage() 
    exit(1)

  email = sys.argv[1]
  app_id = sys.argv[2]

  secret = appscale_info.get_secret()
  server = get_soap_accessor()

  if server.does_user_exist(email, secret) == "false":
    print "User does not exist."
    exit(1)

  ret = server.add_admin_for_app(email, app_id, secret)
  if ret == "true":
    print "{0} granted admin access to {1}".format(email, app_id)
  else:
    print "Error with application: {0} -- {1}".format(app_id, ret)
