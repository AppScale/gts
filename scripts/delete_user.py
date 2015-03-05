""" This script deletes a user. """

import M2Crypto
import os
import string
import sys
import SOAPpy

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

def delete_user(server, email):
  """ Deletes a user.

  Args:
    server: A SOAP server accessor.
    email: A str, the user email.
  Returns:
    True on success, False otherwise.
  """
  secret = appscale_info.get_secret()
  server.disable_user(email, secret)
  return server.delete_user(email, secret) == "true"

def does_user_exist(email, server):
  """ Checks to see if a user already exists. 

  Args:
    email: A str, an email address to check.
    server: A SOAP server accessor.
  Returns:
    True if the user exists, False otherwise.
  """
  secret = appscale_info.get_secret()
  return server.does_user_exist(email, secret) == "true"

def usage():
  print ""
  print "Deletes a user in AppScale."
  print "Args: email address"
  print ""
  print "Examples:"
  print "  python delete_user.py bob@appscale.com"
  print ""

if __name__ == "__main__":
  total = len(sys.argv)
  if total != 2:
    usage() 
    exit(1)

  email = sys.argv[1]

  server = get_soap_accessor()
  if not does_user_exist(email, server):
    print "User does not exist."
    exit(1)

  print "Deleting user...",
  delete_user(server, email)
  print "Done."
